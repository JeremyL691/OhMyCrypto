"""JSON Lines IPC sidecar interface for the Tauri desktop shell.

Follows Sections 4, 5, and 10 of PROJECT_EXECUTION_GUIDE.md:
- Versioned JSON Lines over stdin / stdout; stdout reserved strictly for
  protocol messages; stderr used for all logging and diagnostics
- Parent owns child lifetime (stdin EOF or shutdown action triggers clean exit)
- Single instance writer lock
- Every financial value is serialized as a decimal string with currency
  identifiers; no NaN/infinity JSON (DecimalJSONEncoder)

Actions are dispatched to the same domain/services layer used by the CLI:
monitoring (start/pause/resume/stop with the continuous loop), opportunity
events, feed diagnostics incidents, execution cost comparison, and deterministic
replay. Unknown actions are errors; every response carries a request id.
"""

from __future__ import annotations

import atexit
from decimal import Decimal, InvalidOperation
import json
import os
import signal
import sys
import time
from typing import Any, Dict, Optional

from ohmycrypto.domain.models import (
    DecimalJSONEncoder,
    FeeProfile,
    Instrument,
    dumps_canonical_json,
)
from ohmycrypto.services.monitor import MonitoringService

PROTOCOL_VERSION = "1.0.0"


def send_response(request_id: Optional[str], status: str, payload: Any = None, error: Optional[str] = None) -> None:
    """Send protocol response to stdout as a single JSON line."""
    resp = {
        "id": request_id,
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "payload": payload or {},
    }
    if error is not None:
        resp["error"] = error
    line = json.dumps(resp, cls=DecimalJSONEncoder)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def send_event(event_name: str, payload: Any) -> None:
    """Broadcast an asynchronous event line to stdout."""
    event_msg = {
        "event": event_name,
        "protocol_version": PROTOCOL_VERSION,
        "timestamp_utc_ms": int(time.time() * 1000),
        "payload": payload,
    }
    line = json.dumps(event_msg, cls=DecimalJSONEncoder)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


