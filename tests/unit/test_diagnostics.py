"""Unit tests for market data quality diagnostics, incident grouping, recovery, and reproduction."""

import os
import tempfile
import pytest

from ohmycrypto.services.diagnostics import DiagnosticService
from ohmycrypto.storage.db import create_connection
from ohmycrypto.storage.migrations import run_migrations
from ohmycrypto.storage.repository import StorageRepository
from ohmycrypto.storage.archives import ArchiveManager


def test_fault_detection_and_grouping():
    """Verify faults group within the 60s window under the same incident ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        arch = ArchiveManager(archive_dir=os.path.join(tmpdir, "archives"))
        service = DiagnosticService(repo, arch)

        # Fault 1 at t=1000ms
        f1 = service.record_fault(
            connector="kraken",
            channel="book_v2",
            fault_class="sequence_gap",
            trigger="seq 12 after seq 10",
            evidence={"expected": 11, "received": 12},
            now_utc_ms=1000,
        )
        assert f1.severity == "error"

        # Fault 2 at t=15000ms (14s later, within 60s window)
        f2 = service.record_fault(
            connector="kraken",
            channel="book_v2",
            fault_class="sequence_gap",
            trigger="seq 25 after seq 22",
            evidence={"expected": 23, "received": 25},
            now_utc_ms=15000,
        )
        assert f2.finding_id == f1.finding_id, "Faults within grouping window must share incident ID"
        assert f2.raw_evidence["samples_count"] == 2


def test_incident_recovery_and_closure():
    """Verify 3 consecutive clean observations close open incidents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite3")
        conn = create_connection(db_path)
        run_migrations(conn)
        repo = StorageRepository(conn)
        arch = ArchiveManager(archive_dir=os.path.join(tmpdir, "archives"))
        service = DiagnosticService(repo, arch)

        f = service.record_fault(
            connector="coinbase",
            channel="rest_l2",
            fault_class="consecutive_failures",
            trigger="3 consecutive 503 timeouts",
            evidence={"http_status": 503},
            now_utc_ms=1000,
        )
        assert f.is_recovered is False

        # Clean observation 1
        rec1 = service.record_clean_observation("coinbase", "rest_l2", now_utc_ms=2000)
        assert len(rec1) == 0

        # Clean observation 2
        rec2 = service.record_clean_observation("coinbase", "rest_l2", now_utc_ms=3000)
        assert len(rec2) == 0

        # Clean observation 3 -> closes incident
        rec3 = service.record_clean_observation("coinbase", "rest_l2", now_utc_ms=4000)
        assert len(rec3) == 1
        assert rec3[0].finding_id == f.finding_id
        assert rec3[0].is_recovered is True
        assert rec3[0].recovery_timestamp_utc_ms == 4000


def test_latency_distribution_percentiles():
    """Verify p50, p95, and p99 calculation from observed response latencies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = create_connection(os.path.join(tmpdir, "test.sqlite3"))
        run_migrations(conn)
        service = DiagnosticService(StorageRepository(conn), ArchiveManager(archive_dir=tmpdir))

        for lat in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]:
            service.record_latency("kraken", lat)

        dist = service.get_latency_distribution("kraken")
        assert dist["count"] == 10
        assert dist["p50"] == 60.0
        assert dist["p95"] == 100.0


def test_incident_bundle_export_and_offline_reproduction():
    """Verify export of self-contained incident bundle and offline reproduction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = create_connection(os.path.join(tmpdir, "test.sqlite3"))
        run_migrations(conn)
        service = DiagnosticService(StorageRepository(conn), ArchiveManager(archive_dir=tmpdir))

        finding = service.record_fault(
            connector="kraken",
            channel="book_v2",
            fault_class="checksum_mismatch",
            trigger="CRC 12345 != 67890",
            evidence={"expected": 12345, "calculated": 67890},
            now_utc_ms=1000,
        )

        bundle = service.export_incident_bundle(finding.finding_id)
        assert bundle["incident_id"] == finding.finding_id
        assert bundle["fault_class"] == "checksum_mismatch"
        assert "offline_reproduction_command" in bundle

        # Offline reproduction
        repro = DiagnosticService.reproduce_incident(bundle)
        assert repro["status"] == "REPRODUCED"
        assert repro["incident_id"] == finding.finding_id
