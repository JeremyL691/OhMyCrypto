"""JSON Lines IPC sidecar interface for Tauri desktop integration.

Follows Section 4 and Section 10 (T01 spike) of PROJECT_EXECUTION_GUIDE.md:
- Versioned JSON Lines over stdin / stdout
- stdout reserved strictly for protocol messages
- stderr used for all logging and diagnostics
- Parent owns child lifetime (stdin EOF or shutdown action triggers clean exit)
- Single instance writer lock
"""

from __future__ import annotations

import atexit
from decimal import Decimal
import json
import os
import signal
import sys
import time
from typing import Any, Dict, Optional

from ohmycrypto.domain.models import DecimalJSONEncoder, dumps_canonical_json

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
    """Stateful sidecar engine managing requests and lifecycle."""

    def __init__(self):
        self.running = True
        self.status = "idle"  # "idle", "monitoring", "paused", "stopped"
        self.start_time = time.time()
        self.lock_file_path: Optional[str] = None

    def acquire_lock(self, lock_dir: Optional[str] = None) -> bool:
        """Acquire a single-instance writer lock file."""
        if lock_dir is None:
            lock_dir = os.path.expanduser("~/.ohmycrypto")
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
                    except (OSError, ProcessLookupError):
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

    def handle_request(self, req: Dict[str, Any]) -> None:
        """Dispatch action to handler and send response."""
        req_id = req.get("id")
        action = req.get("action")
        payload = req.get("payload", {})

        if not action:
            send_response(req_id, status="error", error="Missing action field")
            return

        try:
            if action == "ping":
                send_response(req_id, status="ok", payload={
                    "pong": True,
                    "version": PROTOCOL_VERSION,
                    "pid": os.getpid(),
                    "server_time_ms": int(time.time() * 1000),
                })

            elif action == "get_status":
                send_response(req_id, status="ok", payload={
                    "status": self.status,
                    "uptime_sec": int(time.time() - self.start_time),
                    "pid": os.getpid(),
                })

            elif action == "start_monitor":
                self.status = "monitoring"
                send_response(req_id, status="ok", payload={"status": self.status})

            elif action == "pause_monitor":
                self.status = "paused"
                send_response(req_id, status="ok", payload={"status": self.status})

            elif action == "resume_monitor":
                self.status = "monitoring"
                send_response(req_id, status="ok", payload={"status": self.status})

            elif action == "stop_monitor":
                self.status = "stopped"
                send_response(req_id, status="ok", payload={"status": self.status})

            elif action == "shutdown":
                send_response(req_id, status="ok", payload={"message": "shutting down"})
                self.running = False

            else:
                send_response(req_id, status="error", error=f"Unknown action: {action}")

        except Exception as err:
            sys.stderr.write(f"[sidecar] Error handling {action}: {err}\n")
            send_response(req_id, status="error", error=str(err))


def main() -> None:
    """Sidecar main loop over stdin/stdout."""
    engine = SidecarEngine()

    # Ensure lock cleanup on exit
    atexit.register(engine.release_lock)

    def handle_signal(sig, frame):
        sys.stderr.write(f"[sidecar] Caught signal {sig}, terminating gracefully...\n")
        engine.release_lock()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Acquire lock in temp/test safe path
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
        engine.release_lock()
        sys.stderr.write("[sidecar] Sidecar cleanly exited.\n")


if __name__ == "__main__":
    main()
