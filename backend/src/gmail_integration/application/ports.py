"""Ports for external services used by Gmail Integration use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .dto import GmailIdentity, GmailMessagePage, HistoryPage, ImportableMessage, TokenGrant


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


class GmailError(Exception):
    """Base error raised by GmailGateway implementations."""


class GmailAuthError(GmailError):
    """Credentials revoked/invalid (invalid_grant, 401 after refresh)."""


class GmailRateLimitError(GmailError):
    def __init__(self, message: str = "Gmail API rate limit exceeded",
                 retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GmailUnavailableError(GmailError):
    """Transient outage (5xx / network)."""


class HistoryExpiredError(GmailError):
    """Stored history id is too old (Gmail returns 404)."""


class GmailTokenExpired(GmailError):
    """Access token rejected (401) — caller should refresh and retry once."""


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str
    state: str


@dataclass
class AccessContext:
    """Credentials handed to the gateway; gateway may refresh tokens and report back."""

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime | None
    google_account_id: str


class GmailGateway(Protocol):
    """Anti-corruption layer boundary: only implementations know Gmail API shapes."""

    def authorization_url(self, state: str) -> str: ...

    def exchange_code(self, code: str) -> TokenGrant: ...

    def fetch_identity(self, grant: TokenGrant) -> GmailIdentity: ...

    def refresh(self, ctx: AccessContext) -> TokenGrant: ...

    def revoke(self, ctx: AccessContext) -> None: ...

    def current_history_id(self, ctx: AccessContext) -> str: ...

    def list_recent_message_ids(self, ctx: AccessContext, *, days: int,
                                page_token: str | None = None) -> GmailMessagePage: ...

    def list_history(self, ctx: AccessContext, *, start_history_id: str,
                     page_token: str | None = None) -> HistoryPage: ...

    def get_message(self, ctx: AccessContext, message_id: str) -> ImportableMessage: ...


class SyncQueue(Protocol):
    """Enqueues background synchronization work (Celery in infrastructure)."""

    def enqueue_sync(self, account_id: int, sync_id: int, delay_seconds: int = 0) -> None: ...


class AccountLock(Protocol):
    """Per-account mutual exclusion so the same account is never synced concurrently."""

    def acquire(self, account_id: int) -> bool: ...

    def release(self, account_id: int) -> None: ...


class MailboxImporter(Protocol):
    """Hands provider-neutral messages to the Mailbox context (ImportEmail)."""

    def import_message(self, msg: ImportableMessage, *, user_id: int, account_id: int) -> bool: ...
