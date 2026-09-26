from __future__ import annotations

from typing import Protocol

from .email_analysis import AiUsageLog, EmailAnalysis


class EmailAnalysisRepository(Protocol):
    def get(self, analysis_id: int) -> EmailAnalysis | None: ...

    def find(self, email_id: int, model: str, prompt_version: str) -> EmailAnalysis | None: ...

    def current_for_email(self, email_id: int) -> EmailAnalysis | None: ...

    def save(self, analysis: EmailAnalysis) -> EmailAnalysis: ...

    def try_claim(self, analysis_id: int) -> bool:
        """Atomically move PENDING/FAILED → RUNNING (attempts + 1). False if another worker
        already claimed it — makes duplicate/re-enqueued jobs harmless."""
        ...


class AiUsageLogRepository(Protocol):
    def add(self, log: AiUsageLog) -> AiUsageLog: ...
