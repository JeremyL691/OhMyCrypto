"""Integration tests for WebSocket full-duplex streaming connectors.

Covers:
- Full-duplex send/receive over a real local WebSocket server
- Incremental orderbook maintenance and depth truncation
- CRC32 checksum verification and automatic resync on mismatch
- Sequence gap detection and REST snapshot resync
- Reconnection with bounded backoff after transport failure
- Concurrent symbol streams under reconnect churn (zero crash)
- Bounded memory across a high volume of delta updates

A local WebSocket server stands in for the venue so these tests are
hermetic: they never depend on network reachability or venue availability.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
import json
import time
from typing import Any, Dict, List

import pytest
from websockets.asyncio.server import serve

from ohmycrypto.adapters.coinbase import CoinbaseConnector
from ohmycrypto.adapters.kraken import KrakenConnector
from ohmycrypto.adapters.stream import (
    LatencySamples,
    OrderbookMaintenance,
    WebSocketStreamSession,
    format_venue_num,
)
from ohmycrypto.domain.models import BookLevel


# ---------------------------------------------------------------------------
# Local WebSocket test server
# ---------------------------------------------------------------------------

class ScriptedServer:
    """Minimal WebSocket server that replays scripted frames to each client."""

    def __init__(self):
        self.connections: List[Any] = []
        self.received: List[str] = []
        self._server = None
        self.port: int = 0
        self.drop_next: bool = False

    async def start(self) -> int:
        self._server = await serve(self._handler, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handler(self, ws: Any) -> None:
        self.connections.append(ws)
        try:
            async for message in ws:
                self.received.append(message)
                if self.drop_next:
                    self.drop_next = False
                    await ws.close(code=1011, reason="simulated outage")
                    return
        except Exception:
            pass

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Send a frame to every connected client."""
        raw = json.dumps(payload)
        for ws in list(self.connections):
            try:
                await ws.send(raw)
            except Exception:
                pass

    async def force_close_all(self) -> None:
        """Server-initiated abnormal close, simulating a venue-side outage."""
        for ws in list(self.connections):
            try:
                await ws.close(code=1011, reason="simulated outage")
            except Exception:
                pass
        self.connections.clear()


@pytest.fixture
async def ws_server():
    server = ScriptedServer()
    await server.start()
    yield server
    await server.stop()


# ---------------------------------------------------------------------------
# Orderbook maintenance unit behaviour
# ---------------------------------------------------------------------------

def test_orderbook_incremental_apply_and_delete():
    """Levels are inserted, replaced, and deleted by zero amount."""
    book = OrderbookMaintenance(venue="kraken", symbol="BTC/USDT", max_depth=10)
    book.replace_snapshot(
        bids=[(Decimal("100.0"), Decimal("1.0")), (Decimal("99.0"), Decimal("2.0"))],
        asks=[(Decimal("101.0"), Decimal("1.5")), (Decimal("102.0"), Decimal("3.0"))],
        sequence=1,
    )
    book.apply_deltas(
        bid_deltas=[(Decimal("99.0"), Decimal("0")), (Decimal("100.5"), Decimal("0.5"))],
        ask_deltas=[(Decimal("101.0"), Decimal("2.5"))],
    )

    bids = book.sorted_bids(10)
    asks = book.sorted_asks(10)

    assert [str(l.price) for l in bids] == ["100.5", "100.0"]
    assert asks[0].amount == Decimal("2.5")
    assert book.level_counts() == (2, 2)


def test_orderbook_depth_truncation_bounds_memory():
    """Depth never exceeds the configured bound no matter how many levels arrive."""
    book = OrderbookMaintenance(venue="kraken", symbol="BTC/USDT", max_depth=5)
    many = [(Decimal(str(1000 + i)), Decimal("1.0")) for i in range(500)]
    book.replace_snapshot(bids=many, asks=many)

    bid_levels, ask_levels = book.level_counts()
    assert bid_levels <= 5
    assert ask_levels <= 5

    # Kept levels must be the best ones: highest bids, lowest asks.
    assert book.sorted_bids(5)[0].price == Decimal("1499")
    assert book.sorted_asks(5)[0].price == Decimal("1000")


def test_format_venue_num_kraken_v2():
    assert format_venue_num(Decimal("45285.2")) == "452852"
    assert format_venue_num(Decimal("0.00100000")) == "100000"
    assert format_venue_num("0.00100000") == "100000"
    assert format_venue_num(Decimal("0")) == "0"


