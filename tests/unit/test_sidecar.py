"""Unit tests for the OhMyCrypto JSON Lines sidecar interface."""

import json
import os
import subprocess
import sys
import tempfile
import time
import pytest


def test_sidecar_ping_and_clean_eof_quit():
    """Verify sidecar processes ping requests and terminates on parent stdin EOF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["OHMYCRYPTO_LOCK_DIR"] = tmpdir
        env["PYTHONPATH"] = "src"

        proc = subprocess.Popen(
            [sys.executable, "-m", "ohmycrypto.interfaces.sidecar"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            # Send ping
            req = {"id": "req-1", "action": "ping", "payload": {}}
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            # Read response
            line = proc.stdout.readline()
            assert line, "Expected line from sidecar stdout"
            resp = json.loads(line.strip())

            assert resp["id"] == "req-1"
            assert resp["status"] == "ok"
            assert resp["payload"]["pong"] is True
            assert resp["protocol_version"] == "1.0.0"

            # Send get_status
            req2 = {"id": "req-2", "action": "get_status", "payload": {}}
            proc.stdin.write(json.dumps(req2) + "\n")
            proc.stdin.flush()

            line2 = proc.stdout.readline()
            assert line2
            resp2 = json.loads(line2.strip())
            assert resp2["id"] == "req-2"
            assert resp2["status"] == "ok"
            assert resp2["payload"]["status"] == "idle"

            # Close stdin to simulate parent exit / EOF
            proc.stdin.close()

            # Process must exit cleanly with code 0 within 3 seconds
            retcode = proc.wait(timeout=3.0)
            assert retcode == 0, f"Sidecar should exit with code 0 on EOF, got {retcode}"

        finally:
            if proc.poll() is None:
                proc.kill()


def test_sidecar_shutdown_action():
    """Verify sidecar handles explicit shutdown action."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["OHMYCRYPTO_LOCK_DIR"] = tmpdir
        env["PYTHONPATH"] = "src"

        proc = subprocess.Popen(
            [sys.executable, "-m", "ohmycrypto.interfaces.sidecar"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            req = {"id": "req-shut", "action": "shutdown", "payload": {}}
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            line = proc.stdout.readline()
            assert line
            resp = json.loads(line.strip())
            assert resp["id"] == "req-shut"
            assert resp["status"] == "ok"

            retcode = proc.wait(timeout=3.0)
            assert retcode == 0
        finally:
            if proc.poll() is None:
                proc.kill()
