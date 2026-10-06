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
            if is_pinned:
                self.pin_capture(content_hash)
            return content_hash

        # Safe quota check: if non-pinned and quota is exceeded, prune
        if not is_pinned and self.get_total_size_bytes() >= self.quota_bytes:
            self.prune_old_captures()
            if self.get_total_size_bytes() >= self.quota_bytes:
                # Quota full; safely omit unpinned archive capture
                return ""

        tmp_file = f"{target_file}.tmp.{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(canon_str)

        # Atomic replace
        os.replace(tmp_file, target_file)
        if is_pinned:
            self.pin_capture(content_hash)
        return content_hash

    def pin_capture(self, content_hash: str) -> bool:
        """Mark a capture as pinned so it is exempt from automated quota pruning."""
        shard_dir = os.path.join(self.archive_dir, content_hash[:2])
        target_file = os.path.join(shard_dir, f"{content_hash}.json")
        if not os.path.exists(target_file):
            return False
        marker = os.path.join(shard_dir, f"{content_hash}.pinned")
        with open(marker, "w", encoding="utf-8") as f:
            f.write("1")
        return True

    def unpin_capture(self, content_hash: str) -> None:
        """Remove pinned status from a capture."""
        shard_dir = os.path.join(self.archive_dir, content_hash[:2])
        marker = os.path.join(shard_dir, f"{content_hash}.pinned")
        if os.path.exists(marker):
            try:
                os.remove(marker)
            except OSError:
                pass

    def is_capture_pinned(self, content_hash: str) -> bool:
        """Check whether a capture is pinned."""
        shard_dir = os.path.join(self.archive_dir, content_hash[:2])
        marker = os.path.join(shard_dir, f"{content_hash}.pinned")
        return os.path.exists(marker)

    def read_capture(self, content_hash: str) -> Optional[Any]:
        """Read and parse raw capture by content hash."""
        if not content_hash:
            return None
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

    def get_quota_status(self) -> Dict[str, Any]:
        """Return total size, pinned size, quota bytes, and whether quota is full."""
        total = 0
        pinned = 0
        for root, _, files in os.walk(self.archive_dir):
            for fname in files:
                if fname.endswith(".json"):
                    sz = os.path.getsize(os.path.join(root, fname))
                    total += sz
                    h = fname[:-5]
                    if self.is_capture_pinned(h):
                        pinned += sz
        return {
            "total_bytes": total,
            "pinned_bytes": pinned,
            "quota_bytes": self.quota_bytes,
            "is_full": total >= self.quota_bytes,
            "usage_percent": (total / self.quota_bytes * 100.0) if self.quota_bytes > 0 else 100.0,
        }

    def prune_old_captures(self, max_age_seconds: float = 48 * 3600) -> int:
        """Prune unpinned files older than max_age_seconds when approaching quota."""
        pruned_count = 0
        now = time.time()
        for root, _, files in os.walk(self.archive_dir):
            for fname in files:
                if fname.endswith(".json"):
                    h = fname[:-5]
                    if self.is_capture_pinned(h):
                        continue
                    fpath = os.path.join(root, fname)
                    mtime = os.path.getmtime(fpath)
                    if (now - mtime) > max_age_seconds:
                        try:
                            os.remove(fpath)
                            pruned_count += 1
                        except OSError:
                            pass
        return pruned_count
