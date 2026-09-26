from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.domain import DomainEvent


@dataclass(frozen=True, kw_only=True)
class GmailAccountConnected(DomainEvent):
    account_id: int
    user_id: int
    reconnected: bool = False


@dataclass(frozen=True, kw_only=True)
class GmailAuthorizationRevoked(DomainEvent):
    account_id: int
    user_id: int


@dataclass(frozen=True, kw_only=True)
class GmailAccountDisconnected(DomainEvent):
    account_id: int
    user_id: int


@dataclass(frozen=True, kw_only=True)
class EmailSyncCompleted(DomainEvent):
    sync_id: int
    account_id: int
    status: str
    imported_count: int


@dataclass(frozen=True, kw_only=True)
class EmailSyncFailed(DomainEvent):
    sync_id: int
    account_id: int
    error: str
