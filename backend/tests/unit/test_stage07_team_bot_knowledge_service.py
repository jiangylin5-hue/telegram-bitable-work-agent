import json
from typing import Any
from uuid import uuid4

import pytest

from app.agents.interfaces import StructuredLLMRequest, StructuredLLMResult
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    invoke_digital_employee,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
    list_view_records,
)
from app.services.stage07_team_bot_knowledge import summarize_team_bot_knowledge


class CapturingLLMClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[StructuredLLMRequest] = []

    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        self.requests.append(request)
        return StructuredLLMResult(
            content=self.response,
            model_provider="openrouter",
            model_name="openrouter/test-model",
            prompt_version=request.prompt_version,
        )


def test_live_team_summary_uses_only_the_server_bounded_override_window() -> None:
    uow, owner, employee, view = _fixture()
    visible_records = [
        {"id": str(uuid4()), "fields": {"title": f"permitted-{index}"}}
        for index in range(101)
    ]
    client = CapturingLLMClient(
        {"answer": "Safe team summary.", "citations": [{"record_id": visible_records[0]["id"]}]}
    )

    response = invoke_digital_employee(
        uow,
        employee.id,
        action="summarize",
        view_id=view.id,
        actor=owner,
        runtime_mode="live_openrouter",
        prompt="Summarize this selected view.",
        llm_client=client,
        view_records_override=visible_records[:100],
    )

    request_payload = json.loads(client.requests[0].messages[1].content)
    assert len(request_payload["records"]) == 100
    assert visible_records[100]["fields"]["title"] not in client.requests[0].messages[1].content
    assert response["record_count"] == 100
    assert response["records"] == [record["fields"] for record in visible_records[:100]]


def test_live_record_override_is_summary_only() -> None:
    uow, owner, employee, view = _fixture()

    with pytest.raises(PlatformValidationError) as error:
        invoke_digital_employee(
            uow,
            employee.id,
            action="draft_update",
            view_id=view.id,
            record_id=uuid4(),
            actor=owner,
            runtime_mode="live_openrouter",
            view_records_override=[{"id": str(uuid4()), "fields": {}}],
        )

    assert error.value.code == "live_employee_record_override_not_allowed"


def test_team_bot_summary_limits_context_filters_citations_and_replays() -> None:
    uow, owner, employee, view = _fixture(record_count=101)
    permitted = list_view_records(uow, view.id, actor=owner, limit=101)["records"]
    visible_ids = [record["id"] for record in permitted[:100]]
    excluded_id = permitted[100]["id"]
    client = CapturingLLMClient(
        {
            "answer": "There are permitted current tasks.",
            "citations": [
                {"record_id": visible_ids[0]},
                {"record_id": excluded_id},
                {"record_id": str(uuid4())},
            ],
        }
    )

    receipt = summarize_team_bot_knowledge(
        uow,
        employee_id=employee.id,
        base_id=employee.base_id,
        view_id=view.id,
        actor=owner,
        instruction="Summarize current tasks.",
        idempotency_key="team-summary-1",
        llm_client=client,
    )
    replay = summarize_team_bot_knowledge(
        uow,
        employee_id=employee.id,
        base_id=employee.base_id,
        view_id=view.id,
        actor=owner,
        instruction="Summarize current tasks.",
        idempotency_key="team-summary-1",
        llm_client=client,
    )

    request_payload = json.loads(client.requests[0].messages[1].content)
    assert len(request_payload["records"]) == 100
    assert excluded_id not in client.requests[0].messages[1].content
    assert receipt.kind == "summary"
    assert receipt.knowledge_window_truncated is True
    assert receipt.citation_record_ids == [visible_ids[0]]
    assert replay == receipt
    assert len(client.requests) == 1
    assert uow.audit_events[-1].after_state == {
        "employee_id": str(employee.id),
        "base_id": str(employee.base_id),
        "view_id": str(view.id),
        "record_count": 100,
        "truncated": True,
        "outcome": "summary",
    }


def test_team_bot_empty_context_is_audited_without_provider_call() -> None:
    uow, owner, employee, view = _fixture()
    client = CapturingLLMClient({"answer": "must not be called", "citations": []})

    receipt = summarize_team_bot_knowledge(
        uow,
        employee_id=employee.id,
        base_id=employee.base_id,
        view_id=view.id,
        actor=owner,
        instruction=None,
        idempotency_key="team-empty-1",
        llm_client=client,
    )

    assert receipt.kind == "empty_context"
    assert receipt.citation_record_ids == []
    assert receipt.knowledge_window_truncated is False
    assert client.requests == []
    assert uow.audit_events[-1].after_state["outcome"] == "empty_context"


def _fixture(*, record_count: int = 0):
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Team knowledge", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    view = create_form_view(
        uow, base.id, table.id, name="Current tasks", view_type="grid", config={"fields": []}, actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Team knowledge assistant",
        description="Summarizes permitted team views.",
        telegram_alias="",
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize", "draft_update"],
        actor=owner,
    )
    for index in range(record_count):
        create_record(uow, table.id, values={"title": f"task-{index}"}, actor=owner)
    return uow, owner, employee, view
