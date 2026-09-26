"""GetDashboardSummary — Mailbox read model: counts + recent emails + sync/analysis status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mailbox_context.application import facade

from .dto import InboxItem, Thresholds


@dataclass(frozen=True)
class DashboardCounts:
    total: int
    unread: int
    high_priority: int
    high_urgency: int
    potential_spam: int


@dataclass(frozen=True)
class AnalysisProgress:
    analyzed: int
    in_progress: int
    failed: int
    skipped: int


@dataclass(frozen=True)
class DashboardSummary:
    counts: DashboardCounts
    analysis: AnalysisProgress
    recent: list[InboxItem]
    sync: dict | None


class DashboardQueryService(Protocol):
    def counts(self, user_id: int, thresholds: Thresholds) -> tuple[DashboardCounts, AnalysisProgress]: ...

    def recent(self, user_id: int, thresholds: Thresholds, limit: int) -> list[InboxItem]: ...


@dataclass
class GetDashboardSummary:
    queries: DashboardQueryService

    def __call__(self, *, user_id: int, thresholds: Thresholds, recent_limit: int = 5) -> DashboardSummary:
        counts, progress = self.queries.counts(user_id, thresholds)
        sync = None
        for provider in facade.sync_status_providers():
            sync = provider.status_for_user(user_id)
            if sync:
                break
        return DashboardSummary(counts=counts, analysis=progress,
                                recent=self.queries.recent(user_id, thresholds, recent_limit), sync=sync)
