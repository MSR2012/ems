"""GetNeedsAttention — applies the AttentionPolicy product rule (§17)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from email_intelligence.domain.attention_policy import AttentionCandidate, AttentionPolicy
from email_intelligence.domain.classifications import Priority, Thresholds


@dataclass(frozen=True)
class AnalysisRow:
    email_id: int
    priority: str
    priority_confidence: int
    reply_urgency: int
    spam_likelihood: int
    category: str
    analyzed_at: datetime | None


@dataclass(frozen=True)
class EmailSummary:
    id: int
    sender_name: str
    sender_email: str
    subject: str
    snippet: str
    received_at: datetime
    is_read: bool


@dataclass(frozen=True)
class AttentionItem:
    email: EmailSummary
    analysis: AnalysisRow
    reasons: list[str]


@dataclass(frozen=True)
class NeedsAttention:
    description: str
    total: int
    items: list[AttentionItem]


class AttentionCandidates(Protocol):
    def current_completed(self, user_id: int, thresholds: Thresholds) -> list[AnalysisRow]:
        """Current completed analyses that may need attention (SQL pre-filter)."""
        ...


class EmailSummaries(Protocol):
    def summaries(self, user_id: int, email_ids: list[int]) -> list[EmailSummary]: ...


@dataclass
class GetNeedsAttention:
    candidates: AttentionCandidates
    emails: EmailSummaries

    def __call__(self, *, user_id: int, thresholds: Thresholds, limit: int = 10) -> NeedsAttention:
        policy = AttentionPolicy(thresholds)
        rows = {r.email_id: r for r in self.candidates.current_completed(user_id, thresholds)}
        summaries = {e.id: e for e in self.emails.summaries(user_id, list(rows))}
        cands = [AttentionCandidate(email_id=eid, priority=Priority(r.priority),
                                    reply_urgency=r.reply_urgency, spam_likelihood=r.spam_likelihood,
                                    is_read=summaries[eid].is_read,
                                    received_at=summaries[eid].received_at)
                 for eid, r in rows.items() if eid in summaries]
        chosen = policy.select(cands)
        items = []
        for c in chosen[:limit]:
            reasons = []
            if thresholds.is_high_urgency(c.reply_urgency):
                reasons.append(f"Reply urgency {c.reply_urgency}%")
            if c.priority.is_high_or_critical:
                reasons.append(f"{c.priority.value.title()} priority")
            items.append(AttentionItem(email=summaries[c.email_id], analysis=rows[c.email_id],
                                       reasons=reasons))
        return NeedsAttention(description=AttentionPolicy.DESCRIPTION, total=len(chosen), items=items)
