from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import DateTime, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.models.telegram import Message
from app.runtime.stage08_context_contracts import ResolvedBusinessScope
from app.schemas.telegram import MockTelegramUpdate
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    update_record,
)
from app.services.stage08_group_context import (
    _materialize_group_context_window,
    Stage08GroupContextAuthorityFactory,
    build_group_context_window,
    purge_expired_group_context_projections,
    purge_group_context_projection,
)
from app.services.stage08_context import resolve_business_scope
from app.services.telegram_ingestion import (
    IngestedMessage,
    SqlAlchemyTelegramIngestionUnitOfWork,
    TelegramIngestionPersistenceError,
    ingest_mock_telegram_update,
)
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    stage06_postgres,
)


NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
    ),
]


def _seed(stage06_postgres: Stage06Postgres):
    session = stage06_postgres.session_factory()
    uow = SqlAlchemyStage06PlatformUnitOfWork(session)
    workspace = create_workspace(
        uow,
        name=f"Stage08 C2 {uuid4().hex[:8]}",
        owner_user_id="stage08-c2-owner",
    )
    session.flush()
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="C2 Base")
    customer_table = create_table(
        uow,
        base.id,
        name="Customers",
        key="customers",
    )
    project_table = create_table(
        uow,
        base.id,
        name="Projects",
        key="projects",
    )
    customer = create_record(uow, customer_table.id, values={})
    project = create_record(uow, project_table.id, values={})
    telegram_binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="-100800900",
        telegram_user_id="800900",
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(telegram_binding)
    session.flush()
    mapping = Stage08GroupBusinessContextBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        telegram_binding_id=telegram_binding.id,
        customer_record_id=customer.id,
        project_record_id=project.id,
        mapping_version=1,
        status="active",
    )
    uow.add_group_business_context_binding(mapping)
    session.flush()
    return session, uow, workspace, telegram_binding, customer, project, mapping


def _message(*, event_at: datetime = NOW) -> Message:
    return Message(
        id=uuid4(),
        telegram_update_id=f"update-{uuid4()}",
        telegram_chat_id="-100800900",
        telegram_message_id=f"message-{uuid4()}",
        telegram_user_id="800900",
        raw_text=None,
        raw_caption=None,
        normalized_text=None,
        message_type="text",
        intent_status="unclassified",
        received_at=event_at,
        ingestion_status="stored",
        binding_status="bound",
        processing_status="queued",
        outbox_status="pending",
        trace_id=f"trace-{uuid4()}",
    )


def _projection(
    *,
    mapping_id,
    source_message_id,
    content_fragment: str = "safe controlled fragment",
    content_version: int = 1,
    event_at: datetime = NOW,
    retention_expires_at: datetime | None = None,
    lifecycle_status: str = "active",
    source_chat_type: str = "group",
) -> Stage08GroupMessageProjection:
    return Stage08GroupMessageProjection(
        id=uuid4(),
        source_message_id=source_message_id,
        business_context_binding_id=mapping_id,
        content_fragment=content_fragment,
        content_version=content_version,
        event_at=event_at,
        edited_at=None,
        retention_expires_at=(
            retention_expires_at
            if retention_expires_at is not None
            else event_at + timedelta(days=30)
        ),
        lifecycle_status=lifecycle_status,
        source_chat_type=source_chat_type,
    )


def _assert_database_rejects(session, value) -> None:
    with pytest.raises((IntegrityError, DBAPIError, StatementError)):
        with session.begin_nested():
            session.add(value)
            session.flush()


