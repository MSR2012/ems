"""Django implementation of the UnitOfWork port."""

from __future__ import annotations

from django.db import transaction

from shared_kernel.application.ports import EventBus
from shared_kernel.domain import AggregateRoot

from .event_bus import event_bus as default_bus


class DjangoUnitOfWork:
    """Wraps `transaction.atomic`; events are published via `transaction.on_commit`
    so asynchronous handlers never observe uncommitted data."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or default_bus
        self._aggregates: list[AggregateRoot] = []
        self._atomic = None

    def __enter__(self) -> DjangoUnitOfWork:
        self._aggregates = []
        self._atomic = transaction.atomic()
        self._atomic.__enter__()
        return self

    def register(self, aggregate: AggregateRoot) -> None:
        if aggregate not in self._aggregates:
            self._aggregates.append(aggregate)

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            events = [e for agg in self._aggregates for e in agg.pull_events()]
            if events:
                transaction.on_commit(lambda: self._bus.publish(events))
        self._atomic.__exit__(exc_type, exc, tb)
        self._aggregates = []
