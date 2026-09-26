"""In-process event bus. Handlers typically enqueue Celery tasks."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from shared_kernel.application.ports import EventHandler
from shared_kernel.domain import DomainEvent

logger = logging.getLogger(__name__)


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._muted = 0

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    @contextmanager
    def muted(self) -> Iterator[None]:
        """Suppress dispatch (used by the demo seed, which creates analyses itself)."""
        self._muted += 1
        try:
            yield
        finally:
            self._muted -= 1

    def publish(self, events: Iterable[DomainEvent]) -> None:
        if self._muted:
            return
        for event in events:
            for handler in self._handlers.get(type(event), []):
                try:
                    handler(event)
                except Exception:  # a failing subscriber must not break the publisher
                    logger.exception("event handler failed", extra={"event": event.name})


event_bus = InProcessEventBus()