def _seed_runtime_window(stage06_postgres: Stage06Postgres):
    session, uow, workspace, binding, customer, project, mapping = _seed(
        stage06_postgres
    )
    actor = Actor(
        actor_type="user",
        actor_id="stage08-c2-owner",
        role="owner",
    )
    customer_table = uow.get_table(customer.table_id)
    project_table = uow.get_table(project.table_id)
    assert customer_table is not None
    assert project_table is not None
    create_field(
        uow,
        customer_table.id,
        name="Name",
        key="name",
        field_type="text",
        actor=actor,
    )
    create_field(
        uow,
        project_table.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customer_table.id)},
        actor=actor,
    )
    session.flush()
    customer = update_record(
        uow,
        customer.id,
        values={"name": "Lifecycle customer"},
        expected_version=customer.version,
        actor=actor,
    )
    project = update_record(
        uow,
        project.id,
        values={"customer": [str(customer.id)]},
        expected_version=project.version,
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        project_table.base_id,
        name="Stage08 C2 employee",
        description="PostgreSQL lifecycle evidence",
        telegram_alias=None,
        accessible_tables=[str(customer_table.id), str(project_table.id)],
        accessible_views=[],
        allowed_actions=["summarize"],
        actor=actor,
    )
    source = _message(event_at=NOW - timedelta(minutes=1))
    session.add(source)
    session.flush()
    projection = _projection(
        mapping_id=mapping.id,
        source_message_id=source.id,
        content_fragment="private lifecycle fragment",
        event_at=source.received_at,
    )
    uow.add_group_message_projection(projection)
    session.flush()
    scope = resolve_business_scope(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        customer_record_id=customer.id,
        project_record_id=project.id,
    )
    assert isinstance(scope, ResolvedBusinessScope)
    assert scope.relation_kind == "visible_linked_record"
    authority = Stage08GroupContextAuthorityFactory.build(
        uow,
        actor=actor,
        employee_id=employee.id,
        workspace_id=workspace.id,
    )
    window = build_group_context_window(
        uow,
        authority,
        business_scope=scope,
        now=NOW,
    )
    materialized = _materialize_group_context_window(
        uow,
        authority,
        window,
        business_scope=scope,
        now=NOW,
    )
    assert materialized._available is True
    assert [item._text for item in materialized._fragments] == [
        "private lifecycle fragment"
    ]
    return {
        "session": session,
        "uow": uow,
        "workspace": workspace,
        "member": uow.list_workspace_members(workspace.id)[0],
        "binding": binding,
        "mapping": mapping,
        "customer": customer,
        "project": project,
        "employee": employee,
        "source": source,
        "projection": projection,
        "authority": authority,
        "scope": scope,
        "window": window,
    }


def test_group_context_migration_has_timezone_and_partial_active_mapping_contract(
    stage06_postgres: Stage06Postgres,
) -> None:
    inspector = inspect(stage06_postgres.engine)
    assert {
        "stage08_group_business_context_bindings",
        "stage08_group_message_projections",
    }.issubset(inspector.get_table_names())

    projection_columns = {
        column["name"]: column
        for column in inspector.get_columns("stage08_group_message_projections")
    }
    assert projection_columns["source_chat_type"]["nullable"] is False
    assert "unknown" in str(projection_columns["source_chat_type"].get("default", ""))
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == [
        "20260730_0039"
    ]
    for name, nullable in (
        ("event_at", False),
        ("edited_at", True),
        ("retention_expires_at", False),
        ("created_at", False),
        ("updated_at", False),
    ):
        assert isinstance(projection_columns[name]["type"], DateTime)
        assert projection_columns[name]["type"].timezone is True
        assert projection_columns[name]["nullable"] is nullable

    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("stage08_group_business_context_bindings")
    }
    active_index = indexes["uq_stage08_group_context_active_telegram_binding"]
    assert active_index["unique"] is True
    assert active_index["column_names"] == ["telegram_binding_id"]
    assert "status" in str(active_index.get("dialect_options", {})).lower()
    assert "active" in str(active_index.get("dialect_options", {})).lower()


