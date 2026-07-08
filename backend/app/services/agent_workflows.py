from collections.abc import Iterable
from dataclasses import replace
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.account_inventory_agent import (
    build_account_assignment_draft,
    plan_account_status_exception,
)
from app.agents.bm_invite_draft_agent import build_bm_invite_draft
from app.agents.card_binding_draft_agent import build_card_binding_draft
from app.agents.customer_reply_draft_agent import build_customer_reply_draft
from app.agents.interfaces import StructuredLLMClient, StructuredLLMRequest
from app.agents.message_intake_router import (
    ROUTER_INVALID_OUTPUT_ERROR_CODE,
    RouterOutputInvalid,
    build_router_request,
    parse_router_result,
    select_child_agents,
)
from app.agents.recharge_draft_agent import build_recharge_draft
from app.agents.schemas import DraftAgentContext, RouterIntent, Stage05DraftCandidate
from app.agents.stage05_skill_matching import build_skill_evidence
from app.agents.stage05_state import Stage05WorkflowState, new_stage05_workflow_state
from app.agents.stage05_supervisor import (
    Stage05SupervisorNodeSet,
    build_stage05_supervisor_graph,
)
from app.models.accounts import AccountAssignment, AccountInventory, AccountStatusEvent
from app.models.agent import AgentRun
from app.models.service_drafts import ServiceDraft
from app.models.telegram import Message
from app.services.account_inventory import (
    AccountExceptionMarkResult,
    InventoryStateError,
    mark_account_exception_from_agent,
)
from app.services.agent_runs import (
    create_agent_run_record,
    create_failed_agent_run_record,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor, PermissionDenied
from app.services.service_drafts import create_service_draft_from_stage05_candidate
from app.services.telegram_ingestion import IngestedMessage


STAGE05_GRAPH_NAME = "stage05_supervisor"
STAGE05_ROUTER_AGENT_NAME = "message_intake_router"
MANUAL_REVIEW_CONFIDENCE_THRESHOLD = Decimal("0.7000")
TERMINAL_INTENT_STATUSES = {"routed", "manual_review", "agent_failed"}

INTENT_TO_DRAFT_BUILDER = {
    "account_assignment": build_account_assignment_draft,
    "recharge": build_recharge_draft,
    "card_binding": build_card_binding_draft,
    "bm_invite": build_bm_invite_draft,
    "customer_reply": build_customer_reply_draft,
}


@dataclass(frozen=True)
class Stage05WorkflowOutcome:
    status: str
    reason: str | None = None
    selected_agents: list[str] = field(default_factory=list)
    manual_review_reasons: list[str] = field(default_factory=list)


class Stage05WorkflowUnitOfWork(Protocol):
    def get_message(self, message_id: str) -> IngestedMessage | Message | None:
        pass

    def save_message(self, message: IngestedMessage | Message) -> None:
        pass

    def add_agent_run(self, agent_run: AgentRun) -> None:
        pass

    def get_service_draft_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ServiceDraft | None:
        pass

    def add_service_draft(self, draft: ServiceDraft) -> None:
        pass

    def add_status_event(self, event: AccountStatusEvent) -> None:
        pass

    def add_assignment(self, assignment: AccountAssignment) -> None:
        pass

    def get_inventory_account(self, account_id: UUID) -> AccountInventory | None:
        pass

    def get_assignment(self, assignment_id: UUID) -> AccountAssignment | None:
        pass

    def list_inventory_accounts(self) -> list[AccountInventory]:
        pass

    def add(self, value: object) -> None:
        pass

    def commit(self) -> None:
        pass


class InMemoryStage05WorkflowUnitOfWork:
    def __init__(
        self,
        *,
        messages: Iterable[IngestedMessage | Message] | None = None,
        inventory_accounts: Iterable[AccountInventory] | None = None,
        assignments: Iterable[AccountAssignment] | None = None,
        status_events: Iterable[AccountStatusEvent] | None = None,
    ) -> None:
        self.messages = {str(message.id): message for message in messages or []}
        self.saved_messages: list[IngestedMessage | Message] = []
        self.agent_runs: list[AgentRun] = []
        self.service_drafts: list[ServiceDraft] = []
        self.inventory_accounts: list[AccountInventory] = list(
            inventory_accounts or []
        )
        self.assignments: list[AccountAssignment] = list(assignments or [])
        self.status_events: list[AccountStatusEvent] = list(status_events or [])
        self.audit_events: list[object] = []
        self.commits = 0

    def get_message(self, message_id: str) -> IngestedMessage | Message | None:
        return self.messages.get(message_id)

    def save_message(self, message: IngestedMessage | Message) -> None:
        self.messages[str(message.id)] = message
        self.saved_messages.append(message)

    def add_agent_run(self, agent_run: AgentRun) -> None:
        if agent_run.id is None:
            agent_run.id = uuid4()
        self.agent_runs.append(agent_run)

    def get_service_draft_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ServiceDraft | None:
        return next(
            (
                draft
                for draft in self.service_drafts
                if draft.idempotency_key == idempotency_key
            ),
            None,
        )

    def add_service_draft(self, draft: ServiceDraft) -> None:
        self.service_drafts.append(draft)

    def add_status_event(self, event: AccountStatusEvent) -> None:
        self.status_events.append(event)

    def add_assignment(self, assignment: AccountAssignment) -> None:
        self.assignments.append(assignment)

    def get_inventory_account(self, account_id: UUID) -> AccountInventory | None:
        return next(
            (
                account
                for account in self.inventory_accounts
                if account.id == account_id
            ),
            None,
        )

    def get_assignment(self, assignment_id: UUID) -> AccountAssignment | None:
        return next(
            (
                assignment
                for assignment in self.assignments
                if assignment.id == assignment_id
            ),
            None,
        )

    def list_inventory_accounts(self) -> list[AccountInventory]:
        return list(self.inventory_accounts)

    def add(self, value: object) -> None:
        self.audit_events.append(value)

    def commit(self) -> None:
        self.commits += 1


class SqlAlchemyStage05WorkflowUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_message(self, message_id: str) -> Message | None:
        return self.session.get(Message, UUID(message_id))

    def save_message(self, message: IngestedMessage | Message) -> None:
        self.session.add(message)

    def add_agent_run(self, agent_run: AgentRun) -> None:
        if agent_run.id is None:
            agent_run.id = uuid4()
        self.session.add(agent_run)

    def get_service_draft_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ServiceDraft | None:
        return self.session.scalar(
            select(ServiceDraft).where(ServiceDraft.idempotency_key == idempotency_key)
        )

    def add_service_draft(self, draft: ServiceDraft) -> None:
        self.session.add(draft)

    def add_status_event(self, event: AccountStatusEvent) -> None:
        self.session.add(event)

    def add_assignment(self, assignment: AccountAssignment) -> None:
        self.session.add(assignment)

    def get_inventory_account(self, account_id: UUID) -> AccountInventory | None:
        return self.session.get(AccountInventory, account_id)

    def get_assignment(self, assignment_id: UUID) -> AccountAssignment | None:
        return self.session.get(AccountAssignment, assignment_id)

    def list_inventory_accounts(self) -> list[AccountInventory]:
        return list(self.session.scalars(select(AccountInventory)))

    def add(self, value: object) -> None:
        self.session.add(value)

    def commit(self) -> None:
        self.session.commit()


class Stage05AgentWorkflowService:
    def __init__(
        self,
        *,
        uow: Stage05WorkflowUnitOfWork,
        llm_client: StructuredLLMClient,
        model_name: str | None = None,
    ) -> None:
        self.uow = uow
        self.llm_client = llm_client
        self.model_name = model_name

    def run_message(self, message_id: str) -> Stage05WorkflowOutcome:
        message = self.uow.get_message(message_id)
        if message is None:
            return Stage05WorkflowOutcome(status="skipped", reason="message_not_found")
        if message.intent_status in TERMINAL_INTENT_STATUSES:
            return Stage05WorkflowOutcome(status="skipped", reason="already_processed")
        if not _is_stage05_eligible(message):
            return Stage05WorkflowOutcome(status="skipped", reason="not_eligible")

        initial_state = new_stage05_workflow_state(
            trace_id=message.trace_id,
            message_id=str(message.id),
            customer_id=str(message.customer_id),
            source_text_summary=_source_text_summary(message),
        )
        nodes = Stage05SupervisorNodeSet(
            mark_running=lambda state: self._mark_running(state, message),
            route_message=lambda state: self._route_message(state, message),
            apply_policy=self._apply_policy,
            finalize_message=lambda state: self._finalize_message(state, message),
        )
        final_state = build_stage05_supervisor_graph(nodes).invoke(initial_state)
        return Stage05WorkflowOutcome(
            status=final_state["status"],
            reason=_first_error_code(final_state),
            selected_agents=list(final_state["selected_agents"]),
            manual_review_reasons=list(final_state["manual_review_reasons"]),
        )

    def run_for_message(
        self,
        *,
        message: IngestedMessage | Message,
        trace_id: str,
        uow: object | None = None,
    ) -> Stage05WorkflowOutcome:
        return self.run_message(str(message.id))

    def _mark_running(
        self,
        state: Stage05WorkflowState,
        message: IngestedMessage | Message,
    ) -> Stage05WorkflowState:
        before_status = message.intent_status
        message.intent_status = "agent_running"
        message.last_error_code = None
        state["status"] = "agent_running"
        self.uow.save_message(message)
        record_audit_event(
            self.uow,
            trace_id=state["trace_id"],
            actor_type="agent",
            actor_id=STAGE05_GRAPH_NAME,
            event_type="agent.workflow_started",
            entity_type="message",
            entity_id=_uuid_or_none(message.id),
            before_state={"intent_status": before_status},
            after_state={"intent_status": message.intent_status},
        )
        return state

    def _route_message(
        self,
        state: Stage05WorkflowState,
        message: IngestedMessage | Message,
    ) -> Stage05WorkflowState:
        request = build_router_request(
            trace_id=state["trace_id"],
            message_id=state["message_id"],
            customer_id=state["customer_id"],
            source_text_summary=state["source_text_summary"],
            context_summary=state["context_summary"],
            model_name=self.model_name,
        )
        result = None
        try:
            result = self.llm_client.generate_json(request)
            router_result = parse_router_result(result.content)
        except RouterOutputInvalid as exc:
            return self._record_router_failure(
                state,
                message,
                request=request,
                error_code=exc.error_code,
                error_message_redacted=str(exc),
                model_provider=getattr(result, "model_provider", "unknown"),
                model_name=getattr(result, "model_name", self.model_name or "unknown"),
            )
        except Exception as exc:
            return self._record_router_failure(
                state,
                message,
                request=request,
                error_code="llm_runtime_error",
                error_message_redacted=exc.__class__.__name__,
                model_provider=getattr(result, "model_provider", "unknown"),
                model_name=getattr(result, "model_name", self.model_name or "unknown"),
            )

        skill_evidence = build_skill_evidence(
            router_result=router_result,
            source_text_summary=state["source_text_summary"],
        )
        enriched_result = replace(
            result,
            content={**result.content, "skill_evidence": skill_evidence},
        )

        agent_run = create_agent_run_record(
            agent_name=STAGE05_ROUTER_AGENT_NAME,
            graph_name=STAGE05_GRAPH_NAME,
            trace_id=state["trace_id"],
            request=request,
            result=enriched_result,
            message_id=_uuid_or_none(message.id),
            created_entity_refs=[],
        )
        if agent_run.id is None:
            agent_run.id = uuid4()
        self.uow.add_agent_run(agent_run)
        state["router_result"] = router_result
        state["selected_agents"] = select_child_agents(router_result)
        _append_agent_run_ref(state, agent_run)
        record_audit_event(
            self.uow,
            trace_id=state["trace_id"],
            actor_type="agent",
            actor_id=STAGE05_ROUTER_AGENT_NAME,
            event_type="agent.router_completed",
            entity_type="message",
            entity_id=_uuid_or_none(message.id),
            after_state={
                "selected_agents": state["selected_agents"],
                "requires_manual_review": router_result.requires_manual_review,
                "overall_confidence": str(router_result.overall_confidence),
            },
        )
        return state

    def _apply_policy(self, state: Stage05WorkflowState) -> Stage05WorkflowState:
        if state["status"] == "agent_failed":
            return state
        router_result = state["router_result"]
        if router_result is None:
            state["status"] = "agent_failed"
            state["errors"].append({"error_code": ROUTER_INVALID_OUTPUT_ERROR_CODE})
            return state

        reasons: list[str] = []
        if router_result.requires_manual_review:
            reasons.extend(router_result.manual_review_reasons)
        if (
            router_result.overall_confidence < MANUAL_REVIEW_CONFIDENCE_THRESHOLD
            and not reasons
        ):
            reasons.append("low_confidence")
        if any(
            intent.risk_flags
            for intent in router_result.intents
            if intent.intent_type != "account_status_exception"
        ):
            reasons.append("risk_flags_present")
        if not state["selected_agents"] and not reasons:
            reasons.append("no_supported_child_agent")

        if reasons:
            state["status"] = "manual_review"
            state["manual_review_reasons"] = _unique_strings(reasons)
        else:
            state["status"] = "routed"
        return state

    def _finalize_message(
        self,
        state: Stage05WorkflowState,
        message: IngestedMessage | Message,
    ) -> Stage05WorkflowState:
        message.intent_status = state["status"]
        if state["status"] == "agent_failed":
            message.last_error_code = _first_error_code(state)
            audit_type = "agent.workflow_failed"
        else:
            message.last_error_code = None
            audit_type = "agent.workflow_completed"
        if state["status"] == "routed":
            self._persist_draft_candidates(state, message)
            self._persist_account_inventory_outcomes(state, message)
            if state["manual_review_reasons"] and not _has_business_output(state):
                state["status"] = "manual_review"
                message.intent_status = "manual_review"
        if state["status"] == "manual_review":
            record_audit_event(
                self.uow,
                trace_id=state["trace_id"],
                actor_type="agent",
                actor_id=STAGE05_GRAPH_NAME,
                event_type="agent.manual_review_requested",
                entity_type="message",
                entity_id=_uuid_or_none(message.id),
                after_state={
                    "manual_review_reasons": state["manual_review_reasons"],
                },
            )
        record_audit_event(
            self.uow,
            trace_id=state["trace_id"],
            actor_type="agent",
            actor_id=STAGE05_GRAPH_NAME,
            event_type=audit_type,
            entity_type="message",
            entity_id=_uuid_or_none(message.id),
            after_state={
                "intent_status": message.intent_status,
                "selected_agents": state["selected_agents"],
                "manual_review_reasons": state["manual_review_reasons"],
                "errors": state["errors"],
            },
        )
        self.uow.save_message(message)
        self.uow.commit()
        return state

    def _record_router_failure(
        self,
        state: Stage05WorkflowState,
        message: IngestedMessage | Message,
        *,
        request: StructuredLLMRequest,
        error_code: str,
        error_message_redacted: str,
        model_provider: str,
        model_name: str,
    ) -> Stage05WorkflowState:
        agent_run = create_failed_agent_run_record(
            agent_name=STAGE05_ROUTER_AGENT_NAME,
            graph_name=STAGE05_GRAPH_NAME,
            trace_id=state["trace_id"],
            request=request,
            model_provider=model_provider,
            model_name=model_name,
            error_code=error_code,
            error_message_redacted=error_message_redacted,
            message_id=_uuid_or_none(message.id),
        )
        if agent_run.id is None:
            agent_run.id = uuid4()
        self.uow.add_agent_run(agent_run)
        state["status"] = "agent_failed"
        state["errors"].append(
            {
                "error_code": error_code,
                "error_message_redacted": error_message_redacted,
            }
        )
        _append_agent_run_ref(state, agent_run)
        record_audit_event(
            self.uow,
            trace_id=state["trace_id"],
            actor_type="agent",
            actor_id=STAGE05_ROUTER_AGENT_NAME,
            event_type="agent.router_failed",
            entity_type="message",
            entity_id=_uuid_or_none(message.id),
            after_state={"error_code": error_code},
        )
        return state

    def _persist_draft_candidates(
        self,
        state: Stage05WorkflowState,
        message: IngestedMessage | Message,
    ) -> None:
        candidates = _build_draft_candidates(state)
        for candidate in candidates:
            state["draft_candidates"].append(candidate.model_dump(mode="json"))
            existing = self.uow.get_service_draft_by_idempotency_key(
                candidate.idempotency_key
            )
            if existing is not None:
                continue
            draft = create_service_draft_from_stage05_candidate(candidate)
            self.uow.add_service_draft(draft)
            state["created_entity_refs"].append(
                {"entity_type": "service_draft", "id": str(draft.id)}
            )
            record_audit_event(
                self.uow,
                trace_id=state["trace_id"],
                actor_type="agent",
                actor_id=candidate.agent_name,
                event_type="agent.draft_created",
                entity_type="service_draft",
                entity_id=draft.id,
                after_state={
                    "draft_type": draft.draft_type,
                    "status": draft.status,
                    "missing_fields": draft.missing_fields,
                    "risk_flags": draft.risk_flags,
                    "source_message_id": str(draft.source_message_id),
                    "intent_index": draft.intent_index,
                },
            )

    def _persist_account_inventory_outcomes(
        self,
        state: Stage05WorkflowState,
        message: IngestedMessage | Message,
    ) -> None:
        router_result = state["router_result"]
        if router_result is None:
            return
        for intent in router_result.intents:
            if intent.intent_type != "account_status_exception":
                continue
            decision = plan_account_status_exception(intent)
            if decision.status_action is None:
                state["manual_review_reasons"].extend(decision.manual_review_reasons)
                continue
            account = _resolve_inventory_account(
                self.uow,
                decision.status_action.account_hint,
            )
            if account is None:
                state["manual_review_reasons"].append("account_hint_not_found")
                continue
            try:
                result = mark_account_exception_from_agent(
                    self.uow,
                    actor=Actor(
                        actor_type="agent",
                        actor_id="account_inventory_agent",
                        role="agent",
                    ),
                    account_inventory_id=account.id,
                    target_status=decision.status_action.target_status,
                    confidence=decision.status_action.confidence,
                    risk_flags=decision.status_action.risk_flags,
                    source_message_id=_uuid_or_none(message.id) or uuid4(),
                    reason=decision.status_action.reason,
                    trace_id=state["trace_id"],
                )
            except (InventoryStateError, PermissionDenied) as exc:
                state["manual_review_reasons"].append(exc.__class__.__name__)
                continue
            _append_account_status_action(state, result)


def _is_stage05_eligible(message: IngestedMessage | Message) -> bool:
    return (
        message.binding_status == "bound"
        and message.intent_status == "intent_ready"
        and message.customer_id is not None
    )


def _source_text_summary(message: IngestedMessage | Message) -> str:
    return (
        message.normalized_text
        or message.raw_text
        or message.raw_caption
        or "[empty message]"
    )


def _uuid_or_none(value: object) -> UUID | None:
    return value if isinstance(value, UUID) else None


def _append_agent_run_ref(state: Stage05WorkflowState, agent_run: AgentRun) -> None:
    if agent_run.id is not None:
        state["agent_run_ids"].append(str(agent_run.id))
        state["created_entity_refs"].append(
            {"entity_type": "agent_run", "id": str(agent_run.id)}
        )


def _build_draft_candidates(
    state: Stage05WorkflowState,
) -> list[Stage05DraftCandidate]:
    router_result = state["router_result"]
    if router_result is None:
        return []
    context = DraftAgentContext(
        source_message_id=state["message_id"],
        customer_id=state["customer_id"],
        trace_id=state["trace_id"],
        source_text_summary=state["source_text_summary"],
        source_agent_run_id=state["agent_run_ids"][0]
        if state["agent_run_ids"]
        else None,
    )
    candidates: list[Stage05DraftCandidate] = []
    for fallback_index, intent in enumerate(router_result.intents):
        builder = INTENT_TO_DRAFT_BUILDER.get(intent.intent_type)
        if builder is None:
            continue
        indexed_intent = _with_intent_index(intent, fallback_index)
        candidates.append(builder(indexed_intent, context))
    return candidates


def _with_intent_index(intent: RouterIntent, fallback_index: int) -> RouterIntent:
    if intent.intent_index is not None:
        return intent
    return intent.model_copy(update={"intent_index": fallback_index})


def _resolve_inventory_account(
    uow: Stage05WorkflowUnitOfWork,
    account_hint: str,
) -> AccountInventory | None:
    try:
        return uow.get_inventory_account(UUID(account_hint))
    except ValueError:
        pass
    matches = [
        account
        for account in uow.list_inventory_accounts()
        if account.external_account_id == account_hint
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _append_account_status_action(
    state: Stage05WorkflowState,
    result: AccountExceptionMarkResult,
) -> None:
    state["account_status_actions"].append(
        {
            "account_inventory_id": str(result.account.id),
            "inventory_status": result.account.inventory_status,
            "changed": result.changed,
        }
    )
    if result.event is not None:
        state["created_entity_refs"].append(
            {"entity_type": "account_status_event", "id": str(result.event.id)}
        )


def _has_business_output(state: Stage05WorkflowState) -> bool:
    return any(
        ref.get("entity_type") in {"service_draft", "account_status_event"}
        for ref in state["created_entity_refs"]
    )


def _first_error_code(state: Stage05WorkflowState) -> str | None:
    if not state["errors"]:
        return None
    return str(state["errors"][0].get("error_code"))


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


__all__ = [
    "InMemoryStage05WorkflowUnitOfWork",
    "MANUAL_REVIEW_CONFIDENCE_THRESHOLD",
    "STAGE05_GRAPH_NAME",
    "STAGE05_ROUTER_AGENT_NAME",
    "SqlAlchemyStage05WorkflowUnitOfWork",
    "Stage05AgentWorkflowService",
    "Stage05WorkflowOutcome",
    "Stage05WorkflowUnitOfWork",
]