def test_checksum_computation_is_stable_and_ordered():
    """Checksum reflects asks-then-bids ordering and is deterministic."""
    book = OrderbookMaintenance(venue="kraken", symbol="BTC/USDT")
    book.replace_snapshot(
        bids=[(Decimal("50000.00"), Decimal("1.5")), (Decimal("49990.00"), Decimal("2.0"))],
        asks=[(Decimal("50010.00"), Decimal("0.8")), (Decimal("50020.00"), Decimal("1.2"))],
    )
    import zlib

    expected = zlib.crc32("50010008500200012500000015499900020".encode("utf-8"))
    assert book.compute_checksum() == expected
    assert book.verify_checksum(expected) is True


def test_checksum_mismatch_is_detected():
    book = OrderbookMaintenance(venue="kraken", symbol="BTC/USDT")
    book.replace_snapshot(
        bids=[(Decimal("100.0"), Decimal("1.0"))],
        asks=[(Decimal("101.0"), Decimal("1.0"))],
    )
    assert book.verify_checksum(99999999) is False
    assert book.checksum_failures == 1


def test_latency_quantiles_bounded_and_correct():
    """Latency sample ring is bounded and reports p50/p95/p99 accurately."""
    samples = LatencySamples(capacity=100)
    for i in range(500):
        samples.add(float(i))

    q = samples.quantiles()
    assert q["count"] == 100, "sample ring must stay bounded at capacity"
    # Retained window is the newest 100 values: 400..499.
    # Nearest-rank index for quantile q over n=100 is round(q*(n-1)).
    assert q["p50"] == 450.0
    assert q["p95"] == 494.0
    assert q["p99"] == 498.0
    assert q["min"] == 400.0
    assert q["max"] == 499.0


# ---------------------------------------------------------------------------
# Full-duplex session behaviour
# ---------------------------------------------------------------------------

async def test_session_full_duplex_send_and_receive(ws_server: ScriptedServer):
    """Subscription frames are sent and inbound frames are dispatched."""
    seen: List[Dict[str, Any]] = []

    async def on_message(raw: str) -> None:
        seen.append(json.loads(raw))

    async def subscribe(session: WebSocketStreamSession) -> None:
        await session.send_json({"method": "subscribe", "params": {"channel": "book"}})

    session = WebSocketStreamSession(
        url=f"ws://127.0.0.1:{ws_server.port}",
        on_message=on_message,
        subscribe_factory=subscribe,
        name="test-duplex",
    )
    task = asyncio.create_task(session.run())
    await asyncio.sleep(0.4)

    await ws_server.broadcast({"channel": "book", "data": [{"type": "update"}]})
    await asyncio.sleep(0.4)
    await session.stop()
    await asyncio.wait_for(task, timeout=5)

    assert session.messages_sent >= 1, "outbound subscription must be sent"
    assert session.messages_received >= 1, "inbound frames must be dispatched"
    assert {"channel": "book", "data": [{"type": "update"}]} in seen
    assert ws_server.received, "server must have observed the subscription frame"


async def test_session_reconnects_after_transport_drop(ws_server: ScriptedServer):
    """A dropped connection triggers reconnect and resubscribe."""
    subscribes = 0

    async def on_message(raw: str) -> None:
        return None

    async def subscribe(session: WebSocketStreamSession) -> None:
        nonlocal subscribes
        subscribes += 1
        await session.send_json({"type": "subscribe"})

    session = WebSocketStreamSession(
        url=f"ws://127.0.0.1:{ws_server.port}",
        on_message=on_message,
        subscribe_factory=subscribe,
        name="test-reconnect",
    )
    task = asyncio.create_task(session.run())
    await asyncio.sleep(0.4)
    assert subscribes == 1

    # Simulate a venue-side outage: the server closes the connection abnormally.
    await ws_server.force_close_all()
    await asyncio.sleep(2.0)

    assert session.reconnect_count >= 1, "reconnect must be attempted"
    assert subscribes >= 2, "subscriptions must be re-established after reconnect"

    await session.stop()
    await asyncio.wait_for(task, timeout=5)


# ---------------------------------------------------------------------------
# Kraken connector stream integration
# ---------------------------------------------------------------------------

