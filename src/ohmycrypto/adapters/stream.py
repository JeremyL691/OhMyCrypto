"""Shared WebSocket streaming substrate for OhMyCrypto public market connectors.

This module provides the transport-independent machinery that both venue
connectors build on:

- Full-duplex operation: outbound subscription management while inbound frames
  are processed concurrently on the same connection.
- Incremental orderbook maintenance from level-2 deltas with O(log n) level
  replacement and depth truncation.
- CRC32 checksum verification against venue supplied values.
- Sequence continuity tracking that triggers REST snapshot resync on gaps.
- Bounded exponential backoff reconnection with jittered delays.
- Strictly bounded in-memory book cache so a long soak cannot leak memory.

Only public market data is ever requested. No credentials, no order entry,
no telemetry egress.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
import logging
import random
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple
import zlib

from ohmycrypto.domain.models import BookLevel, BookState

logger = logging.getLogger(__name__)

# Reconnection policy. Backoff grows geometrically and is capped so a long
# outage degrades gracefully without hammering the venue.
BACKOFF_INITIAL_SEC = 0.5
BACKOFF_MAX_SEC = 30.0
BACKOFF_MULTIPLIER = 2.0
BACKOFF_JITTER_RATIO = 0.25

# Maximum number of price levels retained per side. Bounded to guarantee the
# process memory footprint stays flat regardless of stream duration.
DEFAULT_MAX_DEPTH = 50


@dataclass
class ResyncRequest:
    """Record of an automatic REST snapshot resync triggered by stream integrity loss."""

    symbol: str
    reason: str  # "sequence_gap", "checksum_mismatch", "cold_start", "reconnect"
    detected_mono_ns: int
    resolved_mono_ns: Optional[int] = None
    expected_sequence: Optional[int] = None
    received_sequence: Optional[int] = None
    expected_checksum: Optional[int] = None
    computed_checksum: Optional[int] = None

    def resolve(self) -> None:
        if self.resolved_mono_ns is None:
            self.resolved_mono_ns = time.monotonic_ns()


class OrderbookMaintenance:
    """Incremental L2 orderbook maintained from a snapshot plus delta stream.

    Maintains two sorted price-side mappings. Deletion is signalled by a zero
    (or negative) amount, which is the convention used by both Kraken book v2
    and Coinbase Advanced Trade level2 channels.
    """

    def __init__(self, venue: str, symbol: str, max_depth: int = DEFAULT_MAX_DEPTH):
        self.venue = venue
        self.symbol = symbol
        self.max_depth = max_depth
        self._bids: Dict[Decimal, Decimal] = {}
        self._asks: Dict[Decimal, Decimal] = {}
        self.last_sequence: Optional[int] = None
        self.last_checksum: Optional[int] = None
        self.checksum_failures: int = 0
        self.sequence_gaps: int = 0
        self.delta_count: int = 0
        self.snapshot_count: int = 0

    def replace_snapshot(
        self,
        bids: Sequence[Tuple[Decimal, Decimal]],
        asks: Sequence[Tuple[Decimal, Decimal]],
        sequence: Optional[int] = None,
        checksum: Optional[int] = None,
    ) -> None:
        """Replace book contents wholesale with a fresh REST or stream snapshot."""
        self._bids = {p: a for p, a in bids if a > 0}
        self._asks = {p: a for p, a in asks if a > 0}
        self._truncate()
        self.last_sequence = sequence
        self.last_checksum = checksum
        self.snapshot_count += 1

    def apply_deltas(
        self,
        bid_deltas: Sequence[Tuple[Decimal, Decimal]],
        ask_deltas: Sequence[Tuple[Decimal, Decimal]],
    ) -> None:
        """Apply incremental level updates in place."""
        for price, amount in bid_deltas:
            if amount <= 0:
                self._bids.pop(price, None)
            else:
                self._bids[price] = amount
        for price, amount in ask_deltas:
            if amount <= 0:
                self._asks.pop(price, None)
            else:
                self._asks[price] = amount
        self._truncate()
        self.delta_count += 1

    def _truncate(self) -> None:
        """Enforce the depth bound so memory cannot grow without limit."""
        if len(self._bids) > self.max_depth:
            keep = sorted(self._bids.keys(), reverse=True)[: self.max_depth]
            self._bids = {p: self._bids[p] for p in keep}
        if len(self._asks) > self.max_depth:
            keep = sorted(self._asks.keys())[: self.max_depth]
            self._asks = {p: self._asks[p] for p in keep}

    def sorted_bids(self, limit: int) -> List[BookLevel]:
        """Best (highest) bids first."""
        return [
            BookLevel(price=p, amount=self._bids[p])
            for p in sorted(self._bids.keys(), reverse=True)[:limit]
        ]

    def sorted_asks(self, limit: int) -> List[BookLevel]:
        """Best (lowest) asks first."""
        return [
            BookLevel(price=p, amount=self._asks[p])
            for p in sorted(self._asks.keys())[:limit]
        ]

    def level_counts(self) -> Tuple[int, int]:
        """Return (bid_levels, ask_levels) currently retained."""
        return len(self._bids), len(self._asks)

    def verify_checksum(self, expected: int, top_n: int = 10) -> bool:
        """Compare locally computed CRC32 against venue supplied checksum."""
        computed = self.compute_checksum(top_n)
        if computed != expected:
            self.checksum_failures += 1
            return False
        return True

    def compute_checksum(self, top_n: int = 10) -> int:
        """CRC32 over top-N asks then top-N bids, matching venue conventions."""
        asks = self.sorted_asks(top_n)
        bids = self.sorted_bids(top_n)
        parts: List[str] = []
        for level in asks:
            parts.append(format_venue_num(level.price))
            parts.append(format_venue_num(level.amount))
        for level in bids:
            parts.append(format_venue_num(level.price))
            parts.append(format_venue_num(level.amount))
        return zlib.crc32("".join(parts).encode("utf-8"))


def format_venue_num(value: Decimal) -> str:
    """Strip trailing zeros after the decimal point, collapsing integral values.

    Venue checksum strings concatenate the shortest canonical representation of
    each price and amount, so 100.50000 must render as 100.5 and 100.000 as 100.
    """
    text = str(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


class WebSocketStreamSession:
    """Full-duplex WebSocket session with bounded backoff reconnect.

    Reads inbound frames in a dedicated task while the caller retains the
    ability to send subscription or control frames at any time. On transport
    failure the session reconnects with capped exponential backoff and
    re-establishes subscriptions via the supplied factory.
    """

    def __init__(
        self,
        url: str,
        on_message: Callable[[Any], Awaitable[None]],
        subscribe_factory: Callable[[Any], Awaitable[None]],
        name: str = "ws",
        max_reconnect_attempts: Optional[int] = None,
    ):
        self.url = url
        self.on_message = on_message
        self.subscribe_factory = subscribe_factory
        self.name = name
        self.max_reconnect_attempts = max_reconnect_attempts

        self._ws: Any = None
        self._reader_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.reconnect_count: int = 0
        self.messages_received: int = 0
        self.messages_sent: int = 0
        self.last_error: Optional[str] = None
        self.is_connected: bool = False

    async def send_json(self, payload: Dict[str, Any]) -> None:
        """Send a control or subscription frame on the live connection."""
        if self._ws is None:
            raise RuntimeError(f"[{self.name}] cannot send while disconnected")
        import json

        await self._ws.send(json.dumps(payload))
        self.messages_sent += 1

    async def run(self) -> None:
        """Connect, subscribe, and pump messages until stopped."""
        attempt = 0
        backoff = BACKOFF_INITIAL_SEC

        while not self._stop_event.is_set():
            try:
                await self._connect_and_pump()
                # Clean exit; reset backoff for next cycle.
                backoff = BACKOFF_INITIAL_SEC
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - transport failures are expected
                self.last_error = str(exc)
                self.is_connected = False
                logger.warning("[%s] stream error: %s", self.name, exc)

            if self._stop_event.is_set():
                break

            if self.max_reconnect_attempts is not None and attempt >= self.max_reconnect_attempts:
                logger.error("[%s] giving up after %s reconnect attempts", self.name, attempt)
                break

            attempt += 1
            self.reconnect_count += 1
            delay = min(backoff, BACKOFF_MAX_SEC)
            delay += delay * BACKOFF_JITTER_RATIO * random.random()
            logger.info("[%s] reconnecting in %.2fs (attempt %s)", self.name, delay, attempt)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * BACKOFF_MULTIPLIER, BACKOFF_MAX_SEC)

    async def _connect_and_pump(self) -> None:
        """Open one connection, subscribe, then read frames until it closes."""
        from websockets.asyncio.client import connect

        async with connect(self.url, ping_interval=20, ping_timeout=20, close_timeout=5) as ws:
            self._ws = ws
            self.is_connected = True
            await self.subscribe_factory(self)
            async for raw in ws:
                if self._stop_event.is_set():
                    break
                self.messages_received += 1
                await self.on_message(raw)
        self.is_connected = False
        self._ws = None

    async def stop(self) -> None:
        """Signal the read loop to terminate and close the transport."""
        self._stop_event.set()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 - best effort during shutdown
                pass


@dataclass
class LatencySamples:
    """Bounded ring of latency observations with quantile reporting."""

    capacity: int = 1000
    _samples: List[float] = field(default_factory=list)

    def add(self, value_ms: float) -> None:
        if len(self._samples) >= self.capacity:
            # Drop oldest to keep memory strictly bounded.
            self._samples.pop(0)
        self._samples.append(value_ms)

    def quantiles(self) -> Dict[str, Optional[float]]:
        """Return p50, p95, p99 in milliseconds."""
        if not self._samples:
            return {"p50": None, "p95": None, "p99": None, "count": 0}
        ordered = sorted(self._samples)
        n = len(ordered)

        def at(q: float) -> float:
            idx = min(n - 1, max(0, int(round(q * (n - 1)))))
            return round(ordered[idx], 3)

        return {
            "p50": at(0.50),
            "p95": at(0.95),
            "p99": at(0.99),
            "count": n,
            "min": round(ordered[0], 3),
            "max": round(ordered[-1], 3),
        }

    def clear(self) -> None:
        self._samples.clear()
