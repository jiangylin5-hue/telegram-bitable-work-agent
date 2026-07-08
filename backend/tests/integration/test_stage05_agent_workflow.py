from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.agents.interfaces import StructuredLLMRequest, StructuredLLMResult
from app.models.accounts import AccountInventory
from app.services.telegram_ingestion import IngestedMessage


def test_stage05_supervisor_graph_invokes_langgraph_nodes() -> None:
    from app.agents.stage05_state import new_stage05_workflow_state
    from app.agents.stage05_supervisor import (
        Stage05SupervisorNodeSet,
        build_stage05_supervisor_graph,
    )

    def mark_running(state):
        state["status"] = "agent_running"
        return state

    def route_message(state):
        state["selected_agents"] = ["customer_reply_draft_agent"]
        return state

    def apply_policy(state):
        state["status"] = "routed"
        return state

    def finalize_message(state):
        state["created_entity_refs"] = [{"entity_type": "agent_run", "id": "run-1"}]
        return state

    graph = build_stage05_supervisor_graph(
        Stage05SupervisorNodeSet(
            mark_running=mark_running,
            route_message=route_message,
            apply_policy=apply_policy,
            finalize_message=finalize_message,
        )
    )

    result = graph.invoke(
        new_stage05_workflow_state(
            trace_id="trace-stage05-graph",
            message_id="message-stage05-graph",
            customer_id="customer-1",
            source_text_summary="Customer asks for a reply draft.",
        )
    )

    assert result["status"] == "routed"
    assert result["selected_agents"] == ["customer_reply_draft_agent"]
    assert result["created_entity_refs"] == [
        {"entity_type": "agent_run", "id": "run-1"}
    ]


def test_workflow_routes_bound_intent_ready_message_and_records_agent_run() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="customer recharge act_1001 100 USD and reply thanks")
    uow = InMemoryStage05WorkflowUnitOfWork(messages=[message])
    llm_client = FakeWorkflowLLMClient(
        response=_router_payload(
            [
                _intent("recharge", entities={"account_hint": "act_1001"}),
                _intent("customer_reply"),
            ],
            overall_confidence="0.9100",
            redacted_summary="Customer asks for recharge and reply draft.",
        )
    )
    service = Stage05AgentWorkflowService(uow=uow, llm_client=llm_client)

    outcome = service.run_message(str(message.id))

    assert outcome.status == "routed"
    assert outcome.selected_agents == [
        "recharge_draft_agent",
        "customer_reply_draft_agent",
    ]
    assert message.intent_status == "routed"
    assert message.last_error_code is None
    assert len(llm_client.requests) == 1
    assert len(uow.agent_runs) == 1
    assert len(uow.service_drafts) == 2
    assert uow.agent_runs[0].agent_name == "message_intake_router"
    assert uow.agent_runs[0].graph_name == "stage05_supervisor"
    assert uow.agent_runs[0].status == "succeeded"
    assert uow.agent_runs[0].message_id == message.id
    assert uow.agent_runs[0].output_summary["redacted_summary"] == (
        "Customer asks for recharge and reply draft."
    )
    skill_evidence = uow.agent_runs[0].output_summary["skill_evidence"]
    selected_skill_ids = {
        item["skill_id"] for item in skill_evidence["selected_skills"]
    }
    assert "recharge-draft" in selected_skill_ids
    assert "customer-reply-draft" in selected_skill_ids
    assert skill_evidence["mode"] == "sidecar_candidate_logging"
    assert [draft.draft_type for draft in uow.service_drafts] == [
        "recharge",
        "customer_reply",
    ]
    assert [draft.idempotency_key for draft in uow.service_drafts] == [
        f"draft:{message.id}:recharge:0",
        f"draft:{message.id}:customer_reply:1",
    ]
    assert uow.service_drafts[0].created_by_id == "recharge_draft_agent"
    assert uow.service_drafts[1].created_by_id == "customer_reply_draft_agent"
    assert [audit.event_type for audit in uow.audit_events] == [
        "agent.workflow_started",
        "agent.router_completed",
        "agent.draft_created",
        "agent.draft_created",
        "agent.workflow_completed",
    ]


