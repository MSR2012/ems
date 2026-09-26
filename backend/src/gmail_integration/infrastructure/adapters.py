from __future__ import annotations

import logging

import redis
from django.conf import settings

from gmail_integration.application.dto import ImportableMessage
from mailbox_context.application import facade

from .gmail.translator import to_import_command

logger = logging.getLogger(__name__)


class RedisAccountLock:
    """Per-account sync lock (SET NX with expiry) shared by all workers."""

    def __init__(self, ttl_seconds: int = 900) -> None:
        self._redis = redis.Redis.from_url(settings.REDIS_URL)
        self._ttl = ttl_seconds

    def _key(self, account_id: int) -> str:
        return f"lock:gmail-sync:{account_id}"

    def acquire(self, account_id: int) -> bool:
        return bool(self._redis.set(self._key(account_id), "1", nx=True, ex=self._ttl))

    def release(self, account_id: int) -> None:
        self._redis.delete(self._key(account_id))


class CelerySyncQueue:
    def enqueue_sync(self, account_id: int, sync_id: int, delay_seconds: int = 0) -> None:
        from django.db import transaction

        from .tasks import sync_gmail_account

        # Only after the PENDING sync row is committed, so the worker can see it.
        transaction.on_commit(lambda: sync_gmail_account.apply_async(
            kwargs={"account_id": account_id, "sync_id": sync_id},
            countdown=delay_seconds or None))


class FacadeMailboxImporter:
    def import_message(self, msg: ImportableMessage, *, user_id: int, account_id: int) -> bool:
        return facade.import_email(to_import_command(msg, user_id=user_id, account_id=account_id)).created
