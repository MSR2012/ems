from __future__ import annotations

from datetime import datetime

from gmail_integration.application.ports import TokenCipher
from gmail_integration.domain.email_sync import EmailSync, SyncStatus, SyncType
from gmail_integration.domain.gmail_account import GmailAccount, GmailAccountStatus
from gmail_integration.domain.value_objects import HistoryId, OAuthCredentials
from shared_kernel.domain import UserId

from .models import EmailSyncModel, GmailAccountModel


class DjangoGmailAccountRepository:
    def __init__(self, cipher: TokenCipher) -> None:
        self._cipher = cipher

    # mapping -----------------------------------------------------------------
    def _to_domain(self, m: GmailAccountModel) -> GmailAccount:
        creds = None
        if m.encrypted_access_token:
            creds = OAuthCredentials(
                access_token=self._cipher.decrypt(m.encrypted_access_token),
                refresh_token=self._cipher.decrypt(m.encrypted_refresh_token)
                if m.encrypted_refresh_token else "",
                expires_at=m.token_expires_at,
                scopes=tuple(m.scopes or ()),
            )
        return GmailAccount(
            id=m.pk, user_id=UserId(m.user_id), google_account_id=m.google_account_id,
            email=m.email, credentials=creds, status=GmailAccountStatus(m.status),
            history_id=HistoryId(m.history_id) if m.history_id else None,
            last_synced_at=m.last_synced_at, next_sync_at=m.next_sync_at,
            last_error=m.last_error, created_at=m.created_at,
        )

    def _apply(self, a: GmailAccount, m: GmailAccountModel) -> None:
        m.user_id = int(a.user_id)
        m.google_account_id = a.google_account_id
        m.email = a.email
        if a.credentials is None:
            m.encrypted_access_token = ""
            m.encrypted_refresh_token = ""
            m.token_expires_at = None
            m.scopes = []
        else:
            m.encrypted_access_token = self._cipher.encrypt(a.credentials.access_token)
            m.encrypted_refresh_token = (self._cipher.encrypt(a.credentials.refresh_token)
                                         if a.credentials.refresh_token else "")
            m.token_expires_at = a.credentials.expires_at
            m.scopes = list(a.credentials.scopes)
        m.history_id = str(a.history_id) if a.history_id else ""
        m.status = str(a.status)
        m.last_error = a.last_error
        m.last_synced_at = a.last_synced_at
        m.next_sync_at = a.next_sync_at

    # queries -----------------------------------------------------------------
    def get(self, account_id: int) -> GmailAccount | None:
        m = GmailAccountModel.objects.filter(pk=account_id).first()
        return self._to_domain(m) if m else None

    def get_for_update(self, account_id: int) -> GmailAccount | None:
        m = GmailAccountModel.objects.select_for_update().filter(pk=account_id).first()
        return self._to_domain(m) if m else None

    def get_for_user(self, account_id: int, user_id: int) -> GmailAccount | None:
        m = GmailAccountModel.objects.filter(pk=account_id, user_id=user_id).first()
        return self._to_domain(m) if m else None

    def find_by_google_id(self, user_id: int, google_account_id: str) -> GmailAccount | None:
        m = GmailAccountModel.objects.filter(user_id=user_id,
                                             google_account_id=google_account_id).first()
        return self._to_domain(m) if m else None

    def list_for_user(self, user_id: int) -> list[GmailAccount]:
        return [self._to_domain(m) for m in
                GmailAccountModel.objects.filter(user_id=user_id).order_by("id")]

    def list_due(self, now: datetime) -> list[GmailAccount]:
        qs = GmailAccountModel.objects.filter(status__in=["ACTIVE", "ERROR"],
                                              next_sync_at__lte=now).exclude(
            encrypted_access_token="")
        return [self._to_domain(m) for m in qs]

    def save(self, account: GmailAccount) -> GmailAccount:
        m = (GmailAccountModel.objects.filter(pk=account.id).first()
             if account.id else None) or GmailAccountModel()
        self._apply(account, m)
        m.save()
        account.id = m.pk
        account.created_at = m.created_at
        return account


def _sync_to_domain(m: EmailSyncModel) -> EmailSync:
    return EmailSync(
        id=m.pk, gmail_account_id=m.gmail_account_id, type=SyncType(m.type),
        status=SyncStatus(m.status), fetched_count=m.fetched_count,
        imported_count=m.imported_count, failed_count=m.failed_count, started_at=m.started_at,
        completed_at=m.completed_at, error=m.error, created_at=m.created_at,
    )


class DjangoEmailSyncRepository:
    def get(self, sync_id: int) -> EmailSync | None:
        m = EmailSyncModel.objects.filter(pk=sync_id).first()
        return _sync_to_domain(m) if m else None

    def list_for_account(self, account_id: int, limit: int = 20) -> list[EmailSync]:
        return [_sync_to_domain(m) for m in
                EmailSyncModel.objects.filter(gmail_account_id=account_id)[:limit]]

    def latest_for_account(self, account_id: int) -> EmailSync | None:
        m = EmailSyncModel.objects.filter(gmail_account_id=account_id).first()
        return _sync_to_domain(m) if m else None

    def has_active(self, account_id: int) -> bool:
        return EmailSyncModel.objects.filter(gmail_account_id=account_id,
                                             status__in=["PENDING", "RUNNING"]).exists()

    def save(self, sync: EmailSync) -> EmailSync:
        fields = dict(
            gmail_account_id=sync.gmail_account_id, type=str(sync.type), status=str(sync.status),
            fetched_count=sync.fetched_count, imported_count=sync.imported_count,
            failed_count=sync.failed_count, started_at=sync.started_at,
            completed_at=sync.completed_at, error=sync.error,
        )
        if sync.id:
            EmailSyncModel.objects.filter(pk=sync.id).update(**fields)
        else:
            m = EmailSyncModel.objects.create(**fields)
            sync.id = m.pk
            sync.created_at = m.created_at
            # events recorded before the id existed get the id patched in
            sync._events = [  # noqa: SLF001
                type(e)(**{**e.__dict__, "sync_id": m.pk}) if hasattr(e, "sync_id") else e
                for e in sync._events  # noqa: SLF001
            ]
        return sync
