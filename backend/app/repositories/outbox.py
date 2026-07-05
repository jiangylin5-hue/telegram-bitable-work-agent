from collections.abc import Iterable

from app.models.outbox import OutboxEvent

READY_OUTBOX_STATUSES = {"pending", "retry"}


class InMemoryOutboxRepository:
    def __init__(self, events: Iterable[OutboxEvent] | None = None) -> None:
        self.events = list(events or [])
        self.saved: list[OutboxEvent] = []

    def add(self, event: OutboxEvent) -> None:
        self.events.append(event)

    def list_ready(self, limit: int = 10) -> list[OutboxEvent]:
        return [
            event
            for event in self.events
            if event.status in READY_OUTBOX_STATUSES
        ][:limit]

    def save(self, event: OutboxEvent) -> None:
        self.saved.append(event)
