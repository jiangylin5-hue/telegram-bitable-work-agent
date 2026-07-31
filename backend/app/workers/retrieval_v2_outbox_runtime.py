"""Default-off, allowlist-filtered SQL runtime for Retrieval V2 Outbox rows."""

from __future__ import annotations

from datetime import UTC, datetime
from time import sleep
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, validate_runtime_settings
from app.core.database import get_session_factory
from app.models.outbox import OutboxEvent
from app.repositories.outbox import READY_OUTBOX_STATUSES
from app.services.retrieval_v2_indexing import SqlAlchemyRetrievalIndexUnitOfWork
from app.services.retrieval_v2_runtime import build_stage12_query_embedding_provider
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork
from app.workers.outbox_dispatcher import OutboxDispatcher
from app.workers.retrieval_v2_outbox import (
    build_registered_retrieval_v2_outbox_handlers,
)


RETRIEVAL_V2_EVENT_TYPES = frozenset(
    {
        "stage12.retrieval_source.changed",
        "stage12.retrieval_projection.requested",
        "stage12.retrieval_projection.revoked",
        "stage12.retrieval_scope.bootstrap_requested",
    }
)


def build_retrieval_v2_ready_query(
    *,
    workspace_ids: frozenset[UUID],
    limit: int,
):
    if (
        not workspace_ids
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 100
    ):
        raise ValueError("retrieval_v2_outbox_query_invalid")
    workspace_values = tuple(sorted((str(item) for item in workspace_ids)))
    return (
        select(OutboxEvent)
        .where(
            OutboxEvent.event_type.in_(tuple(sorted(RETRIEVAL_V2_EVENT_TYPES))),
            OutboxEvent.payload["workspace_id"].as_string().in_(workspace_values),
            OutboxEvent.status.in_(READY_OUTBOX_STATUSES),
            or_(
                OutboxEvent.available_at.is_(None),
                OutboxEvent.available_at <= datetime.now(UTC),
            ),
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )


class RetrievalV2SqlOutboxRepository:
    def __init__(
        self,
        session: Session,
        *,
        workspace_ids: frozenset[UUID],
    ) -> None:
        if not workspace_ids:
            raise ValueError("retrieval_v2_outbox_allowlist_empty")
        self.session = session
        self.workspace_ids = workspace_ids

    def list_ready(self, limit: int = 10) -> list[OutboxEvent]:
        return list(
            self.session.scalars(
                build_retrieval_v2_ready_query(
                    workspace_ids=self.workspace_ids,
                    limit=limit,
                )
            )
        )

    def save(self, event: OutboxEvent) -> None:
        self.session.add(event)


class UnicodeCodePointTokenCounter:
    """Conservative dependency-free counter for bounded materialization chunks."""

    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(ord(character) for character in text)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "".join(chr(token_id) for token_id in token_ids)


def create_retrieval_v2_outbox_dispatcher(
    *,
    session: Session,
    settings: Settings,
    token_counter,
    embedding_provider,
    now,
) -> OutboxDispatcher:
    if settings.retrieval_v2_mode != "shadow":
        raise RuntimeError("retrieval_v2_outbox_runtime_disabled")
    try:
        workspace_ids = frozenset(
            UUID(value) for value in settings.retrieval_v2_workspace_allowlist
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError("retrieval_v2_outbox_allowlist_invalid") from exc
    if not workspace_ids:
        raise RuntimeError("retrieval_v2_outbox_allowlist_empty")
    platform_uow = SqlAlchemyStage06PlatformUnitOfWork(
        session,
        stage12_retrieval_workspace_ids=workspace_ids,
    )
    index_uow = SqlAlchemyRetrievalIndexUnitOfWork(session)
    return OutboxDispatcher(
        repository=RetrievalV2SqlOutboxRepository(
            session,
            workspace_ids=workspace_ids,
        ),
        handlers=build_registered_retrieval_v2_outbox_handlers(
            platform_uow=platform_uow,
            uow=index_uow,
            token_counter=token_counter,
            embedding_provider=embedding_provider,
            now=now,
        ),
        audit_session=session,
    )


def main() -> None:
    settings = validate_runtime_settings()
    if settings.retrieval_v2_mode != "shadow":
        raise RuntimeError("retrieval_v2_outbox_runtime_disabled")
    provider = build_stage12_query_embedding_provider(settings)
    session_factory = get_session_factory()
    counter = UnicodeCodePointTokenCounter()
    try:
        while True:
            with session_factory() as session:
                dispatcher = create_retrieval_v2_outbox_dispatcher(
                    session=session,
                    settings=settings,
                    token_counter=counter,
                    embedding_provider=provider,
                    now=lambda: datetime.now(UTC),
                )
                result = dispatcher.dispatch_once(limit=20)
                session.commit()
            if not any(
                (
                    result.processed,
                    result.retried,
                    result.dead_lettered,
                    result.missing_handler,
                )
            ):
                sleep(0.5)
    finally:
        provider.close()


if __name__ == "__main__":
    main()


__all__ = [
    "RETRIEVAL_V2_EVENT_TYPES",
    "RetrievalV2SqlOutboxRepository",
    "UnicodeCodePointTokenCounter",
    "build_retrieval_v2_ready_query",
    "create_retrieval_v2_outbox_dispatcher",
]
