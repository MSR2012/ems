"""Gmail Integration use cases (application layer — framework free)."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from gmail_integration.domain.email_sync import EmailSync, SyncStatus, SyncType
from gmail_integration.domain.gmail_account import GmailAccount, GmailAccountStatus
from gmail_integration.domain.repositories import EmailSyncRepository, GmailAccountRepository
from gmail_integration.domain.value_objects import HistoryId, OAuthCredentials
from shared_kernel.application.ports import UnitOfWork
from shared_kernel.domain import DomainError, InvalidStateTransition, NotFoundError, UserId, utcnow

from .dto import GmailAccountView, SyncView, TokenGrant
from .ports import (
    AccessContext,
    AccountLock,
    GmailAuthError,
    GmailGateway,
    GmailRateLimitError,
    GmailTokenExpired,
    GmailUnavailableError,
    HistoryExpiredError,
    MailboxImporter,
    SyncQueue,
)

logger = logging.getLogger(__name__)
UowFactory = Callable[[], UnitOfWork]


class SyncNotAllowed(DomainError):
    pass


class SyncAlreadyRunning(DomainError):
    pass


class RetryableSyncError(Exception):
    """The sync failed for a transient reason (rate limit / outage); retry with backoff."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


# --- views -----------------------------------------------------------------------------
def sync_view(s: EmailSync) -> SyncView:
    return SyncView(id=s.id or 0, type=str(s.type), status=str(s.status),
                    fetched_count=s.fetched_count, imported_count=s.imported_count,
                    failed_count=s.failed_count, started_at=s.started_at,
                    completed_at=s.completed_at, error=s.error, created_at=s.created_at)


def account_view(a: GmailAccount, latest: EmailSync | None) -> GmailAccountView:
    return GmailAccountView(id=a.id or 0, email=a.email, status=str(a.status),
                            last_synced_at=a.last_synced_at, next_sync_at=a.next_sync_at,
                            last_error=a.last_error, created_at=a.created_at,
                            latest_sync=sync_view(latest) if latest else None)


# --- connection --------------------------------------------------------------------------
@dataclass
class StartGmailConnection:
    gateway: GmailGateway

    def __call__(self) -> tuple[str, str]:
        """Returns (authorization_url, state). The caller binds `state` to the user session."""
        state = secrets.token_urlsafe(32)
        return self.gateway.authorization_url(state), state


def _credentials(grant: TokenGrant, previous: OAuthCredentials | None = None) -> OAuthCredentials:
    return OAuthCredentials(
        access_token=grant.access_token,
        refresh_token=grant.refresh_token or (previous.refresh_token if previous else ""),
        expires_at=grant.expires_at,
        scopes=grant.scopes or (previous.scopes if previous else ()),
    )


@dataclass
class CompleteGmailConnection:
    gateway: GmailGateway
    accounts: GmailAccountRepository
    uow: UowFactory

    def __call__(self, *, user_id: int, code: str) -> GmailAccount:
        grant = self.gateway.exchange_code(code)
        identity = self.gateway.fetch_identity(grant)
        with self.uow() as uow:
            account = self.accounts.find_by_google_id(user_id, identity.google_account_id)
            if account is None:
                account = GmailAccount.connect(user_id=UserId(user_id),
                                               google_account_id=identity.google_account_id,
                                               email=identity.email,
                                               credentials=_credentials(grant))
                self.accounts.save(account)
                account.mark_connected()
            else:
                account.reconnect(email=identity.email,
                                  credentials=_credentials(grant, account.credentials))
                self.accounts.save(account)
            uow.register(account)
        return account


@dataclass
class DisconnectGmailAccount:
    gateway: GmailGateway
    accounts: GmailAccountRepository
    uow: UowFactory

    def __call__(self, *, user_id: int, account_id: int) -> None:
        account = self.accounts.get_for_user(account_id, user_id)
        if account is None:
            raise NotFoundError("gmail account not found")
        if account.credentials is not None:
            try:  # best-effort revocation at Google; local deletion happens regardless
                self.gateway.revoke(_ctx(account))
            except Exception:  # noqa: BLE001
                logger.warning("gmail token revocation failed", extra={"account_id": account_id})
        with self.uow() as uow:
            account.disconnect()
            self.accounts.save(account)
            uow.register(account)