def test_group_context_database_rejects_duplicate_active_mapping_and_invalid_projection(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, workspace, telegram_binding, customer, project, mapping = _seed(
        stage06_postgres
    )
    try:
        _assert_database_rejects(
            session,
            Stage08GroupBusinessContextBinding(
                id=uuid4(),
                workspace_id=workspace.id,
                telegram_binding_id=telegram_binding.id,
                customer_record_id=customer.id,
                project_record_id=project.id,
                mapping_version=2,
                status="active",
            ),
        )

        source_message = _message()
        session.add(source_message)
        session.flush()
        valid = _projection(
            mapping_id=mapping.id,
            source_message_id=source_message.id,
            content_fragment="x" * 500,
        )
        uow.add_group_message_projection(valid)
        session.flush()
        assert valid.business_context_binding_id == mapping.id
        assert valid.source_message_id == source_message.id
        assert mapping.workspace_id == workspace.id
        assert uow.get_record(mapping.customer_record_id).table_id == customer.table_id
        assert uow.get_record(mapping.project_record_id).table_id == project.table_id
        customer_base = uow.get_base(uow.get_table(customer.table_id).base_id)
        project_base = uow.get_base(uow.get_table(project.table_id).base_id)
        assert customer_base.workspace_id == workspace.id
        assert project_base.workspace_id == workspace.id

        invalid_factories = (
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=uuid4(),
            ),
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_version=0,
            ),
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_version=2,
                retention_expires_at=NOW,
            ),
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_version=2,
                lifecycle_status="deleted",
            ),
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_version=2,
                content_fragment="y" * 501,
            ),
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_version=1,
            ),
            lambda: _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_version=2,
                source_chat_type="channel",
            ),
        )
        for factory in invalid_factories:
            _assert_database_rejects(session, factory())

        incompatible_timestamp = _projection(
            mapping_id=mapping.id,
            source_message_id=source_message.id,
            content_version=2,
        )
        incompatible_timestamp.event_at = "not-a-timestamp"
        _assert_database_rejects(session, incompatible_timestamp)
    finally:
        session.rollback()
        session.close()


