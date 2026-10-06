"""Hermetic integration tests for MonitoringService (Gen 13 desktop wiring).

Uses stub connectors so no network is involved: the monitor loop must
evaluate, persist, and survive lifecycle transitions with the same code path
it runs in the packaged sidecar.
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from ohmycrypto.adapters.base import BaseSpotConnector
from ohmycrypto.domain.models import BookLevel, BookState, Instrument
from ohmycrypto.services.monitor import MonitoringService


class StubConnector(BaseSpotConnector):
    """Deterministic connector returning a canned coherent book."""

    def __init__(self, venue: str, bid_price: str, ask_price: str):
        super().__init__(venue)
        self.venue_name = venue
        self._bid = Decimal(bid_price)
        self._ask = Decimal(ask_price)
        self.fetch_count = 0

    async def fetch_markets(self):
        inst = Instrument(
            symbol="BTC/USDT",
            base="BTC",
            quote="USDT",
            venue=self.venue_name,
            native_symbol="BTC-USDT" if self.venue_name == "coinbase" else "XXBTZUSDT",
        )
        return {"BTC/USDT": inst}

    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> BookState:
        self.fetch_count += 1
        book = BookState(
            venue=self.venue_name,
            symbol=symbol,
            bids=(BookLevel(price=self._bid, amount=Decimal("5")),),
            asks=(BookLevel(price=self._ask, amount=Decimal("5")),),
            snapshot_origin="stub_rest",
            applied_sequence=self.fetch_count,
            source_time_ms=None,
            source_time_meaning="unknown",
            local_receipt_utc_ms=int(time.time() * 1000),
            local_receipt_mono_ns=time.monotonic_ns(),
        )
        self.set_orderbook(symbol, book)
        return book


@pytest.fixture()
def monitor(tmp_path, monkeypatch):
    monkeypatch.setenv("OHMYCRYPTO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OHMYCRYPTO_LOCK_DIR", str(tmp_path))
    import importlib

    from ohmycrypto.services import monitor as monitor_module

    importlib.reload(monitor_module)

    svc = monitor_module.MonitoringService(
        poll_interval_sec=0.2,
    )
    svc._connectors = {
        "coinbase": StubConnector("coinbase", "85000.0", "85010.0"),
        "kraken": StubConnector("kraken", "85020.0", "85030.0"),
    }
    yield svc
    svc.close()


def test_monitor_lifecycle_and_persistence(monitor):
    """start -> cycles evaluate and persist -> stop terminates the loop."""
    snap = monitor.start()
    assert snap["status"] == "monitoring"

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if monitor.status_snapshot()["cycles_done"] >= 2:
            break
        time.sleep(0.05)

    stopped = monitor.stop()
    assert stopped["status"] == "idle"
    assert stopped["cycles_done"] >= 2
    assert stopped["last_cycle_error"] is None

    events = monitor.recent_events()
    assert len(events) >= 1
    import json

    opp = json.loads(events[0]["opportunity_json"])
    # buy@coinbase 85010 ask -> sell@kraken 85020 bid is a positive spread
    assert opp["symbol"] == "BTC/USDT"
    assert opp["buy_venue"] == "coinbase"
    assert opp["sell_venue"] == "kraken"


def test_monitor_pause_stops_cycle_progress(monitor):
    """Paused monitor keeps its thread but performs no new cycles."""
    monitor.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if monitor.status_snapshot()["cycles_done"] >= 1:
            break
        time.sleep(0.05)
    monitor.pause()
    assert monitor.pause()["status"] == "paused"
    count_at_pause = monitor.status_snapshot()["cycles_done"]
    time.sleep(1.0)
    assert monitor.status_snapshot()["cycles_done"] == count_at_pause
    monitor.stop()


def test_monitor_configure_persists_across_restart(monitor, tmp_path):
    """Configuration survives a full service recreation (restart recovery)."""
    monitor.configure(symbol="ETH/USDT", budget="4321.50")
    monitor.stop()

    from ohmycrypto.services import monitor as monitor_module

    second = monitor_module.MonitoringService(poll_interval_sec=0.2)
    try:
        assert second.status_snapshot()["active_symbol"] == "ETH/USDT"
        assert second.status_snapshot()["active_budget"] == "4321.50"
    finally:
        second.close()


def test_monitor_isolates_connector_fault(monitor):
    """A failing connector does not kill the loop; a diagnostic is raised."""
    coinbase = monitor._connectors["coinbase"]

    async def failing_fetch(symbol: str, depth: int = 20):
        raise RuntimeError("gateway timeout")

    coinbase.fetch_orderbook = failing_fetch
    monitor.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if monitor.status_snapshot()["cycles_done"] >= 1:
            break
        time.sleep(0.05)
    stopped = monitor.stop()
    assert stopped["cycles_done"] >= 1
    # No decision is recorded when one venue lacks a book (unknown coverage).
    assert len(monitor.recent_events()) == 0
    # The failure surfaced as a recorded diagnostic incident.
    incidents = monitor.recent_incidents()
    assert any(
        inc["connector"] == "coinbase" and inc["fault_class"] == "consecutive_failures"
        for inc in incidents
    )
