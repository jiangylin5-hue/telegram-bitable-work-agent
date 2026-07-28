from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.routes import stage07_draft_employee_hub as draft_employee_hub_routes
from app.core.database import get_session
from app.main import create_app
from app.models.audit import OpsAuditEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_runtime import RecordChangeDraft
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import PlatformValidationError
from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork
from tests.integration.test_stage07_governance_postgres import (
    Stage06Postgres,
    _session_override,
    stage06_postgres,
)


def test_s5_confirm_postgres_replays_once_with_terminal_audit(
    stage06_postgres: Stage06Postgres,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(
        stage06_postgres.session_factory
    )
    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "s5-owner"
        workspace_id = owner.post(
            "/workspaces", json={"name": "S5 postgres", "owner_user_id": "s5-owner"}
        ).json()["id"]
        base_id = owner.post(f"/workspaces/{workspace_id}/bases", json={"name": "Ops"}).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables", json={"name": "Tasks", "key": f"tasks_{uuid4().hex[:8]}"}
        ).json()["id"]
        owner.post(f"/tables/{table_id}/fields", json={"name": "Title", "key": "title", "field_type": "text"})
        record_id = owner.post(f"/tables/{table_id}/records", json={"values": {"title": "Before"}}).json()["id"]

    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        record = uow.get_record(UUID(record_id))
        assert record is not None
        draft = RecordChangeDraft(
            id=uuid4(), workspace_id=UUID(workspace_id), base_id=UUID(base_id), table_id=UUID(table_id),
            record_id=record.id, draft_type="update_record", proposed_values={"title": "After"},
            before_values={"title": "Before"}, created_by_type="digital_employee", created_by_id="private",
            status="pending_confirmation", confirmation_policy={}, trace_id="private-trace",
            expected_version=record.version, version=1,
        )
        session.add(draft)
        session.commit()
        draft_id = str(draft.id)

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "s5-owner"
        first = owner.post(
            f"/mini-app/drafts/{draft_id}/confirm", headers={"Idempotency-Key": "s5-pg-confirm"},
            json={"expected_version": 1},
        )
        replay = owner.post(
            f"/mini-app/drafts/{draft_id}/confirm", headers={"Idempotency-Key": "s5-pg-confirm"},
            json={"expected_version": 1},
        )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert "private-trace" not in first.text
    with stage06_postgres.session_factory() as session:
        draft = session.get(RecordChangeDraft, UUID(draft_id))
        record = SqlAlchemyStage06PlatformUnitOfWork(session).get_record(UUID(record_id))
        assert draft is not None and record is not None
        assert (draft.status, draft.version, draft.terminal_audit_event_id) == ("confirmed", 2, UUID(first.json()["terminal_audit_event_id"]))
        assert record.values == {"title": "After"}
        assert record.version == 2
        assert session.scalar(select(func.count()).select_from(OpsAuditEvent).where(
            OpsAuditEvent.event_type == "stage07.record_change_draft_confirmed"
        )) == 1


def test_s5_reject_postgres_replays_without_writing_the_record(
    stage06_postgres: Stage06Postgres,
) -> None:
    draft_id, record_id = _create_pending_update_draft(stage06_postgres, owner_id="s5-reject-owner")
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage06_postgres.session_factory)

    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = "s5-reject-owner"
        first = owner.post(
            f"/mini-app/drafts/{draft_id}/reject",
            headers={"Idempotency-Key": "s5-pg-reject"},
            json={"expected_version": 1},
        )
        replay = owner.post(
            f"/mini-app/drafts/{draft_id}/reject",
            headers={"Idempotency-Key": "s5-pg-reject"},
            json={"expected_version": 1},
        )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    with stage06_postgres.session_factory() as session:
        draft = session.get(RecordChangeDraft, UUID(draft_id))
        record = SqlAlchemyStage06PlatformUnitOfWork(session).get_record(UUID(record_id))
        assert draft is not None and record is not None
        assert (draft.status, draft.version) == ("rejected", 2)
        assert draft.terminal_audit_event_id == UUID(first.json()["terminal_audit_event_id"])
        assert record.values == {"title": "Before"}
        assert record.version == 1
        assert session.scalar(select(func.count()).select_from(OpsAuditEvent).where(
            OpsAuditEvent.event_type == "stage07.record_change_draft_rejected"
        )) == 1


def test_s5_confirm_postgres_locks_second_command_and_rolls_back_its_ledger(
    stage06_postgres: Stage06Postgres,
) -> None:
    draft_id, record_id = _create_pending_update_draft(stage06_postgres, owner_id="s5-concurrent-owner")
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage06_postgres.session_factory)
    barrier = Barrier(2)

    def confirm(idempotency_key: str) -> tuple[int, str | None]:
        with TestClient(app) as owner:
            owner.headers["X-Stage06-User-Id"] = "s5-concurrent-owner"
            barrier.wait()
            response = owner.post(
                f"/mini-app/drafts/{draft_id}/confirm",
                headers={"Idempotency-Key": idempotency_key},
                json={"expected_version": 1},
            )
            detail = response.json().get("detail")
            return response.status_code, None if not isinstance(detail, dict) else detail.get("code")

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(confirm, ["s5-pg-confirm-a", "s5-pg-confirm-b"]))

    assert sorted(status for status, _code in outcomes) == [200, 409]
    assert any(
        code == "record_change_draft_invalid_state" for _status, code in outcomes
    ), outcomes
    with stage06_postgres.session_factory() as session:
        draft = session.get(RecordChangeDraft, UUID(draft_id))
        record = SqlAlchemyStage06PlatformUnitOfWork(session).get_record(UUID(record_id))
        assert draft is not None and record is not None
        assert (draft.status, draft.version) == ("confirmed", 2)
        assert record.values == {"title": "After"}
        assert record.version == 2
        assert session.scalar(select(func.count()).select_from(OpsAuditEvent).where(
            OpsAuditEvent.event_type == "stage07.record_change_draft_confirmed"
        )) == 1
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord).where(
            Stage06IdempotencyRecord.operation == "stage07.s5.draft.confirm"
        )) == 1


