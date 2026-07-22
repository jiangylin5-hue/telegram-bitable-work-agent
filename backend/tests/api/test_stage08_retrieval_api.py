from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4
import warnings

import pytest
from starlette.exceptions import StarletteDeprecationWarning

warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_memory import materialize_memory_from_projection
from app.services.stage08_retrieval import register_memory_knowledge_source


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
PATH = "/api/stage08/knowledge/reindex"
INVALID_DETAIL = {
    "detail": {
        "code": "stage08_retrieval_request_invalid",
        "message": "stage08_retrieval_request_invalid",
    }
}


class _RetrievalApiFixture:
    def __init__(self) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        self.workspace = create_workspace(
            self.uow,
            name="Retrieval API",
            owner_user_id=self.owner.actor_id,
        )
        self.base = create_base(self.uow, self.workspace.id, name="CRM")
        self.table = create_table(
            self.uow,
            self.base.id,
            name="Customers",
            key="customers",
        )
        create_field(
            self.uow,
            self.table.id,
            name="Decision",
            key="decision",
            field_type="text",
        )
        self.record = create_record(
            self.uow,
            self.table.id,
            values={"decision": "approved"},
            actor=self.owner,
        )
        item = materialize_memory_from_projection(
            self.uow,
            MemoryMaterializationProjection(
                memory_type="decision",
                scope=MemoryScopeProjection(
                    workspace_id=self.workspace.id,
                    base_id=self.base.id,
                    table_id=self.table.id,
                ),
                payload={"decision": "approved"},
                source_refs=(
                    MemorySourceRef(
                        source_kind="platform_record",
                        source_id=self.record.id,
                        source_version=self.record.version,
                        field_keys=("decision",),
                    ),
                ),
            ),
            actor=self.owner,
            now=NOW,
        )
        self.registration = register_memory_knowledge_source(
            self.uow,
            item.id,
            actor=self.owner,
            now=NOW,
            trace_id="registration-trace",
        )
        assert self.registration is not None
        for role in ("admin", "builder", "operator", "viewer", "manager"):
            self.uow.add_workspace_member(
                WorkspaceMember(
                    id=uuid4(),
                    workspace_id=self.workspace.id,
                    user_id=f"{role}-1",
                    role=role,
                    status="active",
                    version=1,
                )
            )

    def client(self, user_id: str | None = "owner-1") -> TestClient:
        app = create_app()
        app.dependency_overrides[get_stage06_platform_uow] = lambda: self.uow
        client = TestClient(app)
        if user_id is not None:
            client.headers["X-Stage06-User-Id"] = user_id
        return client

    def payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "workspace_id": str(self.workspace.id),
            "knowledge_source_id": str(self.registration.source.id),
            "idempotency_key": "reindex-api-1",
            "trace_id": "reindex-api-trace-1",
        }
        payload.update(overrides)
        return payload


def test_reindex_api_owner_and_admin_receive_only_safe_receipt() -> None:
    fixture = _RetrievalApiFixture()

    with fixture.client("owner-1") as client:
        owner = client.post(PATH, json=fixture.payload())
    with fixture.client("admin-1") as client:
        admin = client.post(
            PATH,
            json=fixture.payload(
                idempotency_key="reindex-api-admin",
                trace_id="reindex-api-admin-trace",
            ),
        )

    for response in (owner, admin):
        assert response.status_code == 202
        assert set(response.json()) == {"ticket_id", "status"}
        assert response.json()["status"] == "accepted"
        serialized = response.text.casefold()
        for forbidden in (
            "knowledge_source_id",
            "projection",
            "chunk",
            "embedding",
            "query",
            "scope",
            "actor",
            "authority",
            "audit",
        ):
            assert forbidden not in serialized


@pytest.mark.parametrize("user_id", ["builder-1", "operator-1", "viewer-1", "manager-1", "outsider-1"])
def test_reindex_api_fails_closed_for_non_manager_members(user_id: str) -> None:
    fixture = _RetrievalApiFixture()

    with fixture.client(user_id) as client:
        response = client.post(PATH, json=fixture.payload())

    assert response.status_code == 403
    assert fixture.uow.idempotency_records == []


