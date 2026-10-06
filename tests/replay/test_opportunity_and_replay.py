"""Tests for opportunity evaluation, continuous persistence tracking, and deterministic replay."""

from decimal import Decimal
import json
import os
import tempfile
import pytest

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    FeeProfile,
    Instrument,
)
from ohmycrypto.domain.kernel import evaluate_cross_venue_opportunity
from ohmycrypto.services.opportunity import OpportunityService
from ohmycrypto.storage.db import create_connection
from ohmycrypto.storage.migrations import run_migrations
from ohmycrypto.storage.repository import StorageRepository
from ohmycrypto.storage.archives import ArchiveManager


def test_separation_of_verification_economics_and_eligibility():
    """Verify explicit distinction between input verification, economic result, and eligibility."""
    inst = Instrument("BTC/USDT", "BTC", "USDT", "coinbase", "BTC-USDT")
    fee = FeeProfile("generic", taker_rate=Decimal("0.002"))

    # Case 1: Valid inputs, but negative net result (buy 60100, sell 60000)
    asks1 = (BookLevel(price=Decimal("60100.00"), amount=Decimal("1.0")),)
    bids1 = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
    book_b1 = BookState("coinbase", "BTC/USDT", (), asks1, "snap", 1, None, "unknown", 1000, 1000)
    book_s1 = BookState("kraken", "BTC/USDT", bids1, (), "snap", 1, None, "unknown", 1000, 1000)

    res1 = evaluate_cross_venue_opportunity("BTC/USDT", book_b1, book_s1, Decimal("1000.0"), fee, fee, inst, inst)
    assert res1.is_positive is False
    assert res1.is_eligible is False
    assert "non_positive_profit" in res1.eligibility_reasons

    # Case 2: Positive profit (+3 USDT), but minimum profit threshold is 5 USDT
    asks2 = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
    bids2 = (BookLevel(price=Decimal("60500.00"), amount=Decimal("1.0")),)
    book_b2 = BookState("coinbase", "BTC/USDT", (), asks2, "snap", 2, None, "unknown", 1000, 1000)
    book_s2 = BookState("kraken", "BTC/USDT", bids2, (), "snap", 2, None, "unknown", 1000, 1000)

    res2 = evaluate_cross_venue_opportunity(
        "BTC/USDT", book_b2, book_s2, Decimal("1000.0"), fee, fee, inst, inst, min_profit_threshold=Decimal("5.0")
    )
    assert res2.is_positive is True
    assert res2.is_eligible is False
    assert any("below_threshold" in r for r in res2.eligibility_reasons)

    # Case 3: Positive profit and satisfies threshold
    res3 = evaluate_cross_venue_opportunity(
        "BTC/USDT", book_b2, book_s2, Decimal("1000.0"), fee, fee, inst, inst, min_profit_threshold=Decimal("1.0")
    )
    assert res3.is_positive is True
    assert res3.is_eligible is True


