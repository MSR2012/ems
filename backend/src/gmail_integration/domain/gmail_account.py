from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from shared_kernel.domain import AggregateRoot, InvalidStateTransition, UserId, utcnow

from .events import GmailAccountConnected, GmailAccountDisconnected, GmailAuthorizationRevoked
from .value_objects import HistoryId, OAuthCredentials


class GmailAccountStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    ERROR = "ERROR"
    DISCONNECTED = "DISCONNECTED"


@dataclass(eq=False, kw_only=True)
class GmailAccount(AggregateRoot):
    user_id: UserId
    google_account_id: str
    email: str
    credentials: OAuthCredentials | None = field(default=None, repr=False)
    status: GmailAccountStatus = GmailAccountStatus.ACTIVE
    history_id: HistoryId | None = None
    last_synced_at: datetime | None = None
    next_sync_at: datetime | None = None
    last_error: str = ""
    created_at: datetime = field(default_factory=utcnow)

    # --- factories -------------------------------------------------------------
    @classmethod
    def connect(cls, *, user_id: UserId, google_account_id: str, email: str,
                credentials: OAuthCredentials, now: datetime | None = None) -> GmailAccount:
        now = now or utcnow()
        account = cls(user_id=user_id, google_account_id=google_account_id, email=email,
                      credentials=credentials, status=GmailAccountStatus.ACTIVE, next_sync_at=now)
        return account

    def mark_connected(self, *, reconnected: bool = False) -> None:
        """Raise the connected event once the aggregate has an id (after first save)."""
        assert self.id is not None
        self.record_event(GmailAccountConnected(account_id=self.id, user_id=int(self.user_id),
                                                reconnected=reconnected))

    # --- lifecycle -------------------------------------------------------------
    def reconnect(self, *, email: str, credentials: OAuthCredentials,
                  now: datetime | None = None) -> None:
        now = now or utcnow()
        self.email = email
        self.credentials = credentials
        self.status = GmailAccountStatus.ACTIVE
        self.last_error = ""
        self.next_sync_at = now
        if self.id is not None:
            self.mark_connected(reconnected=True)

    def revoke(self, reason: str = "authorization revoked") -> None:
        if self.status == GmailAccountStatus.DISCONNECTED:
            raise InvalidStateTransition("a disconnected account cannot be revoked")
        if self.status == GmailAccountStatus.REVOKED:
            return
        self.status = GmailAccountStatus.REVOKED
        self.last_error = reason
        self.next_sync_at = None  # stops scheduled syncs
        self.record_event(GmailAuthorizationRevoked(account_id=self.id or 0,
                                                    user_id=int(self.user_id)))

    def mark_error(self, reason: str) -> None:
        if self.status in (GmailAccountStatus.DISCONNECTED, GmailAccountStatus.REVOKED):
            return
        self.status = GmailAccountStatus.ERROR
        self.last_error = reason[:500]

    def disconnect(self) -> None:
        if self.status == GmailAccountStatus.DISCONNECTED:
            return
        self.credentials = None
        self.status = GmailAccountStatus.DISCONNECTED
        self.next_sync_at = None
        self.history_id = None
        self.record_event(GmailAccountDisconnected(account_id=self.id or 0,
                                                   user_id=int(self.user_id)))

    def update_credentials(self, credentials: OAuthCredentials) -> None:
        self.credentials = credentials

    # --- sync scheduling -------------------------------------------------------
    @property
    def can_sync(self) -> bool:
        return self.status in (GmailAccountStatus.ACTIVE, GmailAccountStatus.ERROR) \
            and self.credentials is not None

    def is_due(self, now: datetime) -> bool:
        return self.can_sync and self.next_sync_at is not None and self.next_sync_at <= now

    def record_sync_success(self, *, history_id: HistoryId | None, now: datetime,
                            interval: timedelta) -> None:
        if history_id is not None and history_id.is_newer_than(self.history_id):
            self.history_id = history_id
        self.last_synced_at = now
        self.next_sync_at = now + interval
        if self.status == GmailAccountStatus.ERROR:
            self.status = GmailAccountStatus.ACTIVE
            self.last_error = ""

    def schedule_next_sync(self, *, now: datetime, interval: timedelta) -> None:
        if self.can_sync:
            self.next_sync_at = now + interval

    def reset_history(self) -> None:
        """History cursor too old (Gmail 404) → next sync is a bounded full re-sync."""
        self.history_id = None
