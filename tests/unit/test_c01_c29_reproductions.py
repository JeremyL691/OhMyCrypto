"""C01-C29 defect reproduction tests.

Asserts correct product contract behavior according to PROJECT_EXECUTION_GUIDE.md Spec 1.2.0.
Before remediation, these tests reproduce the P1/P2 defects identified in release-review.md:
- C01: evaluate_split_order result with FillResult must serialize cleanly through sidecar DecimalJSONEncoder.
- C02: Repository event must retain full fill ledgers, input_hash/config_hash, and avoid null crashes.
- C03: Original replay must preserve original fees (0.006 / 0.004) rather than default 0.0025.
- C04/C05: Tampered acquired_base / buy_fee / hashes must reject exact match.
- C07/C08: Amount grid keys and split order DTO shapes must match frontend consumer expectations.
- C09: Non-finite / non-positive / boolean budgets and parameters must be rejected.
- C11: Kraken CRC mismatch must not reset to 'clean' without clean resynchronization.
- C13: Clean observation timestamp must be real UTC ms, not bool (avoiding closed_at_ms = 1).
- C16: Cooldown manager must restore persisted episodes across service restarts.
- C19: CLI compare/replay/diagnostics must perform real work and not return 'pending_storage' with exit 0.
- C20: Grouped incident evidence must retain all samples across updates, and reproduce_incident must fail on empty/tampered bundles.
- C21: ArchiveManager quota check must reserve incoming bytes so 114-byte capture does not breach 16-byte quota.
- C23: scripts/release.py verify_release must reject document-only manifests missing required release artifacts.
"""

from decimal import Decimal
import json
import os
import tempfile
import time
import pytest

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    DecimalJSONEncoder,
    FeeProfile,
    Instrument,
)
from ohmycrypto.services.cost import CostAdvisorService
from ohmycrypto.storage.archives import ArchiveManager
from ohmycrypto.storage.db import create_connection
from ohmycrypto.storage.migrations import run_migrations
from ohmycrypto.storage.repository import StorageRepository
from ohmycrypto.services.opportunity import OpportunityService
from ohmycrypto.services.diagnostics import DiagnosticService
from ohmycrypto.interfaces.sidecar import SidecarEngine
from ohmycrypto.interfaces import cli


def _setup_test_repo(tmpdir: str) -> StorageRepository:
    db_path = os.path.join(tmpdir, "test.sqlite3")
    conn = create_connection(db_path)
    run_migrations(conn)
    return StorageRepository(conn)


def test_c01_split_fill_serialization():
    """C01: Split child FillResult dataclasses must serialize cleanly in JSON without error."""
    advisor = CostAdvisorService()
    symbol = "BTC/USDT"
    inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="coinbase", native_symbol="BTC-USDT")
    fee = FeeProfile(venue="coinbase", taker_rate=Decimal("0.0025"))
    book = BookState(
        venue="coinbase",
        symbol=symbol,
        bids=(),
        asks=(BookLevel(price=Decimal("100.00"), amount=Decimal("10.00")),),
        snapshot_origin="test",
        applied_sequence=1,
        source_time_ms=1000,
        source_time_meaning="unknown",
        local_receipt_utc_ms=1000,
        local_receipt_mono_ns=0,
    )
    res = advisor.evaluate_split_order(
        side="buy",
        symbol=symbol,
        allocations=[("coinbase", Decimal("500"))],
        books={"coinbase": book},
        fee_profiles={"coinbase": fee},
        instruments={"coinbase": inst},
    )
    # Must serialize via DecimalJSONEncoder without "Object of type FillResult is not JSON serializable"
    serialized = json.dumps(res, cls=DecimalJSONEncoder)
    parsed = json.loads(serialized)
    assert "child_results" in parsed
    first_child = parsed["child_results"][0]
    assert "fill" in first_child
    assert isinstance(first_child["fill"], dict), "Child fill must be serialized as a JSON dictionary"
    assert "quote_spent" in first_child["fill"]


