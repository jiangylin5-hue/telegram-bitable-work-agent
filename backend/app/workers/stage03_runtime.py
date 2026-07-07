import os

from sqlalchemy.orm import Session

from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.clients.telegram_bot import TelegramBotClient
from app.core.config import Settings, validate_runtime_settings
from app.core.database import get_session_factory
from app.queues.redis_streams import RedisStreams, RedisStreamsClient
from app.services.agent_workflows import (
    SqlAlchemyStage05WorkflowUnitOfWork,
    Stage05AgentWorkflowService,
)
from app.workers.runner import RedisStreamsWorker
from app.workers.stage03_handlers import (
    SqlAlchemyStage03WorkerUnitOfWork,
    Stage03WorkerUnitOfWork,
    Stage05WorkflowTrigger,
    handle_telegram_message_received,
    handle_telegram_test_send_requested,
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
    telegram_bot_client: TelegramBotClient | None = None,
    telegram_test_send_allowed_chat_ids: tuple[str, ...] = (),
    stage05_workflow: Stage05WorkflowTrigger | None = None,
) -> RedisStreamsWorker:
    handlers = {
        "telegram.message_received": (
            lambda fields: handle_telegram_message_received(
                fields,
                uow,
                stage05_workflow=stage05_workflow,
            )
        )
    }
    if telegram_bot_client is not None:
        handlers["telegram.test_send_requested"] = (
            lambda fields: handle_telegram_test_send_requested(
                fields,
                uow,
                bot_client=telegram_bot_client,
                allowed_chat_ids=telegram_test_send_allowed_chat_ids,
            )
        )
    return RedisStreamsWorker(
        streams=streams,
        stream_name=stream_name,
        group_name=group_name,
        consumer_name=consumer_name,
        handlers=handlers,
        failure_uow=uow,
    )


def create_stage03_worker_for_session(
    *,
    session: Session,
    streams: RedisStreams,
    consumer_name: str,
    stream_name: str = DEFAULT_STAGE03_STREAM_NAME,
    group_name: str = DEFAULT_STAGE03_GROUP_NAME,
    telegram_bot_client: TelegramBotClient | None = None,
    telegram_test_send_allowed_chat_ids: tuple[str, ...] = (),
    stage05_workflow: Stage05WorkflowTrigger | None = None,
) -> RedisStreamsWorker:
    return create_stage03_worker(
        streams=streams,
        uow=SqlAlchemyStage03WorkerUnitOfWork(session),
        stream_name=stream_name,
        group_name=group_name,
        consumer_name=consumer_name,
        telegram_bot_client=telegram_bot_client,
        telegram_test_send_allowed_chat_ids=telegram_test_send_allowed_chat_ids,
        stage05_workflow=stage05_workflow,
    )


def main() -> None:
    settings = validate_runtime_settings()
    streams = RedisStreamsClient.from_url(settings.redis_url)
    telegram_bot_client = (
        TelegramBotClient(bot_token=settings.telegram_bot_token)
        if settings.telegram_send_mode == "restricted_test"
        and settings.telegram_bot_token is not None
        else None
    )
    session_factory = get_session_factory()
    with session_factory() as session:
        stage05_workflow = _build_stage05_workflow(
            settings=settings,
            session=session,
        )
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
            telegram_bot_client=telegram_bot_client,
            telegram_test_send_allowed_chat_ids=(
                settings.telegram_test_send_allowed_chat_ids
            ),
            stage05_workflow=stage05_workflow,
        )
        worker.run_continuously(
            limit=_env_int("STAGE03_WORKER_BATCH_SIZE", 10),
            poll_interval_seconds=_env_float(
                "STAGE03_WORKER_POLL_INTERVAL_SECONDS",
                1.0,
            ),
        )


def _build_stage05_workflow(
    *,
    settings: Settings,
    session: Session,
) -> Stage05AgentWorkflowService | None:
    if not (
        settings.llm_enabled
        and settings.agent_workflow_mode == "real_openrouter"
    ):
        return None
    return Stage05AgentWorkflowService(
        uow=SqlAlchemyStage05WorkflowUnitOfWork(session),
        llm_client=OpenRouterStructuredLLMClient(
            api_key=settings.openrouter_api_key,
            model_name=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
        ),
        model_name=settings.openrouter_model,
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