def test_s5_postgres_runtime_failure_releases_the_draft_invocation_key(
    stage06_postgres: Stage06Postgres,
    monkeypatch,
) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage06_postgres.session_factory)
    owner_id = "s5-runtime-retry-owner"
    suffix = uuid4().hex[:8]
    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = owner_id
        workspace_id = owner.post(
            "/workspaces", json={"name": "S5 runtime retry", "owner_user_id": owner_id}
        ).json()["id"]
        base_id = owner.post(f"/workspaces/{workspace_id}/bases", json={"name": "Ops"}).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables", json={"name": "Tasks", "key": f"tasks_{suffix}"}
        ).json()["id"]
        owner.post(
            f"/tables/{table_id}/fields", json={"name": "Title", "key": "title", "field_type": "text"}
        )
        record_id = owner.post(
            f"/tables/{table_id}/records", json={"values": {"title": "Before"}}
        ).json()["id"]
        view_id = owner.post(
            f"/bases/{base_id}/views",
            json={"table_id": table_id, "name": "Current tasks", "view_type": "grid", "config": {"fields": ["title"]}},
        ).json()["id"]

    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        employee = create_digital_employee(
            uow,
            UUID(base_id),
            name="Draft retry assistant",
            description="Creates controlled drafts only.",
            telegram_alias=None,
            accessible_tables=[table_id],
            accessible_views=[view_id],
            allowed_actions=["draft_update"],
            actor=Actor(actor_type="user", actor_id=owner_id, role="owner"),
        )
        session.commit()
        employee_id = str(employee.id)

    calls = 0

    def runtime_unavailable(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise PlatformValidationError("openrouter_runtime_error", "private provider failure")

    monkeypatch.setattr(draft_employee_hub_routes, "invoke_digital_employee", runtime_unavailable)
    payload = {
        "intent": "draft_update",
        "base_id": base_id,
        "view_id": view_id,
        "record_id": record_id,
    }
    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = owner_id
        first = owner.post(
            f"/mini-app/digital-employees/{employee_id}/invocations",
            headers={"Idempotency-Key": "s5-pg-runtime-retry"},
            json=payload,
        )
        retry = owner.post(
            f"/mini-app/digital-employees/{employee_id}/invocations",
            headers={"Idempotency-Key": "s5-pg-runtime-retry"},
            json=payload,
        )

    assert first.status_code == retry.status_code == 422
    assert first.json()["detail"]["code"] == retry.json()["detail"]["code"] == "openrouter_runtime_error"
    assert calls == 2
    assert "private provider failure" not in (first.text + retry.text)
    with stage06_postgres.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord).where(
            Stage06IdempotencyRecord.operation == "stage07.s5.digital_employee.draft_update"
        )) == 0


def _create_pending_update_draft(
    stage06_postgres: Stage06Postgres,
    *,
    owner_id: str,
) -> tuple[str, str]:
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(stage06_postgres.session_factory)
    with TestClient(app) as owner:
        owner.headers["X-Stage06-User-Id"] = owner_id
        workspace_id = owner.post(
            "/workspaces", json={"name": "S5 postgres", "owner_user_id": owner_id}
        ).json()["id"]
        base_id = owner.post(f"/workspaces/{workspace_id}/bases", json={"name": "Ops"}).json()["id"]
        table_id = owner.post(
            f"/bases/{base_id}/tables", json={"name": "Tasks", "key": f"tasks_{uuid4().hex[:8]}"}
        ).json()["id"]
        owner.post(f"/tables/{table_id}/fields", json={"name": "Title", "key": "title", "field_type": "text"})
        record_id = owner.post(f"/tables/{table_id}/records", json={"values": {"title": "Before"}}).json()["id"]

    with stage06_postgres.session_factory() as session:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        record = uow.get_record(UUID(record_id))
        assert record is not None
        draft = RecordChangeDraft(
            id=uuid4(), workspace_id=UUID(workspace_id), base_id=UUID(base_id), table_id=UUID(table_id),
            record_id=record.id, draft_type="update_record", proposed_values={"title": "After"},
            before_values={"title": "Before"}, created_by_type="digital_employee", created_by_id="private",
            status="pending_confirmation", confirmation_policy={}, trace_id="private-trace",
            expected_version=record.version, version=1,
        )
        session.add(draft)
        session.commit()
        return str(draft.id), record_id