# --- queries -----------------------------------------------------------------------------
@dataclass
class GetGmailConnection:
    accounts: GmailAccountRepository
    syncs: EmailSyncRepository

    def __call__(self, *, user_id: int) -> list[GmailAccountView]:
        return [account_view(a, self.syncs.latest_for_account(a.id or 0))
                for a in self.accounts.list_for_user(user_id)]


@dataclass
class ListSyncs:
    accounts: GmailAccountRepository
    syncs: EmailSyncRepository

    def __call__(self, *, user_id: int, account_id: int, limit: int = 50) -> list[SyncView]:
        if self.accounts.get_for_user(account_id, user_id) is None:
            raise NotFoundError("gmail account not found")
        return [sync_view(s) for s in self.syncs.list_for_account(account_id, limit)]


# --- synchronization ---------------------------------------------------------------------
@dataclass
class RequestSync:
    """Create a PENDING EmailSync (visible immediately in the UI) and enqueue it."""

    accounts: GmailAccountRepository
    syncs: EmailSyncRepository
    queue: SyncQueue
    uow: UowFactory

    def __call__(self, *, account_id: int, user_id: int | None = None,
                 enqueue: bool = True, delay_seconds: int = 0) -> EmailSync:
        account = (self.accounts.get_for_user(account_id, user_id) if user_id is not None
                   else self.accounts.get(account_id))
        if account is None:
            raise NotFoundError("gmail account not found")
        if not account.can_sync:
            raise SyncNotAllowed(f"account is {account.status.value.lower()}; reconnect Gmail to sync")
        if self.syncs.has_active(account_id):
            raise SyncAlreadyRunning("a synchronization is already in progress")
        sync_type = SyncType.INITIAL if account.history_id is None else SyncType.INCREMENTAL
        with self.uow() as uow:
            sync = EmailSync.request(account_id, sync_type)
            self.syncs.save(sync)
            uow.register(sync)
        if enqueue:
            self.queue.enqueue_sync(account_id, sync.id or 0, delay_seconds)
        return sync


