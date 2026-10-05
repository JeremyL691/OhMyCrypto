"""Unit tests for SQLite storage, migrations, corruption handling, and atomic archives."""

from decimal import Decimal
import os
import sqlite3
import tempfile
import pytest

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    DecisionEvent,
    DiagnosticFinding,
    FeeProfile,
    Instrument,
)
from ohmycrypto.domain.kernel import evaluate_cross_venue_opportunity
from ohmycrypto.domain.cooldown import EpisodeState
from ohmycrypto.storage.db import (
    DatabaseCorruptionError,
    create_connection,
)
from ohmycrypto.storage.migrations import run_migrations
from ohmycrypto.storage.repository import StorageRepository
from ohmycrypto.storage.archives import ArchiveManager


def test_migrations_and_foreign_keys():
    """Verify migrations apply cleanly and foreign keys are enforced."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        try:
            latest_version = run_migrations(conn)
            assert latest_version == 1

            # Foreign key violation: inserting event without episode must fail
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO events (event_id, episode_id, route_key, timestamp_utc_ms, opportunity_json, input_hash, config_hash, kernel_version)
                    VALUES ('e1', 'nonexistent_ep', 'route', 1000, '{}', 'h1', 'h2', '1.0.0');
                    """
                )
                conn.commit()
        finally:
            conn.close()


def test_settings_and_fee_profiles():
    """Verify storing and retrieving settings and fee profiles with Decimal values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        try:
            # Settings
            repo.set_setting("active_symbol", "ETH/USDT")
            assert repo.get_setting("active_symbol") == "ETH/USDT"

            # Fee profile
            profile = FeeProfile(
                venue="kraken",
                maker_rate=Decimal("0.0016"),
                taker_rate=Decimal("0.0026"),
                fixed_fee=Decimal("1.50"),
                fee_currency="QUOTE",
                charged_on="quote",
                is_override=True,
            )
            repo.save_fee_profile(profile)

            fetched = repo.get_fee_profile("kraken")
            assert fetched is not None
            assert fetched.venue == "kraken"
            assert fetched.taker_rate == Decimal("0.0026")
            assert fetched.fixed_fee == Decimal("1.50")
            assert fetched.is_override is True
        finally:
            conn.close()


def test_episodes_and_events_persistence():
    """Verify episode and event creation and follow-up updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        try:
            ep = EpisodeState(
                episode_id="ep_42",
                route_key="cb->kr:BTC/USDT:1000USDT",
                created_utc_ms=1000,
                last_seen_utc_ms=1000,
                last_notified_utc_ms=1000,
                last_profit_quote=Decimal("5.25"),
                last_spread=Decimal("0.00525"),
                last_midpoint=Decimal("60000.0"),
                notification_count=1,
            )
            repo.save_episode(ep)

            inst = Instrument("BTC/USDT", "BTC", "USDT", "cb", "BTC-USDT")
            fee = FeeProfile("generic", taker_rate=Decimal("0.001"))
            asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
            bids = (BookLevel(price=Decimal("60500.00"), amount=Decimal("1.0")),)
            b_buy = BookState("cb", "BTC/USDT", (), asks, "snap", 1, None, "unknown", 1000, 1000)
            b_sell = BookState("kr", "BTC/USDT", bids, (), "snap", 1, None, "unknown", 1000, 1000)

            opp = evaluate_cross_venue_opportunity("BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst, inst)
            event = DecisionEvent(
                event_id="evt_100",
                episode_id="ep_42",
                route_key="cb->kr:BTC/USDT:1000USDT",
                timestamp_utc_ms=1000,
                opportunity=opp,
                follow_up_500ms="persisted",
                continuous_persistence_status="continuous",
            )
            repo.save_event(event)

            events = repo.list_events()
            assert len(events) == 1
            assert events[0]["event_id"] == "evt_100"
            assert events[0]["follow_up_500ms"] == "persisted"
            assert events[0]["continuous_persistence_status"] == "continuous"
        finally:
            conn.close()


def test_atomic_archive_writes_and_content_addressing():
    """Verify atomic write, SHA-256 naming, and readback of capture bundles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        arch = ArchiveManager(archive_dir=tmpdir)
        payload = {"venue": "kraken", "symbol": "BTC/USDT", "bids": [["60000", "1.5"]]}

        content_hash = arch.write_capture(payload)
        assert len(content_hash) == 64

        # Read back
        read_data = arch.read_capture(content_hash)
        assert read_data == payload

        # Verify duplicate write is idempotent
        h2 = arch.write_capture(payload)
        assert h2 == content_hash


def test_database_corruption_handling():
    """Defect repair: Database corruption must raise DatabaseCorruptionError, not silently overwrite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "corrupt.sqlite3")
        # Write corrupted header
        with open(db_path, "wb") as f:
            f.write(b"NOT A SQLITE DATABASE HEADER TRUNCATED CORRUPTION")

        with pytest.raises(DatabaseCorruptionError):
            create_connection(db_path)
