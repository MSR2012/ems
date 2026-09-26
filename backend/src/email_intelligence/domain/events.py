from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.domain import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EmailAnalysisCompleted(DomainEvent):
    analysis_id: int
    email_id: int
    user_id: int


@dataclass(frozen=True, kw_only=True)
class EmailAnalysisFailed(DomainEvent):
    analysis_id: int
    email_id: int
    user_id: int
    error: str
