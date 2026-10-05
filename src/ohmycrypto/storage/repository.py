"""Domain repositories for persistent SQLite storage.

Follows Section 5.2 and Section 6 of PROJECT_EXECUTION_GUIDE.md:
- Strict typed record retrieval
- Transaction-bound operations
- Decimal and JSON preservation
"""

from __future__ import annotations

from decimal import Decimal
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from ohmycrypto.domain.models import (
    DecisionEvent,
    DiagnosticFinding,
    FeeProfile,
    NotificationRecord,
    OpportunityResult,
    FillResult,
    DecimalJSONEncoder,
    dumps_canonical_json,
)
from ohmycrypto.domain.cooldown import EpisodeState


class StorageRepository:
    """Consolidated repository accessing SQLite tables."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        cursor = self.conn.execute("SELECT value_json FROM settings WHERE key = ?;", (key,))
        row = cursor.fetchone()
        if row is None:
            return default
        return json.loads(row["value_json"])

    def set_setting(self, key: str, value: Any) -> None:
        now_ms = int(time.time() * 1000)
        val_str = json.dumps(value, cls=DecimalJSONEncoder)
        self.conn.execute(
            """
            INSERT INTO settings (key, value_json, updated_at_ms)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at_ms=excluded.updated_at_ms;
            """,
            (key, val_str, now_ms),
        )
        self.conn.commit()

    # Fee Profiles
    def get_fee_profile(self, venue: str) -> Optional[FeeProfile]:
        cursor = self.conn.execute(
            "SELECT * FROM fee_profiles WHERE venue = ?;",
            (venue,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return FeeProfile(
            venue=row["venue"],
            maker_rate=Decimal(row["maker_rate"]),
            taker_rate=Decimal(row["taker_rate"]),
            fixed_fee=Decimal(row["fixed_fee"]),
            fee_currency=row["fee_currency"],
            charged_on=row["charged_on"],
            is_override=bool(row["is_override"]),
            as_of_utc_ms=row["updated_at_ms"],
        )

    def save_fee_profile(self, profile: FeeProfile) -> None:
        now_ms = int(time.time() * 1000)
        self.conn.execute(
            """
            INSERT INTO fee_profiles (venue, maker_rate, taker_rate, fixed_fee, fee_currency, charged_on, is_override, updated_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(venue) DO UPDATE SET
                maker_rate=excluded.maker_rate,
                taker_rate=excluded.taker_rate,
                fixed_fee=excluded.fixed_fee,
                fee_currency=excluded.fee_currency,
                charged_on=excluded.charged_on,
                is_override=excluded.is_override,
                updated_at_ms=excluded.updated_at_ms;
            """,
            (
                profile.venue,
                str(profile.maker_rate),
                str(profile.taker_rate),
                str(profile.fixed_fee),
                profile.fee_currency,
                profile.charged_on,
                1 if profile.is_override else 0,
                now_ms,
            ),
        )
        self.conn.commit()

    # Episodes
    def save_episode(self, ep: EpisodeState) -> None:
        self.conn.execute(
            """
            INSERT INTO episodes (episode_id, route_key, created_at_ms, last_seen_at_ms, last_notified_at_ms, last_profit, last_spread, last_midpoint, notification_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                last_seen_at_ms=excluded.last_seen_at_ms,
                last_notified_at_ms=excluded.last_notified_at_ms,
                last_profit=excluded.last_profit,
                last_spread=excluded.last_spread,
                last_midpoint=excluded.last_midpoint,
                notification_count=excluded.notification_count,
                is_active=excluded.is_active;
            """,
            (
                ep.episode_id,
                ep.route_key,
                ep.created_utc_ms,
                ep.last_seen_utc_ms,
                ep.last_notified_utc_ms,
                str(ep.last_profit_quote),
                str(ep.last_spread),
                str(ep.last_midpoint),
                ep.notification_count,
                1 if ep.is_active else 0,
            ),
        )
        self.conn.commit()

    def get_episode(self, episode_id: str) -> Optional[EpisodeState]:
        cursor = self.conn.execute("SELECT * FROM episodes WHERE episode_id = ?;", (episode_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return EpisodeState(
            episode_id=row["episode_id"],
            route_key=row["route_key"],
            created_utc_ms=row["created_at_ms"],
            last_seen_utc_ms=row["last_seen_at_ms"],
            last_notified_utc_ms=row["last_notified_at_ms"],
            last_profit_quote=Decimal(row["last_profit"]),
            last_spread=Decimal(row["last_spread"]),
            last_midpoint=Decimal(row["last_midpoint"]),
            notification_count=row["notification_count"],
            is_active=bool(row["is_active"]),
        )

    # Opportunity Events
    def save_event(self, event: DecisionEvent) -> None:
        opp_dict = {
            "symbol": event.opportunity.symbol,
            "buy_venue": event.opportunity.buy_venue,
            "sell_venue": event.opportunity.sell_venue,
            "budget_amount": str(event.opportunity.budget_amount),
            "budget_units": event.opportunity.budget_units,
            "buy_spent": str(event.opportunity.buy_fill.quote_spent),
            "buy_fee": str(event.opportunity.buy_fill.fee_quote),
            "acquired_base": str(event.opportunity.buy_fill.acquired_base),
            "net_quote_received": str(event.opportunity.sell_fill.quote_received),
            "sell_fee": str(event.opportunity.sell_fill.fee_quote),
            "net_profit_quote": str(event.opportunity.net_profit_quote),
            "effective_spread": str(event.opportunity.effective_spread),
            "midpoint_price": str(event.opportunity.midpoint_price),
            "is_positive": event.opportunity.is_positive,
            "is_eligible": event.opportunity.is_eligible,
            "eligibility_reasons": list(event.opportunity.eligibility_reasons),
        }

        self.conn.execute(
            """
            INSERT INTO events (event_id, episode_id, route_key, timestamp_utc_ms, opportunity_json, input_hash, config_hash, kernel_version, follow_up_500ms, follow_up_1s, follow_up_3s, continuous_persistence_status, notification_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                follow_up_500ms=excluded.follow_up_500ms,
                follow_up_1s=excluded.follow_up_1s,
                follow_up_3s=excluded.follow_up_3s,
                continuous_persistence_status=excluded.continuous_persistence_status,
                notification_state=excluded.notification_state;
            """,
            (
                event.event_id,
                event.episode_id,
                event.route_key,
                event.timestamp_utc_ms,
                json.dumps(opp_dict),
                event.opportunity.input_hash,
                event.opportunity.config_hash,
                event.opportunity.kernel_version,
                event.follow_up_500ms,
                event.follow_up_1s,
                event.follow_up_3s,
                event.continuous_persistence_status,
                event.notification_state,
            ),
        )
        self.conn.commit()

    def list_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM events ORDER BY timestamp_utc_ms DESC LIMIT ?;",
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]

    # Incidents
    def save_incident(self, inc: DiagnosticFinding) -> None:
        self.conn.execute(
            """
            INSERT INTO incidents (incident_id, connector, channel, fault_class, trigger, severity, opened_at_ms, closed_at_ms, raw_evidence_json, is_recovered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(incident_id) DO UPDATE SET
                closed_at_ms=excluded.closed_at_ms,
                is_recovered=excluded.is_recovered;
            """,
            (
                inc.finding_id,
                inc.connector,
                inc.channel,
                inc.fault_class,
                inc.trigger,
                inc.severity,
                inc.timestamp_utc_ms,
                inc.recovery_timestamp_utc_ms,
                json.dumps(inc.raw_evidence, cls=DecimalJSONEncoder),
                1 if inc.is_recovered else 0,
            ),
        )
        self.conn.commit()

    def list_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM incidents ORDER BY opened_at_ms DESC LIMIT ?;",
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]
