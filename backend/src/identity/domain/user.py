from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from shared_kernel.domain import AggregateRoot, InvariantViolation, utcnow

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise InvariantViolation("invalid email address")
    return email


@dataclass(eq=False, kw_only=True)
class User(AggregateRoot):
    email: str
    name: str = ""
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.email = normalize_email(self.email)
        self.name = (self.name or "").strip()

    def update_profile(self, *, name: str | None = None) -> None:
        if name is not None:
            name = name.strip()
            if len(name) > 150:
                raise InvariantViolation("name too long")
            self.name = name
