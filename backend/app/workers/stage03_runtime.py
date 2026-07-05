import os

from sqlalchemy.orm import Session

from app.core.config import validate_runtime_settings
from app.core.database import get_session_factory
from app.queues.redis_streams import RedisStreams, RedisStreamsClient
from app.workers.runner import RedisStreamsWorker
from app.workers.stage03_handlers import (
    SqlAlchemyStage03WorkerUnitOfWork,
    Stage03WorkerUnitOfWork,
    handle_telegram_message_received,
)

DEFAULT_STAGE03_STREAM_NAME = "stage03:events"
DEFAULT_STAGE03_GROUP_NAME = "telegram-message-workers"
DEFAULT_STAGE03_CONSUMER_NAME = "stage03-worker-1"


def create_stage03_worker(
    *,
    streams: RedisStreams,
    uow: Stage03WorkerUnitOfWork,
    consumer_name: str,
    stream_name: str = DEFAULT_STAGE03_STREAM_NAME,
    group_name: str = DEFAULT_STAGE03_GROUP_NAME,
) -> RedisStreamsWorker:
    return RedisStreamsWorker(
        streams=streams,
        stream_name=stream_name,
        group_name=group_name,
        consumer_name=consumer_name,
        handlers={
            "telegram.message_received": (
                lambda fields: handle_telegram_message_received(fields, uow)
            )
        },
        failure_uow=uow,
    )


def create_stage03_worker_for_session(
    *,
    session: Session,
    streams: RedisStreams,
    consumer_name: str,
    stream_name: str = DEFAULT_STAGE03_STREAM_NAME,
    group_name: str = DEFAULT_STAGE03_GROUP_NAME,
) -> RedisStreamsWorker:
    return create_stage03_worker(
        streams=streams,
        uow=SqlAlchemyStage03WorkerUnitOfWork(session),
        stream_name=stream_name,
        group_name=group_name,
        consumer_name=consumer_name,
    )


def main() -> None:
    settings = validate_runtime_settings()
    streams = RedisStreamsClient.from_url(settings.redis_url)
    session_factory = get_session_factory()
    with session_factory() as session:
        worker = create_stage03_worker_for_session(
            session=session,
            streams=streams,
            stream_name=os.getenv(
                "STAGE03_REDIS_STREAM_NAME",
                DEFAULT_STAGE03_STREAM_NAME,
            ),
            group_name=os.getenv(
                "STAGE03_REDIS_GROUP_NAME",
                DEFAULT_STAGE03_GROUP_NAME,
            ),
            consumer_name=os.getenv(
                "STAGE03_REDIS_CONSUMER_NAME",
                DEFAULT_STAGE03_CONSUMER_NAME,
            ),
        )
        worker.run_continuously(
            limit=_env_int("STAGE03_WORKER_BATCH_SIZE", 10),
            poll_interval_seconds=_env_float(
                "STAGE03_WORKER_POLL_INTERVAL_SECONDS",
                1.0,
            ),
        )


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
