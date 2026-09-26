"""ImportEmail — the Mailbox command the Gmail ACL calls with a provider-neutral DTO."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from mailbox_context.application.ports import ContentProcessor, DuplicateEmailError
from mailbox_context.domain.email import Email, EmailAttachment, EmailLabel, Recipient
from mailbox_context.domain.repositories import EmailRepository
from mailbox_context.domain.value_objects import EmailAddress, ProviderMessageRef
from shared_kernel.application.ports import UnitOfWork
from shared_kernel.domain import InvariantViolation, UserId

FALLBACK_SENDER = "unknown@unknown.invalid"


@dataclass(frozen=True)
class ImportEmailCommand:
    user_id: int
    mail_account_id: int
    provider: str
    external_message_id: str
    external_thread_id: str
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    body_text: str = ""
    body_html: str = ""
    snippet: str = ""
    is_read: bool = False
    recipients: list[dict] = field(default_factory=list)  # {type, email, name}
    labels: list[tuple[str, str]] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ImportEmailResult:
    email_id: int
    created: bool
    updated: bool = False


def _address(email: str, name: str = "") -> EmailAddress:
    try:
        return EmailAddress(email, name)
    except InvariantViolation:
        return EmailAddress(FALLBACK_SENDER, name or email)


class ImportEmail:
    """Idempotent upsert keyed by (mail account, external message id)."""

    def __init__(self, repository: EmailRepository, uow_factory: Callable[[], UnitOfWork],
                 content: ContentProcessor) -> None:
        self._repo = repository
        self._uow_factory = uow_factory
        self._content = content

    def __call__(self, cmd: ImportEmailCommand) -> ImportEmailResult:
        labels = [EmailLabel(external_label_id=lid, name=name) for lid, name in cmd.labels]
        try:
            return self._import(cmd, labels)
        except DuplicateEmailError:
            # A concurrent import won the race; treat as an update of the existing row.
            return self._import(cmd, labels)

    def _import(self, cmd: ImportEmailCommand, labels: list[EmailLabel]) -> ImportEmailResult:
        with self._uow_factory() as uow:
            existing = self._repo.find_by_external_id(cmd.mail_account_id, cmd.external_message_id)
            if existing is not None:
                if existing.user_id != cmd.user_id:
                    raise InvariantViolation("message belongs to a different user")
                changed = existing.sync_provider_state(is_read=cmd.is_read, labels=labels)
                if changed:
                    self._repo.save(existing)
                return ImportEmailResult(email_id=existing.id or 0, created=False, updated=changed)

            content = self._content.process(html=cmd.body_html, text=cmd.body_text)
            recipients = []
            for r in cmd.recipients:
                try:
                    recipients.append(Recipient(kind=r.get("type", "to"),
                                                address=EmailAddress(r["email"], r.get("name", ""))))
                except (InvariantViolation, KeyError):
                    continue
            email = Email(
                user_id=UserId(cmd.user_id),
                ref=ProviderMessageRef(provider=cmd.provider, mail_account_id=cmd.mail_account_id,
                                       external_message_id=cmd.external_message_id,
                                       external_thread_id=cmd.external_thread_id),
                sender=_address(cmd.sender_email, cmd.sender_name),
                subject=cmd.subject,
                received_at=cmd.received_at,
                recipients=recipients,
                body_text=content.text,
                body_html_sanitized=content.sanitized_html,
                snippet=cmd.snippet,
                is_read=cmd.is_read,
                labels=labels,
                attachments=[EmailAttachment(external_attachment_id=a.get("external_attachment_id", ""),
                                             filename=a.get("filename") or "attachment",
                                             mime_type=a.get("mime_type", ""),
                                             size=max(int(a.get("size") or 0), 0))
                             for a in cmd.attachments],
            )
            self._repo.save(email)
            email.mark_imported()
            uow.register(email)
            return ImportEmailResult(email_id=email.id or 0, created=True)
