"""Composition root for Gmail Integration (selects fake vs Google gateway by settings)."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings

from gmail_integration.application import use_cases as uc
from shared_kernel.infrastructure.encryption import FernetTokenCipher
from shared_kernel.infrastructure.unit_of_work import DjangoUnitOfWork

from .adapters import CelerySyncQueue, FacadeMailboxImporter, RedisAccountLock
from .persistence.repositories import DjangoEmailSyncRepository, DjangoGmailAccountRepository


def gateway():
    if settings.GMAIL_GATEWAY == "google":
        from .gmail.google_gateway import GoogleGmailGateway

        return GoogleGmailGateway()
    from .gmail.fake_gateway import FakeGmailGateway

    return FakeGmailGateway()


def accounts() -> DjangoGmailAccountRepository:
    return DjangoGmailAccountRepository(FernetTokenCipher())


def syncs() -> DjangoEmailSyncRepository:
    return DjangoEmailSyncRepository()


def start_connection() -> uc.StartGmailConnection:
    return uc.StartGmailConnection(gateway())


def complete_connection() -> uc.CompleteGmailConnection:
    return uc.CompleteGmailConnection(gateway(), accounts(), DjangoUnitOfWork)


def disconnect() -> uc.DisconnectGmailAccount:
    return uc.DisconnectGmailAccount(gateway(), accounts(), DjangoUnitOfWork)


def get_connection() -> uc.GetGmailConnection:
    return uc.GetGmailConnection(accounts(), syncs())


def list_syncs() -> uc.ListSyncs:
    return uc.ListSyncs(accounts(), syncs())


def request_sync() -> uc.RequestSync:
    return uc.RequestSync(accounts(), syncs(), CelerySyncQueue(), DjangoUnitOfWork)


def dispatch_due_syncs() -> uc.DispatchDueSyncs:
    return uc.DispatchDueSyncs(accounts(), request_sync())


def sync_account() -> uc.SyncGmailAccount:
    return uc.SyncGmailAccount(
        gateway=gateway(), accounts=accounts(), syncs=syncs(), importer=FacadeMailboxImporter(),
        lock=RedisAccountLock(), uow=DjangoUnitOfWork,
        initial_days=settings.GMAIL_INITIAL_SYNC_DAYS,
        interval=timedelta(seconds=settings.GMAIL_SYNC_INTERVAL_SECONDS),
    )
