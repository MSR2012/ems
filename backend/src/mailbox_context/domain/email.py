from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared_kernel.domain import AggregateRoot, Entity, InvariantViolation, UserId, utcnow

from .events import EmailImported
from .value_objects import EmailAddress, ProviderMessageRef

MAX_SNIPPET = 200


@dataclass(eq=False, kw_only=True)
class EmailLabel(Entity):
    external_label_id: str
    name: str


@dataclass(eq=False, kw_only=True)
class EmailAttachment(Entity):
    external_attachment_id: str
    filename: str
    mime_type: str
    size: int

    def __post_init__(self) -> None:
        if self.size < 0:
            raise InvariantViolation("attachment size cannot be negative")


@dataclass(frozen=True)
class Recipient:
    kind: str  # to | cc | bcc
    address: EmailAddress


@dataclass(eq=False, kw_only=True)
class Email(AggregateRoot):
    user_id: UserId
    ref: ProviderMessageRef
    sender: EmailAddress
    subject: str
    received_at: datetime
    recipients: list[Recipient] = field(default_factory=list)
    body_text: str = ""
    body_html_sanitized: str = ""
    snippet: str = ""
    is_read: bool = False
    labels: list[EmailLabel] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.subject = (self.subject or "").strip()[:998]
        if not self.snippet:
            self.snippet = " ".join(self.body_text.split())[:MAX_SNIPPET]
        self.snippet = self.snippet[:MAX_SNIPPET]

    @property
    def is_analyzable(self) -> bool:
        """Eligible for AI analysis: there is some text content to classify."""
        return bool(self.body_text.strip() or self.subject.strip())

    def mark_imported(self) -> None:
        """Raise EmailImported once the aggregate is persisted and has an id."""
        if self.id is None:
            raise InvariantViolation("email must be persisted before it is announced")
        self.record_event(EmailImported(email_id=self.id, user_id=int(self.user_id),
                                        analyzable=self.is_analyzable))

    def sync_provider_state(self, *, is_read: bool, labels: list[EmailLabel]) -> bool:
        """Apply mutable provider state on re-import (idempotent upsert). Returns changed."""
        changed = self.is_read != is_read or [(lbl.external_label_id, lbl.name) for lbl in self.labels] \
            != [(lbl.external_label_id, lbl.name) for lbl in labels]
        self.is_read = is_read
        self.labels = labels
        return changed

    def mark_read(self) -> None:
        self.is_read = True
