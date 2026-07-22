from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_workspace,
)


def test_runtime_api_rejects_unknown_and_prompt_like_input_before_dispatch() -> None:
    fixture = _api_fixture()

    with fixture.client() as client:
        unknown = client.post(
            "/api/stage08/runtime/execute-plan",
            json={**fixture.payload(), "actor": "user:forged"},
        )
        sensitive = client.post(
            "/api/stage08/runtime/execute-plan",
            json=fixture.payload(invocations=[{"tool_name": "tool_catalog.inspect", "input": {"nested": {"prompt": "secret"}}}]),
        )

    assert unknown.status_code == 422
    assert sensitive.status_code == 422
    assert fixture.uow.execution_tickets == []


@pytest.mark.parametrize(
    ("budget_field", "invalid_value"),
    [
        ("max_tool_calls", True),
        ("max_tool_calls", 1.0),
        ("max_retrieval_chunks", False),
        ("max_retrieval_chunks", 0.0),
        ("max_retrieval_chunks", "0"),
    ],
)
def test_runtime_api_rejects_non_strict_nested_budget_values_before_dispatch(
    budget_field: str,
    invalid_value: object,
) -> None:
    fixture = _api_fixture()
    budget = fixture.payload()["budget"]
    assert isinstance(budget, dict)
    budget[budget_field] = invalid_value

    with fixture.client() as client:
        response = client.post(
            "/api/stage08/runtime/execute-plan",
            json=fixture.payload(budget=budget),
        )

    assert response.status_code == 422
    assert fixture.uow.execution_tickets == []


def test_runtime_api_validation_response_redacts_raw_invalid_request_body() -> None:
    fixture = _api_fixture()
    sentinel = "RUNTIME_VALIDATION_SECRET"

    with fixture.client() as client:
        response = client.post(
            "/api/stage08/runtime/execute-plan",
            json=fixture.payload(
                invocations=[{
                    "tool_name": "tool_catalog.inspect",
                    "input": {"nested": {"prompt": sentinel}},
                }],
            ),
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "stage08_runtime_request_invalid",
            "message": "stage08_runtime_request_invalid",
        }
    }
    response_text = response.text.casefold()
    assert sentinel.casefold() not in response_text
    assert '"body"' not in response_text
    assert '"input"' not in response_text
    assert '"ctx"' not in response_text
    assert "prompt" not in response_text
    assert "response" not in response_text
    assert "token" not in response_text
    assert "raw_text" not in response_text
    assert fixture.uow.execution_tickets == []


@pytest.mark.parametrize("forbidden_field", ["actor", "ticket_id", "state"])
def test_runtime_api_derives_actor_ticket_and_state_server_side(forbidden_field: str) -> None:
    fixture = _api_fixture()
    forbidden_value = "user:forged" if forbidden_field == "actor" else "succeeded"
    if forbidden_field == "ticket_id":
        forbidden_value = str(uuid4())

    with fixture.client() as client:
        rejected = client.post(
            "/api/stage08/runtime/execute-plan",
            json={**fixture.payload(), forbidden_field: forbidden_value},
        )
        allowed = client.post("/api/stage08/runtime/execute-plan", json=fixture.payload())

    assert rejected.status_code == 422
    assert allowed.status_code == 201
    ticket = fixture.uow.execution_tickets[0]
    assert ticket.actor_id == "user:owner-1"
    assert ticket.status == "succeeded"
    assert allowed.json()["ticket_id"] == str(ticket.id)


def test_runtime_api_rejects_wrong_workspace_before_ticket_or_gateway_dispatch() -> None:
    fixture = _api_fixture()
    foreign_workspace = create_workspace(
        fixture.uow,
        name="Foreign runtime",
        owner_user_id="foreign-owner",
        actor=fixture.owner,
    )
    foreign_base = create_base(fixture.uow, foreign_workspace.id, name="Foreign", actor=fixture.owner)
    foreign_employee = create_digital_employee(
        fixture.uow,
        foreign_base.id,
        name="Foreign employee",
        description="Foreign scope",
        telegram_alias=None,
        accessible_tables=[],
        accessible_views=[],
        allowed_actions=["tool_catalog.inspect"],
        actor=fixture.owner,
    )

    with fixture.client() as client:
        response = client.post(
            "/api/stage08/runtime/execute-plan",
            json=fixture.payload(
                workspace_id=str(foreign_workspace.id),
                employee_id=str(foreign_employee.id),
            ),
        )

    assert response.status_code == 403
    assert fixture.uow.execution_tickets == []


