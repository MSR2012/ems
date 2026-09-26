from __future__ import annotations

from email_intelligence.domain.classifications import (
    AnalysisResult,
    AnalysisStatus,
    Category,
    Percentage,
    Priority,
    Sentiment,
)
from email_intelligence.domain.email_analysis import AiUsageLog, EmailAnalysis
from shared_kernel.domain import UserId

from .models import AiUsageLogModel, EmailAnalysisModel


def to_domain(m: EmailAnalysisModel) -> EmailAnalysis:
    result = None
    if m.status == "COMPLETED" and m.priority:
        result = AnalysisResult(
            priority=Priority(m.priority),
            priority_confidence=Percentage(m.priority_confidence or 0),
            spam_likelihood=Percentage(m.spam_likelihood),
            reply_urgency=Percentage(m.reply_urgency),
            category=Category(m.category),
            sentiment=Sentiment(m.sentiment) if m.sentiment else None,
        )
    return EmailAnalysis(
        id=m.pk, email_id=m.email_id, user_id=UserId(m.user_id), model=m.model,
        prompt_version=m.prompt_version, status=AnalysisStatus(m.status), result=result,
        model_version=m.model_version,
        analyzed_at=m.analyzed_at, error=m.error, attempts=m.attempts, created_at=m.created_at,
    )


class DjangoEmailAnalysisRepository:
    def get(self, analysis_id: int) -> EmailAnalysis | None:
        m = EmailAnalysisModel.objects.filter(pk=analysis_id).first()
        return to_domain(m) if m else None

    def get_for_update(self, analysis_id: int) -> EmailAnalysis | None:
        m = EmailAnalysisModel.objects.select_for_update().filter(pk=analysis_id).first()
        return to_domain(m) if m else None

    def find(self, email_id: int, model: str, prompt_version: str) -> EmailAnalysis | None:
        m = EmailAnalysisModel.objects.filter(email_id=email_id, model=model,
                                              prompt_version=prompt_version).first()
        return to_domain(m) if m else None

    def current_for_email(self, email_id: int) -> EmailAnalysis | None:
        m = (EmailAnalysisModel.objects.filter(email_id=email_id, status="COMPLETED")
             .order_by("-analyzed_at", "-id").first()
             or EmailAnalysisModel.objects.filter(email_id=email_id).order_by("-id").first())
        return to_domain(m) if m else None

    def try_claim(self, analysis_id: int) -> bool:
        from django.db.models import F

        return EmailAnalysisModel.objects.filter(
            pk=analysis_id, status__in=["PENDING", "FAILED"]
        ).update(status="RUNNING", attempts=F("attempts") + 1, error="") == 1

    def save(self, a: EmailAnalysis) -> EmailAnalysis:
        r = a.result
        fields = dict(
            email_id=a.email_id, user_id=int(a.user_id), status=str(a.status),
            priority=str(r.priority) if r else None,
            priority_confidence=r.priority_confidence.value if r else None,
            spam_likelihood=r.spam_likelihood.value if r else None,
            reply_urgency=r.reply_urgency.value if r else None,
            category=str(r.category) if r else None,
            sentiment=str(r.sentiment) if r and r.sentiment else None,
            model=a.model, model_version=a.model_version, prompt_version=a.prompt_version,
            analyzed_at=a.analyzed_at,
            error=a.error, attempts=a.attempts,
        )
        if a.id:
            EmailAnalysisModel.objects.filter(pk=a.id).update(**fields)
        else:
            m = EmailAnalysisModel.objects.create(**fields)
            a.id = m.pk
            a.created_at = m.created_at
        return a


class DjangoAiUsageLogRepository:
    def add(self, log: AiUsageLog) -> AiUsageLog:
        m = AiUsageLogModel.objects.create(
            user_id=int(log.user_id), email_id=log.email_id, provider=log.provider,
            model=log.model, input_tokens=log.input_tokens, output_tokens=log.output_tokens,
            duration_ms=log.duration_ms, status=log.status,
        )
        log.id = m.pk
        return log
