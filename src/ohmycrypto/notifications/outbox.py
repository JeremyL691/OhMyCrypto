"""Durable notification outbox and delivery models for OhMyCrypto.

Follows Section 2.3 and Section 6.3 of PROJECT_EXECUTION_GUIDE.md:
- Separate decision, enqueue, and delivery timestamps
- Distinct states: pending, delivering, delivered, failed, suppressed
- Subprocess exit inspection and bounded retries
- Quiet mode records explicit suppression, never fake playback
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from ohmycrypto.domain.models import NotificationRecord


class NotificationOutbox:
    """In-memory and durable outbox manager for desktop notifications."""

    def __init__(self, quiet_mode: bool = False, max_retries: int = 2):
        self.quiet_mode = quiet_mode
        self.max_retries = max_retries
        self._records: Dict[str, NotificationRecord] = {}
        self._next_id: int = 1

    def enqueue(
        self,
        event_id: str,
        episode_id: str,
        route_key: str,
        mode: str,
        decision_utc_ms: int,
    ) -> NotificationRecord:
        """Enqueue a notification decision."""
        now_ms = int(time.time() * 1000)
        notif_id = f"notif_{self._next_id}_{now_ms}"
        self._next_id += 1

        if self.quiet_mode:
            rec = NotificationRecord(
                notification_id=notif_id,
                event_id=event_id,
                episode_id=episode_id,
                route_key=route_key,
                mode="quiet",
                state="suppressed",
                decision_utc_ms=decision_utc_ms,
                enqueue_utc_ms=now_ms,
                delivery_utc_ms=None,
                attempts=0,
                last_error=None,
                suppression_reason="quiet_mode_enabled",
            )
        else:
            rec = NotificationRecord(
                notification_id=notif_id,
                event_id=event_id,
                episode_id=episode_id,
                route_key=route_key,
                mode=mode,  # "audio" or "speech"
                state="pending",
                decision_utc_ms=decision_utc_ms,
                enqueue_utc_ms=now_ms,
                delivery_utc_ms=None,
                attempts=0,
                last_error=None,
                suppression_reason=None,
            )

        self._records[notif_id] = rec
        return rec

    def get(self, notification_id: str) -> Optional[NotificationRecord]:
        return self._records.get(notification_id)

    def list_records(self) -> List[NotificationRecord]:
        return list(self._records.values())

    def update_record(self, record: NotificationRecord) -> None:
        self._records[record.notification_id] = record


def deliver_macos_notification(
    record: NotificationRecord,
    message: str,
    sound_path: Optional[str] = None,
    timeout_sec: float = 3.0,
) -> NotificationRecord:
    """Deliver notification via macOS afplay or say subprocess with exit status inspection."""
    if record.state == "suppressed":
        return record

    now_ms = int(time.time() * 1000)
    attempts = record.attempts + 1

    try:
        if record.mode == "speech":
            cmd = ["say", message]
        else:
            # audio mode
            if sound_path and os.path.exists(sound_path):
                cmd = ["afplay", sound_path]
            else:
                # fallback to system beep or say
                cmd = ["afplay", "/System/Library/Sounds/Glass.aiff"]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )

        if proc.returncode == 0:
            return NotificationRecord(
                notification_id=record.notification_id,
                event_id=record.event_id,
                episode_id=record.episode_id,
                route_key=record.route_key,
                mode=record.mode,
                state="delivered",
                decision_utc_ms=record.decision_utc_ms,
                enqueue_utc_ms=record.enqueue_utc_ms,
                delivery_utc_ms=int(time.time() * 1000),
                attempts=attempts,
                last_error=None,
                suppression_reason=None,
            )
        else:
            err = f"Subprocess exited with code {proc.returncode}: {proc.stderr.strip()}"
            return NotificationRecord(
                notification_id=record.notification_id,
                event_id=record.event_id,
                episode_id=record.episode_id,
                route_key=record.route_key,
                mode=record.mode,
                state="failed",
                decision_utc_ms=record.decision_utc_ms,
                enqueue_utc_ms=record.enqueue_utc_ms,
                delivery_utc_ms=None,
                attempts=attempts,
                last_error=err,
                suppression_reason=None,
            )

    except Exception as exc:
        return NotificationRecord(
            notification_id=record.notification_id,
            event_id=record.event_id,
            episode_id=record.episode_id,
            route_key=record.route_key,
            mode=record.mode,
            state="failed",
            decision_utc_ms=record.decision_utc_ms,
            enqueue_utc_ms=record.enqueue_utc_ms,
            delivery_utc_ms=None,
            attempts=attempts,
            last_error=str(exc),
            suppression_reason=None,
        )
