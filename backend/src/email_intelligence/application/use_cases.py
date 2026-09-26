"""Email Intelligence use cases: RequestAnalysis, AnalyzeEmail, ReanalyzeEmails."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from email_intelligence.domain.classifications import AnalysisStatus
from email_intelligence.domain.email_analysis import AiUsageLog, EmailAnalysis
from email_intelligence.domain.repositories import AiUsageLogRepository, EmailAnalysisRepository
from shared_kernel.application.ports import UnitOfWork
from shared_kernel.domain import NotFoundError, UserId

from .content import prepare
from .ports import (
    AIClassifier,
    AIConfigurationError,
    AIError,
    AIInvalidOutput,
    AITimeout,
    AnalysisQueue,
    ClassificationRequest,
    EmailContentProvider,
)

logger = logging.getLogger(__name__)
UowFactory = Callable[[], UnitOfWork]


class RetryableAnalysisError(Exception):
    pass


@dataclass(frozen=True)
class AIVersion:
    model: str
    prompt_version: str


@dataclass
class RequestAnalysis:
    """Idempotently create the PENDING analysis for the active model/prompt and enqueue it.
    `force` re-runs an already finished analysis of the same version."""

    analyses: EmailAnalysisRepository
    content: EmailContentProvider
    queue: AnalysisQueue
    uow: UowFactory
    version: AIVersion

    def __call__(self, *, email_id: int, user_id: int | None = None,
                 force: bool = False) -> EmailAnalysis:
        return self.request(email_id=email_id, user_id=user_id, force=force)[0]

    def request(self, *, email_id: int, user_id: int | None = None, force: bool = False,
                requeue_pending: bool = False) -> tuple[EmailAnalysis, bool]:
        """Returns (analysis, queued) — queued is False when nothing needed doing."""
        c = self.content.get_content(email_id)
        if c is None or (user_id is not None and c.user_id != user_id):
            raise NotFoundError("email not found")
        with self.uow() as uow:
            a = self.analyses.find(email_id, self.version.model, self.version.prompt_version)
            if a is None:
                a = EmailAnalysis.request(email_id=email_id, user_id=UserId(c.user_id),
                                          model=self.version.model,
                                          prompt_version=self.version.prompt_version)
            elif a.status == AnalysisStatus.RUNNING:
                return a, False  # in progress
            elif a.status == AnalysisStatus.PENDING:
                if not requeue_pending:
                    return a, False  # already queued
                # Bulk runs re-enqueue pending rows (their job may have been lost); the atomic
                # claim in AnalyzeEmail makes a duplicate job a no-op.
                self.queue.enqueue_analysis(a.id or 0)
                return a, True
            elif a.status in (AnalysisStatus.COMPLETED, AnalysisStatus.SKIPPED) and not force:
                return a, False
            else:
                a.reset_for_rerun()
            if not (c.subject.strip() or c.body_text.strip()):
                a.skip("Not eligible for analysis: empty subject and body")
                self.analyses.save(a)
                uow.register(a)
                return a, False
            self.analyses.save(a)
            uow.register(a)
        self.queue.enqueue_analysis(a.id or 0)
        return a, True


@dataclass
class AnalyzeEmail:
    """§9 pipeline: fetch content → prepare → classify (untrusted data) → validated result →
    persist with model & prompt version → usage log. Retry/fail per policy."""

    analyses: EmailAnalysisRepository
    usage: AiUsageLogRepository
    content: EmailContentProvider
    classifier: AIClassifier
    uow: UowFactory
    max_input_chars: int = 12000

    def __call__(self, *, analysis_id: int, final_attempt: bool) -> EmailAnalysis | None:
        a = self.analyses.get(analysis_id)
        if a is None:
            return None
        if a.status in (AnalysisStatus.COMPLETED, AnalysisStatus.SKIPPED):
            return a  # idempotent redelivery
        c = self.content.get_content(a.email_id)
        if c is None:
            return a
        if not (c.subject.strip() or c.body_text.strip()):
            if a.status == AnalysisStatus.RUNNING:
                a.release_for_retry("")
            a.skip("Not eligible for analysis: empty subject and body")
            self._save(a)
            return a

        if a.status == AnalysisStatus.RUNNING:
            return a  # another worker is on it (stuck rows are reset by requeue_stale_analyses)
        if not self.analyses.try_claim(a.id or 0):
            return self.analyses.get(a.id or 0)  # lost the race to a duplicate job
        a = self.analyses.get(a.id or 0)
        assert a is not None

        subject, body, truncated = prepare(c.subject, c.body_text, self.max_input_chars)
        request = ClassificationRequest(sender=c.sender_email, subject=subject, body=body,
                                        truncated=truncated, prompt_version=a.prompt_version)
        started = time.monotonic()
        try:
            outcome = self.classifier.classify(request)
        except AIError as exc:
            status = ("INVALID_OUTPUT" if isinstance(exc, AIInvalidOutput)
                      else "TIMEOUT" if isinstance(exc, AITimeout)
                      else "CONFIG_ERROR" if isinstance(exc, AIConfigurationError) else "ERROR")
            self._log_usage(a, status, started, exc.input_tokens, exc.output_tokens)
            message = f"{type(exc).__name__}: {exc}"
            logger.warning("ai analysis attempt failed",
                           extra={"analysis_id": a.id, "email_id": a.email_id, "status": status})
            if final_attempt or isinstance(exc, AIConfigurationError):
                a.fail(message)
                self._save(a)
                return a
            a.release_for_retry(message)
            self._save(a)
            raise RetryableAnalysisError(message) from exc

        a.complete(outcome.result, model_version=outcome.model_version)
        self._save(a)
        self._log_usage(a, "SUCCESS", started, outcome.input_tokens, outcome.output_tokens,
                        model=outcome.model_version)
        return a

    def _save(self, a: EmailAnalysis) -> None:
        with self.uow() as uow:
            self.analyses.save(a)
            uow.register(a)

    def _log_usage(self, a: EmailAnalysis, status: str, started: float, tin: int, tout: int,
                   model: str | None = None) -> None:
        self.usage.add(AiUsageLog(
            user_id=a.user_id, email_id=a.email_id, provider=self.classifier.provider,
            model=model or self.classifier.model, input_tokens=max(tin, 0), output_tokens=max(tout, 0),
            duration_ms=int((time.monotonic() - started) * 1000), status=status))


@dataclass
class ReanalyzeEmails:
    """Bulk analysis with the active provider/model/prompt version (the "Analyze" button and the
    `reanalyze_emails` command). Queues every email of the user that has no analysis for the
    active version or whose analysis failed; `force` also re-runs finished analyses.
    Without a user it covers all users' previously analyzed emails (post version change)."""

    request: RequestAnalysis
    missing_email_ids: Callable[[str, str, int | None], list[int]]
    user_email_ids: Callable[[int], list[int]]

    def __call__(self, *, user_id: int | None = None, force: bool = False) -> int:
        v = self.request.version
        if user_id is not None:
            ids = self.user_email_ids(user_id)
        else:
            ids = self.missing_email_ids(v.model, v.prompt_version, None)
        count = 0
        for email_id in ids:
            try:
                _, queued = self.request.request(email_id=email_id, force=force,
                                                 requeue_pending=True)
            except NotFoundError:
                continue
            count += int(queued)
        return count
