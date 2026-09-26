from __future__ import annotations

from django.conf import settings

from email_intelligence.application.use_cases import (
    AIVersion,
    AnalyzeEmail,
    ReanalyzeEmails,
    RequestAnalysis,
)
from shared_kernel.infrastructure.unit_of_work import DjangoUnitOfWork

from .adapters import CeleryAnalysisQueue, MailboxContentProvider
from .ai.config import active_model, active_prompt_version
from .persistence.queries import missing_email_ids
from .persistence.repositories import DjangoAiUsageLogRepository, DjangoEmailAnalysisRepository


def classifier():
    if settings.AI_PROVIDER == "jev_ai":
        from .ai.jev_ai import JevAIClassifier

        return JevAIClassifier()
    from .ai.fake import FakeClassifier

    return FakeClassifier()


def version() -> AIVersion:
    return AIVersion(model=active_model(), prompt_version=active_prompt_version())


def request_analysis() -> RequestAnalysis:
    return RequestAnalysis(DjangoEmailAnalysisRepository(), MailboxContentProvider(),
                           CeleryAnalysisQueue(), DjangoUnitOfWork, version())


def analyze_email() -> AnalyzeEmail:
    return AnalyzeEmail(DjangoEmailAnalysisRepository(), DjangoAiUsageLogRepository(),
                        MailboxContentProvider(), classifier(), DjangoUnitOfWork,
                        max_input_chars=settings.AI_MAX_INPUT_CHARS)


def reanalyze_emails() -> ReanalyzeEmails:
    from mailbox_context.application import facade

    return ReanalyzeEmails(request_analysis(), missing_email_ids,
                           lambda user_id: facade.content_query().email_ids_for_user(user_id))


def needs_attention():
    from email_intelligence.application.needs_attention import GetNeedsAttention

    from .adapters import MailboxEmailSummaries, SqlAttentionCandidates

    return GetNeedsAttention(SqlAttentionCandidates(), MailboxEmailSummaries())