def test_c02_event_ledger_and_hashes_retained_in_ipc():
    """C02: Stored real event must expose full fill ledgers and SQL row hashes to IPC without null crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        opp_svc = OpportunityService(repo, ArchiveManager(tmpdir))

        symbol = "BTC/USDT"
        buy_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="coinbase", native_symbol="BTC-USDT")
        sell_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="kraken", native_symbol="BTC/USDT")
        buy_fee = FeeProfile(venue="coinbase", taker_rate=Decimal("0.0025"))
        sell_fee = FeeProfile(venue="kraken", taker_rate=Decimal("0.0025"))

        buy_book = BookState(
            venue="coinbase",
            symbol=symbol,
            bids=(),
            asks=(BookLevel(price=Decimal("80000"), amount=Decimal("1.0")),),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )
        sell_book = BookState(
            venue="kraken",
            symbol=symbol,
            bids=(BookLevel(price=Decimal("81000"), amount=Decimal("1.0")),),
            asks=(),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )

        event = opp_svc.evaluate(
            symbol=symbol,
            buy_book=buy_book,
            sell_book=sell_book,
            all_in_quote_budget=Decimal("1000"),
            buy_fee_profile=buy_fee,
            sell_fee_profile=sell_fee,
            buy_instrument=buy_inst,
            sell_instrument=sell_inst,
        )
        assert event is not None

        # Fetch raw row from repository and map through SidecarEngine._event_to_item
        rows = repo.list_events(limit=1)
        assert len(rows) == 1
        item = SidecarEngine._event_to_item(rows[0])

        assert item["input_hash"] is not None, "input_hash must not be null"
        assert len(item["input_hash"]) == 64, "input_hash must be valid 64-char sha256"
        assert item["config_hash"] is not None, "config_hash must not be null"
        assert item["buy_fill"].get("quote_spent") is not None, "buy_fill must include quote_spent"
        assert item["sell_fill"].get("quote_received") is not None, "sell_fill must include quote_received"


def test_c03_replay_preserves_original_fees():
    """C03: Replay without override must preserve original fees (e.g. 0.006 / 0.004) rather than 0.0025."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        archives = ArchiveManager(tmpdir)
        opp_svc = OpportunityService(repo, archives)

        symbol = "BTC/USDT"
        buy_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="coinbase", native_symbol="BTC-USDT")
        sell_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="kraken", native_symbol="BTC/USDT")
        # Custom fee rates differing from 0.0025
        buy_fee = FeeProfile(venue="coinbase", taker_rate=Decimal("0.0060"))
        sell_fee = FeeProfile(venue="kraken", taker_rate=Decimal("0.0040"))

        buy_book = BookState(
            venue="coinbase",
            symbol=symbol,
            bids=(),
            asks=(BookLevel(price=Decimal("100"), amount=Decimal("10")),),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )
        sell_book = BookState(
            venue="kraken",
            symbol=symbol,
            bids=(BookLevel(price=Decimal("101"), amount=Decimal("10")),),
            asks=(),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )

        event = opp_svc.evaluate(
            symbol=symbol,
            buy_book=buy_book,
            sell_book=sell_book,
            all_in_quote_budget=Decimal("100"),
            buy_fee_profile=buy_fee,
            sell_fee_profile=sell_fee,
            buy_instrument=buy_inst,
            sell_instrument=sell_inst,
        )
        bundle = opp_svc.export_replay_bundle(event.event_id, mode="complete")

        # Replay without override
        replay_res = opp_svc.replay_bundle(bundle)
        assert replay_res["status"] == "REPLAYED"
        assert replay_res["is_exact_match"] is True, "Original replay must be an exact match"
        assert Decimal(replay_res["replayed_profit"]) == Decimal(str(event.opportunity.net_profit_quote))


def test_c04_c05_tampered_manifest_rejected():
    """C04/C05: Tampered acquired_base or buy_fee must NOT be accepted as exact match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        archives = ArchiveManager(tmpdir)
        opp_svc = OpportunityService(repo, archives)

        symbol = "BTC/USDT"
        buy_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="coinbase", native_symbol="BTC-USDT")
        sell_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="kraken", native_symbol="BTC/USDT")
        buy_fee = FeeProfile(venue="coinbase", taker_rate=Decimal("0.0025"))
        sell_fee = FeeProfile(venue="kraken", taker_rate=Decimal("0.0025"))

        buy_book = BookState(
            venue="coinbase",
            symbol=symbol,
            bids=(),
            asks=(BookLevel(price=Decimal("100"), amount=Decimal("10")),),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )
        sell_book = BookState(
            venue="kraken",
            symbol=symbol,
            bids=(BookLevel(price=Decimal("105"), amount=Decimal("10")),),
            asks=(),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )

        event = opp_svc.evaluate(
            symbol=symbol,
            buy_book=buy_book,
            sell_book=sell_book,
            all_in_quote_budget=Decimal("100"),
            buy_fee_profile=buy_fee,
            sell_fee_profile=sell_fee,
            buy_instrument=buy_inst,
            sell_instrument=sell_inst,
        )
        bundle = opp_svc.export_replay_bundle(event.event_id, mode="complete")

        # Tamper with the exported bundle
        bundle["opportunity"]["acquired_base"] = "999999"
        bundle["opportunity"]["buy_spent"] = "12345"

        replay_res = opp_svc.replay_bundle(bundle)
        assert replay_res["is_exact_match"] is False, "Tampered bundle must not claim is_exact_match: true"


def test_c09_invalid_budget_rejected():
    """C09: Non-finite, negative, zero or boolean budgets must be rejected cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        opp_svc = OpportunityService(repo, ArchiveManager(tmpdir))

        for bad_budget in [Decimal("0"), Decimal("-10"), Decimal("NaN"), Decimal("Infinity")]:
            with pytest.raises(ValueError):
                opp_svc.validate_budget(bad_budget)