class SidecarEngine:
    """Stateful sidecar engine: lifecycle plus dispatch to real services.

    The engine stack (storage, monitor, services) is initialized lazily on
    first use so protocol-level actions such as ping stay fast and the
    single-instance lock remains the only startup side effect.
    """

    def __init__(self):
        self.running = True
        self.status = "idle"  # idle | monitoring | paused | stopped
        self.start_time = time.time()
        self.lock_file_path: Optional[str] = None
        self._monitor: Optional[MonitoringService] = None

    # ------------------------------------------------------------- engine stack

    def _engine(self) -> MonitoringService:
        """Create the monitoring service stack on first real use."""
        if self._monitor is None:
            self._monitor = MonitoringService()
        return self._monitor

    def close(self) -> None:
        if self._monitor is not None:
            self._monitor.close()
            self._monitor = None

    # -------------------------------------------------------------- lock file

    def acquire_lock(self, lock_dir: Optional[str] = None) -> bool:
        """Acquire a single-instance writer lock file."""
        if lock_dir is None:
            lock_dir = os.environ.get("OHMYCRYPTO_DATA_DIR")
            if not lock_dir:
                lock_dir = os.path.expanduser("~/Library/Application Support/OhMyCrypto")
        os.makedirs(lock_dir, exist_ok=True)
        self.lock_file_path = os.path.join(lock_dir, "engine.lock")

        try:
            # Check if existing lock is active
            if os.path.exists(self.lock_file_path):
                with open(self.lock_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    try:
                        old_pid = int(content)
                        # Check if process with old_pid is running
                        os.kill(old_pid, 0)
                        # Process exists, cannot acquire
                        sys.stderr.write(f"[sidecar] Active instance with PID {old_pid} already holds lock.\n")
                        return False
                    except (OSError, ProcessLookupError, ValueError):
                        # Stale lock file
                        sys.stderr.write(f"[sidecar] Clearing stale lock file from PID {content}.\n")

            with open(self.lock_file_path, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            sys.stderr.write(f"[sidecar] Failed to acquire lock: {e}\n")
            return False

    def release_lock(self) -> None:
        """Release single-instance lock file."""
        if self.lock_file_path and os.path.exists(self.lock_file_path):
            try:
                with open(self.lock_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content == str(os.getpid()):
                    os.remove(self.lock_file_path)
            except Exception as e:
                sys.stderr.write(f"[sidecar] Error removing lock file: {e}\n")

    # ---------------------------------------------------------------- dispatch

    def handle_request(self, req: Dict[str, Any]) -> None:
        """Dispatch action to handler and send response."""
        req_id = req.get("id")
        action = req.get("action")
        payload = req.get("payload") or {}

        if not action:
            send_response(req_id, status="error", error="Missing action field")
            return

        try:
            handler = getattr(self, f"_action_{action}", None)
            if handler is None:
                send_response(req_id, status="error", error=f"Unknown action: {action}")
                return
            result = handler(payload)
            # A handler may already have sent a response (streaming actions do);
            # otherwise answer with its payload.
            if result is not None:
                send_response(req_id, status="ok", payload=result)
            self.status = self._status_label()

        except InvalidOperation as err:
            send_response(req_id, status="error", error=f"Invalid decimal argument: {err}")
        except Exception as err:  # noqa: BLE001 - errors must reach the caller
            sys.stderr.write(f"[sidecar] Error handling {action}: {err}\n")
            send_response(req_id, status="error", error=str(err))

    def _status_label(self) -> str:
        if self._monitor is None:
            return self.status if self.status != "monitoring" else "idle"
        return self._monitor.status_snapshot()["status"]

    # ------------------------------------------------------------- actions

    def _action_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pong": True,
            "version": PROTOCOL_VERSION,
            "pid": os.getpid(),
            "server_time_ms": int(time.time() * 1000),
        }

    def _action_get_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine().status_snapshot()

    def _action_start_monitor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        monitor = self._engine()
        if payload.get("symbol") or payload.get("budget"):
            monitor.configure(
                symbol=payload.get("symbol"),
                budget=payload.get("budget"),
            )
        snap = monitor.start()
        self.status = "monitoring"
        return snap

    def _action_pause_monitor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine().pause()

    def _action_resume_monitor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine().resume()

    def _action_stop_monitor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine().stop()

    def _action_shutdown(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.running = False
        return {"message": "shutting down"}

    def _action_configure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine().configure(
            symbol=payload.get("symbol"),
            budget=payload.get("budget"),
            buy_venue=payload.get("buy_venue"),
            sell_venue=payload.get("sell_venue"),
        )

    def _action_get_overview(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        monitor = self._engine()
        return {
            "status": monitor.status_snapshot(),
            "recent_events": monitor.recent_events(limit=20),
            "recent_incidents": monitor.recent_incidents(limit=20),
        }

    def _action_get_opportunities(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(payload.get("limit") or 50)
        events = self._engine().recent_events(limit=max(1, min(limit, 200)))
        return {"opportunities": [self._event_to_item(row) for row in events]}

    def _action_get_incidents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(payload.get("limit") or 50)
        rows = self._engine().recent_incidents(limit=max(1, min(limit, 200)))
        return {"incidents": [self._incident_to_item(row) for row in rows]}

    def _action_compare_costs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        side = payload.get("side")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        amount = Decimal(str(payload.get("amount") or "1000"))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("amount must be a finite positive decimal")
        symbol = str(payload.get("symbol") or "BTC/USDT")

        monitor = self._engine()
        books = {}
        for venue, connector in monitor._connectors.items():
            t0 = time.monotonic()
            try:
                book = _run_async(connector.fetch_orderbook(symbol))
                books[venue] = book
                monitor.diagnostics.record_latency(venue, (time.monotonic() - t0) * 1000)
            except Exception as exc:  # noqa: BLE001 - report per-venue failure
                sys.stderr.write(f"[sidecar] compare_costs: {venue} fetch failed: {exc}\n")
        if not books:
            raise RuntimeError("No venue book could be captured; comparison is UNKNOWN")

        base, quote = symbol.split("/")
        instruments = {
            venue: Instrument(symbol=symbol, base=base, quote=quote, venue=venue, native_symbol=symbol)
            for venue in books
        }
        fee_profiles = {
            venue: FeeProfile(venue=venue, taker_rate=Decimal("0.0025"))
            for venue in books
        }
        from ohmycrypto.services.cost import CostAdvisorService

        advisor = CostAdvisorService()
        results = advisor.compare_single_amount(
            side=side,
            amount=amount,
            symbol=symbol,
            books=books,
            fee_profiles=fee_profiles,
            instruments=instruments,
        )
        return {"side": side, "symbol": symbol, "results": results}

    def _action_replay_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_id = payload.get("event_id")
        if not event_id:
            raise ValueError("event_id is required")
        override = payload.get("override_fee")
        override_decimal = Decimal(str(override)) if override not in (None, "") else None
        service = self._engine().opportunity
        bundle = service.export_replay_bundle(event_id)
        replayed = service.replay_bundle(
            bundle,
            override_buy_fee=override_decimal,
        )
        return {"bundle_manifest": bundle.get("manifest"), "replay": replayed}

    def _action_export_incident_bundle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        incident_id = payload.get("incident_id")
        if not incident_id:
            raise ValueError("incident_id is required")
        return self._engine().diagnostics.export_incident_bundle(incident_id)

    # ------------------------------------------------------------- mapping

    @staticmethod
    def _event_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        opp = json.loads(row["opportunity_json"]) if isinstance(row.get("opportunity_json"), str) else row.get("opportunity", {})
        buy_fill = opp.get("buy_fill") or {}
        sell_fill = opp.get("sell_fill") or {}
        return {
            "event_id": row.get("event_id"),
            "episode_id": row.get("episode_id"),
            "route_key": row.get("route_key"),
            "timestamp_utc_ms": row.get("timestamp_utc_ms"),
            "symbol": opp.get("symbol"),
            "buy_venue": opp.get("buy_venue"),
            "sell_venue": opp.get("sell_venue"),
            "budget_amount": opp.get("budget_amount"),
            "budget_units": opp.get("budget_units"),
            "net_profit_quote": opp.get("net_profit_quote"),
            "effective_spread": opp.get("effective_spread"),
            "midpoint_price": opp.get("midpoint_price"),
            "is_positive": opp.get("is_positive"),
            "is_eligible": opp.get("is_eligible"),
            "eligibility_reasons": opp.get("eligibility_reasons") or [],
            "input_hash": opp.get("input_hash"),
            "config_hash": opp.get("config_hash"),
            "follow_up_500ms": row.get("follow_up_500ms"),
            "follow_up_1s": row.get("follow_up_1s"),
            "follow_up_3s": row.get("follow_up_3s"),
            "continuous_persistence_status": row.get("continuous_persistence_status"),
            "notification_state": row.get("notification_state"),
            "buy_fill": buy_fill,
            "sell_fill": sell_fill,
        }

    @staticmethod
    def _incident_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            evidence = json.loads(row["raw_evidence_json"]) if row.get("raw_evidence_json") else {}
        except (TypeError, json.JSONDecodeError):
            evidence = {}
        return {
            "incident_id": row.get("incident_id"),
            "connector": row.get("connector"),
            "channel": row.get("channel"),
            "fault_class": row.get("fault_class"),
            "trigger": row.get("trigger"),
            "severity": row.get("severity"),
            "opened_at_ms": row.get("opened_at_ms"),
            "closed_at_ms": row.get("closed_at_ms"),
            "is_recovered": bool(row.get("is_recovered")),
            "raw_evidence": evidence,
        }


def _run_async(coro: Any) -> Any:
    """Run a coroutine on a fresh event loop from synchronous code."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def main() -> None:
    """Sidecar main loop over stdin/stdout."""
    engine = SidecarEngine()

    # Ensure lock cleanup on exit
    atexit.register(engine.close)
    atexit.register(engine.release_lock)

    def handle_signal(sig, frame):
        sys.stderr.write(f"[sidecar] Caught signal {sig}, terminating gracefully...\n")
        engine.close()
        engine.release_lock()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Acquire lock in the per-user application support directory (overridable
    # for tests via OHMYCRYPTO_LOCK_DIR).
    lock_dir = os.environ.get("OHMYCRYPTO_LOCK_DIR")
    if not engine.acquire_lock(lock_dir):
        sys.stderr.write("[sidecar] Another instance is running. Exiting.\n")
        send_response(None, status="error", error="ALREADY_RUNNING")
        sys.exit(1)

    sys.stderr.write(f"[sidecar] Started OhMyCrypto sidecar (PID={os.getpid()})\n")
    sys.stderr.flush()

    try:
        while engine.running:
            line = sys.stdin.readline()
            if not line:
                # EOF reached: parent process exited or closed stdin pipe
                sys.stderr.write("[sidecar] Stdin closed (EOF). Parent terminated. Exiting.\n")
                break

            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError as err:
                send_response(None, status="error", error=f"Invalid JSON: {err}")
                continue

            engine.handle_request(req)

    except Exception as exc:
        sys.stderr.write(f"[sidecar] Fatal error: {exc}\n")
    finally:
        engine.close()
        engine.release_lock()
        sys.stderr.write("[sidecar] Sidecar cleanly exited.\n")


if __name__ == "__main__":
    main()
