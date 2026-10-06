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
        """Acquire an atomic OS-backed single-instance writer lock file."""
        import fcntl

        if lock_dir is None:
            lock_dir = os.environ.get("OHMYCRYPTO_DATA_DIR")
            if not lock_dir:
                lock_dir = os.path.expanduser("~/Library/Application Support/OhMyCrypto")
        os.makedirs(lock_dir, exist_ok=True)
        self.lock_file_path = os.path.join(lock_dir, "engine.lock")

        try:
            self._lock_file = open(self.lock_file_path, "a+", encoding="utf-8")
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                # Lock is currently held by another active process
                self._lock_file.seek(0)
                old_pid = self._lock_file.read().strip()
                sys.stderr.write(f"[sidecar] Active instance with PID {old_pid} already holds lock.\n")
                self._lock_file.close()
                self._lock_file = None
                return False

            self._lock_file.seek(0)
            self._lock_file.truncate(0)
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            return True
        except Exception as e:
            sys.stderr.write(f"[sidecar] Failed to acquire lock: {e}\n")
            return False

    def release_lock(self) -> None:
        """Release single-instance lock file."""
        import fcntl

        if getattr(self, "_lock_file", None) is not None:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None

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

    def _action_get_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._engine()._db_lock:
            settings = self._engine().repo.get_setting("system_settings")
        if not isinstance(settings, dict):
            settings = {
                "retention_days": 7,
                "raw_quota_gb": 2,
                "audio_enabled": True,
                "speech_enabled": False,
                "quiet_mode": False,
            }
        return {"settings": settings}

    def _action_update_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._engine()._db_lock:
            existing = self._engine().repo.get_setting("system_settings")
            if not isinstance(existing, dict):
                existing = {
                    "retention_days": 7,
                    "raw_quota_gb": 2,
                    "audio_enabled": True,
                    "speech_enabled": False,
                    "quiet_mode": False,
                }
            updates = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
            if not isinstance(updates, dict):
                raise ValueError("Settings payload must be a dictionary")

            if "retention_days" in updates:
                try:
                    val = int(updates["retention_days"])
                    if val < 1:
                        raise ValueError("retention_days must be at least 1")
                    existing["retention_days"] = val
                except (ValueError, TypeError) as err:
                    raise ValueError(f"Invalid retention_days: {updates['retention_days']}") from err

            if "raw_quota_gb" in updates:
                try:
                    val = float(updates["raw_quota_gb"])
                    if val <= 0:
                        raise ValueError("raw_quota_gb must be positive")
                    existing["raw_quota_gb"] = val
                    if hasattr(self._engine(), "archives") and self._engine().archives is not None:
                        self._engine().archives.quota_bytes = int(val * 1024 * 1024 * 1024)
                except (ValueError, TypeError) as err:
                    raise ValueError(f"Invalid raw_quota_gb: {updates['raw_quota_gb']}") from err

            for bool_field in ("audio_enabled", "speech_enabled", "quiet_mode"):
                if bool_field in updates:
                    val = updates[bool_field]
                    if not isinstance(val, bool):
                        raise ValueError(f"{bool_field} must be a boolean, got {type(val).__name__}")
                    existing[bool_field] = val

            self._engine().repo.set_setting("system_settings", existing)
        return {"settings": existing}

    def _action_export_replay_bundle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_id = payload.get("event_id")
        mode = payload.get("mode") or "complete"
        service = self._engine().opportunity
        if not event_id:
            with self._engine()._db_lock:
                cursor = self._engine().repo.conn.execute(
                    "SELECT event_id FROM events ORDER BY timestamp_utc_ms DESC LIMIT 1;"
                )
                row = cursor.fetchone()
            if row is None:
                raise ValueError("No recorded events to export")
            event_id = row["event_id"]
        return service.export_replay_bundle(event_id, mode=mode)

    def _action_get_incidents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(payload.get("limit") or 50)
        rows = self._engine().recent_incidents(limit=max(1, min(limit, 200)))
        incidents = [self._incident_to_item(row) for row in rows]
        latencies = {
            "coinbase": self._engine().diagnostics.get_latency_distribution("coinbase"),
            "kraken": self._engine().diagnostics.get_latency_distribution("kraken"),
        }
        return {"incidents": incidents, "latencies": latencies}

    def _action_get_diagnostics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._action_get_incidents(payload)

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
                book = monitor.run_async(connector.fetch_orderbook(symbol))
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

        grid = advisor.compute_amount_grid(
            side=side,
            grid_amounts=[Decimal("100"), Decimal("1000"), Decimal("10000")],
            symbol=symbol,
            books=books,
            fee_profiles=fee_profiles,
            instruments=instruments,
        )

        split_pct = Decimal(str(payload.get("split_ratio", 50))) / Decimal("100")
        if "coinbase" in books and "kraken" in books:
            allocations = [
                ("coinbase", amount * split_pct),
                ("kraken", amount * (Decimal("1") - split_pct)),
            ]
            split_res = advisor.evaluate_split_order(
                side=side,
                symbol=symbol,
                allocations=allocations,
                books=books,
                fee_profiles=fee_profiles,
                instruments=instruments,
            )
        else:
            split_res = None

        return {
            "side": side,
            "symbol": symbol,
            "results": results,
            "grid": grid,
            "split": split_res,
        }

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
        res = dict(replayed)
        res["bundle_manifest"] = bundle.get("manifest")
        res["replay"] = replayed
        return res

    def _action_export_incident_bundle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        incident_id = payload.get("incident_id")
        if not incident_id:
            raise ValueError("incident_id is required")
        return self._engine().diagnostics.export_incident_bundle(incident_id)

    # ------------------------------------------------------------- mapping

    @staticmethod
    def _event_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        opp = json.loads(row["opportunity_json"]) if isinstance(row.get("opportunity_json"), str) else (row.get("opportunity") or {})
        buy_raw = opp.get("buy_fill") or {}
        sell_raw = opp.get("sell_fill") or {}

        def _norm_fill(f: Dict[str, Any], side: str) -> Dict[str, Any]:
            spent = f.get("quote_spent") or f.get("spent_quote") or (opp.get("buy_spent") if side == "buy" else "0.0") or "0.0"
            received = f.get("quote_received") or f.get("proceeds_quote") or (opp.get("sell_proceeds") if side == "sell" else "0.0") or "0.0"
            fee = f.get("fee_quote") or f.get("fee_paid") or opp.get(f"{side}_fee") or "0.0"
            avg_px = f.get("avg_price") or f.get("effective_avg_price") or opp.get(f"{side}_price") or "0.0"
            acq = f.get("acquired_base") or opp.get("acquired_base") or "0.0"
            return {
                "side": side,
                "requested_amount": str(f.get("requested_amount", "")),
                "acquired_base": str(acq),
                "spent_quote": str(spent),
                "quote_spent": str(spent),
                "proceeds_quote": str(received),
                "quote_received": str(received),
                "fee_paid": str(fee),
                "fee_quote": str(fee),
                "fee_base": str(f.get("fee_base", "0.0")),
                "effective_avg_price": str(avg_px),
                "avg_price": str(avg_px),
                "residual_quote": str(f.get("residual_quote", "0.0")),
                "residual_base": str(f.get("residual_base", "0.0")),
                "levels_consumed": int(f.get("levels_consumed", 0)),
                "is_complete": bool(f.get("is_complete", True)),
                "rejection_reason": f.get("rejection_reason"),
            }

        buy_fill = _norm_fill(buy_raw, "buy")
        sell_fill = _norm_fill(sell_raw, "sell")
        input_hash = row.get("input_hash") or opp.get("input_hash") or ""
        config_hash = row.get("config_hash") or opp.get("config_hash") or ""

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
            "input_hash": input_hash,
            "config_hash": config_hash,
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


def _run_async(coro: Any, engine: Optional[SidecarEngine] = None) -> Any:
    """Run a coroutine on the engine's persistent I/O event loop or a fresh loop if needed."""
    if engine is not None and engine._monitor is not None and engine._monitor._io_loop is not None and engine._monitor._io_loop.is_running():
        return engine._monitor.run_async(coro)
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
