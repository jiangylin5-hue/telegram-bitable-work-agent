from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import Stage06TelegramBinding, WorkspaceMember
from app.runtime.stage08_memory_contracts import GroupMemoryCandidateProjection
from app.services.permissions import Actor
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork, create_workspace
from app.services.stage08_group_memory_source import (
    TrustedGroupMessageInput,
    resolve_authorized_group_message_source,
)
from app.services.stage08_memory import (
    create_group_memory_candidate,
    resolve_group_candidate,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
SECRET = "GROUP_MEMORY_API_RAW_SENTINEL"


class _MemoryApiFixture:
    def __init__(self) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        self.workspace = create_workspace(
            self.uow,
            name="Memory API",
            owner_user_id=self.owner.actor_id,
        )
        self.member = self.uow.workspace_members[0]
        self.viewer = WorkspaceMember(
            id=uuid4(),
            workspace_id=self.workspace.id,
            user_id="viewer-1",
            role="viewer",
            status="active",
            version=1,
        )
        self.uow.add_workspace_member(self.viewer)
        self.binding = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=self.workspace.id,
            workspace_member_id=self.member.id,
            telegram_chat_id="-100123456",
            telegram_user_id="998877",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        self.uow.add_telegram_binding(self.binding)
        trusted = TrustedGroupMessageInput(
            message_id=uuid4(),
            chat_id=self.binding.telegram_chat_id,
            chat_type="group",
            binding_id=self.binding.id,
        )
        source = resolve_authorized_group_message_source(self.uow, trusted)
        assert source is not None
        projection = GroupMemoryCandidateProjection(
            candidate_type="decision",
            confidence=Decimal("0.85"),
            scope=source.scope,
            normalized_payload={"decision": "approved"},
            source_refs=(source.source_ref,),
        )
        self.candidate = create_group_memory_candidate(
            self.uow,
            projection,
            source=source,
            actor=self.owner,
            now=NOW,
        )
        self.item = resolve_group_candidate(
            self.uow,
            self.candidate.id,
            actor=self.owner,
            now=NOW,
        )
        assert self.item is not None

    def client(self, user_id: str = "owner-1") -> TestClient:
        app = create_app()
        app.dependency_overrides[get_stage06_platform_uow] = lambda: self.uow
        client = TestClient(app)
        client.headers["X-Stage06-User-Id"] = user_id
        return client


def test_list_requires_workspace_read_and_never_returns_source_or_raw_fields() -> None:
    fixture = _MemoryApiFixture()

    with fixture.client() as client:
        response = client.get(
            f"/api/stage08/memory?workspace_id={fixture.workspace.id}&status=active"
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "memory_type": "decision",
                "status": "active",
                "version": 1,
                "payload": {"decision": "approved"},
                "valid_until": None,
            }
        ]
    }
    item = response.json()["items"][0]
    assert {
        "id",
        "scope",
        "source_refs",
        "group_chat_ref",
        "binding_id",
        "chat_id",
        "telegram_user_id",
    }.isdisjoint(item)
    serialized = response.text.casefold()
    for forbidden in (
        "scope",
        "source_refs",
        "group_chat_ref",
        "binding_id",
        "chat_id",
        "telegram_user_id",
        SECRET.casefold(),
    ):
        assert forbidden not in serialized


def test_foreign_workspace_is_403_and_revoke_requires_member_manage_and_version() -> None:
    fixture = _MemoryApiFixture()
    foreign = create_workspace(
        fixture.uow,
        name="Foreign",
        owner_user_id="foreign-owner",
    )
    url = f"/api/stage08/memory/extractions/{fixture.candidate.id}/revoke"

    with fixture.client() as owner_client:
        foreign_response = owner_client.get(
            f"/api/stage08/memory?workspace_id={foreign.id}"
        )
        version_conflict = owner_client.post(url, json={"expected_version": 99})
    with fixture.client("viewer-1") as viewer_client:
        forbidden = viewer_client.post(url, json={"expected_version": 2})

    assert foreign_response.status_code == 403
    assert version_conflict.status_code == 409
    assert forbidden.status_code == 403
    assert fixture.item.status == "active"


def test_manager_revoke_returns_only_safe_lifecycle_receipt() -> None:
    fixture = _MemoryApiFixture()
    url = f"/api/stage08/memory/extractions/{fixture.candidate.id}/revoke"

    with fixture.client() as client:
        response = client.post(url, json={"expected_version": 2})

    assert response.status_code == 200
    assert response.json() == {
        "candidate_status": "accepted",
        "candidate_version": 2,
        "memory_status": "revoked",
    }
    assert fixture.item.status == "revoked"
    assert "payload" not in response.text
    assert "source" not in response.text