def test_workflow_marks_low_confidence_router_output_manual_review() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="maybe something is wrong")
    uow = InMemoryStage05WorkflowUnitOfWork(messages=[message])
    llm_client = FakeWorkflowLLMClient(
        response=_router_payload(
            [_intent("unknown", confidence="0.3100")],
            overall_confidence="0.3100",
            requires_manual_review=True,
            manual_review_reasons=["insufficient evidence"],
            redacted_summary="Ambiguous customer message.",
        )
    )

    outcome = Stage05AgentWorkflowService(
        uow=uow,
        llm_client=llm_client,
    ).run_message(str(message.id))

    assert outcome.status == "manual_review"
    assert outcome.manual_review_reasons == ["insufficient evidence"]
    assert outcome.selected_agents == []
    assert message.intent_status == "manual_review"
    assert len(uow.agent_runs) == 1
    assert uow.agent_runs[0].status == "succeeded"
    assert "agent.manual_review_requested" in [
        audit.event_type for audit in uow.audit_events
    ]


def test_workflow_maps_invalid_router_output_to_agent_failed() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="create a new account")
    uow = InMemoryStage05WorkflowUnitOfWork(messages=[message])
    llm_client = FakeWorkflowLLMClient(
        response=_router_payload(
            [_intent("produce_account")],
            redacted_summary="Unsupported account production request.",
        )
    )

    outcome = Stage05AgentWorkflowService(
        uow=uow,
        llm_client=llm_client,
    ).run_message(str(message.id))

    assert outcome.status == "agent_failed"
    assert message.intent_status == "agent_failed"
    assert message.last_error_code == "agent_output_invalid"
    assert len(uow.agent_runs) == 1
    assert uow.agent_runs[0].status == "failed"
    assert uow.agent_runs[0].error_code == "agent_output_invalid"
    assert [audit.event_type for audit in uow.audit_events] == [
        "agent.workflow_started",
        "agent.router_failed",
        "agent.workflow_failed",
    ]


def test_workflow_maps_llm_runtime_failure_to_agent_failed() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="reply thanks")
    uow = InMemoryStage05WorkflowUnitOfWork(messages=[message])

    outcome = Stage05AgentWorkflowService(
        uow=uow,
        llm_client=FailingWorkflowLLMClient(),
    ).run_message(str(message.id))

    assert outcome.status == "agent_failed"
    assert outcome.reason == "llm_runtime_error"
    assert message.intent_status == "agent_failed"
    assert message.last_error_code == "llm_runtime_error"
    assert len(uow.agent_runs) == 1
    assert uow.agent_runs[0].status == "failed"
    assert uow.agent_runs[0].error_code == "llm_runtime_error"


def test_workflow_duplicate_trigger_does_not_create_second_agent_run() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="reply thanks")
    uow = InMemoryStage05WorkflowUnitOfWork(messages=[message])
    llm_client = FakeWorkflowLLMClient(
        response=_router_payload(
            [_intent("customer_reply")],
            redacted_summary="Customer asks for reply draft.",
        )
    )
    service = Stage05AgentWorkflowService(uow=uow, llm_client=llm_client)

    first = service.run_message(str(message.id))
    second = service.run_message(str(message.id))

    assert first.status == "routed"
    assert second.status == "skipped"
    assert second.reason == "already_processed"
    assert message.intent_status == "routed"
    assert len(llm_client.requests) == 1
    assert len(uow.agent_runs) == 1


def test_workflow_marks_high_confidence_account_exception_status_event() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="act_stage05_001 is under risk control")
    account = _inventory_account(
        status="allocated",
        customer_id=message.customer_id,
    )
    uow = InMemoryStage05WorkflowUnitOfWork(
        messages=[message],
        inventory_accounts=[account],
    )
    llm_client = FakeWorkflowLLMClient(
        response=_router_payload(
            [
                _intent(
                    "account_status_exception",
                    confidence="0.9600",
                    entities={
                        "account_inventory_id": str(account.id),
                        "target_status": "risk_controlled",
                        "reason": "customer message clearly reports risk control",
                    },
                    risk_flags=["risk_control_confirmed"],
                )
            ],
            overall_confidence="0.9600",
            redacted_summary="Customer reports account risk control.",
        )
    )

    outcome = Stage05AgentWorkflowService(
        uow=uow,
        llm_client=llm_client,
    ).run_message(str(message.id))

    assert outcome.status == "routed"
    assert message.intent_status == "routed"
    assert account.inventory_status == "risk_controlled"
    assert len(uow.status_events) == 1
    assert uow.status_events[0].event_type == "risk_controlled"
    assert uow.status_events[0].confidence == Decimal("0.9600")
    assert uow.status_events[0].risk_flags == ["risk_control_confirmed"]
    assert "account.exception_marked" in [
        audit.event_type for audit in uow.audit_events
    ]


