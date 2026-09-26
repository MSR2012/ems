from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class InboxFilters:
    q: str = ""
    priorities: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    spam_min: int | None = None
    spam_max: int | None = None
    urgency_min: int | None = None
    urgency_max: int | None = None
    hide_potential_spam: bool = False
    is_read: bool | None = None
    received_from: datetime | None = None
    received_to: datetime | None = None


@dataclass(frozen=True)
class Thresholds:
    spam: int
    urgency: int


@dataclass(frozen=True)
class AnalysisSummary:
    status: str
    priority: str | None
    priority_confidence: int | None
    spam_likelihood: int | None
    reply_urgency: int | None
    category: str | None
    sentiment: str | None
    model: str
    prompt_version: str
    analyzed_at: datetime | None
    error: str | None
    latest_status: str
    model_version: str | None
    is_potential_spam: bool
    is_high_urgency: bool


@dataclass(frozen=True)
class InboxItem:
    id: int
    thread_id: str
    sender_name: str
    sender_email: str
    subject: str
    snippet: str
    received_at: datetime
    is_read: bool
    has_attachments: bool
    thread_count: int
    analysis: AnalysisSummary | None


@dataclass(frozen=True)
class InboxPage:
    count: int
    page: int
    page_size: int
    results: list[InboxItem]


@dataclass(frozen=True)
class AttachmentDTO:
    id: int
    filename: str
    mime_type: str
    size: int


@dataclass(frozen=True)
class ThreadMessage:
    id: int
    sender_name: str
    sender_email: str
    subject: str
    snippet: str
    received_at: datetime
    is_read: bool


@dataclass(frozen=True)
class EmailDetail:
    id: int
    provider: str
    external_message_id: str
    thread_id: str
    sender_name: str
    sender_email: str
    recipients: list[dict]
    subject: str
    body_text: str
    body_html_sanitized: str
    snippet: str
    received_at: datetime
    is_read: bool
    labels: list[str]
    attachments: list[AttachmentDTO]
    analysis: AnalysisSummary | None
    thread: list[ThreadMessage] = field(default_factory=list)


@dataclass(frozen=True)
class ThreadDetail:
    thread_id: str
    subject: str
    messages: list[EmailDetail]
