from __future__ import annotations

import os
import re
import time
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import DateTime, Integer, Numeric, String, event, func, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.models.stage08_memory import (
    Stage08MemoryExtractionCandidate,
    Stage08MemoryItem,
)
from app.models.outbox import OutboxEvent
from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage06_runtime import RecordChangeDraft
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.permissions import Actor
from app.runtime.stage08_memory_contracts import (
    GroupMemoryCandidateProjection,
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.stage08_group_memory_source import (
    TrustedGroupMessageInput,
    resolve_authorized_group_message_source,
)
from app.services.stage08_memory import (
    CandidateRevocationResult,
    create_group_memory_candidate,
    enqueue_confirmed_record_memory_event,
    list_memory_projections,
    materialize_stage08_memory_outbox_event,
    materialize_memory_from_projection,
    read_memory_projection,
    resolve_group_candidate,
    revoke_memory_candidate,
)
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    stage06_postgres,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _status_literals(check_sql: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", check_sql))


def _normalized_sql(value: str) -> str:
    return " ".join(value.lower().split())


def _assert_uuid_column(column: dict, *, nullable: bool) -> None:
    assert str(column["type"]).lower() == "uuid"
    assert column["nullable"] is nullable


def _assert_string_column(
    column: dict,
    *,
    length: int,
    nullable: bool,
) -> None:
    assert isinstance(column["type"], String)
    assert column["type"].length == length
    assert column["nullable"] is nullable


def _assert_integer_column(column: dict, *, nullable: bool) -> None:
    assert isinstance(column["type"], Integer)
    assert column["nullable"] is nullable


def _assert_jsonb_column(column: dict, *, nullable: bool) -> None:
    assert isinstance(column["type"], postgresql.JSONB)
    assert column["nullable"] is nullable


def _assert_timezone_datetime_column(column: dict, *, nullable: bool) -> None:
    assert isinstance(column["type"], DateTime)
    assert column["type"].timezone is True
    assert column["nullable"] is nullable


def _wait_until_backend_is_blocked(
    stage06_postgres: Stage06Postgres,
    *,
    blocked_pid: int,
    blocking_pid: int,
) -> None:
    deadline = time.monotonic() + 5
    with stage06_postgres.engine.connect() as observer:
        while time.monotonic() < deadline:
            blocking_pids = observer.scalar(select(func.pg_blocking_pids(blocked_pid)))
            if blocking_pid in set(blocking_pids or ()):
                return
            time.sleep(0.05)
    pytest.fail("second lifecycle-lock session did not block on the PostgreSQL row lock")


def _memory_item(*, workspace_id, **overrides) -> Stage08MemoryItem:
    values = {
        "id": uuid4(),
        "workspace_id": workspace_id,
        "memory_type": "customer_fact",
        "status": "active",
        "scope": {"workspace_id": str(workspace_id)},
        "payload": {"customer_key": "acme"},
        "source_refs": [{"source_kind": "platform_record", "source_id": str(uuid4())}],
        "source_fingerprint": uuid4().hex,
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Stage08MemoryItem(**values)


def _candidate(*, workspace_id, **overrides) -> Stage08MemoryExtractionCandidate:
    values = {
        "id": uuid4(),
        "workspace_id": workspace_id,
        "candidate_type": "customer_fact",
        "status": "candidate",
        "confidence": 0.9,
        "scope": {"workspace_id": str(workspace_id)},
        "normalized_payload": {"customer_key": "acme"},
        "source_refs": [{"source_kind": "telegram_message", "source_id": str(uuid4())}],
        "source_fingerprint": uuid4().hex,
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Stage08MemoryExtractionCandidate(**values)


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_memory_migration_has_contract_tables_constraints_and_indexes(
    stage06_postgres: Stage06Postgres,
) -> None:
    inspector = inspect(stage06_postgres.engine)

    expected_columns = {
        "stage08_memory_items": {
            "id", "workspace_id", "memory_type", "status", "scope", "payload",
            "source_refs", "source_fingerprint", "version", "supersedes_id",
            "valid_until", "revoked_at", "deleted_at", "created_at", "updated_at",
        },
        "stage08_memory_extraction_candidates": {
            "id", "workspace_id", "candidate_type", "status", "confidence", "scope",
            "normalized_payload", "source_refs", "source_fingerprint", "version",
            "valid_until", "reviewed_at", "reviewed_by_user_id", "created_at", "updated_at",
        },
    }
    for table_name, status_constraint, statuses, payload_column in (
        (
            "stage08_memory_items",
            "ck_stage08_memory_item_status",
            {"active", "conflicted", "superseded", "revoked", "expired", "deleted"},
            "payload",
        ),
        (
            "stage08_memory_extraction_candidates",
            "ck_stage08_memory_candidate_status",
            {"candidate", "accepted", "rejected", "expired"},
            "normalized_payload",
        ),
    ):
        assert table_name in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert set(columns) == expected_columns[table_name]
        assert isinstance(columns["scope"]["type"], postgresql.JSONB)
        assert isinstance(columns[payload_column]["type"], postgresql.JSONB)
        assert isinstance(columns["source_refs"]["type"], postgresql.JSONB)
        assert str(columns["id"]["type"]).lower() == "uuid"
        assert str(columns["workspace_id"]["type"]).lower() == "uuid"
        assert columns["workspace_id"]["nullable"] is False
        assert columns["status"]["nullable"] is False
        assert columns["scope"]["nullable"] is False
        assert columns[payload_column]["nullable"] is False
        assert columns["source_refs"]["nullable"] is False
        assert columns["source_fingerprint"]["nullable"] is False
        assert columns["version"]["nullable"] is False
        assert columns["valid_until"]["nullable"] is True
        assert columns["created_at"]["nullable"] is False
        assert columns["updated_at"]["nullable"] is False
        checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints(table_name)
        }
        assert _status_literals(checks[status_constraint]) == statuses
        assert "status" in _normalized_sql(checks[status_constraint])

    item_columns = {
        column["name"]: column
        for column in inspector.get_columns("stage08_memory_items")
    }
    candidate_columns = {
        column["name"]: column
        for column in inspector.get_columns("stage08_memory_extraction_candidates")
    }
    for name in ("id", "workspace_id"):
        _assert_uuid_column(item_columns[name], nullable=False)
    _assert_string_column(item_columns["memory_type"], length=120, nullable=False)
    _assert_string_column(item_columns["status"], length=40, nullable=False)
    for name in ("scope", "payload", "source_refs"):
        _assert_jsonb_column(item_columns[name], nullable=False)
    _assert_string_column(
        item_columns["source_fingerprint"],
        length=64,
        nullable=False,
    )
    _assert_integer_column(item_columns["version"], nullable=False)
    _assert_uuid_column(item_columns["supersedes_id"], nullable=True)
    for name in (
        "valid_until",
        "revoked_at",
        "deleted_at",
    ):
        _assert_timezone_datetime_column(item_columns[name], nullable=True)
    for name in ("created_at", "updated_at"):
        _assert_timezone_datetime_column(item_columns[name], nullable=False)

    for name in ("id", "workspace_id"):
        _assert_uuid_column(candidate_columns[name], nullable=False)
    _assert_string_column(
        candidate_columns["candidate_type"],
        length=120,
        nullable=False,
    )
    _assert_string_column(candidate_columns["status"], length=40, nullable=False)
    assert isinstance(candidate_columns["confidence"]["type"], Numeric)
    assert candidate_columns["confidence"]["type"].precision == 5
    assert candidate_columns["confidence"]["type"].scale == 4
    assert candidate_columns["confidence"]["nullable"] is False
    for name in ("scope", "normalized_payload", "source_refs"):
        _assert_jsonb_column(candidate_columns[name], nullable=False)
    _assert_string_column(
        candidate_columns["source_fingerprint"],
        length=64,
        nullable=False,
    )
    _assert_integer_column(candidate_columns["version"], nullable=False)
    for name in ("valid_until", "reviewed_at"):
        _assert_timezone_datetime_column(candidate_columns[name], nullable=True)
    _assert_uuid_column(candidate_columns["reviewed_by_user_id"], nullable=True)
    for name in ("created_at", "updated_at"):
        _assert_timezone_datetime_column(candidate_columns[name], nullable=False)

    assert {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints("stage08_memory_items")
    } == {
        "uq_stage08_memory_item_workspace_type_fingerprint": [
            "workspace_id", "memory_type", "source_fingerprint"
        ]
    }
    assert {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints(
            "stage08_memory_extraction_candidates"
        )
    } == {
        "uq_stage08_memory_candidate_workspace_type_fingerprint": [
            "workspace_id", "candidate_type", "source_fingerprint"
        ]
    }
    item_indexes = {
        index["name"]: index["column_names"]
        for index in inspector.get_indexes("stage08_memory_items")
    }
    candidate_indexes = {
        index["name"]: index["column_names"]
        for index in inspector.get_indexes("stage08_memory_extraction_candidates")
    }
    assert item_indexes[
        "ix_stage08_memory_item_workspace_status_valid_until"
    ] == ["workspace_id", "status", "valid_until"]
    assert candidate_indexes[
        "ix_stage08_memory_candidate_workspace_status_valid_until"
    ] == ["workspace_id", "status", "valid_until"]
    item_foreign_keys = {
        (
            tuple(constraint["constrained_columns"]),
            constraint["referred_table"],
            tuple(constraint["referred_columns"]),
        )
        for constraint in inspector.get_foreign_keys("stage08_memory_items")
    }
    assert item_foreign_keys == {
        (("workspace_id",), "workspaces", ("id",)),
        (("supersedes_id",), "stage08_memory_items", ("id",)),
    }
    candidate_foreign_keys = inspector.get_foreign_keys(
        "stage08_memory_extraction_candidates"
    )
    assert {
        (
            tuple(constraint["constrained_columns"]),
            constraint["referred_table"],
            tuple(constraint["referred_columns"]),
        )
        for constraint in candidate_foreign_keys
    } == {(("workspace_id",), "workspaces", ("id",))}


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_memory_postgres_lifecycle_locks_block_competing_sessions(
    stage06_postgres: Stage06Postgres,
) -> None:
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 lock {uuid4().hex[:8]}",
            owner_user_id="stage08-memory-owner",
        )
        session.flush()
        item = _memory_item(workspace_id=workspace.id)
        candidate = _candidate(workspace_id=workspace.id)
        uow.add_memory_item(item)
        uow.add_memory_extraction_candidate(candidate)
        session.commit()

    for item_id, lock_method, table_name in (
        (item.id, "lock_memory_item_for_lifecycle", "stage08_memory_items"),
        (
            candidate.id,
            "lock_memory_extraction_candidate_for_lifecycle",
            "stage08_memory_extraction_candidates",
        ),
    ):
        blocked_pid_ready = Event()
        blocked_pids: list[int] = []
        statements: list[str] = []

        def capture_statement(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        def acquire_in_second_session() -> UUID:
            with stage06_postgres.session_factory() as session_b:
                uow_b = SqlAlchemyStage06PlatformUnitOfWork(session_b)
                blocked_pid = session_b.scalar(select(func.pg_backend_pid()))
                assert isinstance(blocked_pid, int)
                blocked_pids.append(blocked_pid)
                blocked_pid_ready.set()
                locked = getattr(uow_b, lock_method)(item_id)
                assert locked is not None
                session_b.rollback()
                return locked.id

        event.listen(stage06_postgres.engine, "before_cursor_execute", capture_statement)
        try:
            with stage06_postgres.session_factory() as session_a:
                uow_a = SqlAlchemyStage06PlatformUnitOfWork(session_a)
                locked = getattr(uow_a, lock_method)(item_id)
                assert locked is not None
                blocking_pid = session_a.scalar(select(func.pg_backend_pid()))
                assert isinstance(blocking_pid, int)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(acquire_in_second_session)
                    assert blocked_pid_ready.wait(timeout=5)
                    _wait_until_backend_is_blocked(
                        stage06_postgres,
                        blocked_pid=blocked_pids[0],
                        blocking_pid=blocking_pid,
                    )
                    session_a.rollback()
                    assert future.result(timeout=15) == item_id
        finally:
            event.remove(
                stage06_postgres.engine,
                "before_cursor_execute",
                capture_statement,
            )
        assert any(
            table_name in statement.lower() and "for update" in statement.lower()
            for statement in statements
        )


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_memory_postgres_breaks_equal_created_at_ties_by_id_descending(
    stage06_postgres: Stage06Postgres,
) -> None:
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 ordering {uuid4().hex[:8]}",
            owner_user_id="stage08-memory-owner",
        )
        session.flush()
        lower_id = UUID(int=1)
        higher_id = UUID(int=2)
        lower_item = _memory_item(
            workspace_id=workspace.id,
            id=lower_id,
        )
        higher_item = _memory_item(
            workspace_id=workspace.id,
            id=higher_id,
        )
        lower_candidate = _candidate(
            workspace_id=workspace.id,
            id=lower_id,
        )
        higher_candidate = _candidate(
            workspace_id=workspace.id,
            id=higher_id,
        )
        uow.add_memory_item(lower_item)
        uow.add_memory_item(higher_item)
        uow.add_memory_extraction_candidate(lower_candidate)
        uow.add_memory_extraction_candidate(higher_candidate)
        session.commit()

        assert uow.list_memory_items(workspace.id) == [higher_item, lower_item]
        assert uow.list_memory_extraction_candidates(workspace.id) == [
            higher_candidate,
            lower_candidate,
        ]


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_memory_postgres_allows_fingerprint_namespace_variants_and_confidence_bounds(
    stage06_postgres: Stage06Postgres,
) -> None:
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 namespace {uuid4().hex[:8]}",
            owner_user_id="stage08-memory-owner",
        )
        other_workspace = create_workspace(
            uow,
            name=f"Stage08 namespace other {uuid4().hex[:8]}",
            owner_user_id="stage08-memory-owner",
        )
        session.flush()
        shared_fingerprint = "f" * 64
        uow.add_memory_item(
            _memory_item(
                workspace_id=workspace.id,
                source_fingerprint=shared_fingerprint,
            )
        )
        uow.add_memory_item(
            _memory_item(
                workspace_id=workspace.id,
                memory_type="project_fact",
                source_fingerprint=shared_fingerprint,
            )
        )
        uow.add_memory_item(
            _memory_item(
                workspace_id=other_workspace.id,
                source_fingerprint=shared_fingerprint,
            )
        )
        uow.add_memory_extraction_candidate(
            _candidate(
                workspace_id=workspace.id,
                source_fingerprint=shared_fingerprint,
                confidence=0,
            )
        )
        uow.add_memory_extraction_candidate(
            _candidate(
                workspace_id=workspace.id,
                candidate_type="project_fact",
                source_fingerprint=shared_fingerprint,
                confidence=1,
            )
        )
        uow.add_memory_extraction_candidate(
            _candidate(
                workspace_id=other_workspace.id,
                source_fingerprint=shared_fingerprint,
            )
        )
        session.commit()


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_memory_postgres_round_trip_constraints_unique_fingerprints_and_lifecycle_locks(
    stage06_postgres: Stage06Postgres,
) -> None:
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 memory {uuid4().hex[:8]}",
            owner_user_id="stage08-memory-owner",
        )
        session.flush()
        item = _memory_item(workspace_id=workspace.id)
        candidate = _candidate(workspace_id=workspace.id)
        uow.add_memory_item(item)
        uow.add_memory_extraction_candidate(candidate)
        session.commit()

        assert uow.get_memory_item(item.id) is not None
        assert uow.lock_memory_item_for_lifecycle(item.id) is not None
        assert uow.get_memory_extraction_candidate(candidate.id) is not None
        assert uow.lock_memory_extraction_candidate_for_lifecycle(candidate.id) is not None

        later_item = _memory_item(
            workspace_id=workspace.id,
            created_at=NOW + timedelta(seconds=1),
            updated_at=NOW + timedelta(seconds=1),
        )
        later_candidate = _candidate(
            workspace_id=workspace.id,
            created_at=NOW + timedelta(seconds=1),
            updated_at=NOW + timedelta(seconds=1),
        )
        uow.add_memory_item(later_item)
        uow.add_memory_extraction_candidate(later_candidate)
        session.commit()
        assert uow.list_memory_items(workspace.id) == [later_item, item]
        assert uow.list_memory_extraction_candidates(workspace.id) == [later_candidate, candidate]

        uow.add_memory_item(
            _memory_item(
                workspace_id=workspace.id,
                source_fingerprint=item.source_fingerprint,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        uow.add_memory_extraction_candidate(
            _candidate(
                workspace_id=workspace.id,
                source_fingerprint=candidate.source_fingerprint,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        for invalid_item in (
            _memory_item(workspace_id=workspace.id, status="candidate"),
            _memory_item(workspace_id=workspace.id, scope=[]),
            _memory_item(workspace_id=workspace.id, payload=[]),
            _memory_item(workspace_id=workspace.id, source_refs={}),
            _memory_item(workspace_id=workspace.id, version=0),
        ):
            uow.add_memory_item(invalid_item)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        for invalid_candidate in (
            _candidate(workspace_id=workspace.id, status="active"),
            _candidate(workspace_id=workspace.id, scope=[]),
            _candidate(workspace_id=workspace.id, normalized_payload=[]),
            _candidate(workspace_id=workspace.id, source_refs={}),
            _candidate(workspace_id=workspace.id, version=0),
            _candidate(workspace_id=workspace.id, confidence=-0.1),
            _candidate(workspace_id=workspace.id, confidence=1.1),
        ):
            uow.add_memory_extraction_candidate(invalid_candidate)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


def _service_projection(
    workspace_id,
    base_id,
    table_id,
    record,
    *,
    decision: str,
    identity_token: str | None = None,
):
    return MemoryMaterializationProjection(
        memory_type="decision",
        scope=MemoryScopeProjection(
            workspace_id=workspace_id,
            base_id=base_id,
            table_id=table_id,
            identity_token=identity_token,
        ),
        payload={"customer": "Acme", "decision": decision},
        source_refs=(
            MemorySourceRef(
                source_kind="platform_record",
                source_id=record.id,
                source_version=record.version,
                field_keys=("customer", "decision"),
            ),
        ),
    )


def _postgres_confirmed_record_fixture(uow, *, owner: Actor):
    workspace = create_workspace(
        uow,
        name=f"Stage08 confirmed outbox {uuid4().hex[:8]}",
        owner_user_id=owner.actor_id,
    )
    uow.session.flush()
    base = create_base(uow, workspace.id, name="CRM")
    uow.session.flush()
    table = create_table(uow, base.id, name="Decisions", key=f"decisions-{uuid4().hex[:8]}")
    for key in ("customer", "project", "subject", "decision", "status", "hidden"):
        create_field(uow, table.id, name=key.title(), key=key, field_type="text")
    uow.session.flush()
    customer = create_record(
        uow, table.id, values={"customer": "Acme"}, actor=owner
    )
    project = create_record(
        uow, table.id, values={"project": "Renewal"}, actor=owner
    )
    record = create_record(
        uow,
        table.id,
        values={
            "customer": str(customer.id),
            "project": str(project.id),
            "subject": "Renewal",
            "decision": "approved",
            "status": "open",
            "hidden": "B5_HIDDEN_SENTINEL",
        },
        actor=owner,
    )
    table.settings = {
        "memory_policy": {
            "version": 1,
            "rules": [
                {
                    "memory_type": "decision",
                    "identity_field_keys": ["customer", "subject"],
                    "payload_field_keys": ["decision", "status"],
                    "scope_field_keys": {
                        "customer_record_id": "customer",
                        "project_record_id": "project",
                    },
                    "valid_for_days": 90,
                }
            ],
        }
    }
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=record.id,
        draft_type="update_record",
        proposed_values={"decision": "approved"},
        before_values={"decision": "pending"},
        created_by_type="digital_employee",
        created_by_id="b5-employee",
        status="confirmed",
        confirmation_policy={},
        trace_id=f"stage08:b5:{uuid4()}",
        expected_version=record.version,
    )
    uow.add_record_change_draft(draft)
    return workspace, base, table, record, draft


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_confirmed_record_outbox_enqueue_is_idempotent_across_competing_postgres_sessions(
    stage06_postgres: Stage06Postgres,
) -> None:
    owner = Actor(actor_type="user", actor_id="stage08-b5-outbox-owner", role="owner")
    with stage06_postgres.session_factory() as setup_session:
        setup_uow = SqlAlchemyStage06PlatformUnitOfWork(setup_session)
        _workspace, _base, _table, record, draft = _postgres_confirmed_record_fixture(
            setup_uow, owner=owner
        )
        setup_session.commit()

    contender_ready = Event()
    contender_pids: list[int] = []
    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    def enqueue_in_second_session() -> UUID:
        with stage06_postgres.session_factory() as second_session:
            second_uow = SqlAlchemyStage06PlatformUnitOfWork(second_session)
            current_draft = second_uow.get_record_change_draft(draft.id)
            current_record = second_uow.get_record(record.id)
            assert current_draft is not None and current_record is not None
            contender_pid = second_session.scalar(select(func.pg_backend_pid()))
            assert isinstance(contender_pid, int)
            contender_pids.append(contender_pid)
            contender_ready.set()
            event = enqueue_confirmed_record_memory_event(
                second_uow,
                current_draft,
                current_record,
                confirmation_actor=owner,
                now=NOW,
            )
            assert event is not None
            second_session.commit()
            return event.id

    event.listen(stage06_postgres.engine, "before_cursor_execute", capture_statement)
    try:
        with stage06_postgres.session_factory() as first_session:
            first_uow = SqlAlchemyStage06PlatformUnitOfWork(first_session)
            current_draft = first_uow.get_record_change_draft(draft.id)
            current_record = first_uow.get_record(record.id)
            assert current_draft is not None and current_record is not None
            first_event = enqueue_confirmed_record_memory_event(
                first_uow,
                current_draft,
                current_record,
                confirmation_actor=owner,
                now=NOW,
            )
            assert first_event is not None
            first_session.flush()
            first_pid = first_session.scalar(select(func.pg_backend_pid()))
            assert isinstance(first_pid, int)
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                contender = executor.submit(enqueue_in_second_session)
                assert contender_ready.wait(timeout=5)
                _wait_until_backend_is_blocked(
                    stage06_postgres,
                    blocked_pid=contender_pids[0],
                    blocking_pid=first_pid,
                )
                first_session.commit()
                assert contender.result(timeout=15) == first_event.id
            finally:
                if first_session.in_transaction():
                    first_session.rollback()
                executor.shutdown(wait=True)
    finally:
        event.remove(stage06_postgres.engine, "before_cursor_execute", capture_statement)

    lowered_statements = [statement.lower() for statement in statements]
    draft_lock_index = next(
        index
        for index, statement in enumerate(lowered_statements)
        if "record_change_drafts" in statement and "for update" in statement
    )
    outbox_lookup_index = next(
        index
        for index, statement in enumerate(lowered_statements)
        if "outbox_events" in statement and "idempotency_key" in statement
    )
    assert draft_lock_index < outbox_lookup_index

    with stage06_postgres.session_factory() as verify_session:
        verify_uow = SqlAlchemyStage06PlatformUnitOfWork(verify_session)
        assert len(
            [
                event
                for event in verify_uow.session.scalars(
                    select(OutboxEvent)
                )
                if event.event_type == "stage08.memory.confirmed_record.v1"
                and event.aggregate_id == str(record.id)
            ]
        ) == 1


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_confirmed_record_postgres_outbox_redacts_hidden_field_and_fails_closed_on_field_revocation(
    stage06_postgres: Stage06Postgres,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "b5-postgres-identity-key")
    owner = Actor(actor_type="user", actor_id="stage08-b5-field-owner", role="owner")
    with stage06_postgres.session_factory() as producer_session:
        producer_uow = SqlAlchemyStage06PlatformUnitOfWork(producer_session)
        workspace, _base, table, record, draft = _postgres_confirmed_record_fixture(
            producer_uow, owner=owner
        )
        producer_session.flush()
        event = enqueue_confirmed_record_memory_event(
            producer_uow, draft, record, confirmation_actor=owner, now=NOW
        )
        assert event is not None
        assert event.payload == {
            "workspace_id": str(workspace.id),
            "table_id": str(table.id),
            "record_id": str(record.id),
            "record_version": record.version,
            "policy_version": 1,
            "rule_index": 0,
        }
        assert "B5_HIDDEN_SENTINEL" not in json.dumps(event.payload, sort_keys=True)
        event_id = event.id
        table_id = table.id
        producer_session.commit()

    with stage06_postgres.session_factory() as worker_session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(worker_session)
        item = materialize_stage08_memory_outbox_event(
            uow, event_id, actor=owner, now=NOW
        )
        assert item is not None
        assert item.payload == {"decision": "approved", "status": "open"}
        event = uow.get_outbox_event(event_id)
        assert event is not None
        assert event.status == "processed"

        next(field for field in uow.list_fields(table_id) if field.key == "decision").permission_policy = {
            "owner": "hidden"
        }
        assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
        assert item.status == "deleted"

        memory_audit_dump = json.dumps(
            [
                {
                    "event_type": audit.event_type,
                    "after_state": audit.after_state,
                    "permission_snapshot": audit.permission_snapshot,
                }
                for audit in uow.list_audit_events()
                if audit.event_type.startswith("stage08.memory")
            ],
            sort_keys=True,
        )
        for forbidden in (
            "B5_HIDDEN_SENTINEL",
            "raw_text",
            "prompt",
            "response",
            "telegram_user_id",
        ):
            assert forbidden not in memory_audit_dump


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_memory_postgres_ttl_cross_workspace_and_deleted_source_fail_closed(
    stage06_postgres: Stage06Postgres,
) -> None:
    owner = Actor(actor_type="user", actor_id="stage08-b5-lifecycle-owner", role="owner")
    foreign = Actor(actor_type="user", actor_id="stage08-b5-foreign-owner", role="owner")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 B5 lifecycle {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
        )
        foreign_workspace = create_workspace(
            uow,
            name=f"Stage08 B5 foreign {uuid4().hex[:8]}",
            owner_user_id=foreign.actor_id,
        )
        session.flush()
        base = create_base(uow, workspace.id, name="CRM")
        session.flush()
        table = create_table(uow, base.id, name="Decisions", key=f"b5-{uuid4().hex[:8]}")
        create_field(uow, table.id, name="Customer", key="customer", field_type="text")
        create_field(uow, table.id, name="Decision", key="decision", field_type="text")
        session.flush()
        expired_record = create_record(
            uow, table.id, values={"customer": "Acme", "decision": "approved"}, actor=owner
        )
        deleted_source_record = create_record(
            uow, table.id, values={"customer": "Acme", "decision": "approved"}, actor=owner
        )
        session.flush()
        expired_item = materialize_memory_from_projection(
            uow,
            _service_projection(workspace.id, base.id, table.id, expired_record, decision="approved"),
            actor=owner,
            now=NOW,
        )
        deleted_item = materialize_memory_from_projection(
            uow,
            _service_projection(
                workspace.id,
                base.id,
                table.id,
                deleted_source_record,
                decision="approved",
                identity_token="d" * 64,
            ),
            actor=owner,
            now=NOW,
        )
        expired_item.valid_until = NOW - timedelta(seconds=1)
        assert read_memory_projection(uow, expired_item.id, actor=foreign, now=NOW) is None
        assert expired_item.status == "active"
        assert read_memory_projection(uow, expired_item.id, actor=owner, now=NOW) is None
        assert expired_item.status == "expired"

        deleted_source_record.record_status = "deleted"
        assert read_memory_projection(uow, deleted_item.id, actor=owner, now=NOW) is None
        assert deleted_item.status == "deleted"
        assert uow.get_workspace(foreign_workspace.id) is not None


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
@pytest.mark.parametrize("same_fingerprint", (True, False))
def test_memory_materialization_workspace_lock_serializes_competing_sessions(
    stage06_postgres: Stage06Postgres,
    same_fingerprint: bool,
) -> None:
    owner = Actor(actor_type="user", actor_id="stage08-memory-owner", role="owner")
    with stage06_postgres.session_factory() as setup_session:
        setup_uow = SqlAlchemyStage06PlatformUnitOfWork(setup_session)
        workspace = create_workspace(
            setup_uow,
            name=f"Stage08 materialize lock {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
        )
        setup_session.flush()
        base = create_base(setup_uow, workspace.id, name="CRM")
        setup_session.flush()
        table = create_table(setup_uow, base.id, name="Customers", key="customers")
        setup_session.flush()
        create_field(setup_uow, table.id, name="Customer", key="customer", field_type="text")
        create_field(setup_uow, table.id, name="Decision", key="decision", field_type="text")
        setup_session.flush()
        first_record = create_record(
            setup_uow,
            table.id,
            values={"customer": "Acme", "decision": "approved"},
            actor=owner,
        )
        second_record = create_record(
            setup_uow,
            table.id,
            values={"customer": "Acme", "decision": "rejected"},
            actor=owner,
        )
        setup_session.commit()

    first_projection = _service_projection(
        workspace.id, base.id, table.id, first_record, decision="approved"
    )
    second_projection = (
        first_projection
        if same_fingerprint
        else _service_projection(
            workspace.id, base.id, table.id, second_record, decision="rejected"
        )
    )
    blocked_pid_ready = Event()
    blocked_pids: list[int] = []

    def materialize_in_second_session() -> Stage08MemoryItem:
        with stage06_postgres.session_factory() as session_b:
            uow_b = SqlAlchemyStage06PlatformUnitOfWork(session_b)
            blocked_pid = session_b.scalar(select(func.pg_backend_pid()))
            assert isinstance(blocked_pid, int)
            blocked_pids.append(blocked_pid)
            blocked_pid_ready.set()
            result = materialize_memory_from_projection(
                uow_b, second_projection, actor=owner, now=NOW
            )
            session_b.commit()
            return result

    with stage06_postgres.session_factory() as session_a:
        uow_a = SqlAlchemyStage06PlatformUnitOfWork(session_a)
        first = materialize_memory_from_projection(
            uow_a, first_projection, actor=owner, now=NOW
        )
        blocking_pid = session_a.scalar(select(func.pg_backend_pid()))
        assert isinstance(blocking_pid, int)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(materialize_in_second_session)
            assert blocked_pid_ready.wait(timeout=5)
            _wait_until_backend_is_blocked(
                stage06_postgres,
                blocked_pid=blocked_pids[0],
                blocking_pid=blocking_pid,
            )
            session_a.commit()
            second = future.result(timeout=15)

    if same_fingerprint:
        assert second.id == first.id
    else:
        assert first.status == "active"
        assert second.status == "conflicted"
        assert second.version == 2


def _postgres_group_projection(uow, workspace, binding, *, decision: str = "approved"):
    trusted = TrustedGroupMessageInput(
        message_id=uuid4(),
        chat_id=binding.telegram_chat_id,
        chat_type="supergroup",
        binding_id=binding.id,
    )
    source = resolve_authorized_group_message_source(uow, trusted)
    assert source is not None
    projection = GroupMemoryCandidateProjection(
        candidate_type="decision",
        confidence=Decimal("0.85"),
        scope=source.scope,
        normalized_payload={"decision": decision},
        source_refs=(source.source_ref,),
    )
    return projection, source


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_group_candidate_postgres_idempotency_binding_revocation_and_audit_redaction(
    stage06_postgres: Stage06Postgres,
) -> None:
    owner = Actor(actor_type="user", actor_id="stage08-group-owner", role="owner")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 group memory {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
        )
        session.flush()
        member = uow.list_workspace_members(workspace.id)[0]
        binding = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="-100777888",
            telegram_user_id="556677",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        uow.add_telegram_binding(binding)
        session.flush()
        projection, source = _postgres_group_projection(uow, workspace, binding)

        first = create_group_memory_candidate(
            uow, projection, source=source, actor=owner, now=NOW
        )
        replay = create_group_memory_candidate(
            uow, projection, source=source, actor=owner, now=NOW + timedelta(seconds=1)
        )
        assert replay.id == first.id
        assert len(uow.list_memory_extraction_candidates(workspace.id)) == 1

        item = resolve_group_candidate(uow, first.id, actor=owner, now=NOW)
        assert item is not None
        assert item.source_fingerprint == first.source_fingerprint
        session.commit()

        binding.status = "revoked"
        assert list_memory_projections(uow, workspace.id, actor=owner, now=NOW) == []
        assert item.status == "revoked"
        session.commit()

        audit_dump = json.dumps(
            [
                {
                    "event_type": event.event_type,
                    "after_state": event.after_state,
                    "permission_snapshot": event.permission_snapshot,
                }
                for event in uow.list_audit_events()
            ],
            sort_keys=True,
        )
        for forbidden in (
            "GROUP_MEMORY_RAW_SENTINEL",
            "-100777888",
            "556677",
            "raw_text",
            "telegram_user_id",
        ):
            assert forbidden not in audit_dump


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_accepted_group_candidate_postgres_revoke_locks_exact_fingerprint_only(
    stage06_postgres: Stage06Postgres,
) -> None:
    owner = Actor(actor_type="user", actor_id="stage08-revoke-owner", role="owner")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 exact revoke {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
        )
        session.flush()
        member = uow.list_workspace_members(workspace.id)[0]
        binding = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="-100333444",
            telegram_user_id="112233",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        uow.add_telegram_binding(binding)
        session.flush()
        projection, source = _postgres_group_projection(uow, workspace, binding)
        candidate = create_group_memory_candidate(
            uow, projection, source=source, actor=owner, now=NOW
        )
        item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
        assert item is not None
        unrelated = _memory_item(
            workspace_id=workspace.id,
            memory_type="decision",
            scope=item.scope,
            payload={"decision": "unrelated"},
            source_refs=item.source_refs,
        )
        uow.add_memory_item(unrelated)
        session.commit()

        result = revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=2,
            now=NOW + timedelta(seconds=1),
        )
        session.commit()

        assert result == CandidateRevocationResult("accepted", 2, "revoked")
        assert item.status == "revoked"
        assert unrelated.status == "active"


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for disposable Stage08 PostgreSQL tests",
)
def test_group_promotion_postgres_is_visible_to_list_and_exact_revoke_without_commit(
    stage06_postgres: Stage06Postgres,
) -> None:
    owner = Actor(actor_type="user", actor_id="stage08-no-commit-owner", role="owner")
    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = create_workspace(
            uow,
            name=f"Stage08 no commit {uuid4().hex[:8]}",
            owner_user_id=owner.actor_id,
        )
        session.flush()
        member = uow.list_workspace_members(workspace.id)[0]
        binding = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="-100999000",
            telegram_user_id="443322",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        uow.add_telegram_binding(binding)
        session.flush()
        projection, source = _postgres_group_projection(uow, workspace, binding)
        candidate = create_group_memory_candidate(
            uow, projection, source=source, actor=owner, now=NOW
        )

        item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
        assert item is not None
        assert list_memory_projections(
            uow, workspace.id, actor=owner, now=NOW
        ) == [
            {
                "memory_type": "decision",
                "status": "active",
                "version": 1,
                "payload": {"decision": "approved"},
                "valid_until": None,
            }
        ]
        result = revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=2,
            now=NOW + timedelta(seconds=1),
        )

        assert result == CandidateRevocationResult("accepted", 2, "revoked")
        assert item.status == "revoked"
