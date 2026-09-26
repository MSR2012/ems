"""Ports used by Mailbox use cases (implemented in infrastructure)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProcessedContent:
    text: str
    sanitized_html: str
    remote_images_blocked: int = 0


class ContentProcessor(Protocol):
    """Normalizes untrusted MIME/HTML content: sanitized HTML + safe plain text."""

    def process(self, *, html: str, text: str) -> ProcessedContent: ...


class DuplicateEmailError(Exception):
    """Raised by repositories when a concurrent import already created the same message."""