def test_workflow_creates_account_assignment_draft_without_assignment_side_effect() -> None:
    from app.services.agent_workflows import (
        InMemoryStage05WorkflowUnitOfWork,
        Stage05AgentWorkflowService,
    )

    message = _message(raw_text="please assign an account")
    candidate_account_id = uuid4()
    uow = InMemoryStage05WorkflowUnitOfWork(messages=[message])
    llm_client = FakeWorkflowLLMClient(
        response=_router_payload(
            [
                _intent(
                    "account_assignment",
                    confidence="0.8700",
                    entities={
                        "request_type": "account_assignment",
                        "candidate_account_inventory_ids": [str(candidate_account_id)],
                    },
                )
            ],
            overall_confidence="0.8700",
            redacted_summary="Customer asks for an account assignment.",
        )
    )

    outcome = Stage05AgentWorkflowService(
        uow=uow,
        llm_client=llm_client,
    ).run_message(str(message.id))

    assert outcome.status == "routed"
    assert [draft.draft_type for draft in uow.service_drafts] == ["account_assignment"]
    assert uow.service_drafts[0].payload["candidate_account_inventory_ids"] == [
        str(candidate_account_id)
    ]
    assert uow.assignments == []
    assert uow.status_events == []


class FakeWorkflowLLMClient:
    def __init__(self, *, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[StructuredLLMRequest] = []

    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        self.requests.append(request)
        return StructuredLLMResult(
            content=self.response,
            model_provider="fake",
            model_name="fake-stage05-router",
            prompt_version=request.prompt_version,
            request_id="fake-stage05-request",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            raw_text=None,
        )


class FailingWorkflowLLMClient:
    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        raise TimeoutError("fake OpenRouter timeout")


def _message(*, raw_text: str) -> IngestedMessage:
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id="update-stage05",
        telegram_chat_id="chat-stage05",
        telegram_message_id="telegram-message-stage05",
        telegram_user_id="user-stage05",
        customer_group_id=None,
        customer_id=uuid4(),
        raw_text=raw_text,
        raw_caption=None,
        normalized_text=raw_text,
        message_type="text",
        intent_status="intent_ready",
        intent_type=None,
        ingestion_status="stored",
        trace_id="tg:update-stage05",
        binding_status="bound",
        processing_status="processed",
        outbox_status="processed",
    )
    message.received_at = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    return message


def _router_payload(
    intents: list[dict[str, object]],
    *,
    overall_confidence: str = "0.9000",
    requires_manual_review: bool = False,
    manual_review_reasons: list[str] | None = None,
    redacted_summary: str = "Customer message routed.",
) -> dict[str, object]:
    return {
        "intents": intents,
        "overall_confidence": overall_confidence,
        "requires_manual_review": requires_manual_review,
        "manual_review_reasons": list(manual_review_reasons or []),
        "redacted_summary": redacted_summary,
    }


def _intent(
    intent_type: str,
    *,
    confidence: str = "0.8500",
    entities: dict[str, object] | None = None,
    risk_flags: list[str] | None = None,
    missing_context: list[str] | None = None,
) -> dict[str, object]:
    return {
        "intent_type": intent_type,
        "confidence": confidence,
        "entities": dict(entities or {}),
        "risk_flags": list(risk_flags or []),
        "missing_context": list(missing_context or []),
    }


def _inventory_account(
    *,
    status: str,
    customer_id,
) -> AccountInventory:
    return AccountInventory(
        id=uuid4(),
        platform="meta",
        external_account_id="act_stage05_001",
        inventory_status=status,
        production_batch_id="batch-stage05",
        assigned_customer_id=customer_id,
    )
