from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime

from shared_kernel.domain import AggregateRoot, InvalidStateTransition, utcnow

from .events import EmailSyncCompleted, EmailSyncFailed


class SyncType(enum.StrEnum):
    INITIAL = "INITIAL"
    INCREMENTAL = "INCREMENTAL"


class SyncStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


_TRANSITIONS: dict[SyncStatus, set[SyncStatus]] = {
    SyncStatus.PENDING: {SyncStatus.RUNNING, SyncStatus.FAILED},
    SyncStatus.RUNNING: {SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED},
    SyncStatus.COMPLETED: set(),
    SyncStatus.PARTIAL: set(),
    SyncStatus.FAILED: set(),
}


@dataclass(eq=False, kw_only=True)
class EmailSync(AggregateRoot):
    gmail_account_id: int
    type: SyncType
    status: SyncStatus = SyncStatus.PENDING
    fetched_count: int = 0
    imported_count: int = 0
    failed_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str = ""
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def request(cls, gmail_account_id: int, sync_type: SyncType) -> EmailSync:
        return cls(gmail_account_id=gmail_account_id, type=sync_type)

    @property
    def is_finished(self) -> bool:
        return self.status in (SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED)

    def _transition(self, target: SyncStatus) -> None:
        if target not in _TRANSITIONS[self.status]:
            raise InvalidStateTransition(f"sync cannot move from {self.status} to {target}")
        self.status = target

    def start(self, now: datetime | None = None) -> None:
        self._transition(SyncStatus.RUNNING)
        self.started_at = now or utcnow()

    def record_fetched(self, n: int = 1) -> None:
        self._require_running()
        self.fetched_count += n

    def record_imported(self, n: int = 1) -> None:
        self._require_running()
        self.imported_count += n

    def record_failure(self, n: int = 1) -> None:
        self._require_running()
        self.failed_count += n

    def complete(self, now: datetime | None = None) -> None:
        self._transition(SyncStatus.PARTIAL if self.failed_count else SyncStatus.COMPLETED)
        self.completed_at = now or utcnow()
        self.record_event(EmailSyncCompleted(sync_id=self.id or 0,
                                             account_id=self.gmail_account_id,
                                             status=str(self.status),
                                             imported_count=self.imported_count))

    def fail(self, error: str, now: datetime | None = None) -> None:
        self._transition(SyncStatus.FAILED)
        self.error = error[:1000]
        self.completed_at = now or utcnow()
        self.record_event(EmailSyncFailed(sync_id=self.id or 0,
                                          account_id=self.gmail_account_id, error=self.error))

    def _require_running(self) -> None:
        if self.status != SyncStatus.RUNNING:
            raise InvalidStateTransition("sync is not running")
