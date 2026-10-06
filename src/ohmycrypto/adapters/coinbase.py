"""Coinbase spot connector supporting REST market metadata and L2 orderbook snapshots.

Follows Section 5 and Section 6.1 of PROJECT_EXECUTION_GUIDE.md:
- Explicit public venue metadata
- Strict decimal normalization
- Crossed orderbook prevention
- Health tracking and degraded error handling
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ccxt.async_support as ccxt_async

from ohmycrypto.adapters.base import BaseSpotConnector
from ohmycrypto.adapters.stream import (
    DEFAULT_MAX_DEPTH,
    LatencySamples,
    OrderbookMaintenance,
    ResyncRequest,
    WebSocketStreamSession,
)
from ohmycrypto.domain.models import BookLevel, BookState, Instrument

COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"

logger = logging.getLogger(__name__)


class CoinbaseConnector(BaseSpotConnector):
    """Coinbase Advanced Trade public spot connector."""

    def __init__(self):
        super().__init__(venue="coinbase")
        self._ccxt_client: Optional[ccxt_async.coinbase] = None

        # --- WebSocket Advanced Trade streaming state ---
        self._books: Dict[str, OrderbookMaintenance] = {}
        self._session: Optional[WebSocketStreamSession] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._ws_symbols: List[str] = []
        self._ws_depth: int = 10
        self.resync_log: List[ResyncRequest] = []
        self.stream_latency = LatencySamples()
        self._stream_enabled: bool = False

    # ------------------------------------------------------------------
    # WebSocket Advanced Trade streaming
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
    def _to_coinbase_symbol(symbol: str) -> str:
        """Convert canonical BTC/USDT to Coinbase product id BTC-USDT."""
        return symbol.replace("/", "-").upper()

    async def _ws_subscribe(self, session: WebSocketStreamSession) -> None:
        """Send the level2 subscription frame for all requested products."""
        payload = {
            "type": "subscribe",
            "product_ids": [self._to_coinbase_symbol(s) for s in self._ws_symbols],
            "channel": "level2",
        }
        await session.send_json(payload)

    async def _resync_snapshot(self, symbol: str, reason: str, **details: Any) -> None:
        """Fetch a REST snapshot and rebuild the book after integrity loss."""
        req = ResyncRequest(
            symbol=symbol,
            reason=reason,
            detected_mono_ns=time.monotonic_ns(),
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
        """Parse one Coinbase Advanced Trade frame and maintain the book."""
        import json

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return

        channel = msg.get("channel")
        events = msg.get("events") or []
        for event in events:
            if channel == "l2_data":
                await self._handle_l2_update(event)
            elif channel == "subscriptions":
                self.health.record_success(time.monotonic_ns())

    async def _handle_l2_update(self, event: Dict[str, Any]) -> None:
        """Apply one level2 snapshot or update event."""
        updates = event.get("updates") or []
        if not updates:
            return

        # Coinbase places product_id on the event; fall back to the update row.
        product_id = event.get("product_id")
        if not product_id and isinstance(updates[0], dict):
            product_id = updates[0].get("product_id")
        symbol = self._canonical_from_stream(product_id)
        if symbol is None:
            return

        book = self._book_for(symbol)
        bid_deltas: List[Tuple[Decimal, Decimal]] = []
        ask_deltas: List[Tuple[Decimal, Decimal]] = []

        for upd in updates:
            if not isinstance(upd, dict):
                continue
            side = upd.get("side")
            try:
                price = Decimal(str(upd.get("price_level")))
                amount = Decimal(str(upd.get("new_quantity", "0")))
            except (TypeError, ValueError):
                continue
            if not price.is_finite() or not amount.is_finite() or price <= 0:
                continue
            if side == "bid":
                bid_deltas.append((price, amount))
            elif side == "offer":
                ask_deltas.append((price, amount))

        event_type = event.get("type")
        if event_type == "snapshot":
            book.replace_snapshot(bid_deltas, ask_deltas)
            self._publish_book(symbol, book, origin="stream_snapshot")
            return

        if event_type == "update":
            book.apply_deltas(bid_deltas, ask_deltas)
            self._publish_book(symbol, book, origin="stream_delta")

    def _canonical_from_stream(self, product_id: Optional[str]) -> Optional[str]:
        """Map a Coinbase product id back to the canonical symbol."""
        if not product_id:
            return None
        target = product_id.upper()
        for subscribed in self._ws_symbols:
            if self._to_coinbase_symbol(subscribed) == target:
                return subscribed
        return target.replace("-", "/") if "-" in target else target

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
            )
        except ValueError:
            # Crossed book after delta application; flag for resync.
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
        url: str = COINBASE_WS_URL,
    ) -> None:
        """Start the full-duplex level2 stream in a background task."""
        await self.stop_stream()
        self._ws_symbols = list(symbols)
        self._ws_depth = depth

        self._session = WebSocketStreamSession(
            url=url,
            on_message=self._handle_ws_message,
            subscribe_factory=self._ws_subscribe,
            name="coinbase-ws",
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

    async def _get_client(self) -> ccxt_async.coinbase:
        current_loop = asyncio.get_running_loop()
        if self._ccxt_client is not None:
            client_loop = getattr(self._ccxt_client, "asyncio_loop", None) or getattr(self, "_client_loop", None)
            if client_loop is not None and (client_loop.is_closed() or client_loop is not current_loop):
                self._ccxt_client = None
        if self._ccxt_client is None:
            self._client_loop = current_loop
            self._ccxt_client = ccxt_async.coinbase({
                "enableRateLimit": True,
                "timeout": 10000,
                "asyncio_loop": current_loop,
            })
        return self._ccxt_client

    async def close(self) -> None:
        if self._ccxt_client is not None:
            try:
                await self._ccxt_client.close()
            except Exception:
                pass
            self._ccxt_client = None
            self._client_loop = None

    async def fetch_markets(self) -> Dict[str, Instrument]:
        """Fetch spot instruments from Coinbase."""
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
        """Fetch REST snapshot of orderbook from Coinbase."""
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

            # Proper sort order
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
                source_time_meaning="last_trade" if source_ts is not None else "unknown",
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
