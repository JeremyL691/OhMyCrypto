"""Database schema migrations for OhMyCrypto.

Follows Section 5.2 of PROJECT_EXECUTION_GUIDE.md:
- Versioned schema migrations
- Atomic application within transactions
- Clean tracking of applied versions
"""

from __future__ import annotations

import sqlite3
import time
from typing import List, Tuple

MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_profiles (
    venue TEXT PRIMARY KEY,
    maker_rate TEXT NOT NULL,
    taker_rate TEXT NOT NULL,
    fixed_fee TEXT NOT NULL,
    fee_currency TEXT NOT NULL,
    charged_on TEXT NOT NULL,
    is_override INTEGER NOT NULL DEFAULT 0,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    route_key TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    last_seen_at_ms INTEGER NOT NULL,
    last_notified_at_ms INTEGER NOT NULL,
    last_profit TEXT NOT NULL,
    last_spread TEXT NOT NULL,
    last_midpoint TEXT NOT NULL,
    notification_count INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    route_key TEXT NOT NULL,
    timestamp_utc_ms INTEGER NOT NULL,
    opportunity_json TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    kernel_version TEXT NOT NULL,
    follow_up_500ms TEXT,
    follow_up_1s TEXT,
    follow_up_3s TEXT,
    continuous_persistence_status TEXT,
    notification_state TEXT NOT NULL DEFAULT 'unnotified',
    is_pinned INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    route_key TEXT NOT NULL,
    mode TEXT NOT NULL,
    state TEXT NOT NULL,
    decision_utc_ms INTEGER NOT NULL,
    enqueue_utc_ms INTEGER NOT NULL,
    delivery_utc_ms INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    suppression_reason TEXT,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    connector TEXT NOT NULL,
    channel TEXT NOT NULL,
    fault_class TEXT NOT NULL,
    trigger TEXT NOT NULL,
    severity TEXT NOT NULL,
    opened_at_ms INTEGER NOT NULL,
    closed_at_ms INTEGER,
    raw_evidence_json TEXT NOT NULL,
    is_recovered INTEGER NOT NULL DEFAULT 0,
    is_pinned INTEGER NOT NULL DEFAULT 0
);
"""

MIGRATIONS: List[Tuple[int, str]] = [
    (1, MIGRATION_V1),
]


def run_migrations(conn: sqlite3.Connection) -> int:
    """Run pending schema migrations on SQLite connection."""
    # Ensure migrations tracking table exists
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_ms INTEGER NOT NULL
        );
        """
    )
    conn.commit()

    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
    applied_versions = {row[0] for row in cursor.fetchall()}

    latest = max(applied_versions, default=0)

    for version, ddl in MIGRATIONS:
        if version not in applied_versions:
            conn.executescript(ddl)
            now_ms = int(time.time() * 1000)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at_ms) VALUES (?, ?);",
                (version, now_ms),
            )
            conn.commit()
            latest = version

    return latest
