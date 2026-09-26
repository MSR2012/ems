"""AttentionPolicy — an explicit, documented product rule (§17), not an objective measure.

Default ordering:
  1. exclude potential spam (spam likelihood ≥ spam threshold);
  2. include emails whose reply urgency ≥ urgency threshold OR priority is CRITICAL/HIGH;
  3. sort by reply urgency % desc, then priority desc, then unread first,
     then received_at desc.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from .classifications import Priority, Thresholds


@dataclass(frozen=True)
class AttentionCandidate:
    email_id: int
    priority: Priority
    reply_urgency: int
    spam_likelihood: int
    is_read: bool
    received_at: datetime


class AttentionPolicy:
    DESCRIPTION = (
        "AI-based suggestion: excludes potential spam; includes emails with reply urgency at "
        "or above the urgency threshold or CRITICAL/HIGH priority; ordered by reply urgency, "
        "then priority, then unread first, then newest."
    )

    def __init__(self, thresholds: Thresholds) -> None:
        self.thresholds = thresholds

    def needs_attention(self, c: AttentionCandidate) -> bool:
        if self.thresholds.is_potential_spam(c.spam_likelihood):
            return False
        return self.thresholds.is_high_urgency(c.reply_urgency) or c.priority.is_high_or_critical

    @staticmethod
    def sort_key(c: AttentionCandidate) -> tuple:
        return (-c.reply_urgency, -c.priority.rank, c.is_read, -c.received_at.timestamp())

    def select(self, candidates: Iterable[AttentionCandidate],
               limit: int | None = None) -> list[AttentionCandidate]:
        chosen = sorted((c for c in candidates if self.needs_attention(c)), key=self.sort_key)
        return chosen[:limit] if limit is not None else chosen
