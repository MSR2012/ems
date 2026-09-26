"""Celery tasks for Gmail Integration. Thin: they delegate to application use cases."""

from __future__ import annotations

import logging
import random

from celery import shared_task

from gmail_integration.application.use_cases import (
    RetryableSyncError,
    SyncAlreadyRunning,
    SyncNotAllowed,
)

logger = logging.getLogger(__name__)
MAX_RETRIES = 4


def backoff_seconds(retries: int, retry_after: int | None = None) -> int:
    """Exponential backoff with jitter (5s, 10s, 20s, 40s … capped at 5 min)."""
    base = min(5 * (2 ** retries), 300)
    return max(retry_after or 0, base) + random.randint(0, max(1, base // 4))


@shared_task(bind=True, name="gmail_integration.sync_gmail_account", acks_late=True,
             max_retries=MAX_RETRIES)
def sync_gmail_account(self, account_id: int, sync_id: int) -> dict:
    from gmail_integration.infrastructure import container

    try:
        sync = container.sync_account()(account_id=account_id, sync_id=sync_id)
        return {"sync_id": sync.id, "status": str(sync.status)}
    except RetryableSyncError as exc:
        if self.request.retries >= self.max_retries:
            logger.error("gmail sync giving up after retries", extra={"account_id": account_id})
            return {"sync_id": sync_id, "status": "FAILED"}
        current = container.syncs().get(sync_id)
        next_sync_id = sync_id
        if current is not None and current.is_finished:
            # The failed attempt stays in history as FAILED; the retry gets a fresh record.
            try:
                next_sync_id = container.request_sync()(account_id=account_id, enqueue=False).id
            except (SyncAlreadyRunning, SyncNotAllowed):
                return {"sync_id": sync_id, "status": "FAILED"}
        countdown = backoff_seconds(self.request.retries, exc.retry_after)
        logger.warning("gmail sync retry scheduled",
                       extra={"account_id": account_id, "countdown": countdown,
                              "attempt": self.request.retries + 1})
        raise self.retry(kwargs={"account_id": account_id, "sync_id": next_sync_id},
                         countdown=countdown, exc=exc) from exc


@shared_task(name="gmail_integration.dispatch_due_syncs", acks_late=True)
def dispatch_due_syncs() -> int:
    from gmail_integration.infrastructure import container

    return container.dispatch_due_syncs()()
