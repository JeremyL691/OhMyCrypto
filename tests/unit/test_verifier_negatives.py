"""Verifier-negative tests (B01-B10).

Ensures that verifiers and acceptance gates fail-closed under missing, corrupted,
tampered, or incomplete evidence per PROJECT_EXECUTION_GUIDE.md Section 12.1.
"""

from decimal import Decimal
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ohmycrypto.services.diagnostics import DiagnosticService
from ohmycrypto.storage.archives import ArchiveManager
from scripts.release import verify_release
from scripts.verify import verify_native


def test_b03_native_gate_rejects_missing_app_bundle():
    """B03: Missing app bundle must fail native gate without ping fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        res = verify_native(Path(tmpdir), "/nonexistent/OhMyCrypto.app")
        assert res["passed"] is False, "Native gate must fail when app bundle is missing"
        assert any(c["check"] == "native_app_bundle" and not c["passed"] for c in res["checks"])


def test_b04_release_gate_rejects_document_only_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        readme = tmp_path / "README.md"
        readme.write_text("# Test Docs")

        import hashlib
        h = hashlib.sha256(readme.read_bytes()).hexdigest()

        # Fabricate document-only manifest
        doc_manifest = {
            "release_id": "test_release_doc_only",
            "version": "1.0.0",
            "artifacts": [
                {"name": "README.md", "sha256": h, "type": "documentation"}
            ],
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(doc_manifest))

        # Must exit non-zero because required DMGs and source archives are missing
        with pytest.raises(SystemExit) as exc_info:
            verify_release(manifest_path)
        assert exc_info.value.code != 0, f"Expected non-zero exit code, got {exc_info.value.code}"


def test_b05_release_gate_rejects_wrong_artifact_hash():
    """B05: Wrong artifact hash must fail release verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dmg = tmp_path / "OhMyCrypto-1.0.0-arm64.dmg"
        dmg.write_bytes(b"dummy dmg content")
        source = tmp_path / "OhMyCrypto-1.0.0-source.tar.gz"
        source.write_bytes(b"dummy source content")

        import hashlib
        real_dmg_h = hashlib.sha256(dmg.read_bytes()).hexdigest()
        real_src_h = hashlib.sha256(source.read_bytes()).hexdigest()

        # Corrupt the DMG hash in the manifest
        tampered_manifest = {
            "release_id": "test_release_tampered_hash",
            "version": "1.0.0",
            "artifacts": [
                {"name": "OhMyCrypto-1.0.0-arm64.dmg", "sha256": "0" * 64, "type": "installer_dmg"},
                {"name": "OhMyCrypto-1.0.0-source.tar.gz", "sha256": real_src_h, "type": "corresponding_source_archive"},
            ],
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(tampered_manifest))

        with pytest.raises(SystemExit) as exc_info:
            verify_release(manifest_path)
        assert exc_info.value.code != 0, "Tampered artifact hash must fail release verification"


def test_b07_resource_quota_exceeded_rejects_write():
    """B07: Payload exceeding quota must not write or pass silently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        arch = ArchiveManager(tmpdir, quota_bytes=16)
        h = arch.write_capture({"large_payload": "a" * 100})
        assert h == "", "Payload exceeding quota must return empty hash (write rejected)"
        assert arch.get_total_size_bytes() <= 16


def test_b09_empty_incident_evidence_rejected():
    """B09: Empty, tampered, or partial incident evidence must not return REPRODUCED status."""
    empty_bundle = {
        "incident_id": "inc_empty",
        "fault_class": "sequence_gap",
        "trigger": "gap detected",
        "evidence": {},
    }
    res = DiagnosticService.reproduce_incident(empty_bundle)
    assert res["status"] != "REPRODUCED", "Empty evidence must fail reproduction"
