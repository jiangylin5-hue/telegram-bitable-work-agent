from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_system_actor
from app.api.routes.telegram_bindings import get_telegram_binding_uow
from app.main import create_app
from app.models.telegram import TelegramCustomerBinding
from app.schemas.telegram_bindings import TelegramBindingCreate
from app.services.telegram_binding_management import InMemoryTelegramBindingUnitOfWork
from app.services.permissions import Actor, can_perform_action


def test_manager_can_manage_telegram_bindings_and_test_sends() -> None:
    actor = Actor(actor_type="operator", actor_id="manager-1", role="manager")

    assert can_perform_action(actor, "manage_telegram_binding")
    assert can_perform_action(actor, "request_test_telegram_send")
    assert can_perform_action(actor, "confirm_test_telegram_send")


def test_sales_cannot_manage_telegram_bindings_or_test_sends() -> None:
    actor = Actor(actor_type="operator", actor_id="sales-1", role="sales")

    assert not can_perform_action(actor, "manage_telegram_binding")
    assert not can_perform_action(actor, "request_test_telegram_send")
    assert not can_perform_action(actor, "confirm_test_telegram_send")


def test_binding_create_schema_requires_chat_id_for_chat_scope() -> None:
    payload = {
        "customer_id": str(uuid4()),
        "binding_scope": "chat",
        "telegram_chat_id": "stage04-chat",
        "label": "Stage04 test chat",
        "created_by": "manager-1",
    }

    binding = TelegramBindingCreate.model_validate(payload)

    assert binding.telegram_chat_id == "stage04-chat"
    assert binding.telegram_user_id is None


def test_binding_create_schema_rejects_missing_scope_identifier() -> None:
    with pytest.raises(ValidationError):
        TelegramBindingCreate.model_validate(
            {
                "customer_id": str(uuid4()),
                "binding_scope": "chat_user",
                "telegram_chat_id": "stage04-chat",
                "created_by": "manager-1",
            }
        )


def test_binding_api_manager_can_create_list_and_disable_binding() -> None:
    app = create_app()
    customer_id = uuid4()
    uow = InMemoryTelegramBindingUnitOfWork(customer_ids={customer_id})
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        create_response = client.post(
            "/telegram/bindings",
            json={
                "customer_id": str(customer_id),
                "binding_scope": "chat",
                "telegram_chat_id": "stage04-chat",
                "label": "Stage04 test chat",
            },
        )
        list_response = client.get(
            f"/telegram/bindings?customer_id={customer_id}&status=active"
        )
        binding_id = create_response.json()["binding_id"]
        disable_response = client.post(
            f"/telegram/bindings/{binding_id}/disable",
            json={"reason": "wrong customer selected"},
        )

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "created"
    assert create_response.json()["customer_id"] == str(customer_id)
    assert list_response.status_code == 200
    assert list_response.json()["bindings"][0]["binding_id"] == binding_id
    assert disable_response.status_code == 200
    assert disable_response.json() == {"status": "disabled", "binding_id": binding_id}
    assert uow.bindings[0].status == "inactive"
    assert [event.event_type for event in uow.audit_events] == [
        "telegram.binding.created",
        "telegram.binding.disabled",
    ]
    assert uow.committed is True


