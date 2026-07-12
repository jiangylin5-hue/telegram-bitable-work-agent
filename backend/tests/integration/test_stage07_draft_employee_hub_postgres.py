from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import get_session
from app.main import create_app
from app.models.audit import OpsAuditEvent
from app.models.stage06_runtime import RecordChangeDraft
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