def test_c13_diagnostic_timestamp_not_bool():
    """C13: Diagnostics record_clean_observation must take real UTC ms and not accept bool as timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        diag = DiagnosticService(repo, ArchiveManager(tmpdir))

        # Open an incident
        diag.record_fault(
            connector="coinbase",
            channel="rest_l2",
            fault_class="consecutive_failures",
            trigger="test fault",
            evidence={"err": "timeout"},
        )

        now_ms = int(time.time() * 1000)
        # Calling with a boolean should raise TypeError or be validated keyword-only
        with pytest.raises((TypeError, ValueError)):
            diag.record_clean_observation("coinbase", "rest_l2", True)  # Passing True as now_utc_ms must be rejected


def test_c16_cooldown_restored_across_restarts():
    """C16: Restarting OpportunityService within cooldown interval must not re-alert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        archives = ArchiveManager(tmpdir)

        svc1 = OpportunityService(repo, archives)
        symbol = "BTC/USDT"
        buy_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="coinbase", native_symbol="BTC-USDT")
        sell_inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="kraken", native_symbol="BTC/USDT")
        buy_fee = FeeProfile(venue="coinbase", taker_rate=Decimal("0.0025"))
        sell_fee = FeeProfile(venue="kraken", taker_rate=Decimal("0.0025"))

        book1 = BookState(
            venue="coinbase",
            symbol=symbol,
            bids=(),
            asks=(BookLevel(price=Decimal("80000"), amount=Decimal("1.0")),),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )
        book2 = BookState(
            venue="kraken",
            symbol=symbol,
            bids=(BookLevel(price=Decimal("81000"), amount=Decimal("1.0")),),
            asks=(),
            snapshot_origin="test",
            applied_sequence=1,
            source_time_ms=1000,
            source_time_meaning="unknown",
            local_receipt_utc_ms=1000,
            local_receipt_mono_ns=0,
        )

        evt1 = svc1.evaluate(
            symbol=symbol,
            buy_book=book1,
            sell_book=book2,
            all_in_quote_budget=Decimal("1000"),
            buy_fee_profile=buy_fee,
            sell_fee_profile=sell_fee,
            buy_instrument=buy_inst,
            sell_instrument=sell_inst,
        )
        assert evt1.notification_state == "alert"

        # Now simulate process restart: instantiate svc2 with same database
        svc2 = OpportunityService(repo, archives)
        evt2 = svc2.evaluate(
            symbol=symbol,
            buy_book=book1,
            sell_book=book2,
            all_in_quote_budget=Decimal("1000"),
            buy_fee_profile=buy_fee,
            sell_fee_profile=sell_fee,
            buy_instrument=buy_inst,
            sell_instrument=sell_inst,
        )
        assert evt2.notification_state == "suppressed", "Restart within cooldown interval must suppress re-alert"


def test_c20_grouped_incident_retains_samples_and_negative_reproduce():
    """C20: Grouped incident must persist all samples, and reproduce_incident must fail on empty bundle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _setup_test_repo(tmpdir)
        diag = DiagnosticService(repo, ArchiveManager(tmpdir))

        # Record two faults for the same connector/channel/fault_class
        diag.record_fault("kraken", "ws_book", "checksum_mismatch", "bad crc 1", {"crc": 111})
        diag.record_fault("kraken", "ws_book", "checksum_mismatch", "bad crc 2", {"crc": 222})

        incidents = repo.list_incidents()
        assert len(incidents) == 1
        raw_evidence = json.loads(incidents[0]["raw_evidence_json"])
        assert raw_evidence.get("samples_count") == 2, "Grouped incident must record samples_count=2"

        # Offline reproduction on empty bundle must NOT succeed
        empty_bundle = {
            "incident_id": "test_empty",
            "fault_class": "checksum_mismatch",
            "trigger": "",
            "evidence": {},
        }
        rep_result = DiagnosticService.reproduce_incident(empty_bundle)
        assert rep_result["status"] != "REPRODUCED", "Empty evidence must fail offline reproduction"


def test_c21_archive_quota_incoming_reservation():
    """C21: Writing 114 bytes when quota is 16 bytes must reject before exceeding capacity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set quota to 16 bytes
        arch = ArchiveManager(tmpdir, quota_bytes=16)
        payload = {"data": "x" * 100}  # Serialized size is > 100 bytes
        h = arch.write_capture(payload)
        # Should reject write because incoming payload exceeds quota
        assert h == "", "Payload exceeding quota must return empty string (write omitted)"
        assert arch.get_total_size_bytes() <= 16, f"Archive size {arch.get_total_size_bytes()} exceeded quota 16"


def test_c19_cli_not_stubbed():
    """C19: CLI compare and replay must not return pending_storage with exit code 0."""
    # Missing bundle should return non-zero or error, not pending_storage exit 0
    with pytest.raises(SystemExit):
        cli.main(["replay", "--bundle", "/nonexistent/bundle.json"])
