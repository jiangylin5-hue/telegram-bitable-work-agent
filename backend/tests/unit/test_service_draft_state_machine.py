from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import raises

from app.api.routes.confirmations import get_confirmation_uow
from app.main import create_app
from app.models.service_drafts import ServiceDraft
from app.services.confirmation import (
    InMemoryConfirmationUnitOfWork,
    SqlAlchemyConfirmationUnitOfWork,
    confirm_service_draft,
    escalate_service_draft,
    reject_service_draft,
    request_more_info_for_service_draft,
)
from app.services.execution_tickets import TicketStateError, use_execution_ticket
from app.services.permissions import Actor, PermissionDenied


class FakeSqlAlchemySession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.objects_by_key: dict[tuple[type, object], object] = {}

    def add(self, value: object) -> None:
        self.added.append(value)

    def get(self, model: type, object_id: object) -> object | None:
        return self.objects_by_key.get((model, object_id))


def make_recharge_draft() -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type="recharge",
        status="pending_confirmation",
        customer_id=uuid4(),
        source_message_id=uuid4(),
        created_by_type="agent",
        created_by_id="mock_router",
        payload={"account_id": "act_1001", "amount": "1000", "currency": "USD"},
        missing_fields=[],
        risk_flags=[],
        confidence=Decimal("0.9000"),
        trace_id="trace-1",
        idempotency_key="draft:message-1:recharge",
    )


def test_default_confirmation_dependency_uses_sqlalchemy_uow() -> None:
    session = FakeSqlAlchemySession()

    uow = get_confirmation_uow(session=session)

    assert isinstance(uow, SqlAlchemyConfirmationUnitOfWork)
    assert uow.session is session


def test_sqlalchemy_confirmation_uow_reads_draft_and_writes_confirmation_records() -> None:
    draft = make_recharge_draft()
    session = FakeSqlAlchemySession()
    session.objects_by_key[(ServiceDraft, draft.id)] = draft
    uow = SqlAlchemyConfirmationUnitOfWork(session)
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")

    result = confirm_service_draft(uow, draft.id, actor)

    assert draft.status == "confirmed"
    assert result.service_record in session.added
    assert result.execution_ticket in session.added
    assert session.added[-1].event_type == "draft_confirmed"


def test_agent_cannot_confirm_draft_and_denial_writes_audit() -> None:
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    actor = Actor(actor_type="agent", actor_id="mock_router", role="agent")

    with raises(PermissionDenied):
        confirm_service_draft(uow, draft.id, actor)

    assert draft.status == "pending_confirmation"
    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.audit_events[0].event_type == "permission_denied"


def test_production_confirmation_creates_service_record_and_ticket() -> None:
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")

    result = confirm_service_draft(uow, draft.id, actor)

    assert draft.status == "confirmed"
    assert result.service_record.service_type == "recharge"
    assert result.service_record.status == "pending"
    assert result.execution_ticket.status == "issued"
    assert result.execution_ticket.allowed_action == "execution.recharge"
    assert result.execution_ticket.idempotency_key.startswith("ticket:")
    assert uow.audit_events[-1].event_type == "draft_confirmed"


def test_execution_ticket_can_only_be_used_once() -> None:
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")
    result = confirm_service_draft(uow, draft.id, actor)

    use_execution_ticket(result.execution_ticket)

    assert result.execution_ticket.status == "used"
    with raises(TicketStateError):
        use_execution_ticket(result.execution_ticket)


def test_reject_path_does_not_create_service_record_or_ticket() -> None:
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")

    rejected = reject_service_draft(uow, draft.id, actor, reason="customer cancelled")

    assert rejected.status == "rejected"
    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.audit_events[-1].event_type == "draft_rejected"


def test_request_more_info_moves_draft_back_to_needs_more_info() -> None:
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="customer_service")

    updated = request_more_info_for_service_draft(
        uow,
        draft.id,
        actor,
        missing_fields=["account_id"],
    )

    assert updated.status == "needs_more_info"
    assert updated.missing_fields == ["account_id"]
    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.audit_events[-1].event_type == "draft_more_info_requested"


def test_escalate_path_moves_draft_to_manual_review() -> None:
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    actor = Actor(actor_type="agent", actor_id="mock_router", role="agent")

    escalated = escalate_service_draft(uow, draft.id, actor, reason="low confidence")

    assert escalated.status == "manual_review"
    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.audit_events[-1].event_type == "draft_escalated"


def test_confirmation_api_can_reject_draft() -> None:
    app = create_app()
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    app.dependency_overrides[get_confirmation_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.post(
            f"/confirmations/service-drafts/{draft.id}/actions",
            json={
                "action": "reject",
                "actor_type": "user",
                "actor_id": str(uuid4()),
                "role": "production",
                "reason": "customer cancelled",
            },
        )

    assert response.status_code == 200
    assert response.json()["draft_status"] == "rejected"
    assert draft.status == "rejected"


def test_confirmation_api_commits_successful_action() -> None:
    app = create_app()
    draft = make_recharge_draft()
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])
    app.dependency_overrides[get_confirmation_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.post(
            f"/confirmations/service-drafts/{draft.id}/actions",
            json={
                "action": "confirm",
                "actor_type": "user",
                "actor_id": str(uuid4()),
                "role": "production",
            },
        )

    assert response.status_code == 200
    assert response.json()["draft_status"] == "confirmed"
    assert uow.committed is True
