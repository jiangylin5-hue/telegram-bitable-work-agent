from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

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


class SqlAlchemyOutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: OutboxEvent) -> None:
        self.session.add(event)

    def list_ready(self, limit: int = 10) -> list[OutboxEvent]:
        now = datetime.now(timezone.utc)
        return list(
            self.session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status.in_(READY_OUTBOX_STATUSES),
                    or_(
                        OutboxEvent.available_at.is_(None),
                        OutboxEvent.available_at <= now,
                    ),
                )
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )

    def save(self, event: OutboxEvent) -> None:
        self.session.add(event)
