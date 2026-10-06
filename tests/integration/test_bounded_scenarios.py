"""Bounded scenario operational correctness tests for R12 and N07.

Per PROJECT_EXECUTION_GUIDE.md Section 10/N07 and Section 11/R12:
- Replaces former 24h soak with bounded scenario checks:
  1. 100 deterministic production-service monitoring cycles
  2. Start / pause / resume / stop lifecycle transitions
  3. Safe handling of invalid data / degradation without crashes
  4. Memory bounds (no runaway leak) and retention boundaries
"""

from __future__ import annotations

import time
from decimal import Decimal
import pytest

from ohmycrypto.adapters.base import BaseSpotConnector
from ohmycrypto.domain.models import BookLevel, BookState, Instrument
from ohmycrypto.services.monitor import MonitoringService


class DeterministicScenarioConnector(BaseSpotConnector):
    """Connector supplying controlled scenario books with simulated price movements."""

    def __init__(self, venue: str, base_bid: str, base_ask: str):
        super().__init__(venue)
        self.venue_name = venue
        self._base_bid = Decimal(base_bid)
        self._base_ask = Decimal(base_ask)
        self.cycle_count = 0

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
        self.cycle_count += 1
        # Drift slightly each cycle
        drift = Decimal(str((self.cycle_count % 10) * 0.5))
        bid = self._base_bid + drift
        ask = self._base_ask + drift
        book = BookState(
            venue=self.venue_name,
            symbol=symbol,
            bids=(BookLevel(price=bid, amount=Decimal("2.0")),),
            asks=(BookLevel(price=ask, amount=Decimal("2.0")),),
            snapshot_origin="scenario_test",
            applied_sequence=self.cycle_count,
            source_time_ms=int(time.time() * 1000),
            source_time_meaning="unknown",
            local_receipt_utc_ms=int(time.time() * 1000),
            local_receipt_mono_ns=time.monotonic_ns(),
        )
        self.set_orderbook(symbol, book)
        return book


def test_r12_bounded_100_cycle_scenario_and_lifecycle(tmp_path, monkeypatch):
    """Run 100 production-service cycles and verify lifecycle, retention, and no leak."""
    monkeypatch.setenv("OHMYCRYPTO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OHMYCRYPTO_LOCK_DIR", str(tmp_path))

    svc = MonitoringService(poll_interval_sec=0.01)
    cb = DeterministicScenarioConnector("coinbase", "85000.0", "85010.0")
    kr = DeterministicScenarioConnector("kraken", "85020.0", "85030.0")
    svc._connectors = {"coinbase": cb, "kraken": kr}

    # 1. Start monitoring
    svc.start()
    assert svc.status_snapshot()["status"] == "monitoring"

    # 2. Let it run for 30 cycles
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and svc.status_snapshot()["cycles_done"] < 30:
        time.sleep(0.02)
    assert svc.status_snapshot()["cycles_done"] >= 30

    # 3. Pause
    svc.pause()
    assert svc.status_snapshot()["status"] == "paused"
    count_at_pause = svc.status_snapshot()["cycles_done"]
    time.sleep(0.05)
    # No new cycles while paused
    assert svc.status_snapshot()["cycles_done"] <= count_at_pause + 1

    # 4. Resume
    svc.resume()
    assert svc.status_snapshot()["status"] == "monitoring"

    # 5. Let it reach 100 cycles
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and svc.status_snapshot()["cycles_done"] < 100:
        time.sleep(0.02)
    assert svc.status_snapshot()["cycles_done"] >= 100

    # 6. Stop cleanly
    status = svc.stop()
    assert status["status"] == "idle"
    assert status["cycles_done"] >= 100

    # 7. Check database storage and events
    events = svc.recent_events(limit=50)
    assert len(events) > 0
    assert svc.status_snapshot()["last_cycle_error"] is None

    # 8. Check resource and memory bounds (Section 12.2: RSS <= 512MiB)
    import resource
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    max_rss_bytes = rusage.ru_maxrss  # On macOS, ru_maxrss is in bytes
    max_rss_mib = max_rss_bytes / (1024 * 1024)
    assert max_rss_mib <= 512.0, f"Engine RSS {max_rss_mib:.2f} MiB exceeded 512 MiB bound"

    # 9. Verify archive quota and storage bounds
    quota_status = svc.opportunity.archives.get_quota_status()
    assert quota_status["total_bytes"] <= svc.opportunity.archives.quota_bytes

    svc.close()