def test_binding_api_sales_create_is_forbidden_and_audited() -> None:
    app = create_app()
    customer_id = uuid4()
    uow = InMemoryTelegramBindingUnitOfWork(customer_ids={customer_id})
    actor = Actor(actor_type="user", actor_id="sales-1", role="sales")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.post(
            "/telegram/bindings",
            json={
                "customer_id": str(customer_id),
                "binding_scope": "chat",
                "telegram_chat_id": "stage04-chat",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "sales cannot perform manage_telegram_binding"
    assert uow.bindings == []
    assert uow.audit_events[0].event_type == "permission_denied"
    assert uow.committed is True


def test_binding_api_unknown_customer_is_rejected_before_create() -> None:
    app = create_app()
    unknown_customer_id = uuid4()
    uow = InMemoryTelegramBindingUnitOfWork(customer_ids=set())
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.post(
            "/telegram/bindings",
            json={
                "customer_id": str(unknown_customer_id),
                "binding_scope": "chat",
                "telegram_chat_id": "stage04-chat",
            },
        )

    assert response.status_code == 404
    assert str(unknown_customer_id) in response.json()["detail"]
    assert uow.bindings == []
    assert uow.audit_events == []
    assert uow.committed is False


def test_binding_api_sales_list_is_forbidden_and_audited() -> None:
    app = create_app()
    uow = InMemoryTelegramBindingUnitOfWork()
    actor = Actor(actor_type="user", actor_id="sales-1", role="sales")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.get("/telegram/bindings?status=active")

    assert response.status_code == 403
    assert response.json()["detail"] == "sales cannot perform manage_telegram_binding"
    assert uow.audit_events[0].event_type == "permission_denied"
    assert uow.audit_events[0].permission_snapshot["action"] == (
        "manage_telegram_binding"
    )
    assert uow.committed is True


def test_binding_api_list_filters_by_telegram_ids_and_empty_result() -> None:
    app = create_app()
    customer_id = uuid4()
    other_customer_id = uuid4()
    now = datetime.now(timezone.utc)
    matching_binding = TelegramCustomerBinding(
        id=uuid4(),
        customer_id=customer_id,
        telegram_chat_id="stage04-chat",
        telegram_user_id="stage04-user",
        binding_scope="chat_user",
        status="active",
        label="Matching binding",
        created_by="manager-1",
        created_at=now,
        updated_at=now,
    )
    non_matching_binding = TelegramCustomerBinding(
        id=uuid4(),
        customer_id=other_customer_id,
        telegram_chat_id="other-chat",
        telegram_user_id="other-user",
        binding_scope="chat_user",
        status="active",
        label="Other binding",
        created_by="manager-1",
        created_at=now,
        updated_at=now,
    )
    uow = InMemoryTelegramBindingUnitOfWork(
        bindings=[matching_binding, non_matching_binding],
        customer_ids={customer_id, other_customer_id},
    )
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        match_response = client.get(
            "/telegram/bindings"
            "?telegram_chat_id=stage04-chat"
            "&telegram_user_id=stage04-user"
            "&status=active"
        )
        empty_response = client.get("/telegram/bindings?telegram_chat_id=missing-chat")

    assert match_response.status_code == 200
    assert [row["binding_id"] for row in match_response.json()["bindings"]] == [
        str(matching_binding.id)
    ]
    assert empty_response.status_code == 200
    assert empty_response.json() == {"bindings": []}
    assert uow.audit_events == []
    assert uow.committed is False


def test_binding_api_list_rejects_invalid_status_filter() -> None:
    app = create_app()
    uow = InMemoryTelegramBindingUnitOfWork()
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.get("/telegram/bindings?status=archived")

    assert response.status_code == 422
    assert uow.audit_events == []
    assert uow.committed is False


def test_binding_api_sales_disable_is_forbidden_and_audited() -> None:
    app = create_app()
    customer_id = uuid4()
    binding_id = uuid4()
    now = datetime.now(timezone.utc)
    binding = TelegramCustomerBinding(
        id=binding_id,
        customer_id=customer_id,
        telegram_chat_id="stage04-chat",
        telegram_user_id=None,
        binding_scope="chat",
        status="active",
        label="Stage04 test chat",
        created_by="manager-1",
        created_at=now,
        updated_at=now,
    )
    uow = InMemoryTelegramBindingUnitOfWork(
        bindings=[binding],
        customer_ids={customer_id},
    )
    actor = Actor(actor_type="user", actor_id="sales-1", role="sales")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/bindings/{binding_id}/disable",
            json={"reason": "not allowed"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "sales cannot perform manage_telegram_binding"
    assert binding.status == "active"
    assert uow.audit_events[0].event_type == "permission_denied"
    assert uow.audit_events[0].permission_snapshot["action"] == (
        "manage_telegram_binding"
    )
    assert uow.committed is True


def test_binding_api_disable_missing_binding_returns_stable_error() -> None:
    app = create_app()
    uow = InMemoryTelegramBindingUnitOfWork()
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/bindings/{uuid4()}/disable",
            json={"reason": "missing"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "telegram_binding_not_found",
            "message": "Telegram binding not found",
        }
    }


def test_binding_api_inactive_binding_does_not_block_new_active_binding() -> None:
    app = create_app()
    customer_id = uuid4()
    now = datetime.now(timezone.utc)
    inactive_binding = TelegramCustomerBinding(
        id=uuid4(),
        customer_id=customer_id,
        telegram_chat_id="stage04-chat",
        telegram_user_id="stage04-user",
        binding_scope="chat_user",
        status="inactive",
        label="Old inactive binding",
        created_by="manager-1",
        created_at=now,
        updated_at=now,
    )
    uow = InMemoryTelegramBindingUnitOfWork(
        bindings=[inactive_binding],
        customer_ids={customer_id},
    )
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.post(
            "/telegram/bindings",
            json={
                "customer_id": str(customer_id),
                "binding_scope": "chat_user",
                "telegram_chat_id": "stage04-chat",
                "telegram_user_id": "stage04-user",
                "label": "Replacement binding",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "created"
    assert len(uow.bindings) == 2
    assert uow.bindings[0].status == "inactive"
    assert uow.bindings[1].status == "active"
    assert uow.audit_events[-1].event_type == "telegram.binding.created"


def test_binding_api_disable_inactive_binding_is_idempotent_state_set() -> None:
    app = create_app()
    customer_id = uuid4()
    binding_id = uuid4()
    now = datetime.now(timezone.utc)
    binding = TelegramCustomerBinding(
        id=binding_id,
        customer_id=customer_id,
        telegram_chat_id="stage04-chat",
        telegram_user_id=None,
        binding_scope="chat",
        status="inactive",
        label="Already inactive",
        created_by="manager-1",
        created_at=now,
        updated_at=now,
    )
    uow = InMemoryTelegramBindingUnitOfWork(
        bindings=[binding],
        customer_ids={customer_id},
    )
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    with TestClient(app) as client:
        response = client.post(
            f"/telegram/bindings/{binding_id}/disable",
            json={"reason": "repeat disable"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "disabled", "binding_id": str(binding_id)}
    assert binding.status == "inactive"
    assert uow.audit_events[0].event_type == "telegram.binding.disabled"
    assert uow.audit_events[0].before_state["status"] == "inactive"
    assert uow.audit_events[0].after_state["status"] == "inactive"


def test_binding_api_rejects_active_conflict() -> None:
    app = create_app()
    customer_id = uuid4()
    uow = InMemoryTelegramBindingUnitOfWork(customer_ids={customer_id})
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")
    app.dependency_overrides[get_telegram_binding_uow] = lambda: uow
    app.dependency_overrides[get_system_actor] = lambda: actor

    payload = {
        "customer_id": str(customer_id),
        "binding_scope": "chat_user",
        "telegram_chat_id": "stage04-chat",
        "telegram_user_id": "stage04-user",
    }

    with TestClient(app) as client:
        first_response = client.post("/telegram/bindings", json=payload)
        conflict_response = client.post("/telegram/bindings", json=payload)

    assert first_response.status_code == 200
    assert conflict_response.status_code == 409
    assert conflict_response.json() == {
        "error": {
            "code": "telegram_binding_conflict",
            "message": "Active Telegram binding already exists",
        }
    }
    assert len(uow.bindings) == 1
    assert uow.audit_events[-1].event_type == "telegram.binding.create_conflict"