def test_invalid_input_is_redacted_422_and_missing_candidate_is_404() -> None:
    fixture = _MemoryApiFixture()
    url = f"/api/stage08/memory/extractions/{fixture.candidate.id}/revoke"

    with fixture.client() as client:
        invalid_body = client.post(url, json={"expected_version": SECRET})
        extra_body = client.post(
            url,
            json={"expected_version": 2, "raw_text": SECRET},
        )
        invalid_query = client.get(
            f"/api/stage08/memory?workspace_id={SECRET}&status=revoked"
        )
        invalid_path = client.post(
            f"/api/stage08/memory/extractions/{SECRET}/revoke",
            json={"expected_version": 1},
        )
        missing = client.post(
            f"/api/stage08/memory/extractions/{uuid4()}/revoke",
            json={"expected_version": 1},
        )

    for response in (invalid_body, extra_body, invalid_query, invalid_path):
        assert response.status_code == 422
        assert response.json() == {
            "detail": {
                "code": "stage08_memory_request_invalid",
                "message": "stage08_memory_request_invalid",
            }
        }
        assert SECRET.casefold() not in response.text.casefold()
        assert "raw_text" not in response.text.casefold()
    assert missing.status_code == 404


def test_list_deletes_corrupt_group_payload_and_never_exposes_identity_carrier() -> None:
    fixture = _MemoryApiFixture()
    fixture.item.payload = {"group_chat_ref": SECRET}

    with fixture.client() as client:
        response = client.get(
            f"/api/stage08/memory?workspace_id={fixture.workspace.id}"
        )

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert SECRET.casefold() not in response.text.casefold()
    assert fixture.item.status == "deleted"


def test_list_deletes_corrupt_group_payload_and_never_exposes_telegram_transport() -> None:
    fixture = _MemoryApiFixture()
    fixture.item.payload = {"decision": {"telegram_update_id": SECRET}}

    with fixture.client() as client:
        response = client.get(
            f"/api/stage08/memory?workspace_id={fixture.workspace.id}"
        )

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert SECRET.casefold() not in response.text.casefold()
    assert fixture.item.status == "deleted"


def test_expired_accepted_candidate_revoke_returns_fixed_409_and_keeps_item() -> None:
    fixture = _MemoryApiFixture()
    fixture.candidate.valid_until = datetime(2020, 1, 1, tzinfo=UTC)
    url = f"/api/stage08/memory/extractions/{fixture.candidate.id}/revoke"

    with fixture.client() as client:
        response = client.post(url, json={"expected_version": 2})

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "memory_candidate_expired",
            "message": "memory_candidate_expired",
        }
    }
    assert fixture.candidate.status == "expired"
    assert fixture.item.status == "active"


def test_api_stale_version_precedes_ttl_expiry_without_mutation() -> None:
    fixture = _MemoryApiFixture()
    fixture.candidate.valid_until = datetime(2020, 1, 1, tzinfo=UTC)
    url = f"/api/stage08/memory/extractions/{fixture.candidate.id}/revoke"
    audit_count = len(fixture.uow.audit_events)
    reviewed_at = fixture.candidate.reviewed_at
    reviewed_by_user_id = fixture.candidate.reviewed_by_user_id
    item_version = fixture.item.version

    with fixture.client() as client:
        stale = client.post(url, json={"expected_version": 99})

    assert stale.status_code == 409
    assert stale.json() == {
        "detail": {
            "code": "memory_candidate_version_conflict",
            "message": "memory_candidate_version_conflict",
        }
    }
    assert fixture.candidate.status == "accepted"
    assert fixture.candidate.version == 2
    assert fixture.candidate.reviewed_at == reviewed_at
    assert fixture.candidate.reviewed_by_user_id == reviewed_by_user_id
    assert fixture.item.status == "active"
    assert fixture.item.version == item_version
    assert fixture.item.revoked_at is None
    assert len(fixture.uow.audit_events) == audit_count

    with fixture.client() as client:
        current = client.post(url, json={"expected_version": 2})

    assert current.status_code == 409
    assert current.json() == {
        "detail": {
            "code": "memory_candidate_expired",
            "message": "memory_candidate_expired",
        }
    }
    assert fixture.candidate.status == "expired"
    assert fixture.candidate.version == 3
    assert fixture.item.status == "active"
