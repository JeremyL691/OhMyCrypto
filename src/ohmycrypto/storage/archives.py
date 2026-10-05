"""Content-addressed raw capture archives and quota management for OhMyCrypto.

Follows Section 5.2 and R04 of PROJECT_EXECUTION_GUIDE.md:
- Content-addressed storage: filename is sha256 of payload
- Atomic file write via temporary rename
- 2 GiB rolling raw capture quota management
- Safe pruning of unpinned captures without data corruption
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from ohmycrypto.domain.models import DecimalJSONEncoder, dumps_canonical_json


class ArchiveManager:
    """Manages raw market capture bundles and storage quotas."""

    def __init__(self, archive_dir: Optional[str] = None, quota_bytes: int = 2 * 1024 * 1024 * 1024):
        if archive_dir is None:
            data_dir = os.environ.get("OHMYCRYPTO_DATA_DIR")
            if not data_dir:
                data_dir = os.path.expanduser("~/Library/Application Support/OhMyCrypto")
            archive_dir = os.path.join(data_dir, "archives")
        self.archive_dir = os.path.abspath(archive_dir)
        self.quota_bytes = quota_bytes
        os.makedirs(self.archive_dir, exist_ok=True)

    def write_capture(self, payload: Any, is_pinned: bool = False) -> str:
        """Atomically store raw payload content-addressed by its SHA-256 hash. Returns hash."""
        canon_str = dumps_canonical_json(payload)
        canon_bytes = canon_str.encode("utf-8")
        content_hash = hashlib.sha256(canon_bytes).hexdigest()

        # Two-level shard directory
        shard_dir = os.path.join(self.archive_dir, content_hash[:2])
        os.makedirs(shard_dir, exist_ok=True)

        target_file = os.path.join(shard_dir, f"{content_hash}.json")
        if os.path.exists(target_file):
            return content_hash

        tmp_file = f"{target_file}.tmp.{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(canon_str)

        # Atomic replace
        os.replace(tmp_file, target_file)
        return content_hash

    def read_capture(self, content_hash: str) -> Optional[Any]:
        """Read and parse raw capture by content hash."""
        shard_dir = os.path.join(self.archive_dir, content_hash[:2])
        target_file = os.path.join(shard_dir, f"{content_hash}.json")
        if not os.path.exists(target_file):
            return None
        with open(target_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_total_size_bytes(self) -> int:
        """Calculate total archive size."""
        total = 0
        for root, _, files in os.walk(self.archive_dir):
            for fname in files:
                if fname.endswith(".json"):
                    total += os.path.getsize(os.path.join(root, fname))
        return total

    def prune_old_captures(self, max_age_seconds: float = 48 * 3600) -> int:
        """Prune unpinned files older than max_age_seconds when approaching quota."""
        pruned_count = 0
        now = time.time()
        for root, _, files in os.walk(self.archive_dir):
            for fname in files:
                if fname.endswith(".json") and not fname.startswith("pinned_"):
                    fpath = os.path.join(root, fname)
                    mtime = os.path.getmtime(fpath)
                    if (now - mtime) > max_age_seconds:
                        try:
                            os.remove(fpath)
                            pruned_count += 1
                        except OSError:
                            pass
        return pruned_count