@dataclass
class DispatchDueSyncs:
    accounts: GmailAccountRepository
    request_sync: RequestSync

    def __call__(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        count = 0
        for account in self.accounts.list_due(now):
            try:
                self.request_sync(account_id=account.id or 0)
                count += 1
            except (SyncAlreadyRunning, SyncNotAllowed):
                continue
        return count


def _ctx(account: GmailAccount) -> AccessContext:
    assert account.credentials is not None
    c = account.credentials
    return AccessContext(access_token=c.access_token, refresh_token=c.refresh_token,
                         expires_at=c.expires_at, google_account_id=account.google_account_id)


@dataclass
class SyncGmailAccount:
    """Run one synchronization: bounded initial window or incremental via history."""

    gateway: GmailGateway
    accounts: GmailAccountRepository
    syncs: EmailSyncRepository
    importer: MailboxImporter
    lock: AccountLock
    uow: UowFactory
    initial_days: int = 30
    interval: timedelta = timedelta(minutes=5)

    def __call__(self, *, account_id: int, sync_id: int) -> EmailSync:
        sync = self.syncs.get(sync_id)
        if sync is None or sync.gmail_account_id != account_id:
            raise NotFoundError("sync not found")
        if sync.is_finished:
            return sync  # idempotent: a redelivered task for a finished sync is a no-op
        if not self.lock.acquire(account_id):
            raise RetryableSyncError("another sync of this account is running", retry_after=15)
        try:
            return self._run(account_id, sync)
        finally:
            self.lock.release(account_id)

    # ------------------------------------------------------------------------------------
    def _save(self, *aggregates) -> None:
        with self.uow() as uow:
            for agg in aggregates:
                if isinstance(agg, GmailAccount):
                    self.accounts.save(agg)
                else:
                    self.syncs.save(agg)
                uow.register(agg)

    def _run(self, account_id: int, sync: EmailSync) -> EmailSync:
        account = self.accounts.get(account_id)
        if account is None or not account.can_sync:
            if sync.status == SyncStatus.PENDING:
                sync.fail("account is not connected")
                self._save(sync)
            return sync
        if sync.status == SyncStatus.RUNNING:
            # Redelivered after a worker crash: close the stale run, then continue fresh.
            sync.fail("worker interrupted; restarted")
            self._save(sync)
            sync = EmailSync.request(account_id, sync.type)
            self._save(sync)

        sync.start()
        self._save(sync)
        try:
            account = self._ensure_fresh_token(account)
            new_history = self._import(account, sync)
        except GmailAuthError as exc:
            account.revoke(f"Gmail authorization was revoked: {exc}")
            sync.fail("Gmail authorization was revoked or expired — reconnect Gmail")
            self._save(account, sync)
            return sync
        except GmailRateLimitError as exc:
            sync.fail("Gmail API rate limit exceeded (HTTP 429); will retry with backoff")
            self._save(sync)
            raise RetryableSyncError(str(exc), retry_after=exc.retry_after) from exc
        except GmailUnavailableError as exc:
            sync.fail(f"Gmail API unavailable: {exc}; will retry with backoff")
            self._save(sync)
            raise RetryableSyncError(str(exc)) from exc
        except Exception as exc:  # unexpected: record and surface
            logger.exception("gmail sync failed", extra={"account_id": account_id})
            sync.fail(f"Unexpected error: {exc.__class__.__name__}")
            account.mark_error(f"last sync failed: {exc.__class__.__name__}")
            self._save(account, sync)
            return sync

        sync.complete()
        account.record_sync_success(history_id=HistoryId(new_history) if new_history else None,
                                    now=utcnow(), interval=self.interval)
        self._save(account, sync)
        return sync

    def _ensure_fresh_token(self, account: GmailAccount) -> GmailAccount:
        assert account.credentials is not None
        if account.credentials.is_expired(utcnow()):
            self._refresh(account)
        return account

    def _refresh(self, account: GmailAccount) -> None:
        grant = self.gateway.refresh(_ctx(account))  # GmailAuthError → revoked
        account.update_credentials(_credentials(grant, account.credentials))
        self._save(account)

    def _call(self, account: GmailAccount, fn, *args, **kwargs):
        """Call the gateway; on a rejected access token refresh once and retry."""
        try:
            return fn(_ctx(account), *args, **kwargs)
        except GmailTokenExpired:
            self._refresh(account)
            try:
                return fn(_ctx(account), *args, **kwargs)
            except GmailTokenExpired as exc:
                raise GmailAuthError("access token rejected after refresh") from exc

    def _import(self, account: GmailAccount, sync: EmailSync) -> str | None:
        # Capture the cursor *before* listing so messages arriving mid-sync are not missed.
        start_history = self._call(account, self.gateway.current_history_id)
        if sync.type == SyncType.INCREMENTAL and account.history_id is not None:
            try:
                ids, latest = self._incremental_ids(account)
                self._import_ids(account, sync, ids)
                return latest or start_history
            except HistoryExpiredError:
                logger.info("history id expired; bounded full re-sync",
                            extra={"account_id": account.id})
                account.reset_history()
        ids = self._recent_ids(account)
        self._import_ids(account, sync, ids)
        return start_history

    def _recent_ids(self, account: GmailAccount) -> list[str]:
        ids: list[str] = []
        token = None
        while True:
            page = self._call(account, self.gateway.list_recent_message_ids,
                              days=self.initial_days, page_token=token)
            ids.extend(page.message_ids)
            token = page.next_page_token
            if not token:
                return ids

    def _incremental_ids(self, account: GmailAccount) -> tuple[list[str], str | None]:
        ids: list[str] = []
        token, latest = None, None
        while True:
            page = self._call(account, self.gateway.list_history,
                              start_history_id=str(account.history_id), page_token=token)
            ids.extend(i for i in page.added_message_ids if i not in ids)
            latest = page.history_id or latest
            token = page.next_page_token
            if not token:
                return ids, latest

    def _import_ids(self, account: GmailAccount, sync: EmailSync, ids: list[str]) -> None:
        for mid in ids:
            sync.record_fetched()
            try:
                msg = self._call(account, self.gateway.get_message, mid)
                created = self.importer.import_message(msg, user_id=int(account.user_id),
                                                       account_id=account.id or 0)
            except (GmailAuthError, GmailRateLimitError, GmailUnavailableError, GmailTokenExpired):
                raise
            except Exception:  # one bad message must not fail the whole sync
                logger.warning("message import failed", extra={"account_id": account.id})
                sync.record_failure()
                continue
            if created:
                sync.record_imported()
        self._save(sync)


__all__ = [
    "CompleteGmailConnection",
    "DisconnectGmailAccount",
    "DispatchDueSyncs",
    "GetGmailConnection",
    "InvalidStateTransition",
    "ListSyncs",
    "RequestSync",
    "RetryableSyncError",
    "StartGmailConnection",
    "SyncAlreadyRunning",
    "SyncGmailAccount",
    "SyncNotAllowed",
    "GmailAccountStatus",
]