async def test_kraken_stream_snapshot_then_delta_maintains_book(ws_server: ScriptedServer):
    """Kraken snapshot + delta frames produce a correctly maintained book."""
    connector = KrakenConnector()
    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book",
        "type": "snapshot",
        "data": [{
            "symbol": "BTC/USDT",
            "type": "snapshot",
            "sequence": 1,
            "bids": [["50000.00", "1.5"], ["49990.00", "2.0"]],
            "asks": [["50010.00", "0.8"], ["50020.00", "1.2"]],
        }],
    })
    await asyncio.sleep(0.3)

    book = connector.get_orderbook("BTC/USDT")
    assert book is not None
    assert str(book.bids[0].price) == "50000.00"
    assert str(book.asks[0].price) == "50010.00"

    await ws_server.broadcast({
        "channel": "book",
        "type": "update",
        "data": [{
            "symbol": "BTC/USDT",
            "type": "update",
            "sequence": 2,
            "bids": [["49990.00", "0"]],
            "asks": [["50010.00", "3.0"]],
        }],
    })
    await asyncio.sleep(0.3)

    book = connector.get_orderbook("BTC/USDT")
    assert len(book.bids) == 1, "deleted bid level must be removed"
    assert book.asks[0].amount == Decimal("3.0"), "ask level must be replaced"

    await connector.stop_stream()
    await connector.close()


async def test_kraken_sequence_gap_triggers_resync(ws_server: ScriptedServer):
    """A skipped sequence number is detected and logged as a resync request."""
    connector = KrakenConnector()
    received: List[Dict[str, Any]] = []

    async def fake_rest(symbol: str, depth: int = 20):
        received.append({"symbol": symbol, "depth": depth})
        from ohmycrypto.domain.models import BookState
        return BookState(
            venue="kraken",
            symbol=symbol,
            bids=(BookLevel(price=Decimal("50000"), amount=Decimal("1")),),
            asks=(BookLevel(price=Decimal("50010"), amount=Decimal("1")),),
            snapshot_origin="rest_snapshot",
            applied_sequence=None,
            source_time_ms=None,
            source_time_meaning="unknown",
            local_receipt_utc_ms=int(time.time() * 1000),
            local_receipt_mono_ns=time.monotonic_ns(),
        )

    connector.fetch_orderbook = fake_rest  # type: ignore[assignment]

    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book",
        "type": "snapshot",
        "data": [{
            "symbol": "BTC/USDT", "type": "snapshot", "sequence": 10,
            "bids": [["50000.00", "1.5"]], "asks": [["50010.00", "0.8"]],
        }],
    })
    await asyncio.sleep(0.3)

    # Jump from sequence 10 to 12: sequence 11 is missing.
    await ws_server.broadcast({
        "channel": "book",
        "type": "update",
        "data": [{
            "symbol": "BTC/USDT", "type": "update", "sequence": 12,
            "bids": [["50000.00", "9.9"]], "asks": [],
        }],
    })
    await asyncio.sleep(0.5)

    assert connector.health.sequence_gaps >= 1, "sequence gap must be counted"
    assert any(r.reason == "sequence_gap" for r in connector.resync_log), \
        "gap must trigger a REST resync request"
    assert received, "REST snapshot must be fetched to rebuild the book"

    await connector.stop_stream()
    await connector.close()


async def test_kraken_checksum_mismatch_triggers_resync(ws_server: ScriptedServer):
    """A bogus venue checksum is detected and triggers snapshot recovery.

    Live Kraken checksums do not reproduce under the documented algorithm, so
    resync-on-mismatch is opt-in (strict_checksum). This test exercises strict
    mode; the non-strict default still records the mismatch without a resync
    storm, which the paired test below verifies.
    """
    connector = KrakenConnector(strict_checksum=True)

    async def fake_rest(symbol: str, depth: int = 20):
        from ohmycrypto.domain.models import BookState
        return BookState(
            venue="kraken", symbol=symbol,
            bids=(BookLevel(price=Decimal("50000"), amount=Decimal("1")),),
            asks=(BookLevel(price=Decimal("50010"), amount=Decimal("1")),),
            snapshot_origin="rest_snapshot", applied_sequence=None,
            source_time_ms=None, source_time_meaning="unknown",
            local_receipt_utc_ms=int(time.time() * 1000),
            local_receipt_mono_ns=time.monotonic_ns(),
        )

    connector.fetch_orderbook = fake_rest  # type: ignore[assignment]
    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book", "type": "snapshot",
        "data": [{
            "symbol": "BTC/USDT", "type": "snapshot", "sequence": 1,
            "bids": [["50000.00", "1.5"]], "asks": [["50010.00", "0.8"]],
        }],
    })
    await asyncio.sleep(0.3)

    # Deliberately wrong checksum value for the resulting book.
    await ws_server.broadcast({
        "channel": "book", "type": "update",
        "data": [{
            "symbol": "BTC/USDT", "type": "update", "sequence": 2,
            "bids": [["50000.00", "1.5"]], "asks": [["50010.00", "0.8"]],
            "checksum": 123456789,
        }],
    })
    await asyncio.sleep(0.5)

    assert connector.health.checksum_failures >= 1, "checksum failure must be counted"
    assert any(r.reason == "checksum_mismatch" for r in connector.resync_log), \
        "checksum mismatch must trigger REST resync in strict mode"

    await connector.stop_stream()
    await connector.close()


