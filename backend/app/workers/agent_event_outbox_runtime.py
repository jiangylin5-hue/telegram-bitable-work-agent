from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import sleep

from sqlalchemy import or_, select

from app.core.config import validate_runtime_settings
from app.core.database import get_session_factory
from app.models.agent_event_runtime import AgentOutboxEvent
from app.queues.agent_event_streams import (
    publish_agent_command_outbox,
    publish_agent_outbox_event,
)
from app.queues.redis_streams import RedisStreams, RedisStreamsClient


@dataclass(frozen=True, slots=True)
class AgentOutboxPublishResult:
    published: int = 0
    duplicate: int = 0
    failed: int = 0


def publish_due_outbox_rows(
    rows: list[AgentOutboxEvent],
    streams: RedisStreams,
    *,
    now: datetime,
) -> AgentOutboxPublishResult:
    published = duplicate = failed = 0
    for row in rows:
        if row.published_at is not None or (
            row.next_attempt_at is not None and row.next_attempt_at > now
        ):
            continue
        try:
            sent = (
                publish_agent_command_outbox(row, streams, now=now)
                if row.aggregate_type == "agent_command"
                else publish_agent_outbox_event(row, streams, now=now)
            )
            if sent:
                published += 1
            else:
                duplicate += 1
        except Exception:
            row.publish_attempts += 1
            row.last_error_code = "redis_publish_failed"
            row.next_attempt_at = now + timedelta(
                seconds=min(60, 2 ** min(row.publish_attempts, 5))
            )
            failed += 1
    return AgentOutboxPublishResult(published, duplicate, failed)


def publish_due_outbox_once(session, streams: RedisStreams, *, now: datetime, limit: int):
    rows = list(
        session.scalars(
            select(AgentOutboxEvent)
            .where(
                AgentOutboxEvent.published_at.is_(None),
                or_(
                    AgentOutboxEvent.next_attempt_at.is_(None),
                    AgentOutboxEvent.next_attempt_at <= now,
                ),
            )
            .order_by(AgentOutboxEvent.created_at, AgentOutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    return publish_due_outbox_rows(rows, streams, now=now)


def main() -> None:
    from datetime import UTC

    settings = validate_runtime_settings()
    streams = RedisStreamsClient.from_url(settings.redis_url)
    session_factory = get_session_factory()
    while True:
        with session_factory() as session:
            result = publish_due_outbox_once(
                session, streams, now=datetime.now(UTC), limit=20
            )
            session.commit()
        if result == AgentOutboxPublishResult():
            sleep(0.5)


if __name__ == "__main__":
    main()
