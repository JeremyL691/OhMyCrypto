"""Integration test for the packaged PyInstaller sidecar binary."""

import json
import os
import subprocess
import pytest


def test_packaged_sidecar_round_trip_and_quit():
    """Verify the frozen standalone sidecar binary runs, responds, and quits on EOF."""
    bin_path = os.path.abspath("dist/ohmycrypto-sidecar/ohmycrypto-sidecar")
    assert os.path.exists(bin_path), f"Packaged binary not found at {bin_path}"

    proc = subprocess.Popen(
        [bin_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Send ping
        req = {"id": "spike-ping", "action": "ping", "payload": {}}
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()

        line = proc.stdout.readline()
        assert line, "No response from sidecar"
        resp = json.loads(line.strip())
        assert resp["id"] == "spike-ping"
        assert resp["status"] == "ok"
        assert resp["payload"]["pong"] is True

        # Send status
        req_status = {"id": "spike-status", "action": "get_status", "payload": {}}
        proc.stdin.write(json.dumps(req_status) + "\n")
        proc.stdin.flush()

        line_status = proc.stdout.readline()
        assert line_status
        resp_status = json.loads(line_status.strip())
        assert resp_status["id"] == "spike-status"
        assert resp_status["payload"]["status"] == "idle"

        # Close stdin to verify owned-child quit
        proc.stdin.close()
        exit_code = proc.wait(timeout=3.0)
        assert exit_code == 0, f"Expected 0 on EOF, got {exit_code}"

    finally:
        if proc.poll() is None:
            proc.kill()