async def test_kraken_checksum_mismatch_is_recorded_without_resync_by_default(ws_server: ScriptedServer):
    """Default mode records mismatches as diagnostics without resync storms."""
    connector = KrakenConnector()
    assert connector.strict_checksum is False

    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book", "type": "snapshot",
        "data": [{
            "symbol": "BTC/USDT", "type": "snapshot", "sequence": 1,
            "bids": [["50000.00", "1.5"]], "asks": [["50010.00", "0.8"]],
        }],
    })
    await asyncio.sleep(0.3)

    await ws_server.broadcast({
        "channel": "book", "type": "update",
        "data": [{
            "symbol": "BTC/USDT", "type": "update", "sequence": 2,
            "bids": [["50000.00", "1.5"]], "asks": [["50010.00", "0.8"]],
            "checksum": 123456789,
        }],
    })
    await asyncio.sleep(0.5)

    assert connector.health.checksum_failures >= 1, "mismatch must still be recorded"
    assert connector.resync_log == [], "non-strict mode must not resync on unreliable checksum"

    # The book must remain usable rather than being torn down.
    book = connector.get_orderbook("BTC/USDT")
    assert book is not None

    await connector.stop_stream()
    await connector.close()


# ---------------------------------------------------------------------------
# Coinbase connector stream integration
# ---------------------------------------------------------------------------

async def test_coinbase_level2_snapshot_and_update(ws_server: ScriptedServer):
    """Coinbase level2 snapshot and update events maintain the book."""
    connector = CoinbaseConnector()
    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "l2_data",
        "events": [{
            "type": "snapshot",
            "product_id": "BTC-USDT",
            "updates": [
                {"side": "bid", "price_level": "50000.00", "new_quantity": "1.5"},
                {"side": "offer", "price_level": "50010.00", "new_quantity": "0.8"},
            ],
        }],
    })
    await asyncio.sleep(0.4)

    book = connector.get_orderbook("BTC/USDT")
    assert book is not None, "snapshot must publish a book"
    assert str(book.bids[0].price) == "50000.00"
    assert str(book.asks[0].price) == "50010.00"

    await ws_server.broadcast({
        "channel": "l2_data",
        "events": [{
            "type": "update",
            "product_id": "BTC-USDT",
            "updates": [
                {"side": "bid", "price_level": "50000.00", "new_quantity": "0"},
                {"side": "offer", "price_level": "50010.00", "new_quantity": "2.5"},
            ],
        }],
    })
    await asyncio.sleep(0.4)

    book = connector.get_orderbook("BTC/USDT")
    assert len(book.bids) == 0, "zero quantity must delete the bid level"
    assert book.asks[0].amount == Decimal("2.5")

    await connector.stop_stream()
    await connector.close()


# ---------------------------------------------------------------------------
# Concurrency, stability, and memory bounds
# ---------------------------------------------------------------------------

async def test_concurrent_streams_with_reconnect_churn_do_not_crash(ws_server: ScriptedServer):
    """Multiple venues streaming concurrently survive repeated transport drops."""
    kraken = KrakenConnector()
    coinbase = CoinbaseConnector()

    await kraken.start_stream(["BTC/USDT", "ETH/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await coinbase.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    # Induce several disconnects while frames keep flowing.
    for _ in range(3):
        await ws_server.force_close_all()
        await asyncio.sleep(0.8)

    await kraken.stop_stream()
    await coinbase.stop_stream()
    await kraken.close()
    await coinbase.close()

    assert kraken._stream_task is None, "kraken stream task must be cleaned up"
    assert coinbase._stream_task is None, "coinbase stream task must be cleaned up"
    assert kraken.stream_stats()["enabled"] is False
    assert coinbase.stream_stats()["enabled"] is False


async def test_kraken_parses_real_v2_frame_schema(ws_server: ScriptedServer):
    """Regression guard for the real Kraken v2 wire format.

    Live Kraken frames differ from simplified documentation examples:
    - snapshot/update is signalled at the FRAME level, not per data entry
    - levels are objects {"price": ..., "qty": ...}, not [price, qty] pairs
    Both were silently dropped by an earlier parser revision.
    """
    connector = KrakenConnector()
    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book",
        "type": "snapshot",
        "data": [{
            "symbol": "BTC/USDT",
            "bids": [{"price": 85975.3, "qty": 0.0205283}],
            "asks": [{"price": 85975.4, "qty": 0.0514232}],
            "checksum": 1,
            "timestamp": "2026-10-05T22:21:40.864093Z",
        }],
    })
    await asyncio.sleep(0.4)

    book = connector.get_orderbook("BTC/USDT")
    assert book is not None, "frame-level snapshot with object levels must be parsed"
    assert book.bids[0].price == Decimal("85975.3")
    assert book.bids[0].amount == Decimal("0.0205283")
    assert book.asks[0].price == Decimal("85975.4")

    # Object-form delta update.
    await ws_server.broadcast({
        "channel": "book",
        "type": "update",
        "data": [{
            "symbol": "BTC/USDT",
            "bids": [{"price": 85975.3, "qty": 0.0}],
            "asks": [{"price": 85975.4, "qty": 0.9}],
            "checksum": 2,
        }],
    })
    await asyncio.sleep(0.4)

    book = connector.get_orderbook("BTC/USDT")
    assert len(book.bids) == 0, "zero qty must delete the level"
    assert book.asks[0].amount == Decimal("0.9")

    await connector.stop_stream()
    await connector.close()