def test_temporal_persistence_and_interruption():
    """Verify that a candidate disappearing at 250ms and returning at 750ms is NOT continuous."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        arch = ArchiveManager(archive_dir=os.path.join(tmpdir, "archives"))
        service = OpportunityService(repo, arch)

        inst = Instrument("BTC/USDT", "BTC", "USDT", "coinbase", "BTC-USDT")
        fee = FeeProfile("generic", taker_rate=Decimal("0.002"))

        asks_good = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
        bids_good = (BookLevel(price=Decimal("60500.00"), amount=Decimal("1.0")),)
        b_buy_good = BookState("coinbase", "BTC/USDT", (), asks_good, "snap", 1, None, "unknown", 1000, 1000)
        b_sell_good = BookState("kraken", "BTC/USDT", bids_good, (), "snap", 1, None, "unknown", 1000, 1000)

        initial_event = service.evaluate("BTC/USDT", b_buy_good, b_sell_good, Decimal("1000.0"), fee, fee, inst, inst)

        # Observations:
        # At 250ms: candidate disappears (negative profit)
        # At 500ms: candidate returns positive
        # At 1000ms: candidate positive
        opp_good = evaluate_cross_venue_opportunity("BTC/USDT", b_buy_good, b_sell_good, Decimal("1000.0"), fee, fee, inst, inst)
        bids_bad = (BookLevel(price=Decimal("59900.00"), amount=Decimal("1.0")),)
        b_sell_bad = BookState("kraken", "BTC/USDT", bids_bad, (), "snap", 2, None, "unknown", 1000, 1000)
        opp_bad = evaluate_cross_venue_opportunity("BTC/USDT", b_buy_good, b_sell_bad, Decimal("1000.0"), fee, fee, inst, inst)

        observations = [
            (250, opp_bad),    # Disappeared at 250ms!
            (500, opp_good),   # Recovered by 500ms
            (1000, opp_good),  # Positive at 1s
        ]

        f500, f1s, f3s, continuous_status = service.assess_continuous_persistence(initial_event, observations)

        # Sampled at 500ms and 1s are persisted
        assert f500 == "persisted"
        assert f1s == "persisted"
        # But continuous persistence must be interrupted!
        assert continuous_status == "interrupted"


def test_deterministic_replay_and_hash_identity():
    """Verify two runs with identical inputs produce identical canonical hashes."""
    inst = Instrument("BTC/USDT", "BTC", "USDT", "coinbase", "BTC-USDT")
    fee = FeeProfile("generic", taker_rate=Decimal("0.0025"))
    asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
    bids = (BookLevel(price=Decimal("60400.00"), amount=Decimal("1.0")),)
    b_buy = BookState("coinbase", "BTC/USDT", (), asks, "snap", 1, None, "unknown", 1000, 1000)
    b_sell = BookState("kraken", "BTC/USDT", bids, (), "snap", 1, None, "unknown", 1000, 1000)

    run1 = evaluate_cross_venue_opportunity("BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst, inst)
    run2 = evaluate_cross_venue_opportunity("BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst, inst)

    assert run1.input_hash == run2.input_hash
    assert run1.config_hash == run2.config_hash
    assert run1.net_profit_quote == run2.net_profit_quote
    assert run1.effective_spread == run2.effective_spread


def test_export_and_replay_cycle():
    """Verify exporting a replay bundle and executing deterministic replay with fee override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        arch = ArchiveManager(archive_dir=os.path.join(tmpdir, "archives"))
        service = OpportunityService(repo, arch)

        inst = Instrument("BTC/USDT", "BTC", "USDT", "coinbase", "BTC-USDT")
        fee = FeeProfile("generic", taker_rate=Decimal("0.0025"))
        asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
        bids = (BookLevel(price=Decimal("60500.00"), amount=Decimal("1.0")),)
        b_buy = BookState("coinbase", "BTC/USDT", (), asks, "snap", 1, None, "unknown", 1000, 1000)
        b_sell = BookState("kraken", "BTC/USDT", bids, (), "snap", 1, None, "unknown", 1000, 1000)

        event = service.evaluate("BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst, inst)

        # Complete export
        complete_bundle = service.export_replay_bundle(event.event_id, mode="complete")
        assert complete_bundle["manifest"]["event_id"] == event.event_id
        assert complete_bundle["omissions"] == []

        # Replay without overrides
        replay_res = service.replay_bundle(complete_bundle)
        assert replay_res["status"] == "REPLAYED"
        assert replay_res["is_exact_match"] is True

        # F02 check: Tampered profit must NOT produce is_exact_match=True
        tampered_bundle = json.loads(json.dumps(complete_bundle))
        tampered_bundle["opportunity"]["net_profit_quote"] = "9.999999"
        tampered_res = service.replay_bundle(tampered_bundle)
        assert tampered_res["is_exact_match"] is False, "Tampered profit must fail exact match!"

        # Replay with higher fee (taker 1.0%)
        higher_fee_res = service.replay_bundle(complete_bundle, override_buy_fee=Decimal("0.0100"), override_sell_fee=Decimal("0.0100"))
        assert higher_fee_res["status"] == "REPLAYED"
        assert higher_fee_res["is_exact_match"] is False
        assert Decimal(higher_fee_res["replayed_profit"]) < Decimal(replay_res["replayed_profit"])

        # Sanitized export
        sanitized_bundle = service.export_replay_bundle(event.event_id, mode="sanitized")
        assert "private_balances" in sanitized_bundle["omissions"]


def test_import_replay_bundle_and_traversal_rejection():
    """Verify import of replay bundle into fresh store and rejection of path traversal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "orig.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        arch = ArchiveManager(archive_dir=os.path.join(tmpdir, "arch1"))
        service = OpportunityService(repo, arch)

        inst = Instrument("BTC/USDT", "BTC", "USDT", "coinbase", "BTC-USDT")
        fee = FeeProfile("generic", taker_rate=Decimal("0.0025"))
        asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
        bids = (BookLevel(price=Decimal("60500.00"), amount=Decimal("1.0")),)
        b_buy = BookState("coinbase", "BTC/USDT", (), asks, "snap", 1, None, "unknown", 1000, 1000)
        b_sell = BookState("kraken", "BTC/USDT", bids, (), "snap", 1, None, "unknown", 1000, 1000)

        event = service.evaluate("BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst, inst)
        bundle = service.export_replay_bundle(event.event_id, mode="complete")

        # Import into fresh store
        db2 = os.path.join(tmpdir, "imported.sqlite3")
        conn2 = create_connection(db2)
        run_migrations(conn2)
        repo2 = StorageRepository(conn2)
        arch2 = ArchiveManager(archive_dir=os.path.join(tmpdir, "arch2"))
        service2 = OpportunityService(repo2, arch2)

        imported_id = service2.import_replay_bundle(bundle)
        assert imported_id == event.event_id

        # Replay imported bundle in service2
        replay_res = service2.replay_bundle(bundle)
        assert replay_res["status"] == "REPLAYED"
        assert replay_res["is_exact_match"] is True

        # Test C22: Path traversal rejection
        bad_bundle = json.loads(json.dumps(bundle))
        bad_bundle["manifest"]["event_id"] = "../../../etc/passwd"
        with pytest.raises(ValueError, match="Path traversal"):
            service2.import_replay_bundle(bad_bundle)


def test_durable_outbox_integration():
    """Verify notification records are durable in SQLite and survive reload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "outbox_test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        arch = ArchiveManager(archive_dir=os.path.join(tmpdir, "arch"))

        service = OpportunityService(repo, arch)
        inst = Instrument("BTC/USDT", "BTC", "USDT", "coinbase", "BTC-USDT")
        fee = FeeProfile("generic", taker_rate=Decimal("0.0025"))
        asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
        bids = (BookLevel(price=Decimal("60500.00"), amount=Decimal("1.0")),)
        b_buy = BookState("coinbase", "BTC/USDT", (), asks, "snap", 1, None, "unknown", 1000, 1000)
        b_sell = BookState("kraken", "BTC/USDT", bids, (), "snap", 1, None, "unknown", 1000, 1000)

        event = service.evaluate("BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst, inst)
        assert event.notification_state == "alert"

        # Outbox should have recorded notification in SQLite
        records = repo.list_notifications()
        assert len(records) == 1
        assert records[0]["event_id"] == event.event_id
        assert records[0]["state"] == "pending"

        # Simulate service restart: new outbox reloads records from repo
        service_reloaded = OpportunityService(repo, arch)
        reloaded_records = service_reloaded.outbox.list_records()
        assert len(reloaded_records) == 1
        assert reloaded_records[0].event_id == event.event_id

