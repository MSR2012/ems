from __future__ import annotations

from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from .models import EmailAnalysisModel


def missing_email_ids(model: str, prompt_version: str, user_id: int | None) -> list[int]:
    """Emails that have been analyzed before but not with the given model/prompt version."""
    qs = EmailAnalysisModel.objects.all()
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    has_version = EmailAnalysisModel.objects.filter(email_id=OuterRef("email_id"), model=model,
                                                    prompt_version=prompt_version)
    return list(qs.annotate(v=Exists(has_version)).filter(v=False)
                .values_list("email_id", flat=True).distinct())


def stale_analysis_ids(pending_after: timedelta, running_after: timedelta) -> list[int]:
    now = timezone.now()
    return list(
        EmailAnalysisModel.objects.filter(status="PENDING", updated_at__lt=now - pending_after)
        .values_list("id", flat=True)[:500]
    ) + list(
        EmailAnalysisModel.objects.filter(status="RUNNING", updated_at__lt=now - running_after)
        .values_list("id", flat=True)[:500]
    )


def attention_candidates(user_id: int, spam_threshold: int, urgency_threshold: int) -> list[dict]:
    """Current completed analyses for the user that pass the policy's SQL pre-filter."""
    from django.db import connection

    sql = """
        SELECT email_id, priority, priority_confidence, reply_urgency, spam_likelihood, category,
               analyzed_at
        FROM current_email_analyses
        WHERE user_id = %s AND status = 'COMPLETED' AND spam_likelihood < %s
          AND (reply_urgency >= %s OR priority IN ('CRITICAL', 'HIGH'))
    """
    with connection.cursor() as cur:
        cur.execute(sql, [user_id, spam_threshold, urgency_threshold])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
