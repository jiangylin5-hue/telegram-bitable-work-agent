from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models.stage07_telegram import Stage07TelegramDeepLink
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_workspace,
)
from tests.integration.test_stage07_governance_postgres import (
    Stage06Postgres,
    stage06_postgres,
)


def _link(*, workspace_id, token_hash: str, expires_at: datetime) -> Stage07TelegramDeepLink:
    return Stage07TelegramDeepLink(
        id=uuid4(),
        token_hash=token_hash,
        workspace_id=workspace_id,
        subject_telegram_user_id="synthetic-user",
        source_telegram_chat_id="synthetic-chat",
        destination_kind="base",
        destination_id=uuid4(),
        status="active",
        expires_at=expires_at,
        created_by_type="system",
        created_by_id="test",
    )


def test_s6_deep_link_migration_has_unique_hash_and_expiry_filtered_lookup(
    stage06_postgres: Stage06Postgres,
) -> None:
    now = datetime.now(UTC)
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name="S6 Telegram deep links",
            owner_user_id="s6-owner",
        )
        active = _link(
            workspace_id=workspace.id,
            token_hash="a" * 64,
            expires_at=now + timedelta(minutes=10),
        )
        expired = _link(
            workspace_id=workspace.id,
            token_hash="b" * 64,
            expires_at=now - timedelta(seconds=1),
        )
        uow.add_telegram_deep_link(active)
        uow.add_telegram_deep_link(expired)
        session.commit()

        assert uow.get_active_telegram_deep_link_by_token_hash("a" * 64, now)
        assert uow.get_active_telegram_deep_link_by_token_hash("b" * 64, now) is None

        session.add(
            _link(
                workspace_id=workspace.id,
                token_hash="a" * 64,
                expires_at=now + timedelta(minutes=10),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    inspector = inspect(stage06_postgres.engine)
    assert "stage07_telegram_deep_links" in inspector.get_table_names()
    assert {item["name"] for item in inspector.get_unique_constraints("stage07_telegram_deep_links")} == {
        "uq_stage07_telegram_deep_links_token_hash"
    }
    indexes = inspector.get_indexes("stage07_telegram_deep_links")
    assert [item["duplicates_constraint"] for item in indexes] == [
        "uq_stage07_telegram_deep_links_token_hash"
    ]
