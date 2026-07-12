from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models.audit import OpsAuditEvent
from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage07_telegram import Stage07TelegramDeepLink
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_table,
    create_workspace,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage07_telegram_deep_links import resolve_telegram_deep_link
from app.services.stage07_telegram_mini_app_identity import (
    ValidatedTelegramMiniAppLaunch,
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


def test_s6_active_link_lock_blocks_a_concurrent_revoke(
    stage06_postgres: Stage06Postgres,
) -> None:
    now = datetime.now(UTC)
    with stage06_postgres.session_factory() as setup_session:
        setup_uow = SqlAlchemyStage06PlatformUnitOfWork(setup_session)
        workspace = create_workspace(
            setup_uow,
            name="S6 Telegram deep link lock",
            owner_user_id="s6-owner",
        )
        link = _link(
            workspace_id=workspace.id,
            token_hash="lock" * 16,
            expires_at=now + timedelta(minutes=10),
        )
        setup_uow.add_telegram_deep_link(link)
        setup_session.commit()

    with stage06_postgres.session_factory() as resolver_session:
        resolver_uow = SqlAlchemyStage06PlatformUnitOfWork(resolver_session)
        locked = resolver_uow.get_active_telegram_deep_link_by_token_hash(
            "lock" * 16,
            now,
            for_update=True,
        )
        assert locked is not None

        with stage06_postgres.session_factory() as revoke_session:
            revoke_session.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(OperationalError):
                revoke_session.execute(
                    update(Stage07TelegramDeepLink)
                    .where(Stage07TelegramDeepLink.id == link.id)
                    .values(status="revoked")
                )
            revoke_session.rollback()

        resolver_session.rollback()


def test_s6_resolved_audit_row_persists_only_closed_metadata(
    stage06_postgres: Stage06Postgres,
) -> None:
    now = datetime.now(UTC)
    start_param = "auditOpaqueToken_123456"
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name="S6 Telegram audit",
            owner_user_id="s6-owner",
        )
        session.flush()
        member = uow.list_workspace_members(workspace.id)[0]
        base = create_base(uow, workspace.id, name="Audit Base")
        create_table(uow, base.id, name="Tasks", key="tasks")
        uow.add_telegram_binding(
            Stage06TelegramBinding(
                id=uuid4(),
                workspace_id=workspace.id,
                workspace_member_id=member.id,
                telegram_chat_id="synthetic-chat",
                telegram_user_id="synthetic-user",
                binding_type="member",
                default_base_id=base.id,
                default_digital_employee_id=None,
                scope_policy={},
                status="active",
            )
        )
        link = Stage07TelegramDeepLink(
            id=uuid4(),
            token_hash=hashlib.sha256(start_param.encode("ascii")).hexdigest(),
            workspace_id=workspace.id,
            subject_telegram_user_id="synthetic-user",
            source_telegram_chat_id="synthetic-chat",
            destination_kind="base",
            destination_id=base.id,
            status="active",
            expires_at=now + timedelta(minutes=10),
            created_by_type="system",
            created_by_id="test",
        )
        uow.add_telegram_deep_link(link)
        session.commit()

        destination = resolve_telegram_deep_link(
            uow,
            identity=Stage06RequestIdentity(
                user_id="s6-owner",
                source="telegram_binding",
                telegram_user_id="synthetic-user",
            ),
            launch=ValidatedTelegramMiniAppLaunch(
                "synthetic-user", now, start_param, "private", "opaque-chat"
            ),
            start_param=start_param,
            now=now,
        )
        assert destination is not None
        session.commit()

        audit = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage07.telegram_deep_link_resolved"
            )
        )
        assert audit is not None
        assert audit.after_state == {
            "outcome": "resolved",
            "destination_kind": "base",
            "destination_id": str(base.id),
        }
        serialized = repr(audit)
        for forbidden in (start_param, "synthetic-user", "synthetic-chat", "opaque-chat"):
            assert forbidden not in serialized
