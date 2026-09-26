"""Celery tasks for Email Intelligence (queue: analysis). Thin wrappers over use cases."""

from __future__ import annotations

import logging
import random
from datetime import timedelta

from celery import shared_task

from email_intelligence.application.use_cases import RetryableAnalysisError

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


def backoff_seconds(retries: int) -> int:
    base = min(2 * (2 ** retries), 120)
    return base + random.randint(0, max(1, base // 2))


@shared_task(bind=True, name="email_intelligence.analyze_email", acks_late=True,
             max_retries=MAX_RETRIES)
def analyze_email(self, analysis_id: int) -> str | None:
    from email_intelligence.infrastructure import container

    final = self.request.retries >= self.max_retries
    try:
        a = container.analyze_email()(analysis_id=analysis_id, final_attempt=final)
        return str(a.status) if a else None
    except RetryableAnalysisError as exc:
        raise self.retry(countdown=backoff_seconds(self.request.retries), exc=exc) from exc


@shared_task(name="email_intelligence.reanalyze_emails", acks_late=True)
def reanalyze_emails(user_id: int | None = None, force: bool = False) -> int:
    """Fan-out task (analysis queue): creates PENDING analyses and enqueues analyze_email jobs."""
    from email_intelligence.infrastructure import container

    n = container.reanalyze_emails()(user_id=user_id, force=force)
    logger.info("bulk analysis queued", extra={"user_id": user_id, "count": n, "force": force})
    return n


@shared_task(name="email_intelligence.requeue_stale_analyses", acks_late=True)
def requeue_stale_analyses() -> int:
    """Safety net: re-enqueue analyses stuck PENDING (lost message) or RUNNING (crashed worker)."""
    from .persistence.models import EmailAnalysisModel
    from .persistence.queries import stale_analysis_ids

    ids = stale_analysis_ids(timedelta(minutes=2), timedelta(minutes=10))
    # Stuck RUNNING rows (crashed worker) go back to PENDING so the job can claim them again.
    EmailAnalysisModel.objects.filter(pk__in=ids, status="RUNNING").update(
        status="PENDING", error="worker interrupted; requeued")
    for analysis_id in ids:
        analyze_email.delay(analysis_id=analysis_id)
    if ids:
        logger.info("requeued stale analyses", extra={"count": len(ids)})
    return len(ids)
