from __future__ import annotations

import re
from dataclasses import dataclass

from shared_kernel.domain import InvariantViolation, ValueObject

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


@dataclass(frozen=True)
class EmailAddress(ValueObject):
    email: str
    name: str = ""

    def __post_init__(self) -> None:
        normalized = (self.email or "").strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise InvariantViolation(f"invalid email address: {self.email!r}")
        object.__setattr__(self, "email", normalized)
        object.__setattr__(self, "name", (self.name or "").strip())

    @property
    def display(self) -> str:
        return self.name or self.email


@dataclass(frozen=True)
class ProviderMessageRef(ValueObject):
    """Provider-neutral reference to the source message (e.g. provider='gmail')."""

    provider: str
    mail_account_id: int
    external_message_id: str
    external_thread_id: str

    def __post_init__(self) -> None:
        if not self.provider or not self.external_message_id:
            raise InvariantViolation("provider and external message id are required")


# Backwards-friendly alias used in the requirements document.
GmailMessageRef = ProviderMessageRef