def test_group_context_uow_lists_only_current_active_projection_and_purges_body(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        projections = []
        for index, (status, expires_at, content) in enumerate(
            (
                ("active", NOW + timedelta(days=30), "available"),
                ("active", NOW, "expired"),
                ("superseded", NOW + timedelta(days=30), "superseded"),
                ("purged", NOW + timedelta(days=30), ""),
            ),
            start=1,
        ):
            source_message = _message(event_at=NOW - timedelta(minutes=index))
            session.add(source_message)
            session.flush()
            projection = _projection(
                mapping_id=mapping.id,
                source_message_id=source_message.id,
                content_fragment=content,
                event_at=source_message.received_at,
                retention_expires_at=expires_at,
                lifecycle_status=status,
            )
            uow.add_group_message_projection(projection)
            projections.append(projection)
        session.flush()

        assert uow.list_active_group_message_projections(mapping.id, now=NOW) == [
            projections[0]
        ]
        assert (
            uow.lock_group_business_context_binding_for_lifecycle(mapping.id) is mapping
        )
        assert (
            uow.lock_group_message_projection_for_lifecycle(projections[0].id)
            is projections[0]
        )
        assert uow.purge_group_message_projection(projections[0].id) is True
        session.flush()
        assert projections[0].lifecycle_status == "purged"
        assert projections[0].content_fragment == ""
        assert uow.list_active_group_message_projections(mapping.id, now=NOW) == []
    finally:
        session.rollback()
        session.close()


def test_group_context_expiry_service_locks_erases_and_is_idempotent(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        expired_message = _message(event_at=NOW - timedelta(days=30))
        stale_message = _message(event_at=NOW - timedelta(days=31))
        current_message = _message(event_at=NOW)
        session.add_all([expired_message, stale_message, current_message])
        session.flush()
        expired = _projection(
            mapping_id=mapping.id,
            source_message_id=expired_message.id,
            content_fragment="expired controlled projection",
            event_at=expired_message.received_at,
            retention_expires_at=NOW,
        )
        current = _projection(
            mapping_id=mapping.id,
            source_message_id=current_message.id,
            content_fragment="current controlled projection",
            event_at=current_message.received_at,
            retention_expires_at=NOW + timedelta(days=30),
        )
        stale = _projection(
            mapping_id=mapping.id,
            source_message_id=stale_message.id,
            content_fragment="stale controlled projection",
            event_at=stale_message.received_at,
            retention_expires_at=NOW + timedelta(days=60),
        )
        uow.add_group_message_projection(expired)
        uow.add_group_message_projection(stale)
        uow.add_group_message_projection(current)
        session.flush()

        assert purge_expired_group_context_projections(uow, now=NOW).purged_count == 2
        session.flush()
        assert expired.lifecycle_status == "purged"
        assert expired.content_fragment == ""
        assert expired.source_chat_type == "group"
        assert stale.lifecycle_status == "purged"
        assert stale.content_fragment == ""
        assert stale.source_chat_type == "group"
        assert current.lifecycle_status == "active"
        assert current.content_fragment == "current controlled projection"
        assert purge_expired_group_context_projections(uow, now=NOW).purged_count == 0
    finally:
        session.rollback()
        session.close()


def test_group_context_window_uow_counts_old_rows_without_loading_their_bodies(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        projections = []
        for index in range(122):
            event_at = NOW - timedelta(minutes=index)
            source = _message(event_at=event_at)
            session.add(source)
            session.flush()
            projection = _projection(
                mapping_id=mapping.id,
                source_message_id=source.id,
                content_fragment=f"eligible-{index}",
                event_at=event_at,
            )
            uow.add_group_message_projection(projection)
            projections.append(projection)
        expired_source = _message(event_at=NOW - timedelta(days=31))
        session.add(expired_source)
        session.flush()
        expired = _projection(
            mapping_id=mapping.id,
            source_message_id=expired_source.id,
            content_fragment="old-body-must-not-be-loaded",
            event_at=expired_source.received_at,
            retention_expires_at=NOW + timedelta(days=60),
        )
        uow.add_group_message_projection(expired)
        session.flush()

        age_omissions, limit_omissions = (
            uow.count_group_message_projection_window_omissions(
                mapping.id,
                now=NOW,
                event_cutoff=NOW - timedelta(days=30),
                eligible_limit=120,
            )
        )
        eligible = uow.list_eligible_group_message_projections_for_window(
            mapping.id,
            now=NOW,
            event_cutoff=NOW - timedelta(days=30),
            limit=120,
        )
        assert age_omissions == 1
        assert limit_omissions == 2
        assert len(eligible) == 120
        assert expired not in eligible
        assert all(
            item.content_fragment != "old-body-must-not-be-loaded" for item in eligible
        )
    finally:
        session.rollback()
        session.close()


def test_group_context_unknown_default_is_backfilled_but_never_window_eligible(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        unknown_source = _message()
        valid_source = _message(event_at=NOW - timedelta(minutes=1))
        session.add_all([unknown_source, valid_source])
        session.flush()
        unknown = _projection(
            mapping_id=mapping.id,
            source_message_id=unknown_source.id,
            content_fragment="historical unknown must not load",
        )
        del unknown.source_chat_type
        valid = _projection(
            mapping_id=mapping.id,
            source_message_id=valid_source.id,
            content_fragment="verified group",
            event_at=valid_source.received_at,
            source_chat_type="group",
        )
        uow.add_group_message_projection(unknown)
        uow.add_group_message_projection(valid)
        session.flush()
        session.refresh(unknown)
        assert unknown.source_chat_type == "unknown"

        eligible = uow.list_eligible_group_message_projections_for_window(
            mapping.id,
            now=NOW,
            event_cutoff=NOW - timedelta(days=30),
            limit=120,
        )
        assert eligible == [valid]
        assert unknown not in eligible
    finally:
        session.rollback()
        session.close()


def test_group_context_fresh_handle_query_filters_unknown_before_body_selection(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        source = _message()
        session.add(source)
        session.flush()
        projection = _projection(
            mapping_id=mapping.id,
            source_message_id=source.id,
            content_fragment="must not materialize after provenance drift",
            source_chat_type="group",
        )
        uow.add_group_message_projection(projection)
        session.flush()
        handle_projection_id = projection.id

        assert (
            uow.get_eligible_group_message_projection_for_materialization(
                handle_projection_id,
                mapping.id,
                now=NOW,
                event_cutoff=NOW - timedelta(days=30),
            )
            is projection
        )
        projection.source_chat_type = "unknown"
        session.flush()
        session.expire(projection)

        selected = uow.get_eligible_group_message_projection_for_materialization(
            handle_projection_id,
            mapping.id,
            now=NOW,
            event_cutoff=NOW - timedelta(days=30),
        )
        assert selected is None
        assert "must not materialize" not in repr(selected)
    finally:
        session.rollback()
        session.close()


@pytest.mark.parametrize(
    "drift",
    (
        "known_edit",
        "retention_expiry",
        "authorized_purge",
        "member_inactive",
        "binding_inactive",
        "mapping_inactive",
        "business_relation_changed",
        "provenance_unknown",
    ),
)
def test_group_context_planned_window_fails_closed_after_current_state_drift(
    stage06_postgres: Stage06Postgres,
    drift: str,
) -> None:
    seeded = _seed_runtime_window(stage06_postgres)
    session = seeded["session"]
    uow = seeded["uow"]
    authority = seeded["authority"]
    scope = seeded["scope"]
    window = seeded["window"]
    projection = seeded["projection"]
    source = seeded["source"]
    check_now = NOW
    try:
        if drift == "known_edit":
            projection.lifecycle_status = "superseded"
            replacement = _projection(
                mapping_id=seeded["mapping"].id,
                source_message_id=source.id,
                content_fragment="current edited fragment",
                content_version=2,
                event_at=projection.event_at,
            )
            replacement.edited_at = NOW
            uow.add_group_message_projection(replacement)
        elif drift == "retention_expiry":
            check_now = NOW + timedelta(days=31)
        elif drift == "authorized_purge":
            result = purge_group_context_projection(
                uow,
                authority,
                projection_handle=window._projection_handles[0],
                now=NOW,
            )
            assert result.model_dump(mode="json") == {
                "contract_version": "stage08-group-context-purge.v1",
                "purged_count": 1,
            }
        elif drift == "member_inactive":
            seeded["member"].status = "inactive"
        elif drift == "binding_inactive":
            seeded["binding"].status = "inactive"
        elif drift == "mapping_inactive":
            seeded["mapping"].status = "inactive"
        elif drift == "business_relation_changed":
            seeded["project"].record_values = {"customer": []}
        elif drift == "provenance_unknown":
            projection.source_chat_type = "unknown"
        else:  # pragma: no cover - parameter list is exhaustive
            raise AssertionError(drift)
        session.flush()

        stale = _materialize_group_context_window(
            uow,
            authority,
            window,
            business_scope=scope,
            now=check_now,
        )
        assert stale._available is False
        assert stale._fragments == ()
        assert "private lifecycle fragment" not in repr(stale)
        assert str(projection.id) not in repr(stale)
        assert str(source.id) not in repr(stale)

        safe_payload = window.view().model_dump(mode="json")
        assert set(safe_payload) == {
            "contract_version",
            "status",
            "usage",
            "omissions",
            "compression_required",
        }
        safe_dump = str(safe_payload)
        assert "private lifecycle fragment" not in safe_dump
        assert str(projection.id) not in safe_dump
        assert str(source.id) not in safe_dump

        rebuilt = build_group_context_window(
            uow,
            authority,
            business_scope=scope,
            now=check_now,
        )
        rebuilt_materialization = _materialize_group_context_window(
            uow,
            authority,
            rebuilt,
            business_scope=scope,
            now=check_now,
        )
        if drift == "known_edit":
            assert rebuilt_materialization._available is True
            assert [item._text for item in rebuilt_materialization._fragments] == [
                "current edited fragment"
            ]
        else:
            assert rebuilt_materialization._available is False
            assert rebuilt_materialization._fragments == ()
        assert "private lifecycle fragment" not in repr(rebuilt_materialization)
    finally:
        session.rollback()
        session.close()


def test_group_context_concurrent_purge_blocks_fresh_reader_until_current_state(
    stage06_postgres: Stage06Postgres,
) -> None:
    seeded = _seed_runtime_window(stage06_postgres)
    seed_session = seeded["session"]
    authority = seeded["authority"]
    scope = seeded["scope"]
    window = seeded["window"]
    projection_id = seeded["projection"].id
    seed_session.commit()
    seed_session.close()

    writer_session = stage06_postgres.session_factory()
    writer_uow = SqlAlchemyStage06PlatformUnitOfWork(writer_session)
    monitor_session = stage06_postgres.session_factory()
    reader_ready = Event()
    reader_go = Event()
    reader_state: dict[str, int] = {}

    def read_current_materialization():
        reader_session = stage06_postgres.session_factory()
        try:
            reader_session.execute(text("set local lock_timeout = '3000ms'"))
            reader_state["pid"] = int(
                reader_session.scalar(text("select pg_backend_pid()"))
            )
            reader_ready.set()
            assert reader_go.wait(timeout=5)
            reader_uow = SqlAlchemyStage06PlatformUnitOfWork(reader_session)
            return _materialize_group_context_window(
                reader_uow,
                authority,
                window,
                business_scope=scope,
                now=NOW,
            )
        finally:
            reader_session.rollback()
            reader_session.close()

    try:
        writer_pid = int(writer_session.scalar(text("select pg_backend_pid()")))
        locked = writer_uow.lock_group_message_projection_for_lifecycle(projection_id)
        assert locked is not None
        locked.content_fragment = ""
        locked.lifecycle_status = "purged"
        writer_session.flush()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(read_current_materialization)
            assert reader_ready.wait(timeout=5)
            reader_go.set()

            reader_is_blocked = False
            for _ in range(500):
                if future.done():
                    break
                reader_is_blocked = bool(
                    monitor_session.scalar(
                        text("select :writer_pid = any(pg_blocking_pids(:reader_pid))"),
                        {
                            "writer_pid": writer_pid,
                            "reader_pid": reader_state["pid"],
                        },
                    )
                )
                if reader_is_blocked:
                    break

            completed_before_transition = future.done()
            if reader_is_blocked:
                writer_session.commit()
            else:
                writer_session.rollback()
            current = future.result(timeout=5)

        assert completed_before_transition is False
        assert reader_is_blocked is True
        assert current._available is False
        assert current._fragments == ()
        assert "private lifecycle fragment" not in repr(current)

        verify_session = stage06_postgres.session_factory()
        try:
            persisted = verify_session.get(
                Stage08GroupMessageProjection,
                projection_id,
            )
            assert persisted is not None
            assert persisted.lifecycle_status == "purged"
            assert persisted.content_fragment == ""
        finally:
            verify_session.rollback()
            verify_session.close()
    finally:
        if writer_session.in_transaction():
            writer_session.rollback()
        writer_session.close()
        monitor_session.rollback()
        monitor_session.close()


def test_group_context_fragment_boundary_counts_unicode_code_points(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        accepted_message = _message()
        rejected_message = _message()
        session.add_all([accepted_message, rejected_message])
        session.flush()
        accepted = _projection(
            mapping_id=mapping.id,
            source_message_id=accepted_message.id,
            content_fragment="🙂" * 500,
        )
        uow.add_group_message_projection(accepted)
        session.flush()
        assert len(accepted.content_fragment) == 500

        _assert_database_rejects(
            session,
            _projection(
                mapping_id=mapping.id,
                source_message_id=rejected_message.id,
                content_fragment="🙂" * 501,
            ),
        )
    finally:
        session.rollback()
        session.close()


def test_group_context_offset_timestamp_is_normalized_by_timestamptz(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    try:
        offset_event_at = NOW.astimezone(timezone(timedelta(hours=8)))
        source_message = _message(event_at=offset_event_at)
        session.add(source_message)
        session.flush()
        projection = _projection(
            mapping_id=mapping.id,
            source_message_id=source_message.id,
            event_at=offset_event_at,
            retention_expires_at=offset_event_at + timedelta(days=30),
        )
        uow.add_group_message_projection(projection)
        session.commit()

        reloaded = uow.get_group_message_projection(projection.id)
        assert reloaded is not None
        assert reloaded.event_at.astimezone(UTC) == NOW
        assert reloaded.retention_expires_at.astimezone(UTC) == NOW + timedelta(days=30)
    finally:
        session.rollback()
        session.close()


def test_verified_ingress_message_and_projection_share_one_transaction(
    stage06_postgres: Stage06Postgres,
) -> None:
    session, _uow, _workspace, _binding, _customer, _project, mapping = _seed(
        stage06_postgres
    )
    ingestion_uow = SqlAlchemyTelegramIngestionUnitOfWork(session)
    try:
        result = ingest_mock_telegram_update(
            MockTelegramUpdate(
                update_id="stage08-c2-ingress-1",
                chat_id="-100800900",
                message_id="stage08-c2-message-1",
                sender_user_id="800900",
                text="  same   transaction  ",
                message_type="text",
                received_at=NOW,
                update_kind="new",
                chat_type="group",
            ),
            ingestion_uow,
        )
        source_message_id = UUID(result.message_id)
        session.flush()

        projection = session.scalar(
            select(Stage08GroupMessageProjection).where(
                Stage08GroupMessageProjection.source_message_id == source_message_id
            )
        )
        assert projection is not None
        assert projection.business_context_binding_id == mapping.id
        assert projection.content_fragment == "same transaction"
        projection_id = projection.id

        secret_fragment = "must-not-leak-projection-body"
        duplicate_version = _projection(
            mapping_id=mapping.id,
            source_message_id=source_message_id,
            content_fragment=secret_fragment,
        )
        with pytest.raises(RuntimeError) as exc_info:
            ingestion_uow.add_group_message_projection(duplicate_version)
        assert str(exc_info.value) == "group_context_projection_write_failed"
        assert exc_info.value.__cause__ is None
        assert secret_fragment not in str(exc_info.value)

        session.rollback()
        assert session.get(Message, source_message_id) is None
        assert session.get(Stage08GroupMessageProjection, projection_id) is None
    finally:
        session.rollback()
        session.close()


def test_message_constraint_failure_raises_stable_error_without_raw_body(
    stage06_postgres: Stage06Postgres,
) -> None:
    session = stage06_postgres.session_factory()
    ingestion_uow = SqlAlchemyTelegramIngestionUnitOfWork(session)

    def message(*, message_id: str, raw_text: str) -> IngestedMessage:
        value = IngestedMessage(
            id=uuid4(),
            telegram_update_id="duplicate-message-update",
            telegram_chat_id="constraint-chat",
            telegram_message_id=message_id,
            telegram_user_id="constraint-user",
            customer_group_id=None,
            customer_id=None,
            raw_text=raw_text,
            raw_caption=None,
            normalized_text=raw_text,
            message_type="text",
            intent_status="needs_review",
            intent_type=None,
            ingestion_status="stored",
            trace_id=f"trace-{message_id}",
        )
        value.received_at = NOW
        return value

    try:
        ingestion_uow.add_message(message(message_id="first", raw_text="safe"))
        secret_raw_text = "must-not-leak-secret-raw-message"

        with pytest.raises(TelegramIngestionPersistenceError) as exc_info:
            ingestion_uow.add_message(
                message(message_id="second", raw_text=secret_raw_text)
            )

        assert str(exc_info.value) == "telegram_message_write_failed"
        assert exc_info.value.args == ("telegram_message_write_failed",)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True
        assert secret_raw_text not in str(exc_info.value)
        assert secret_raw_text not in repr(exc_info.value.args)
    finally:
        session.rollback()
        session.close()
