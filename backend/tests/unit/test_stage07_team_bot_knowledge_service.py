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
    create_form_view,
    create_table,
    create_workspace,
)


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


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Team knowledge", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    view = create_form_view(
        uow, base.id, table.id, name="Current tasks", view_type="grid", config={"fields": []}, actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Team knowledge assistant",
        description="Summarizes permitted team views.",
        telegram_alias="",
        accessible_tables=[],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize", "draft_update"],
        actor=owner,
    )
    return uow, owner, employee, view

