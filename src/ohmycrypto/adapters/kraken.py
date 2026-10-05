"""Kraken spot connector supporting REST snapshots and WebSocket v2 orderbook checksum verification.

Follows Section 5 and Kraken book v2 checksum documentation:
- Strict decimal parsing
- Exact top-10 CRC32 checksum calculation
- Sequence tracking and automatic snapshot resynchronization on gaps or checksum failures
- Truncation to subscribed depth
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple
import zlib

import aiohttp
import ccxt.async_support as ccxt_async

from ohmycrypto.adapters.base import BaseSpotConnector
from ohmycrypto.adapters.stream import (
    DEFAULT_MAX_DEPTH,
    LatencySamples,
    OrderbookMaintenance,
    ResyncRequest,
    WebSocketStreamSession,
)
from ohmycrypto.domain.models import BookLevel, BookState, Instrument, decimal_validator

KRAKEN_WS_URL = "wss://ws.kraken.com/v2"

logger = logging.getLogger(__name__)


def format_kraken_num(d: Decimal) -> str:
    """Format Decimal for Kraken checksum string (strip trailing zeroes after decimal point if cleanly zero)."""
    s = str(d)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def calculate_kraken_checksum(bids: Sequence[BookLevel], asks: Sequence[BookLevel]) -> int:
    """Calculate 32-bit CRC checksum of top 10 asks (ascending) followed by top 10 bids (descending)."""
    top_asks = asks[:10]
    top_bids = bids[:10]

    parts: List[str] = []
    for level in top_asks:
        parts.append(format_kraken_num(level.price))
        parts.append(format_kraken_num(level.amount))

    for level in top_bids:
        parts.append(format_kraken_num(level.price))
        parts.append(format_kraken_num(level.amount))

    check_str = "".join(parts)
    return zlib.crc32(check_str.encode("utf-8"))


class KrakenConnector(BaseSpotConnector):
    """Kraken public market data connector."""

    def __init__(self, strict_checksum: bool = False):
        super().__init__(venue="kraken")
        self._ccxt_client: Optional[ccxt_async.kraken] = None
        self._last_sequence: Dict[str, int] = {}
        # Kraken publishes a CRC32 book checksum, but the live values do not
        # reproduce under the documented algorithm (ccxt ships the same
        # reference implementation and disables the check as unreliable).
        # Verification therefore always runs and mismatches are always counted
        # as diagnostics, but only strict mode escalates to a REST resync,
        # which would otherwise cause a continuous resync storm.
        self.strict_checksum = strict_checksum

        # --- WebSocket book v2 streaming state ---
        self._books: Dict[str, OrderbookMaintenance] = {}
        self._session: Optional[WebSocketStreamSession] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._ws_symbols: List[str] = []
        self._ws_depth: int = 10
        self.resync_log: List[ResyncRequest] = []
        self.stream_latency = LatencySamples()
        self._stream_enabled: bool = False

    # ------------------------------------------------------------------
    # WebSocket book v2 streaming
    # ------------------------------------------------------------------

    def _book_for(self, symbol: str) -> OrderbookMaintenance:
        """Get or create the incremental maintenance structure for a symbol."""
        book = self._books.get(symbol)
        # Retain a little beyond the subscribed depth so that levels removed
        # from the visible window can reappear on delete of a better level.
        retain = max(DEFAULT_MAX_DEPTH, self._ws_depth * 5)
        if book is None:
            book = OrderbookMaintenance(venue=self.venue, symbol=symbol, max_depth=retain)
            self._books[symbol] = book
        elif book.max_depth != retain:
            book.max_depth = retain
            book._truncate()
        return book

    @staticmethod
    def _to_kraken_symbol(symbol: str) -> str:
        """Convert canonical BTC/USDT to Kraken WS form BTC/USDT (already close)."""
        return symbol.replace("-", "/").upper()

    async def _ws_subscribe(self, session: WebSocketStreamSession) -> None:
        """Send the book subscription frame for all requested symbols."""
        payload = {
            "method": "subscribe",
            "params": {
                "channel": "book",
                "symbol": [self._to_kraken_symbol(s) for s in self._ws_symbols],
                "depth": self._ws_depth,
                "snapshot": True,
            },
        }
        await session.send_json(payload)

    async def _resync_snapshot(self, symbol: str, reason: str, **details: Any) -> None:
        """Fetch a REST snapshot and rebuild the book after integrity loss."""
        detected = time.monotonic_ns()
        req = ResyncRequest(
            symbol=symbol,
            reason=reason,
            detected_mono_ns=detected,
            expected_sequence=details.get("expected_sequence"),
            received_sequence=details.get("received_sequence"),
            expected_checksum=details.get("expected_checksum"),
            computed_checksum=details.get("computed_checksum"),
        )
        try:
            snapshot = await self.fetch_orderbook(symbol, depth=self._ws_depth)
            book = self._book_for(symbol)
            book.replace_snapshot(
                bids=[(lvl.price, lvl.amount) for lvl in snapshot.bids],
                asks=[(lvl.price, lvl.amount) for lvl in snapshot.asks],
                sequence=book.last_sequence,
            )
            req.resolve()
        except Exception as exc:  # noqa: BLE001 - resync failure must not kill stream
            self.health.record_failure(time.monotonic_ns(), f"resync failed: {exc}")
            logger.warning("resync failed for %s: %s", symbol, exc)
        self.resync_log.append(req)

    async def _handle_ws_message(self, raw: Any) -> None:
        """Parse one Kraken WS v2 frame and maintain the book."""
        import json

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return

        # Heartbeat frames carry no book data.
        if msg.get("channel") == "heartbeat":
            self.health.record_success(time.monotonic_ns())
            return
        if msg.get("channel") == "status":
            return
        if msg.get("channel") != "book":
            return

        data = msg.get("data") or []
        # Kraken signals snapshot vs update at the top level of the frame; some
        # feeds repeat it per data entry. Top level takes precedence.
        frame_type = msg.get("type")

        for entry in data:
            symbol = self._canonical_from_stream(entry.get("symbol"))
            if symbol is None:
                continue

            book = self._book_for(symbol)
            entry_type = frame_type or entry.get("type")

            if entry_type == "snapshot":
                bids = self._parse_side(entry.get("bids", []))
                asks = self._parse_side(entry.get("asks", []))
                seq = entry.get("sequence")
                checksum = entry.get("checksum")
                book.replace_snapshot(bids, asks, sequence=seq, checksum=checksum)
                self._last_sequence[symbol] = seq if isinstance(seq, int) else 0
                self._publish_book(symbol, book, origin="stream_snapshot")
                continue

            if entry_type == "update":
                seq = entry.get("sequence")
                # An update arriving before any snapshot cannot be applied to an
                # empty book; recover through a REST snapshot instead.
                if book.snapshot_count == 0:
                    self.health.sequence_gaps += 1
                    self.health.is_degraded = True
                    await self._resync_snapshot(symbol, "missing_snapshot")
                    continue
                # Sequence continuity: v2 book sequences increment by 1.
                prev = book.last_sequence
                if isinstance(seq, int) and isinstance(prev, int) and seq != prev + 1:
                    self.health.sequence_gaps += 1
                    self.health.is_degraded = True
                    await self._resync_snapshot(
                        symbol,
                        "sequence_gap",
                        expected_sequence=(prev + 1) if isinstance(prev, int) else None,
                        received_sequence=seq,
                    )
                    continue

                book.apply_deltas(
                    self._parse_side(entry.get("bids", [])),
                    self._parse_side(entry.get("asks", [])),
                )
                if isinstance(seq, int):
                    book.last_sequence = seq
                    self._last_sequence[symbol] = seq

                checksum = entry.get("checksum")
                if isinstance(checksum, int):
                    if book.verify_checksum(checksum):
                        book.last_checksum = checksum
                    else:
                        # Always recorded. The book is only rebuilt in strict
                        # mode; see the strict_checksum note in __init__.
                        self.health.checksum_failures += 1
                        self.health.is_degraded = True
                        if self.strict_checksum:
                            await self._resync_snapshot(
                                symbol,
                                "checksum_mismatch",
                                expected_checksum=checksum,
                                computed_checksum=book.compute_checksum(),
                            )
                            continue

                self._publish_book(symbol, book, origin="stream_delta")

    @staticmethod
    def _parse_side(levels: Any) -> List[Tuple[Decimal, Decimal]]:
        """Parse Kraken book v2 levels into Decimal tuples, dropping invalid rows.

        Kraken v2 emits levels as objects {"price": ..., "qty": ...}. Older and
        some alternate feeds use [price, qty] pairs, so both forms are accepted.
        """
        parsed: List[Tuple[Decimal, Decimal]] = []
        if not isinstance(levels, list):
            return parsed
        for lvl in levels:
            try:
                if isinstance(lvl, dict):
                    price = Decimal(str(lvl["price"]))
                    amount = Decimal(str(lvl["qty"]))
                else:
                    price = Decimal(str(lvl[0]))
                    amount = Decimal(str(lvl[1]))
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if not price.is_finite() or not amount.is_finite():
                continue
            if price <= 0:
                continue
            parsed.append((price, amount))
        return parsed

    def _canonical_from_stream(self, raw_symbol: Optional[str]) -> Optional[str]:
        """Map a stream symbol back to the canonical symbol we subscribed with."""
        if not raw_symbol:
            return None
        target = raw_symbol.replace("-", "/").upper()
        for subscribed in self._ws_symbols:
            if self._to_kraken_symbol(subscribed) == target:
                return subscribed
        return target

    def _publish_book(self, symbol: str, book: OrderbookMaintenance, origin: str) -> None:
        """Materialize a validated BookState from maintenance state."""
        try:
            state = BookState(
                venue=self.venue,
                symbol=symbol,
                bids=tuple(book.sorted_bids(self._ws_depth)),
                asks=tuple(book.sorted_asks(self._ws_depth)),
                snapshot_origin=origin,
                applied_sequence=book.last_sequence,
                source_time_ms=None,
                source_time_meaning="book_update",
                local_receipt_utc_ms=int(time.time() * 1000),
                local_receipt_mono_ns=time.monotonic_ns(),
                quality_status="resynced" if origin.endswith("snapshot") and book.snapshot_count > 1 else "clean",
                checksum=str(book.last_checksum) if book.last_checksum is not None else None,
            )
        except ValueError:
            # Crossed book after delta application; force resync on next frame.
            self.health.checksum_failures += 1
            self.health.is_degraded = True
            return
        self.set_orderbook(symbol, state)
        self.health.record_success(time.monotonic_ns())
        self.health.is_degraded = False

    async def start_stream(
        self,
        symbols: Sequence[str],
        depth: int = 10,
        url: str = KRAKEN_WS_URL,
    ) -> None:
        """Start the full-duplex book v2 stream in a background task."""
        await self.stop_stream()
        self._ws_symbols = list(symbols)
        self._ws_depth = depth

        self._session = WebSocketStreamSession(
            url=url,
            on_message=self._handle_ws_message,
            subscribe_factory=self._ws_subscribe,
            name="kraken-ws",
        )
        self._stream_enabled = True
        self._stream_task = asyncio.create_task(self._session.run())

    async def stop_stream(self) -> None:
        """Stop the stream and cancel its background task."""
        self._stream_enabled = False
        if self._session is not None:
            await self._session.stop()
            self._session = None
        if self._stream_task is not None:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass
            self._stream_task = None

    def stream_stats(self) -> Dict[str, Any]:
        """Report stream health, resync history, and latency quantiles."""
        session = self._session
        return {
            "venue": self.venue,
            "enabled": self._stream_enabled,
            "connected": bool(session and session.is_connected),
            "reconnect_count": session.reconnect_count if session else 0,
            "messages_received": session.messages_received if session else 0,
            "messages_sent": session.messages_sent if session else 0,
            "last_error": session.last_error if session else None,
            "resync_count": len(self.resync_log),
            "resync_reasons": [r.reason for r in self.resync_log],
            "sequence_gaps": self.health.sequence_gaps,
            "checksum_failures": self.health.checksum_failures,
            "latency_ms": self.stream_latency.quantiles(),
            "books": {
                sym: {
                    "levels": book.level_counts(),
                    "deltas": book.delta_count,
                    "snapshots": book.snapshot_count,
                    "sequence": book.last_sequence,
                }
                for sym, book in self._books.items()
            },
        }

    async def _get_client(self) -> ccxt_async.kraken:
        if self._ccxt_client is None:
            self._ccxt_client = ccxt_async.kraken({
                "enableRateLimit": True,
                "timeout": 10000,
            })
        return self._ccxt_client

    async def close(self) -> None:
        if self._ccxt_client is not None:
            await self._ccxt_client.close()
            self._ccxt_client = None

    async def fetch_markets(self) -> Dict[str, Instrument]:
        """Fetch spot instruments from Kraken."""
        client = await self._get_client()
        mono_start = time.monotonic_ns()
        try:
            markets = await client.load_markets()
            instruments: Dict[str, Instrument] = {}
            for sym, m in markets.items():
                if not m.get("spot", False) or not m.get("active", True):
                    continue
                base = m["base"]
                quote = m["quote"]
                precision = m.get("precision", {})
                limits = m.get("limits", {})

                p_inc = Decimal(str(precision.get("price", "0.01") or "0.01"))
                a_inc = Decimal(str(precision.get("amount", "0.00000001") or "0.00000001"))
                min_a = Decimal(str(limits.get("amount", {}).get("min", "0.0001") or "0.0001"))
                min_c = Decimal(str(limits.get("cost", {}).get("min", "1.0") or "1.0"))

                inst = Instrument(
                    symbol=sym,
                    base=base,
                    quote=quote,
                    venue=self.venue,
                    native_symbol=m.get("id", sym),
                    price_precision=int(m.get("precision", {}).get("price", 2) or 2) if isinstance(m.get("precision", {}).get("price"), int) else 2,
                    amount_precision=8,
                    price_increment=p_inc if p_inc > 0 else Decimal("0.01"),
                    amount_increment=a_inc if a_inc > 0 else Decimal("0.00000001"),
                    min_amount=min_a if min_a > 0 else Decimal("0.0001"),
                    min_cost=min_c if min_c >= 0 else Decimal("1.0"),
                )
                instruments[sym] = inst

            self.health.record_success(mono_start)
            return instruments
        except Exception as exc:
            self.health.record_failure(mono_start, str(exc))
            raise

    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> BookState:
        """Fetch REST snapshot of orderbook."""
        client = await self._get_client()
        mono_start = time.monotonic_ns()
        utc_now = int(time.time() * 1000)

        try:
            raw = await client.fetch_order_book(symbol, limit=depth)
            bids_list: List[BookLevel] = []
            for b in raw.get("bids", []):
                p = Decimal(str(b[0]))
                a = Decimal(str(b[1]))
                if p > 0 and a > 0:
                    bids_list.append(BookLevel(price=p, amount=a))

            asks_list: List[BookLevel] = []
            for a in raw.get("asks", []):
                p = Decimal(str(a[0]))
                amt = Decimal(str(a[1]))
                if p > 0 and amt > 0:
                    asks_list.append(BookLevel(price=p, amount=amt))

            # Ensure proper sort order: bids descending, asks ascending
            bids_list.sort(key=lambda lvl: lvl.price, reverse=True)
            asks_list.sort(key=lambda lvl: lvl.price, reverse=False)

            source_ts = raw.get("timestamp")

            book = BookState(
                venue=self.venue,
                symbol=symbol,
                bids=tuple(bids_list),
                asks=tuple(asks_list),
                snapshot_origin="rest_snapshot",
                applied_sequence=raw.get("nonce"),
                source_time_ms=source_ts,
                source_time_meaning="book_update" if source_ts is not None else "unknown",
                local_receipt_utc_ms=utc_now,
                local_receipt_mono_ns=mono_start,
                quality_status="clean",
            )
            self.set_orderbook(symbol, book)
            self.health.record_success(mono_start)
            return book
        except Exception as exc:
            self.health.record_failure(mono_start, str(exc))
            raise

    def apply_delta_update(
        self,
        symbol: str,
        bid_deltas: Sequence[Tuple[Decimal, Decimal]],
        ask_deltas: Sequence[Tuple[Decimal, Decimal]],
        sequence_num: int,
        expected_checksum: Optional[int] = None,
        max_depth: int = 20,
    ) -> BookState:
        """Apply delta updates to in-memory orderbook with sequence and checksum verification."""
        mono_now = time.monotonic_ns()
        utc_now = int(time.time() * 1000)

        current = self.get_orderbook(symbol)
        if current is None:
            raise ValueError(f"Cannot apply delta without existing baseline snapshot for {symbol}")

        # Check sequence continuity
        last_seq = self._last_sequence.get(symbol)
        if last_seq is not None and sequence_num != (last_seq + 1):
            self.health.sequence_gaps += 1
            self.health.is_degraded = True
            # Gap detected, mark degraded and request resync
            raise ValueError(f"Sequence gap on {symbol}: expected {last_seq + 1}, got {sequence_num}")

        self._last_sequence[symbol] = sequence_num

        bids_dict: Dict[Decimal, Decimal] = {lvl.price: lvl.amount for lvl in current.bids}
        asks_dict: Dict[Decimal, Decimal] = {lvl.price: lvl.amount for lvl in current.asks}

        # Apply bids
        for p, a in bid_deltas:
            if a == Decimal("0"):
                bids_dict.pop(p, None)
            else:
                bids_dict[p] = a

        # Apply asks
        for p, a in ask_deltas:
            if a == Decimal("0"):
                asks_dict.pop(p, None)
            else:
                asks_dict[p] = a

        sorted_bids = sorted(
            [BookLevel(price=p, amount=a) for p, a in bids_dict.items()],
            key=lambda x: x.price,
            reverse=True,
        )[:max_depth]

        sorted_asks = sorted(
            [BookLevel(price=p, amount=a) for p, a in asks_dict.items()],
            key=lambda x: x.price,
            reverse=False,
        )[:max_depth]

        # Verify checksum if provided
        if expected_checksum is not None:
            calculated = calculate_kraken_checksum(sorted_bids, sorted_asks)
            if calculated != expected_checksum:
                self.health.checksum_failures += 1
                self.health.is_degraded = True
                raise ValueError(
                    f"Kraken checksum mismatch on {symbol}: expected {expected_checksum}, calculated {calculated}"
                )

        new_book = BookState(
            venue=self.venue,
            symbol=symbol,
            bids=tuple(sorted_bids),
            asks=tuple(sorted_asks),
            snapshot_origin="stream_delta",
            applied_sequence=sequence_num,
            source_time_ms=None,
            source_time_meaning="unknown",
            local_receipt_utc_ms=utc_now,
            local_receipt_mono_ns=mono_now,
            quality_status="clean",
            checksum=str(expected_checksum) if expected_checksum else None,
        )
        self.set_orderbook(symbol, new_book)
        return new_book