async def test_kraken_update_without_snapshot_triggers_resync(ws_server: ScriptedServer):
    """An update arriving before any snapshot is recovered via REST, not dropped."""
    connector = KrakenConnector()
    fetched: List[str] = []

    async def fake_rest(symbol: str, depth: int = 20):
        fetched.append(symbol)
        from ohmycrypto.domain.models import BookState
        return BookState(
            venue="kraken", symbol=symbol,
            bids=(BookLevel(price=Decimal("50000"), amount=Decimal("1")),),
            asks=(BookLevel(price=Decimal("50010"), amount=Decimal("1")),),
            snapshot_origin="rest_snapshot", applied_sequence=None,
            source_time_ms=None, source_time_meaning="unknown",
            local_receipt_utc_ms=int(time.time() * 1000),
            local_receipt_mono_ns=time.monotonic_ns(),
        )

    connector.fetch_orderbook = fake_rest  # type: ignore[assignment]
    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book",
        "type": "update",
        "data": [{
            "symbol": "BTC/USDT",
            "bids": [{"price": 50000.0, "qty": 1.0}],
            "asks": [{"price": 50010.0, "qty": 1.0}],
        }],
    })
    await asyncio.sleep(0.5)

    assert fetched, "update without baseline must trigger REST recovery"
    assert any(r.reason == "missing_snapshot" for r in connector.resync_log)

    await connector.stop_stream()
    await connector.close()


async def test_high_volume_deltas_keep_memory_bounded(ws_server: ScriptedServer):
    """A large volume of updates leaves level counts and sample buffers bounded."""
    connector = KrakenConnector()
    await connector.start_stream(["BTC/USDT"], depth=10, url=f"ws://127.0.0.1:{ws_server.port}")
    await asyncio.sleep(0.4)

    await ws_server.broadcast({
        "channel": "book", "type": "snapshot",
        "data": [{
            "symbol": "BTC/USDT", "type": "snapshot", "sequence": 1,
            "bids": [["50000.00", "1.5"]], "asks": [["50010.00", "0.8"]],
        }],
    })
    await asyncio.sleep(0.3)

    # Flood with many distinct price levels across sequential updates.
    for i in range(200):
        price = 50000 + (i % 300)
        await ws_server.broadcast({
            "channel": "book", "type": "update",
            "data": [{
                "symbol": "BTC/USDT", "type": "update", "sequence": 2 + i,
                "bids": [[f"{price}.00", "1.0"]], "asks": [],
            }],
        })

    await asyncio.sleep(1.0)
    stats = connector.stream_stats()

    bid_levels = stats["books"]["BTC/USDT"]["levels"][0]
    # 200 updates cycle over 300 distinct prices; retention is capped at
    # max(DEFAULT_MAX_DEPTH, depth*5) = 50, so growth must plateau well below 300.
    assert bid_levels <= 50, f"bid levels must stay bounded, got {bid_levels}"

    published = connector.get_orderbook("BTC/USDT")
    assert published is not None
    assert len(published.bids) <= 10, "published view must honour subscribed depth"

    for _ in range(5000):
        connector.stream_latency.add(1.0)
    assert connector.stream_latency.quantiles()["count"] <= 1000, \
        "latency buffer must stay bounded"

    await connector.stop_stream()
    await connector.close()