def test_reindex_api_anonymous_missing_and_cross_workspace_are_non_disclosing() -> None:
    fixture = _RetrievalApiFixture()
    foreign = create_workspace(
        fixture.uow,
        name="Foreign",
        owner_user_id="foreign-owner",
    )

    with fixture.client(None) as client:
        anonymous = client.post(PATH, json=fixture.payload())
    with fixture.client() as client:
        missing = client.post(
            PATH,
            json=fixture.payload(knowledge_source_id=str(uuid4())),
        )
        cross_workspace = client.post(
            PATH,
            json=fixture.payload(workspace_id=str(foreign.id)),
        )

    assert anonymous.status_code == 401
    assert missing.status_code == 403
    assert cross_workspace.status_code == 403


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "projection_text",
        "chunk_text",
        "embedding",
        "query",
        "filter",
        "scope",
        "source_type",
        "source_status",
        "ticket_status",
        "actor",
        "role",
        "carrier",
    ],
)
def test_reindex_api_rejects_forbidden_fields_with_redacted_422(
    forbidden_field: str,
) -> None:
    fixture = _RetrievalApiFixture()
    sentinel = "REINDEX_API_PRIVATE_SENTINEL"

    with fixture.client() as client:
        response = client.post(
            PATH,
            json={**fixture.payload(), forbidden_field: {"raw_text": sentinel}},
        )

    assert response.status_code == 422
    assert response.json() == INVALID_DETAIL
    text = response.text.casefold()
    assert sentinel.casefold() not in text
    assert forbidden_field.casefold() not in text
    assert fixture.uow.idempotency_records == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspace_id", "not-a-uuid"),
        ("knowledge_source_id", "not-a-uuid"),
        ("trace_id", "bad\ntrace"),
        ("idempotency_key", ""),
        ("idempotency_key", True),
    ],
)
def test_reindex_api_rejects_invalid_identifiers_without_echo(
    field: str,
    value: object,
) -> None:
    fixture = _RetrievalApiFixture()

    with fixture.client() as client:
        response = client.post(PATH, json=fixture.payload(**{field: value}))

    assert response.status_code == 422
    assert response.json() == INVALID_DETAIL
    assert "not-a-uuid" not in response.text
    assert "bad" not in response.text


def test_reindex_api_replay_is_stable_and_changed_trace_conflicts() -> None:
    fixture = _RetrievalApiFixture()
    payload = fixture.payload()

    with fixture.client() as client:
        first = client.post(PATH, json=payload)
        audit_count = len(fixture.uow.audit_events)
        replay = client.post(PATH, json=payload)
        conflict = client.post(
            PATH,
            json=fixture.payload(trace_id="different-trace"),
        )

    assert first.status_code == replay.status_code == 202
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert len(fixture.uow.outbox_events) == 1
    assert len(fixture.uow.idempotency_records) == 1
    assert len(fixture.uow.audit_events) == audit_count


@pytest.mark.parametrize("state", ["replaced", "revoked", "deleted", "expired"])
def test_reindex_api_rejects_non_active_source_as_fixed_409(state: str) -> None:
    fixture = _RetrievalApiFixture()
    fixture.registration.source.status = state
    fixture.registration.source.projection_text = None

    with fixture.client() as client:
        response = client.post(PATH, json=fixture.payload())

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "knowledge_reindex_source_invalid"


@pytest.mark.parametrize("source_type", ["document_projection", "approved_summary"])
def test_reindex_api_keeps_unverified_source_types_fail_closed(source_type: str) -> None:
    fixture = _RetrievalApiFixture()
    fixture.registration.source.source_type = source_type

    with fixture.client() as client:
        response = client.post(PATH, json=fixture.payload())

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "knowledge_reindex_source_invalid"