def test_runtime_api_executes_two_invocations_in_order_with_only_redacted_results() -> None:
    fixture = _api_fixture(actions=["contact.resolve", "tool_catalog.inspect"])
    raw_sentinel = "RUNTIME_INPUT_SECRET"

    with fixture.client() as client:
        response = client.post(
            "/api/stage08/runtime/execute-plan",
            json=fixture.payload(
                action="contact.resolve",
                invocations=[
                    {
                        "tool_name": "contact.resolve",
                        "input": {"workspace_member_id": str(fixture.owner_member.id)},
                    },
                    {
                        "tool_name": "tool_catalog.inspect",
                        "input": {},
                    },
                ],
                idempotency_key="two-invocation-key",
                trace_id="two-invocation-trace",
            ),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert [item["tool_name"] for item in body["tool_summary"]] == [
        "contact.resolve",
        "tool_catalog.inspect",
    ]
    ticket = fixture.uow.execution_tickets[0]
    assert ticket.status == "succeeded"
    assert ticket.tool_summary == body["tool_summary"]
    persisted = json.dumps(ticket.tool_summary, sort_keys=True)
    assert raw_sentinel not in response.text
    assert raw_sentinel not in persisted
    assert "workspace_member_id" not in response.text
    assert "workspace_member_id" not in persisted


def test_runtime_api_stops_after_first_denied_invocation() -> None:
    fixture = _api_fixture(actions=["contact.resolve", "tool_catalog.inspect"])

    with fixture.client() as client:
        response = client.post(
            "/api/stage08/runtime/execute-plan",
            json=fixture.payload(
                action="contact.resolve",
                invocations=[
                    {"tool_name": "contact.resolve", "input": {"workspace_member_id": "not-a-uuid"}},
                    {"tool_name": "tool_catalog.inspect", "input": {}},
                ],
            ),
        )

    assert response.status_code == 201
    assert response.json()["status"] == "denied"
    assert response.json()["tool_summary"] == [{
        "tool_name": "contact.resolve",
        "status": "denied",
        "entity_refs": [],
        "visible_field_keys": [],
        "counts": {},
        "error_code": "invalid_input",
    }]


def test_runtime_api_replay_returns_terminal_ticket_without_reexecution() -> None:
    fixture = _api_fixture()
    payload = fixture.payload(idempotency_key="replay-key", trace_id="replay-trace")

    with fixture.client() as client:
        first = client.post("/api/stage08/runtime/execute-plan", json=payload)
        audits_after_first = len(fixture.uow.audit_events)
        replay = client.post("/api/stage08/runtime/execute-plan", json=payload)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert len(fixture.uow.execution_tickets) == 1
    assert len(fixture.uow.audit_events) == audits_after_first


class _ApiFixture:
    def __init__(self, *, actions: list[str] | None = None) -> None:
        self.uow = InMemoryStage06PlatformUnitOfWork()
        self.owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
        self.workspace = create_workspace(
            self.uow,
            name="Stage08 runtime API",
            owner_user_id=self.owner.actor_id,
            actor=self.owner,
        )
        self.owner_member = self.uow.workspace_members[0]
        self.base = create_base(self.uow, self.workspace.id, name="Runtime", actor=self.owner)
        self.employee = create_digital_employee(
            self.uow,
            self.base.id,
            name="Runtime employee",
            description="Runs approved tools",
            telegram_alias=None,
            accessible_tables=[],
            accessible_views=[],
            allowed_actions=actions or ["tool_catalog.inspect"],
            actor=self.owner,
        )

    def client(self) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_stage06_platform_uow] = lambda: self.uow
        client = TestClient(app)
        client.headers["X-Stage06-User-Id"] = self.owner.actor_id
        return client

    def payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "workspace_id": str(self.workspace.id),
            "employee_id": str(self.employee.id),
            "action": "tool_catalog.inspect",
            "trace_id": "runtime-trace",
            "idempotency_key": "runtime-idempotency",
            "budget": {
                "max_tool_calls": 2,
                "max_wall_time_ms": 100,
                "max_graph_depth": 1,
                "max_retries": 0,
                "max_retrieval_chunks": 0,
            },
            "invocations": [{"tool_name": "tool_catalog.inspect", "input": {}}],
        }
        payload.update(overrides)
        return payload


def _api_fixture(*, actions: list[str] | None = None) -> _ApiFixture:
    return _ApiFixture(actions=actions)
