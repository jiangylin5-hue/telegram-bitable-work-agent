from decimal import Decimal
from datetime import UTC, datetime
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
            "risk_flags": [],
            "confidence": "0.9000",
            "created_by_type": "agent",
            "created_by_id": "mock_router",
            "source_message_id": str(pending.source_message_id),
            "created_at": "2026-07-07T00:00:00Z",
        }
    ]


def test_service_drafts_api_filters_by_stage05_query_fields() -> None:
    app = create_app()
    customer_id = uuid4()
    message_id = uuid4()
    matching = make_draft(
        status="pending_confirmation",
        draft_type="customer_reply",
        customer_id=customer_id,
        source_message_id=message_id,
        trace_id="trace-stage05-match",
    )
    wrong_type = make_draft(
        status="pending_confirmation",
        draft_type="recharge",
        customer_id=customer_id,
        source_message_id=message_id,
        trace_id="trace-stage05-match",
    )
    wrong_customer = make_draft(
        status="pending_confirmation",
        draft_type="customer_reply",
        source_message_id=message_id,
        trace_id="trace-stage05-match",
    )
    uow = InMemoryServiceDraftUnitOfWork()
    uow.service_drafts.extend([matching, wrong_type, wrong_customer])
    app.dependency_overrides[get_service_draft_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get(
            "/service-drafts",
            params={
                "status": "pending_confirmation",
                "draft_type": "customer_reply",
                "customer_id": str(customer_id),
                "source_message_id": str(message_id),
                "trace_id": "trace-stage05-match",
            },
        )

    assert response.status_code == 200
    records = response.json()["records"]
    assert [record["id"] for record in records] == [str(matching.id)]


def test_service_drafts_api_response_exposes_stage05_operational_fields_only() -> None:
    app = create_app()
    draft = make_draft(
        status="manual_review",
        draft_type="card_binding",
        risk_flags=["sensitive_payment_data_detected"],
    )
    draft.created_by_id = "card_binding_draft_agent"
    uow = InMemoryServiceDraftUnitOfWork()
    uow.service_drafts.append(draft)
    app.dependency_overrides[get_service_draft_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get("/service-drafts")

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["risk_flags"] == ["sensitive_payment_data_detected"]
    assert record["confidence"] == "0.9000"
    assert record["created_by_type"] == "agent"
    assert record["created_by_id"] == "card_binding_draft_agent"
    assert record["source_message_id"] == str(draft.source_message_id)
    assert record["created_at"] == "2026-07-07T00:00:00Z"
    assert "raw_prompt" not in record
    assert "raw_response" not in record
    assert "full_prompt" not in record
    assert "full_response" not in record


def test_service_drafts_api_supports_limit_contract() -> None:
    app = create_app()
    first = make_draft(status="pending_confirmation", draft_type="recharge")
    second = make_draft(status="pending_confirmation", draft_type="customer_reply")
    uow = InMemoryServiceDraftUnitOfWork()
    uow.service_drafts.extend([first, second])
    app.dependency_overrides[get_service_draft_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.get("/service-drafts?limit=1")

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [str(first.id)]


def make_draft(
    *,
    status: str,
    draft_type: str,
    customer_id=None,
    source_message_id=None,
    trace_id: str = "trace-draft",
    risk_flags: list[str] | None = None,
) -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type=draft_type,
        status=status,
        customer_id=customer_id or uuid4(),
        source_message_id=source_message_id or uuid4(),
        created_by_type="agent",
        created_by_id="mock_router",
        payload={"account_id": "act_1001", "amount": "1000", "currency": "USD"},
        missing_fields=[],
        risk_flags=risk_flags or [],
        confidence=Decimal("0.9000"),
        trace_id=trace_id,
        idempotency_key=f"draft:{uuid4()}:{draft_type}",
        created_at=datetime(2026, 7, 7, tzinfo=UTC),
        updated_at=datetime(2026, 7, 7, tzinfo=UTC),
    )
