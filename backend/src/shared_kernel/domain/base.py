"""Framework-free DDD building blocks shared by every bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NewType

UserId = NewType("UserId", int)


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Something that happened in the domain. Immutable; dispatched after commit."""

    occurred_at: datetime = field(default_factory=utcnow)

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class ValueObject:
    """Marker base for immutable, equality-by-value objects."""


@dataclass(eq=False, kw_only=True)
class Entity:
    """Identity-based equality. `id` is None until persisted."""

    id: int | None = None

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        if self.id is None or other.id is None:  # type: ignore[attr-defined]
            return self is other
        return self.id == other.id  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id)) if self.id is not None else id(self)


@dataclass(eq=False, kw_only=True)
class AggregateRoot(Entity):
    """Entity that guards a consistency boundary and collects domain events."""

    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def record_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

    @property
    def pending_events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)
