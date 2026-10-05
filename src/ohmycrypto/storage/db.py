"""Database management, WAL configuration, and integrity verification for OhMyCrypto.

Follows Section 5.2 and R04 of PROJECT_EXECUTION_GUIDE.md:
- SQLite connection with WAL journal mode and foreign keys enabled
- Strict PRAGMA integrity_check on initialization
- DatabaseCorruptionError on integrity failures (never silently overwrites database)
- Transaction safety and atomic commits
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional


class DatabaseCorruptionError(Exception):
    """Raised when SQLite database fails PRAGMA integrity_check or is corrupted."""
    pass


def get_default_db_path() -> str:
    """Return default platform SQLite database path."""
    override = os.environ.get("OHMYCRYPTO_DB_PATH")
    if override:
        return override

    data_dir = os.environ.get("OHMYCRYPTO_DATA_DIR")
    if not data_dir:
        # Default macOS Application Support directory
        data_dir = os.path.expanduser("~/Library/Application Support/OhMyCrypto")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "ohmycrypto.sqlite3")


def create_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection."""
    if db_path is None:
        db_path = get_default_db_path()

    if db_path != ":memory:":
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(parent_dir, exist_ok=True)

    try:
        conn = sqlite3.connect(db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row

        # Enforce SQLite PRAGMAs in autocommit mode
        conn.execute("PRAGMA foreign_keys = ON;")
        if db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")

        # Verify integrity
        cursor = conn.execute("PRAGMA integrity_check;")
        row = cursor.fetchone()
        if row and row[0] != "ok":
            conn.close()
            raise DatabaseCorruptionError(f"Database at {db_path} failed integrity check: {row[0]}")

        # Switch to DEFERRED transaction mode
        conn.isolation_level = "DEFERRED"
        return conn

    except sqlite3.DatabaseError as err:
        raise DatabaseCorruptionError(f"Database file at {db_path} is corrupt: {err}") from err
