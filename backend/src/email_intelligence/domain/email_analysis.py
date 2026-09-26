from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared_kernel.domain import AggregateRoot, InvalidStateTransition, UserId, utcnow

from .classifications import AnalysisResult, AnalysisStatus
from .events import EmailAnalysisCompleted, EmailAnalysisFailed

_TRANSITIONS: dict[AnalysisStatus, set[AnalysisStatus]] = {
    AnalysisStatus.PENDING: {AnalysisStatus.RUNNING, AnalysisStatus.SKIPPED},
    AnalysisStatus.RUNNING: {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED,
                             AnalysisStatus.PENDING},  # PENDING = released for a retry
    AnalysisStatus.FAILED: {AnalysisStatus.RUNNING, AnalysisStatus.PENDING},  # retryable
    # A user-requested re-run of the same model/prompt version re-opens the analysis.
    AnalysisStatus.COMPLETED: {AnalysisStatus.PENDING},
    AnalysisStatus.SKIPPED: {AnalysisStatus.PENDING},
}


@dataclass(eq=False, kw_only=True)
class EmailAnalysis(AggregateRoot):
    email_id: int
    user_id: UserId
    model: str
    prompt_version: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    result: AnalysisResult | None = None
    model_version: str | None = None  # concrete model version reported by the provider
    analyzed_at: datetime | None = None
    error: str = ""
    attempts: int = 0
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def request(cls, *, email_id: int, user_id: UserId, model: str,
                prompt_version: str) -> EmailAnalysis:
        return cls(email_id=email_id, user_id=user_id, model=model, prompt_version=prompt_version)

    @property
    def is_finished(self) -> bool:
        return self.status in (AnalysisStatus.COMPLETED, AnalysisStatus.SKIPPED)

    def _transition(self, target: AnalysisStatus) -> None:
        if target not in _TRANSITIONS[self.status]:
            raise InvalidStateTransition(f"analysis cannot move from {self.status} to {target}")
        self.status = target

    def start(self) -> None:
        self._transition(AnalysisStatus.RUNNING)
        self.attempts += 1
        self.error = ""

    def complete(self, result: AnalysisResult, now: datetime | None = None,
                 model_version: str | None = None) -> None:
        self._transition(AnalysisStatus.COMPLETED)
        self.result = result
        self.model_version = model_version or self.model
        self.analyzed_at = now or utcnow()
        self.error = ""
        self.record_event(EmailAnalysisCompleted(analysis_id=self.id or 0, email_id=self.email_id,
                                                 user_id=int(self.user_id)))

    def reset_for_rerun(self) -> None:
        """Explicit re-analysis request (same version): back to PENDING, result cleared."""
        self._transition(AnalysisStatus.PENDING)
        self.result = None
        self.model_version = None
        self.analyzed_at = None
        self.error = ""
        self.attempts = 0

    def release_for_retry(self, error: str) -> None:
        """Attempt failed but will be retried: back to PENDING with the reason kept."""
        self._transition(AnalysisStatus.PENDING)
        self.error = error[:1000]

    def fail(self, error: str, now: datetime | None = None) -> None:
        self._transition(AnalysisStatus.FAILED)
        self.error = error[:1000]
        self.analyzed_at = now or utcnow()
        self.record_event(EmailAnalysisFailed(analysis_id=self.id or 0, email_id=self.email_id,
                                              user_id=int(self.user_id), error=self.error))

    def skip(self, reason: str) -> None:
        self._transition(AnalysisStatus.SKIPPED)
        self.error = reason[:1000]
        self.analyzed_at = utcnow()


@dataclass(eq=False, kw_only=True)
class AiUsageLog(AggregateRoot):
    """AI cost/usage observability record. Never contains email content."""

    user_id: UserId
    email_id: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    status: str  # SUCCESS | INVALID_OUTPUT | TIMEOUT | ERROR
    created_at: datetime = field(default_factory=utcnow)
