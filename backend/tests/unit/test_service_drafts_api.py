from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.service_drafts import get_service_draft_uow
from app.main import create_app
from app.models.service_drafts import ServiceDraft
from app.services.service_drafts import (
    InMemoryServiceDraftUnitOfWork,
    SqlAlchemyServiceDraftUnitOfWork,
)


class FakeSession:
    pass


def test_default_service_draft_dependency_uses_sqlalchemy_uow() -> None:
    session = FakeSession()

    uow = get_service_draft_uow(session=session)

    assert isinstance(uow, SqlAlchemyServiceDraftUnitOfWork)
    assert uow.session is session


def test_service_drafts_api_returns_filtered_draft_queue() -> None:
    app = create_app()
    pending = make_draft(status="pending_confirmation", draft_type="recharge")
    confirmed = make_draft(status="confirmed", draft_type="recharge")
    uow = InMemoryServiceDraftUnitOfWork()
    uow.service_drafts.extend([pending, confirmed])
    app.dependency_overrides[get_service_draft_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get("/service-drafts?status=pending_confirmation")

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": str(pending.id),
            "draft_type": "recharge",
            "status": "pending_confirmation",
            "customer_id": str(pending.customer_id),
            "trace_id": "trace-draft",
            "payload": pending.payload,
            "missing_fields": [],
        }
    ]


def make_draft(*, status: str, draft_type: str) -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type=draft_type,
        status=status,
        customer_id=uuid4(),
        source_message_id=uuid4(),
        created_by_type="agent",
        created_by_id="mock_router",
        payload={"account_id": "act_1001", "amount": "1000", "currency": "USD"},
        missing_fields=[],
        risk_flags=[],
        confidence=Decimal("0.9000"),
        trace_id="trace-draft",
        idempotency_key=f"draft:{uuid4()}:{draft_type}",
    )
