"""Continuous market monitoring service.

Implements the application's monitoring loop required by Sections 1, 3, and 8
of PROJECT_EXECUTION_GUIDE.md: the loop runs while the host is awake with
pause/resume support, bounded resources, and explicit recovery. Each cycle
captures both public venue books, evaluates cross-venue opportunities through
the deterministic kernel (OpportunityService), persists DecisionEvents, and
feeds the diagnostics incident registry. Restarts reload the last persisted
configuration from settings; resumption of decisions is manual (start), never
automatic, per Section 5.2 ("rebuild books before resuming decisions").
"""

from __future__ import annotations

import asyncio
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ohmycrypto.adapters.base import BaseSpotConnector
from ohmycrypto.adapters.coinbase import CoinbaseConnector
from ohmycrypto.adapters.kraken import KrakenConnector
from ohmycrypto.domain.models import FeeProfile, Instrument
from ohmycrypto.services.diagnostics import DiagnosticService
from ohmycrypto.services.opportunity import OpportunityService
from ohmycrypto.storage.archives import ArchiveManager
from ohmycrypto.storage.db import create_connection
from ohmycrypto.storage.migrations import run_migrations
from ohmycrypto.storage.repository import StorageRepository

DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_BUDGET = "1000.00"
DEFAULT_POLL_INTERVAL_SEC = 5.0
MAX_SNAPSHOT_EVENTS = 20


