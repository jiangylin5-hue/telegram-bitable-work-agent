import os
from time import sleep

from sqlalchemy.orm import Session

from app.core.config import validate_runtime_settings
from app.core.database import get_session_factory
from app.queues.redis_streams import RedisStreams, RedisStreamsClient
from app.repositories.outbox import SqlAlchemyOutboxRepository
from app.services.outbox import (
    OutboxToRedisStreamsBridge,
    ReadyOutboxRepository,
    RedisBridgeResult,
)
from app.workers.stage03_runtime import DEFAULT_STAGE03_STREAM_NAME


def create_stage03_outbox_bridge(
    *,
    repository: ReadyOutboxRepository,
    streams: RedisStreams,
    stream_name: str = DEFAULT_STAGE03_STREAM_NAME,
) -> OutboxToRedisStreamsBridge:
    return OutboxToRedisStreamsBridge(
        repository=repository,
        streams=streams,
        stream_name=stream_name,
    )


def create_stage03_outbox_bridge_for_session(
    *,
    session: Session,
    streams: RedisStreams,
    stream_name: str = DEFAULT_STAGE03_STREAM_NAME,
) -> OutboxToRedisStreamsBridge:
    return create_stage03_outbox_bridge(
        repository=SqlAlchemyOutboxRepository(session),
        streams=streams,
        stream_name=stream_name,
    )


def main() -> None:
    settings = validate_runtime_settings()
    streams = RedisStreamsClient.from_url(settings.redis_url)
    session_factory = get_session_factory()
    stream_name = os.getenv("STAGE03_REDIS_STREAM_NAME", DEFAULT_STAGE03_STREAM_NAME)
    limit = _env_int("STAGE03_OUTBOX_BRIDGE_BATCH_SIZE", 10)
    poll_interval_seconds = _env_float(
        "STAGE03_OUTBOX_BRIDGE_POLL_INTERVAL_SECONDS",
        1.0,
    )

    while True:
        with session_factory() as session:
            bridge = create_stage03_outbox_bridge_for_session(
                session=session,
                streams=streams,
                stream_name=stream_name,
            )
            result = bridge.dispatch_once(limit=limit)
            session.commit()
        if result == RedisBridgeResult():
            sleep(poll_interval_seconds)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


if __name__ == "__main__":
    main()
