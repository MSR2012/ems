from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.domain import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EmailImported(DomainEvent):
    email_id: int
    user_id: int
    analyzable: bool = True
