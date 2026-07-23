from typing import Any

from app.agents.interfaces import StructuredLLMRequest, StructuredLLMResult
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    invoke_digital_employee,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


def test_stage06_live_summarize_calls_openrouter_with_permission_filtered_context() -> None:
    uow, view, record = _workspace_with_telegram_task_view()
    employee = create_digital_employee(
        uow,
        view.base_id,
        name="Ops Helper",
        description="Summarize Telegram task table",
        telegram_alias="ops",
        accessible_tables=[],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    llm_client = CapturingLLMClient(
        response={
            "answer": "One Telegram task is open and needs an owner check.",
            "citations": [
                {"record_id": str(record.id), "field_keys": ["message", "status"]}
            ],
        }
    )

    response = invoke_digital_employee(
        uow,
        employee.id,
        action="summarize",
        view_id=view.id,
        actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
        runtime_mode="live_openrouter",
        prompt="Summarize the Telegram tasks that need attention.",
        llm_client=llm_client,
    )

    assert response["action"] == "summarize"
    assert response["answer"] == "One Telegram task is open and needs an owner check."
    assert response["runtime"]["mode"] == "live_openrouter"
    assert response["runtime"]["model_provider"] == "openrouter"
    assert response["runtime"]["model_name"] == "openrouter/test-model"
    assert response["citations"] == [
        {"record_id": str(record.id), "field_keys": ["message", "status"]}
    ]
    assert len(llm_client.requests) == 1
    request_text = str(llm_client.requests[0].messages)
    assert "response_schema" in request_text
    assert '"answer"' in request_text
    assert '"citations"' in request_text
    assert "private escalation note" not in request_text
    assert "internal_notes" not in request_text
    skill_evidence = response["skill_evidence"]
    selected_ids = {item["skill_id"] for item in skill_evidence["selected_skills"]}
    assert "platform-base" in selected_ids
    assert "platform-tabular-analysis" in selected_ids
    assert "skill_evidence" in request_text
    assert "platform-base" in request_text
    assert uow.agent_runs[-1].model_provider == "openrouter"
    assert uow.agent_runs[-1].model_name == "openrouter/test-model"
    assert uow.agent_runs[-1].output_summary["skill_evidence"][
        "manifest_version"
    ] == "stage06-larksuite-skills-v1"
    assert uow.agent_runs[-1].usage_summary == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
    }


def test_stage06_live_draft_update_creates_draft_without_direct_record_write() -> None:
    uow, view, record = _workspace_with_telegram_task_view()
    employee = create_digital_employee(
        uow,
        view.base_id,
        name="Ops Helper",
        description="Draft Telegram task updates",
        telegram_alias="ops",
        accessible_tables=[str(record.table_id)],
        accessible_views=[str(view.id)],
        allowed_actions=["draft_update"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    llm_client = CapturingLLMClient(
        response={
            "answer": "I prepared a status update draft.",
            "draft": {
                "record_id": str(record.id),
                "proposed_values": {"status": "in_progress"},
            },
            "citations": [
                {"record_id": str(record.id), "field_keys": ["message", "status"]}
            ],
        }
    )

    response = invoke_digital_employee(
        uow,
        employee.id,
        action="draft_update",
        view_id=view.id,
        record_id=record.id,
        actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
        runtime_mode="live_openrouter",
        prompt="Prepare a draft that moves this Telegram task forward.",
        llm_client=llm_client,
    )

    assert response["action"] == "draft_update"
    assert response["answer"] == "已提出一个待确认草稿。"
    assert response["draft_id"] == str(uow.record_change_drafts[0].id)
    assert response["status"] == "pending_confirmation"
    assert record.values["status"] == "open"
    assert uow.record_change_drafts[0].proposed_values == {"status": "in_progress"}
    assert uow.agent_runs[-1].model_provider == "openrouter"
    assert "private escalation note" not in str(llm_client.requests[0].messages)


class CapturingLLMClient:
    def __init__(self, *, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[StructuredLLMRequest] = []

    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        self.requests.append(request)
        return StructuredLLMResult(
            content=self.response,
            model_provider="openrouter",
            model_name="openrouter/test-model",
            prompt_version=request.prompt_version,
            request_id="llm-test-request",
            usage={"prompt_tokens": 12, "completion_tokens": 8},
            raw_text='{"answer": "ok"}',
        )


def _workspace_with_telegram_task_view():
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Telegram Ops", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Telegram Productivity")
    table = create_table(uow, base.id, name="Telegram Tasks", key="telegram_tasks")
    create_field(uow, table.id, name="Message", key="message", field_type="text")
    create_field(
        uow,
        table.id,
        name="Status",
        key="status",
        field_type="status",
        permission_policy={"viewer": "read", "operator": "write"},
    )
    create_field(uow, table.id, name="Source Chat", key="source_chat", field_type="text")
    create_field(
        uow,
        table.id,
        name="Internal Notes",
        key="internal_notes",
        field_type="text",
        permission_policy={"viewer": "hidden", "operator": "hidden"},
    )
    record = create_record(
        uow,
        table.id,
        values={
            "message": "Please follow up with the design chat.",
            "status": "open",
            "source_chat": "design-team",
            "internal_notes": "private escalation note",
        },
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Telegram Task Grid",
        view_type="grid",
        config={"fields": ["message", "status", "source_chat", "internal_notes"]},
    )
    return uow, view, record
