"""Application-level ports shared by every context."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from shared_kernel.domain import AggregateRoot, DomainEvent

EventHandler = Callable[[DomainEvent], None]


class EventBus(Protocol):
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None: ...

    def publish(self, events: Iterable[DomainEvent]) -> None: ...


class UnitOfWork(Protocol):
    """Transaction boundary. Events of registered aggregates are dispatched after commit."""

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, exc_type, exc, tb) -> None: ...

    def register(self, aggregate: AggregateRoot) -> None: ...
