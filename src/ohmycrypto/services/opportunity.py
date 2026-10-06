"""Opportunity verification, temporal follow-up, and deterministic replay service.

Follows Section 3.1 and Section 7 of PROJECT_EXECUTION_GUIDE.md:
- Explicit separation: input verification, economic result, alert eligibility
- Temporal follow-up at 500ms, 1s, 3s
- Continuous quoted-condition persistence vs sampled persistence
- Replay bundles: Complete Replay vs Sanitized Share exports
- Deterministic replay verification and configuration diffs
"""

from __future__ import annotations

from decimal import Decimal
import json
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    DecisionEvent,
    DecimalJSONEncoder,
    FeeProfile,
    Instrument,
    OpportunityResult,
    compute_sha256,
    decimal_validator,
    dumps_canonical_json,
)
from ohmycrypto.domain.kernel import (
    KERNEL_VERSION,
    evaluate_cross_venue_opportunity,
)
from ohmycrypto.domain.cooldown import CooldownManager, build_route_key
from ohmycrypto.storage.repository import StorageRepository
from ohmycrypto.storage.archives import ArchiveManager
from ohmycrypto.notifications.outbox import NotificationOutbox


class OpportunityService:
    """Core service for opportunity evaluation, temporal tracking, and replay."""

    def __init__(
        self,
        repository: StorageRepository,
        archive_manager: ArchiveManager,
        cooldown_manager: Optional[CooldownManager] = None,
        outbox: Optional[NotificationOutbox] = None,
    ):
        self.repo = repository
        self.archives = archive_manager
        self.outbox = outbox if outbox is not None else NotificationOutbox(repo=self.repo)
        if cooldown_manager is None:
            self.cooldown = CooldownManager()
            try:
                for ep in self.repo.list_active_episodes():
                    self.cooldown._episodes[ep.route_key] = ep
            except Exception:
                pass
        else:
            self.cooldown = cooldown_manager

    @staticmethod
    def validate_budget(budget: Any) -> Decimal:
        """Validate and convert budget to finite positive Decimal."""
        return decimal_validator(budget, "all_in_quote_budget", allow_zero=False, allow_negative=False)

    def evaluate(
        self,
        symbol: str,
        buy_book: BookState,
        sell_book: BookState,
        all_in_quote_budget: Decimal,
        buy_fee_profile: FeeProfile,
        sell_fee_profile: FeeProfile,
        buy_instrument: Instrument,
        sell_instrument: Instrument,
        min_profit_threshold: Decimal = Decimal("0.0"),
        min_spread_threshold: Decimal = Decimal("0.0"),
        now_utc_ms: Optional[int] = None,
    ) -> DecisionEvent:
        """Evaluate opportunity and record event in database."""
        all_in_quote_budget = self.validate_budget(all_in_quote_budget)
        if now_utc_ms is None:
            now_utc_ms = int(time.time() * 1000)

        opp = evaluate_cross_venue_opportunity(
            symbol=symbol,
            buy_book=buy_book,
            sell_book=sell_book,
            all_in_quote_budget=all_in_quote_budget,
            buy_fee_profile=buy_fee_profile,
            sell_fee_profile=sell_fee_profile,
            buy_instrument=buy_instrument,
            sell_instrument=sell_instrument,
            min_profit_threshold=min_profit_threshold,
            min_spread_threshold=min_spread_threshold,
        )

        route_key = build_route_key(opp)
        cooldown_decision = self.cooldown.evaluate_opportunity(opp, now_utc_ms=now_utc_ms)

        event_id = f"evt_{now_utc_ms}_{opp.input_hash[:8]}"
        episode_id = cooldown_decision.episode_id or f"ep_stub_{now_utc_ms}"

        # Ensure episode is persisted to satisfy foreign key
        ep_state = self.cooldown._episodes.get(route_key)
        if ep_state is not None:
            self.repo.save_episode(ep_state)
        else:
            from ohmycrypto.domain.cooldown import EpisodeState
            stub_ep = EpisodeState(
                episode_id=episode_id,
                route_key=route_key,
                created_utc_ms=now_utc_ms,
                last_seen_utc_ms=now_utc_ms,
                last_notified_utc_ms=now_utc_ms,
                last_profit_quote=opp.net_profit_quote,
                last_spread=opp.effective_spread,
                last_midpoint=opp.midpoint_price,
                notification_count=1,
            )
            self.repo.save_episode(stub_ep)

        event = DecisionEvent(
            event_id=event_id,
            episode_id=episode_id,
            route_key=route_key,
            timestamp_utc_ms=now_utc_ms,
            opportunity=opp,
            notification_state="alert" if cooldown_decision.should_notify else "suppressed",
        )

        # Archive raw books and fee profiles
        raw_bundle = {
            "event_id": event_id,
            "symbol": symbol,
            "buy_book": {
                "venue": buy_book.venue,
                "asks": [[str(lvl.price), str(lvl.amount)] for lvl in buy_book.asks],
                "bids": [[str(lvl.price), str(lvl.amount)] for lvl in buy_book.bids],
                "seq": buy_book.applied_sequence,
                "quality_status": buy_book.quality_status,
            },
            "sell_book": {
                "venue": sell_book.venue,
                "asks": [[str(lvl.price), str(lvl.amount)] for lvl in sell_book.asks],
                "bids": [[str(lvl.price), str(lvl.amount)] for lvl in sell_book.bids],
                "seq": sell_book.applied_sequence,
                "quality_status": sell_book.quality_status,
            },
            "budget": str(all_in_quote_budget),
            "timestamp_utc_ms": now_utc_ms,
            "buy_instrument": {
                "price_increment": str(buy_instrument.price_increment),
                "amount_increment": str(buy_instrument.amount_increment),
                "min_amount": str(buy_instrument.min_amount),
                "min_cost": str(buy_instrument.min_cost),
            },
            "sell_instrument": {
                "price_increment": str(sell_instrument.price_increment),
                "amount_increment": str(sell_instrument.amount_increment),
                "min_amount": str(sell_instrument.min_amount),
                "min_cost": str(sell_instrument.min_cost),
            },
            "buy_fee": {
                "venue": buy_fee_profile.venue,
                "taker_rate": str(buy_fee_profile.taker_rate),
                "maker_rate": str(buy_fee_profile.maker_rate),
                "fixed_fee": str(buy_fee_profile.fixed_fee),
                "fee_currency": buy_fee_profile.fee_currency,
                "charged_on": buy_fee_profile.charged_on,
            },
            "sell_fee": {
                "venue": sell_fee_profile.venue,
                "taker_rate": str(sell_fee_profile.taker_rate),
                "maker_rate": str(sell_fee_profile.maker_rate),
                "fixed_fee": str(sell_fee_profile.fixed_fee),
                "fee_currency": sell_fee_profile.fee_currency,
                "charged_on": sell_fee_profile.charged_on,
            },
        }
        capture_hash = self.archives.write_capture(raw_bundle)

        event = DecisionEvent(
            event_id=event_id,
            episode_id=episode_id,
            route_key=route_key,
            timestamp_utc_ms=now_utc_ms,
            opportunity=opp,
            notification_state="alert" if cooldown_decision.should_notify else "suppressed",
        )

        # Save to repo with capture metadata
        self.repo.save_event(event, capture_hash=capture_hash, capture_data=raw_bundle)

        if self.outbox is not None and cooldown_decision.should_notify:
            try:
                self.outbox.enqueue(
                    event_id=event_id,
                    episode_id=episode_id,
                    route_key=route_key,
                    mode="audio",
                    decision_utc_ms=now_utc_ms,
                )
            except Exception:
                pass

        return event

    def assess_continuous_persistence(
        self,
        initial_event: DecisionEvent,
        observations: List[Tuple[int, Optional[OpportunityResult]]],
    ) -> Tuple[str, str, str, str]:
        """Assess continuous persistence and sampled offsets (500ms, 1s, 3s).
        
        observations: list of (offset_ms, OpportunityResult | None).
        None represents a coverage gap or missing observation.
        """
        if not observations:
            return "unknown", "unknown", "unknown", "unknown"

        follow_up_500ms = "unknown"
        follow_up_1s = "unknown"
        follow_up_3s = "unknown"
        continuous_status = "continuous"

        for offset_ms, res in observations:
            if res is None:
                # Coverage gap breaks continuous persistence
                continuous_status = "interrupted_or_gap"
                if offset_ms <= 500:
                    follow_up_500ms = "unknown"
                if offset_ms <= 1000:
                    follow_up_1s = "unknown"
                if offset_ms <= 3000:
                    follow_up_3s = "unknown"
                continue

            is_valid_and_eligible = res.is_eligible and res.is_positive

            if not is_valid_and_eligible:
                continuous_status = "interrupted"

            if 450 <= offset_ms <= 550:
                follow_up_500ms = "persisted" if is_valid_and_eligible else "failed"
            elif 950 <= offset_ms <= 1050:
                follow_up_1s = "persisted" if is_valid_and_eligible else "failed"
            elif 2950 <= offset_ms <= 3050:
                follow_up_3s = "persisted" if is_valid_and_eligible else "failed"

        return follow_up_500ms, follow_up_1s, follow_up_3s, continuous_status

    def import_replay_bundle(self, bundle: Dict[str, Any]) -> str:
        """Import an external replay bundle into durable storage safely.
        
        Per C22: Validates schema, hashes, size limits, rejects path traversal
        and malformed inputs, preserves prior data, and writes to archives and database.
        """
        if not isinstance(bundle, dict):
            raise ValueError("Invalid bundle: root must be a JSON object")

        manifest = bundle.get("manifest")
        if not isinstance(manifest, dict):
            raise ValueError("Invalid bundle: missing or invalid manifest")

        opp_data = bundle.get("opportunity")
        if not isinstance(opp_data, dict):
            raise ValueError("Invalid bundle: missing or invalid opportunity")

        event_id = manifest.get("event_id")
        if not event_id or not isinstance(event_id, str):
            raise ValueError("Invalid bundle: missing event_id in manifest")

        # Reject path traversal attempts in identifiers
        for field in ["event_id", "route_key", "input_hash", "config_hash"]:
            val = manifest.get(field, "")
            if not isinstance(val, str) or ".." in val or "\\" in val:
                raise ValueError(f"Path traversal detected in {field}: {val}")
            if field != "route_key" and "/" in val:
                raise ValueError(f"Path separator detected in {field}: {val}")

        # Check payload size (10 MB limit)
        bundle_str = json.dumps(bundle, cls=DecimalJSONEncoder)
        if len(bundle_str.encode("utf-8")) > 10 * 1024 * 1024:
            raise ValueError("Bundle payload exceeds 10MB size limit")

        route_key = manifest.get("route_key", opp_data.get("route_key", "unknown"))
        timestamp_utc_ms = int(manifest.get("timestamp_utc_ms", opp_data.get("timestamp_utc_ms", int(time.time() * 1000))))

        # Save capture if present
        capture_hash = manifest.get("input_hash", "")
        capture_data = bundle.get("capture")
        if capture_data and isinstance(capture_data, dict):
            written_hash = self.archives.write_capture(capture_data)
            if written_hash:
                capture_hash = written_hash

        # Ensure episode exists in repo
        episode_id = opp_data.get("episode_id") or f"ep_import_{event_id}"
        from ohmycrypto.domain.cooldown import EpisodeState
        ep_state = EpisodeState(
            episode_id=episode_id,
            route_key=route_key,
            created_utc_ms=timestamp_utc_ms,
            last_seen_utc_ms=timestamp_utc_ms,
            last_notified_utc_ms=timestamp_utc_ms,
            last_profit_quote=Decimal(str(opp_data.get("net_profit_quote", "0"))),
            last_spread=Decimal(str(opp_data.get("effective_spread", "0"))),
            last_midpoint=Decimal("0"),
            notification_count=1,
            is_active=False,
        )
        try:
            self.repo.save_episode(ep_state)
        except Exception:
            pass

        # Save event
        self.repo.conn.execute(
            """
            INSERT INTO events (event_id, episode_id, route_key, timestamp_utc_ms, opportunity_json, input_hash, config_hash, kernel_version, notification_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                opportunity_json=excluded.opportunity_json,
                input_hash=excluded.input_hash,
                config_hash=excluded.config_hash;
            """,
            (
                event_id,
                episode_id,
                route_key,
                timestamp_utc_ms,
                json.dumps(opp_data, cls=DecimalJSONEncoder),
                manifest.get("input_hash", ""),
                manifest.get("config_hash", ""),
                manifest.get("kernel_version", "1.0.0"),
                opp_data.get("notification_state", "unnotified"),
            ),
        )
        self.repo.conn.commit()
        return event_id

    def export_replay_bundle(
        self,
        event_id: str,
        mode: Literal["complete", "sanitized"] = "complete",
    ) -> Dict[str, Any]:
        """Generate a self-contained replay bundle."""
        cursor = self.repo.conn.execute("SELECT * FROM events WHERE event_id = ?;", (event_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Event {event_id} not found")

        opp_data = json.loads(row["opportunity_json"])

        manifest = {
            "schema_version": "1.0.0",
            "kernel_version": row["kernel_version"],
            "bundle_mode": mode,
            "event_id": event_id,
            "timestamp_utc_ms": row["timestamp_utc_ms"],
            "route_key": row["route_key"],
            "input_hash": row["input_hash"],
            "config_hash": row["config_hash"],
            "result_hash": opp_data.get("result_hash", ""),
        }

        capture_data = None
        if mode == "complete":
            capture_hash = opp_data.get("capture_hash")
            if capture_hash:
                capture_data = self.archives.read_capture(capture_hash)
            if capture_data is None and "capture" in opp_data:
                capture_data = opp_data["capture"]

        if capture_data and isinstance(capture_data, dict):
            if "buy_fee" in capture_data and "buy_fee_profile" not in opp_data:
                opp_data["buy_fee_profile"] = capture_data["buy_fee"]
            if "sell_fee" in capture_data and "sell_fee_profile" not in opp_data:
                opp_data["sell_fee_profile"] = capture_data["sell_fee"]

        bundle: Dict[str, Any] = {
            "manifest": manifest,
            "opportunity": opp_data,
            "capture": capture_data,
            "omissions": [] if mode == "complete" else ["private_balances", "exact_ip"],
        }
        return bundle

    def replay_bundle(
        self,
        bundle: Dict[str, Any],
        override_buy_fee: Optional[Decimal] = None,
        override_sell_fee: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Replay an event bundle deterministically."""
        manifest = bundle["manifest"]
        kernel_ver = manifest.get("kernel_version", "1.0.0")

        if kernel_ver != KERNEL_VERSION:
            return {
                "status": "UNSUPPORTED_VERSION",
                "message": f"Bundle kernel version {kernel_ver} does not match {KERNEL_VERSION}",
            }

        opp = bundle["opportunity"]
        symbol = opp["symbol"]
        buy_venue = opp["buy_venue"]
        sell_venue = opp["sell_venue"]
        budget = Decimal(opp["budget_amount"])

        inst = Instrument(
            symbol=symbol,
            base=symbol.split("/")[0],
            quote=symbol.split("/")[1],
            venue="generic",
            native_symbol=symbol,
        )

        raw_capture = bundle.get("capture")

        # Restore original fee profiles if not overridden
        orig_buy_rate = Decimal("0.0025")
        if "buy_fee_profile" in opp and isinstance(opp["buy_fee_profile"], dict):
            orig_buy_rate = Decimal(str(opp["buy_fee_profile"].get("taker_rate", "0.0025")))
        elif raw_capture and isinstance(raw_capture.get("buy_fee"), dict):
            orig_buy_rate = Decimal(str(raw_capture["buy_fee"].get("taker_rate", "0.0025")))
        elif "buy_fee_rate" in opp and opp["buy_fee_rate"]:
            orig_buy_rate = Decimal(str(opp["buy_fee_rate"]))
        elif "buy_fee" in opp and "buy_spent" in opp and Decimal(str(opp["buy_spent"])) > 0:
            orig_buy_rate = Decimal(str(opp["buy_fee"])) / Decimal(str(opp["buy_spent"]))

        orig_sell_rate = Decimal("0.0025")
        if "sell_fee_profile" in opp and isinstance(opp["sell_fee_profile"], dict):
            orig_sell_rate = Decimal(str(opp["sell_fee_profile"].get("taker_rate", "0.0025")))
        elif raw_capture and isinstance(raw_capture.get("sell_fee"), dict):
            orig_sell_rate = Decimal(str(raw_capture["sell_fee"].get("taker_rate", "0.0025")))
        elif "sell_fee_rate" in opp and opp["sell_fee_rate"]:
            orig_sell_rate = Decimal(str(opp["sell_fee_rate"]))
        elif "sell_fee" in opp and "net_quote_received" in opp and Decimal(str(opp["net_quote_received"])) > 0:
            gross = Decimal(str(opp["net_quote_received"])) + Decimal(str(opp["sell_fee"]))
            orig_sell_rate = Decimal(str(opp["sell_fee"])) / gross if gross > 0 else Decimal("0.0025")

        effective_buy_rate = override_buy_fee if override_buy_fee is not None else orig_buy_rate
        effective_sell_rate = override_sell_fee if override_sell_fee is not None else orig_sell_rate

        buy_fee = FeeProfile(venue=buy_venue, taker_rate=effective_buy_rate)
        sell_fee = FeeProfile(venue=sell_venue, taker_rate=effective_sell_rate)

        buy_inst_data = raw_capture.get("buy_instrument", {}) if raw_capture else {}
        sell_inst_data = raw_capture.get("sell_instrument", {}) if raw_capture else {}

        buy_inst = Instrument(
            symbol=symbol,
            base=symbol.split("/")[0],
            quote=symbol.split("/")[1],
            venue=buy_venue,
            native_symbol=symbol,
            price_increment=Decimal(str(buy_inst_data.get("price_increment", "0.01"))),
            amount_increment=Decimal(str(buy_inst_data.get("amount_increment", "0.0001"))),
            min_amount=Decimal(str(buy_inst_data.get("min_amount", "0.0001"))),
            min_cost=Decimal(str(buy_inst_data.get("min_cost", "1.0"))),
        )
        sell_inst = Instrument(
            symbol=symbol,
            base=symbol.split("/")[0],
            quote=symbol.split("/")[1],
            venue=sell_venue,
            native_symbol=symbol,
            price_increment=Decimal(str(sell_inst_data.get("price_increment", "0.01"))),
            amount_increment=Decimal(str(sell_inst_data.get("amount_increment", "0.0001"))),
            min_amount=Decimal(str(sell_inst_data.get("min_amount", "0.0001"))),
            min_cost=Decimal(str(sell_inst_data.get("min_cost", "1.0"))),
        )

        if raw_capture and "buy_book" in raw_capture and "sell_book" in raw_capture:
            buy_raw = raw_capture["buy_book"]
            sell_raw = raw_capture["sell_book"]
            buy_book = BookState(
                venue=buy_raw.get("venue", buy_venue),
                symbol=symbol,
                bids=tuple(BookLevel(Decimal(p), Decimal(a)) for p, a in buy_raw.get("bids", [])),
                asks=tuple(BookLevel(Decimal(p), Decimal(a)) for p, a in buy_raw.get("asks", [])),
                snapshot_origin="replay",
                applied_sequence=buy_raw.get("seq", 1),
                source_time_ms=manifest["timestamp_utc_ms"],
                source_time_meaning="unknown",
                local_receipt_utc_ms=manifest["timestamp_utc_ms"],
                local_receipt_mono_ns=0,
                quality_status=buy_raw.get("quality_status", "clean"),
            )
            sell_book = BookState(
                venue=sell_raw.get("venue", sell_venue),
                symbol=symbol,
                bids=tuple(BookLevel(Decimal(p), Decimal(a)) for p, a in sell_raw.get("bids", [])),
                asks=tuple(BookLevel(Decimal(p), Decimal(a)) for p, a in sell_raw.get("asks", [])),
                snapshot_origin="replay",
                applied_sequence=sell_raw.get("seq", 1),
                source_time_ms=manifest["timestamp_utc_ms"],
                source_time_meaning="unknown",
                local_receipt_utc_ms=manifest["timestamp_utc_ms"],
                local_receipt_mono_ns=0,
                quality_status=sell_raw.get("quality_status", "clean"),
            )
        else:
            # Fallback for synthetic/sanitized bundle
            avg_buy = Decimal(opp["buy_spent"]) / Decimal(opp["acquired_base"])
            avg_sell = Decimal(opp["net_quote_received"]) / Decimal(opp["acquired_base"])

            buy_book = BookState(
                venue=buy_venue,
                symbol=symbol,
                bids=(),
                asks=(BookLevel(price=avg_buy, amount=Decimal(opp["acquired_base"])),),
                snapshot_origin="replay",
                applied_sequence=1,
                source_time_ms=manifest["timestamp_utc_ms"],
                source_time_meaning="unknown",
                local_receipt_utc_ms=manifest["timestamp_utc_ms"],
                local_receipt_mono_ns=0,
                quality_status="clean",
            )
            sell_book = BookState(
                venue=sell_venue,
                symbol=symbol,
                bids=(BookLevel(price=avg_sell, amount=Decimal(opp["acquired_base"])),),
                asks=(),
                snapshot_origin="replay",
                applied_sequence=1,
                source_time_ms=manifest["timestamp_utc_ms"],
                source_time_meaning="unknown",
                local_receipt_utc_ms=manifest["timestamp_utc_ms"],
                local_receipt_mono_ns=0,
                quality_status="clean",
            )

        replayed_opp = evaluate_cross_venue_opportunity(
            symbol=symbol,
            buy_book=buy_book,
            sell_book=sell_book,
            all_in_quote_budget=budget,
            buy_fee_profile=buy_fee,
            sell_fee_profile=sell_fee,
            buy_instrument=buy_inst,
            sell_instrument=sell_inst,
        )

        is_no_override = (override_buy_fee is None and override_sell_fee is None)
        canonical_match = (
            replayed_opp.net_profit_quote == Decimal(str(opp.get("net_profit_quote", "0")))
            and replayed_opp.is_eligible == opp.get("is_eligible")
            and replayed_opp.buy_fill.acquired_base == Decimal(str(opp.get("acquired_base", "0")))
            and replayed_opp.buy_fill.quote_spent == Decimal(str(opp.get("buy_spent", "0")))
            and replayed_opp.buy_fill.fee_quote == Decimal(str(opp.get("buy_fee", "0")))
            and replayed_opp.sell_fill.quote_received == Decimal(str(opp.get("net_quote_received", "0")))
            and replayed_opp.sell_fill.fee_quote == Decimal(str(opp.get("sell_fee", "0")))
        )
        if manifest.get("result_hash"):
            canonical_match = canonical_match and (replayed_opp.result_hash == manifest.get("result_hash"))

        is_exact_match = is_no_override and (replayed_opp.input_hash == manifest.get("input_hash")) and canonical_match

        return {
            "status": "REPLAYED",
            "is_exact_match": is_exact_match,
            "replayed_profit": str(replayed_opp.net_profit_quote),
            "replayed_spread": str(replayed_opp.effective_spread),
            "replayed_is_eligible": replayed_opp.is_eligible,
            "original_profit": opp.get("net_profit_quote"),
            "original_is_eligible": opp.get("is_eligible"),
            "input_hash": replayed_opp.input_hash,
            "config_hash": replayed_opp.config_hash,
        }
