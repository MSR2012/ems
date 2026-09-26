"""Composition root for the Mailbox context."""

from __future__ import annotations

from mailbox_context.application import facade
from mailbox_context.application.commands.import_email import ImportEmail
from shared_kernel.infrastructure.unit_of_work import DjangoUnitOfWork

from .content.sanitizer import NH3ContentProcessor
from .content_query import DjangoEmailContentQuery
from .persistence.repositories import DjangoEmailRepository


def register() -> None:
    facade.configure(
        import_email=ImportEmail(DjangoEmailRepository(), DjangoUnitOfWork,
                                 NH3ContentProcessor()),
        content_query=DjangoEmailContentQuery(),
    )
