"""Integration tests for application lifecycle, single-instance lock, and crash recovery."""

import os
import sys
import tempfile
import time
from decimal import Decimal
import pytest

from ohmycrypto.interfaces.sidecar import SidecarEngine
from ohmycrypto.storage.db import create_connection, DatabaseCorruptionError
from ohmycrypto.notifications.outbox import NotificationOutbox, deliver_macos_notification


def test_single_instance_lock_acquisition_and_duplicate_rejection():
    """Verify single-instance writer lock blocks secondary processes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine1 = SidecarEngine()
        acquired1 = engine1.acquire_lock(tmpdir)
        assert acquired1 is True
        assert os.path.exists(os.path.join(tmpdir, "engine.lock"))

        # Secondary engine attempt with same active PID should reject or recognize owner
        engine2 = SidecarEngine()
        # Simulate active lock by writing current pid
        with open(os.path.join(tmpdir, "engine.lock"), "w") as f:
            f.write(str(os.getpid()))

        # Attempting to acquire when lock is held by live PID
        acquired2 = engine2.acquire_lock(tmpdir)
        assert acquired2 is False

        # Release engine1
        engine1.release_lock()
        assert not os.path.exists(os.path.join(tmpdir, "engine.lock"))


def test_stale_lock_recovery():
    """Verify stale lock from nonexistent PID is safely cleared."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "engine.lock")
        # Write PID 9999999 (presumed dead)
        with open(lock_file, "w") as f:
            f.write("9999999")

        engine = SidecarEngine()
        acquired = engine.acquire_lock(tmpdir)
        assert acquired is True
        engine.release_lock()


def test_database_corruption_handling_and_recovery():
    """Verify corrupt database files raise DatabaseCorruptionError and prevent silent overwrite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_db = os.path.join(tmpdir, "corrupt.db")
        # Write garbage header
        with open(corrupt_db, "wb") as f:
            f.write(b"NOT A SQLITE FILE HEADER GARBAGE DATA 1234567890\n")

        with pytest.raises(DatabaseCorruptionError):
            create_connection(corrupt_db)


def test_quiet_mode_explicit_suppression():
    """Verify quiet mode suppresses audio/speech notifications while recording suppression state."""
    outbox = NotificationOutbox(quiet_mode=True)
    rec = outbox.enqueue(
        event_id="evt_test_quiet",
        episode_id="ep_test_quiet",
        route_key="cb->kr:BTC/USDT:1000USDT",
        mode="speech",
        decision_utc_ms=1728148800000,
    )
    assert rec.state == "suppressed"
    assert rec.suppression_reason == "quiet_mode_enabled"
    assert rec.delivery_utc_ms is None
