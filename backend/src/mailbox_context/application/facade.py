"""Published application API of the Mailbox context for other bounded contexts.

Other contexts (Gmail Integration's ACL, Email Intelligence's content provider) call these
functions; the Mailbox infrastructure configures the concrete implementations at startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from mailbox_context.domain.events import EmailImported  # published event (integration contract)

from .commands.import_email import ImportEmail, ImportEmailCommand, ImportEmailResult


@dataclass(frozen=True)
class EmailContentDTO:
    email_id: int
    user_id: int
    sender_name: str
    sender_email: str
    subject: str
    body_text: str
    received_at: datetime
    has_attachments: bool


@dataclass(frozen=True)
class EmailSummaryDTO:
    id: int
    sender_name: str
    sender_email: str
    subject: str
    snippet: str
    received_at: datetime
    is_read: bool
    external_thread_id: str


class EmailContentQuery(Protocol):
    def get_content(self, email_id: int) -> EmailContentDTO | None: ...

    def get_summaries(self, user_id: int, email_ids: list[int]) -> list[EmailSummaryDTO]: ...

    def owned_email_ids(self, user_id: int, email_ids: list[int]) -> set[int]: ...

    def email_ids_for_user(self, user_id: int) -> list[int]: ...


class SyncStatusProvider(Protocol):
    """Implemented by a mail-provider integration (e.g. Gmail) for the dashboard summary."""

    def status_for_user(self, user_id: int) -> dict | None: ...


class _Registry:
    import_email: ImportEmail | None = None
    content_query: EmailContentQuery | None = None
    sync_status_providers: list[SyncStatusProvider] = []


_registry = _Registry()


def configure(*, import_email: ImportEmail, content_query: EmailContentQuery) -> None:
    _registry.import_email = import_email
    _registry.content_query = content_query


def register_sync_status_provider(provider: SyncStatusProvider) -> None:
    if provider not in _registry.sync_status_providers:
        _registry.sync_status_providers.append(provider)


def sync_status_providers() -> list[SyncStatusProvider]:
    return list(_registry.sync_status_providers)


def import_email(cmd: ImportEmailCommand) -> ImportEmailResult:
    assert _registry.import_email is not None, "mailbox facade not configured"
    return _registry.import_email(cmd)


def content_query() -> EmailContentQuery:
    assert _registry.content_query is not None, "mailbox facade not configured"
    return _registry.content_query


__all__ = [
    "EmailImported",
    "EmailContentDTO",
    "EmailSummaryDTO",
    "ImportEmailCommand",
    "ImportEmailResult",
    "configure",
    "content_query",
    "import_email",
    "register_sync_status_provider",
    "sync_status_providers",
]