class MonitoringService:
    """Bounded continuous monitoring loop shared by the sidecar and the CLI.

    One instance owns one writer connection. The loop thread is a daemon so it
    can never keep the host process alive; stop() joins it explicitly.
    """

    def __init__(
        self,
        repository: Optional[StorageRepository] = None,
        opportunity_service: Optional[OpportunityService] = None,
        diagnostics: Optional[DiagnosticService] = None,
        poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
    ):
        self.conn = create_connection(check_same_thread=False)
        run_migrations(self.conn)
        self.repo = repository or StorageRepository(self.conn)
        self.archives = ArchiveManager()
        # The connection is shared between the interface thread and the loop
        # thread; every repository touch must hold this reentrant lock.
        self._db_lock = threading.RLock()
        self.opportunity = opportunity_service or OpportunityService(
            repository=self.repo,
            archive_manager=self.archives,
        )
        self.diagnostics = diagnostics or DiagnosticService(
            repository=self.repo, archive_manager=self.archives
        )
        self.poll_interval_sec = poll_interval_sec

        self._connectors: Dict[str, BaseSpotConnector] = {
            "coinbase": CoinbaseConnector(),
            "kraken": KrakenConnector(),
        }

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_requested = threading.Event()
        self._wakeup = threading.Event()
        self._status = "idle"  # idle | monitoring | paused | stopped
        self._config: Dict[str, Any] = self._load_config()
        self._cycles_done = 0
        self._last_cycle_error: Optional[str] = None
        self._started_at_mono: Optional[float] = None

    # ------------------------------------------------------------------ config

    def _load_config(self) -> Dict[str, Any]:
        with self._db_lock:
            raw = self.repo.get_setting("monitor_config")
        if isinstance(raw, dict) and raw.get("symbol"):
            return raw
        return {
            "symbol": DEFAULT_SYMBOL,
            "budget": DEFAULT_BUDGET,
            "buy_venue": "coinbase",
            "sell_venue": "kraken",
            "min_profit_threshold": "0",
            "min_spread_threshold": "0",
        }

    def _persist_config(self) -> None:
        with self._db_lock:
            self.repo.set_setting("monitor_config", dict(self._config))

    def configure(
        self,
        symbol: Optional[str] = None,
        budget: Optional[str] = None,
        buy_venue: Optional[str] = None,
        sell_venue: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update monitoring configuration prospectively; never rewrites events."""
        with self._lock:
            if symbol:
                self._config["symbol"] = str(symbol)
            if budget is not None:
                Decimal(str(budget))  # validate finite decimal, raise otherwise
                self._config["budget"] = str(budget)
            if buy_venue:
                self._config["buy_venue"] = str(buy_venue)
            if sell_venue:
                self._config["sell_venue"] = str(sell_venue)
            self._persist_config()
            return dict(self._config)

    # -------------------------------------------------------------- lifecycle

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._status == "monitoring":
                return self._snapshot_locked()
            if self._thread is None or not self._thread.is_alive():
                self._stop_requested.clear()
                self._thread = threading.Thread(
                    target=self._run_loop, name="omc-monitor", daemon=True
                )
                self._thread.start()
            self._status = "monitoring"
            self._started_at_mono = time.monotonic()
            self._wakeup.set()
            return self._snapshot_locked()

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if self._status == "monitoring":
                self._status = "paused"
            return self._snapshot_locked()

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if self._status == "paused":
                self._status = "monitoring"
                self._wakeup.set()
            return self._snapshot_locked()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._status = "stopped"
        self._stop_requested.set()
        self._wakeup.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=10.0)
        with self._lock:
            self._thread = None
            self._status = "idle"
            return self._snapshot_locked()

    def status_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> Dict[str, Any]:
        """Build the status snapshot; caller must already hold self._lock."""
        uptime = (
            int(time.monotonic() - self._started_at_mono)
            if self._started_at_mono is not None and self._status == "monitoring"
            else 0
        )
        return {
            "status": self._status,
            "uptime_sec": uptime,
            "pid": __import__("os").getpid(),
            "active_symbol": self._config.get("symbol", DEFAULT_SYMBOL),
            "active_budget": self._config.get("budget", DEFAULT_BUDGET),
            "buy_venue": self._config.get("buy_venue"),
            "sell_venue": self._config.get("sell_venue"),
            "cycles_done": self._cycles_done,
            "last_cycle_error": self._last_cycle_error,
            "poll_interval_sec": self.poll_interval_sec,
            "is_demo": False,
        }

    # ------------------------------------------------------------------ loop

    def _run_loop(self) -> None:
        while not self._stop_requested.is_set():
            with self._lock:
                active = self._status == "monitoring"
            if not active:
                self._wakeup.wait(timeout=0.5)
                self._wakeup.clear()
                continue
            t0 = time.monotonic()
            try:
                self._run_cycle()
                self._last_cycle_error = None
            except Exception as exc:  # noqa: BLE001 - the loop must survive faults
                self._last_cycle_error = str(exc)
            self._cycles_done += 1
            elapsed = time.monotonic() - t0
            self._wakeup.wait(timeout=max(0.1, self.poll_interval_sec - elapsed))
            self._wakeup.clear()

    def _run_cycle(self) -> None:
        symbol = self._config["symbol"]
        buy_venue = self._config["buy_venue"]
        sell_venue = self._config["sell_venue"]
        try:
            budget = Decimal(str(self._config["budget"]))
        except (InvalidOperation, ValueError):
            budget = Decimal(DEFAULT_BUDGET)

        books: Dict[str, Any] = {}
        fetch_errors: Dict[str, str] = {}
        t0_map: Dict[str, float] = {}
        # Network I/O happens OUTSIDE the database lock so UI reads never
        # block on venue latency.
        for venue in {buy_venue, sell_venue}:
            connector = self._connectors.get(venue)
            if connector is None:
                continue
            t0_map[venue] = time.monotonic()
            try:
                books[venue] = asyncio.run(connector.fetch_orderbook(symbol))
            except Exception as exc:  # noqa: BLE001 - isolated per connector
                fetch_errors[venue] = str(exc)

        with self._db_lock:
            for venue, book in books.items():
                self.diagnostics.record_latency(
                    venue, (time.monotonic() - t0_map[venue]) * 1000
                )
                self.diagnostics.record_clean_observation(
                    venue, "rest_l2", bool(book.bids and book.asks)
                )
            for venue, err in fetch_errors.items():
                self.diagnostics.record_fault(
                    connector=venue,
                    channel="rest_l2",
                    fault_class="consecutive_failures",
                    trigger=f"orderbook fetch failed: {err}",
                    evidence={"error": err},
                )

            if buy_venue not in books or sell_venue not in books:
                return  # unknown coverage: no decision is recorded for this cycle

            buy_instrument = Instrument(
                symbol=symbol,
                base=symbol.split("/")[0],
                quote=symbol.split("/")[1],
                venue=buy_venue,
                native_symbol=symbol,
            )
            sell_instrument = Instrument(
                symbol=symbol,
                base=symbol.split("/")[0],
                quote=symbol.split("/")[1],
                venue=sell_venue,
                native_symbol=symbol,
            )
            min_profit = Decimal(str(self._config.get("min_profit_threshold", "0")))
            min_spread = Decimal(str(self._config.get("min_spread_threshold", "0")))

            self.opportunity.evaluate(
                symbol=symbol,
                buy_book=books[buy_venue],
                sell_book=books[sell_venue],
                all_in_quote_budget=budget,
                buy_fee_profile=FeeProfile(venue=buy_venue, taker_rate=Decimal("0.0025")),
                sell_fee_profile=FeeProfile(venue=sell_venue, taker_rate=Decimal("0.0025")),
                buy_instrument=buy_instrument,
                sell_instrument=sell_instrument,
                min_profit_threshold=min_profit,
                min_spread_threshold=min_spread,
            )

    # -------------------------------------------------------------- queries

    def recent_events(self, limit: int = MAX_SNAPSHOT_EVENTS) -> List[Dict[str, Any]]:
        with self._db_lock:
            return self.repo.list_events(limit=limit)

    def recent_incidents(self, limit: int = MAX_SNAPSHOT_EVENTS) -> List[Dict[str, Any]]:
        with self._db_lock:
            return self.repo.list_incidents(limit=limit)

    def close(self) -> None:
        try:
            self.stop()
        finally:
            try:
                self.conn.close()
            except Exception:  # noqa: BLE001
                pass
