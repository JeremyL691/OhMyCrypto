"""Opportunity identity, episodes, and escalation rules for OhMyCrypto.

Follows Section 2.3 and 6.3 of PROJECT_EXECUTION_GUIDE.md:
- Stable route key based on (buy_venue, sell_venue, instrument, budget, fee_profiles)
- Price movements DO NOT fragment cooldown or create new fingerprints
- Escalation requires both material absolute (>= 2 quote units) and relative (>= 15%) improvement
- Persistent episode lifecycle with disappearance interval (default: 60s)
"""

from __future__ import annotations

from decimal import Decimal
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

from ohmycrypto.domain.models import OpportunityResult, decimal_validator


def build_route_key(opportunity: OpportunityResult) -> str:
    """Build a stable route key. Price fluctuations NEVER alter this key."""
    return (
        f"{opportunity.buy_venue}->"
        f"{opportunity.sell_venue}:"
        f"{opportunity.symbol}:"
        f"{opportunity.budget_amount}"
        f"{opportunity.budget_units}"
    )


@dataclass
class EpisodeState:
    """State tracking for an active or closed opportunity episode."""
    episode_id: str
    route_key: str
    created_utc_ms: int
    last_seen_utc_ms: int
    last_notified_utc_ms: int
    last_profit_quote: Decimal
    last_spread: Decimal
    last_midpoint: Decimal
    notification_count: int
    is_active: bool = True


@dataclass(frozen=True)
class CooldownDecision:
    """Outcome of cooldown / escalation evaluation."""
    should_notify: bool
    severity: str  # "alert", "escalated", "suppressed", "ineligible"
    reason: str
    episode_id: str
    route_key: str


class CooldownManager:
    """Manages opportunity episode lifetimes and alert suppression."""

    def __init__(
        self,
        cooldown_duration_ms: int = 30_000,
        disappearance_window_ms: int = 60_000,
        escalation_relative_ratio: Decimal = Decimal("0.15"),
        escalation_min_absolute_quote: Decimal = Decimal("2.0"),
    ):
        self.cooldown_duration_ms = cooldown_duration_ms
        self.disappearance_window_ms = disappearance_window_ms
        self.escalation_relative_ratio = escalation_relative_ratio
        self.escalation_min_absolute_quote = escalation_min_absolute_quote
        self._episodes: Dict[str, EpisodeState] = {}
        self._next_episode_seq: int = 1

    def evaluate_opportunity(
        self,
        opportunity: OpportunityResult,
        now_utc_ms: Optional[int] = None,
    ) -> CooldownDecision:
        """Evaluate whether an opportunity triggers a notification."""
        if now_utc_ms is None:
            now_utc_ms = int(time.time() * 1000)

        route_key = build_route_key(opportunity)

        if not opportunity.is_eligible:
            return CooldownDecision(
                should_notify=False,
                severity="ineligible",
                reason=f"ineligible: {','.join(opportunity.eligibility_reasons)}",
                episode_id="",
                route_key=route_key,
            )

        existing = self._episodes.get(route_key)

        if existing is None or not existing.is_active or (now_utc_ms - existing.last_seen_utc_ms > self.disappearance_window_ms):
            # Create a new episode
            episode_id = f"ep_{self._next_episode_seq}_{int(now_utc_ms)}"
            self._next_episode_seq += 1
            new_episode = EpisodeState(
                episode_id=episode_id,
                route_key=route_key,
                created_utc_ms=now_utc_ms,
                last_seen_utc_ms=now_utc_ms,
                last_notified_utc_ms=now_utc_ms,
                last_profit_quote=opportunity.net_profit_quote,
                last_spread=opportunity.effective_spread,
                last_midpoint=opportunity.midpoint_price,
                notification_count=1,
                is_active=True,
            )
            self._episodes[route_key] = new_episode
            return CooldownDecision(
                should_notify=True,
                severity="alert",
                reason="new_episode",
                episode_id=episode_id,
                route_key=route_key,
            )

        # Existing active episode
        existing.last_seen_utc_ms = now_utc_ms
        time_since_last_alert = now_utc_ms - existing.last_notified_utc_ms

        # Check cooldown timeout
        if time_since_last_alert >= self.cooldown_duration_ms:
            existing.last_notified_utc_ms = now_utc_ms
            existing.last_profit_quote = opportunity.net_profit_quote
            existing.last_spread = opportunity.effective_spread
            existing.last_midpoint = opportunity.midpoint_price
            existing.notification_count += 1
            return CooldownDecision(
                should_notify=True,
                severity="alert",
                reason="cooldown_elapsed",
                episode_id=existing.episode_id,
                route_key=route_key,
            )

        # Check escalation: requires BOTH relative ratio and absolute quote improvement
        profit_delta = opportunity.net_profit_quote - existing.last_profit_quote
        baseline_profit = max(existing.last_profit_quote, Decimal("0.00000001"))
        relative_improvement = profit_delta / baseline_profit

        if (
            profit_delta >= self.escalation_min_absolute_quote
            and relative_improvement >= self.escalation_relative_ratio
        ):
            existing.last_notified_utc_ms = now_utc_ms
            existing.last_profit_quote = opportunity.net_profit_quote
            existing.last_spread = opportunity.effective_spread
            existing.last_midpoint = opportunity.midpoint_price
            existing.notification_count += 1
            return CooldownDecision(
                should_notify=True,
                severity="escalated",
                reason=f"escalated_profit_plus_{profit_delta}_quote",
                episode_id=existing.episode_id,
                route_key=route_key,
            )

        return CooldownDecision(
            should_notify=False,
            severity="suppressed",
            reason=f"cooldown_active_remaining_{self.cooldown_duration_ms - time_since_last_alert}ms",
            episode_id=existing.episode_id,
            route_key=route_key,
        )

    def close_stale_episodes(self, now_utc_ms: Optional[int] = None) -> int:
        """Mark episodes inactive if not seen within disappearance window."""
        if now_utc_ms is None:
            now_utc_ms = int(time.time() * 1000)
        closed = 0
        for ep in self._episodes.values():
            if ep.is_active and (now_utc_ms - ep.last_seen_utc_ms > self.disappearance_window_ms):
                ep.is_active = False
                closed += 1
        return closed
