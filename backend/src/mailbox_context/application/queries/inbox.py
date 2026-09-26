"""Mailbox read-side use cases (CQRS-lite). Always scoped to the requesting user."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shared_kernel.domain import NotFoundError

from .dto import EmailDetail, InboxFilters, InboxPage, ThreadDetail, Thresholds

MAX_PAGE_SIZE = 100


class InboxQueryService(Protocol):
    def list_inbox(self, user_id: int, filters: InboxFilters, thresholds: Thresholds,
                   page: int, page_size: int) -> InboxPage: ...

    def email_detail(self, user_id: int, email_id: int, thresholds: Thresholds) -> EmailDetail | None: ...

    def thread(self, user_id: int, thread_id: str, thresholds: Thresholds) -> ThreadDetail | None: ...


@dataclass
class ListInbox:
    queries: InboxQueryService

    def __call__(self, *, user_id: int, filters: InboxFilters, thresholds: Thresholds,
                 page: int = 1, page_size: int = 25) -> InboxPage:
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))  # never the full mailbox
        return self.queries.list_inbox(user_id, filters, thresholds, max(page, 1), page_size)


# SearchEmails is ListInbox with a text query (§12.3); kept as an explicit alias.
SearchEmails = ListInbox


@dataclass
class GetEmailDetail:
    queries: InboxQueryService

    def __call__(self, *, user_id: int, email_id: int, thresholds: Thresholds) -> EmailDetail:
        detail = self.queries.email_detail(user_id, email_id, thresholds)
        if detail is None:
            raise NotFoundError("email not found")
        return detail


@dataclass
class GetThread:
    queries: InboxQueryService

    def __call__(self, *, user_id: int, thread_id: str, thresholds: Thresholds) -> ThreadDetail:
        detail = self.queries.thread(user_id, thread_id, thresholds)
        if detail is None:
            raise NotFoundError("thread not found")
        return detail
