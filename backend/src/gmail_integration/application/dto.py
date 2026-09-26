from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TokenGrant:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GmailIdentity:
    google_account_id: str
    email: str


@dataclass(frozen=True)
class GmailMessagePage:
    message_ids: list[str]
    next_page_token: str | None = None


@dataclass(frozen=True)
class HistoryPage:
    added_message_ids: list[str]
    history_id: str
    next_page_token: str | None = None


@dataclass(frozen=True)
class ImportableMessage:
    """Provider-neutral message produced by the Gmail ACL translator."""

    external_message_id: str
    external_thread_id: str
    sender_name: str
    sender_email: str
    recipients: list[dict]
    subject: str
    body_text: str
    body_html: str
    snippet: str
    received_at: datetime
    is_read: bool
    labels: list[tuple[str, str]] = field(default_factory=list)  # (external_label_id, name)
    attachments: list[dict] = field(default_factory=list)  # external_attachment_id, filename, mime_type, size
    history_id: str | None = None


@dataclass(frozen=True)
class GmailAccountView:
    id: int
    email: str
    status: str
    last_synced_at: datetime | None
    next_sync_at: datetime | None
    last_error: str
    created_at: datetime
    latest_sync: SyncView | None = None


@dataclass(frozen=True)
class SyncView:
    id: int
    type: str
    status: str
    fetched_count: int
    imported_count: int
    failed_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error: str
    created_at: datetime
