from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import pickle
import re
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.runtime.stage08_collaboration_contracts import (
    AnalysisDecision,
    AnalysisProviderOutcome,
    CollaborationBudget,
    CompressionOutcome,
    Stage08CollaborationContractFactory,
)
from app.runtime.stage08_tool_gateway import Stage08ToolGateway
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_collaboration import (
    Stage08CollaborationReadDependencies,
    execute_collaboration_reads,
)
import app.services.stage08_collaboration as collaboration
from app.services.stage08_retrieval_provider import PostgresRetrievalProvider


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="e2-owner", role="owner")
    workspace = create_workspace(uow, name="E2", owner_user_id=actor.actor_id, actor=actor)
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    customers = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    projects = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    create_field(uow, customers.id, name="Name", key="name", field_type="text", actor=actor)
    create_field(uow, projects.id, name="Title", key="title", field_type="text", actor=actor)
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=actor,
    )
    customer = create_record(uow, customers.id, values={"name": "E2 Acme"}, actor=actor)
    project = create_record(
        uow,
        projects.id,
        values={"title": "E2 launch", "customer": [str(customer.id)]},
        actor=actor,
    )
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["title", "customer"]},
        actor=actor,
    )
    view.version = 1
    employee = create_digital_employee(
        uow,
        base.id,
        name="E2 employee",
        description="controlled reads",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="-100802",
        telegram_user_id="802",
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
    mapping = Stage08GroupBusinessContextBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        telegram_binding_id=binding.id,
        customer_record_id=customer.id,
        project_record_id=project.id,
        mapping_version=1,
        status="active",
    )
    uow.add_group_business_context_binding(mapping)
    return SimpleNamespace(
        uow=uow,
        actor=actor,
        workspace=workspace,
        employee=employee,
        customer=customer,
        project=project,
        mapping=mapping,
    )


def _command(fixture, *, intent: str = "business_fact", target_record_id=None):
    return Stage08CollaborationContractFactory.command(
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        actor_user_id=fixture.actor.actor_id,
        intent=intent,
        query="给出当前项目进展",
        requested_action="read_only",
        target_record_id=target_record_id,
        idempotency_key="e2-read-1",
    )


def _projection(fixture, text: str, *, minutes_ago: int) -> None:
    fixture.uow.add_group_message_projection(
        Stage08GroupMessageProjection(
            id=uuid4(),
            source_message_id=uuid4(),
            business_context_binding_id=fixture.mapping.id,
            content_fragment=text,
            content_version=1,
            event_at=NOW - timedelta(minutes=minutes_ago),
            edited_at=None,
            retention_expires_at=NOW + timedelta(days=30),
            lifecycle_status="active",
            source_chat_type="group",
        )
    )


def _side_effects(fixture) -> tuple[int, int, int, int, int]:
    return (
        len(fixture.uow.audit_events),
        len(fixture.uow.outbox_events),
        len(fixture.uow.agent_runs),
        len(fixture.uow.record_change_drafts),
        len(fixture.uow.notification_requests),
    )


def test_reads_are_bounded_safe_and_have_no_persistent_side_effects() -> None:
    fixture = _fixture()
    secret = "e2-direct-group-secret"
    _projection(fixture, secret, minutes_ago=0)
    before = _side_effects(fixture)

    result = execute_collaboration_reads(
        fixture.uow, _command(fixture), fixture.actor, now=NOW
    )
    safe = result.safe_view()

    assert safe.status == "internal_evidence"
    assert safe.read_child_count == 2
    assert safe.group_status == "direct"
    assert safe.retrieval_citation_count == 0
    assert secret not in repr(result) + safe.model_dump_json()
    with pytest.raises(TypeError):
        json.dumps(result)
    assert _side_effects(fixture) == before


def test_pending_group_unavailable_compressor_keeps_only_safe_degradation() -> None:
    fixture = _fixture()
    secret = "e2-pending-group-secret"
    for index in range(49):
        marker = f"{secret}-{index:02d}-"
        _projection(fixture, marker + ("x" * (500 - len(marker))), minutes_ago=index)

    result = execute_collaboration_reads(
        fixture.uow, _command(fixture), fixture.actor, now=NOW
    )
    safe = result.safe_view()

    assert safe.read_child_count == 2
    assert safe.group_status == "compression_unavailable"
    assert "compression_unavailable" in safe.degradation_codes
    assert secret not in repr(result) + safe.model_dump_json()


def test_actor_mismatch_is_rejected_before_any_read_or_side_effect() -> None:
    fixture = _fixture()
    before = _side_effects(fixture)
    different_actor = Actor(actor_type="user", actor_id="other-user", role="owner")

    result = execute_collaboration_reads(
        fixture.uow, _command(fixture), different_actor, now=NOW
    )

    assert result.safe_view().status == "degraded"
    assert result.safe_view().read_child_count == 0
    assert _side_effects(fixture) == before


def test_general_advice_skips_d4_and_never_turns_into_unscoped_retrieval() -> None:
    fixture = _fixture()
    calls: list[str] = []

    class RecordingRetrievalProvider(PostgresRetrievalProvider):
        def search(self, *args, **kwargs):
            del args, kwargs
            calls.append("search")
            raise AssertionError("general advice must not call D4")

    result = execute_collaboration_reads(
        fixture.uow,
        _command(fixture, intent="general_advice"),
        fixture.actor,
        deps=Stage08CollaborationReadDependencies(
            retrieval_provider=RecordingRetrievalProvider()
        ),
        now=NOW,
    )

    assert result.safe_view().status == "general_advice_only"
    assert result.safe_view().read_child_count == 3
    assert calls == []


@pytest.mark.parametrize("mapping_change", ["revoked", "ambiguous", "binding_inactive"])
def test_target_record_never_becomes_effective_scope_without_one_current_mapping(
    mapping_change: str,
) -> None:
    fixture = _fixture()
    if mapping_change == "revoked":
        fixture.mapping.status = "revoked"
    elif mapping_change == "ambiguous":
        fixture.uow.add_group_business_context_binding(
            Stage08GroupBusinessContextBinding(
                id=uuid4(),
                workspace_id=fixture.workspace.id,
                telegram_binding_id=fixture.mapping.telegram_binding_id,
                customer_record_id=fixture.customer.id,
                project_record_id=fixture.project.id,
                mapping_version=1,
                status="active",
            )
        )
    else:
        fixture.uow.telegram_bindings[0].status = "inactive"

    result = execute_collaboration_reads(
        fixture.uow,
        _command(fixture, target_record_id=fixture.project.id),
        fixture.actor,
        now=NOW,
    )

    assert result.safe_view().status == "degraded"
    assert result.safe_view().read_child_count == 0


@pytest.mark.parametrize("failure_at", ["search", "render", "safe_view"])
def test_retrieval_branch_exception_is_redacted_and_keeps_c3_material(
    failure_at: str,
) -> None:
    fixture = _fixture()
    secret = f"e2-retrieval-{failure_at}-secret"
    _projection(fixture, "valid group material", minutes_ago=0)

    class FailingRetrievalProvider(PostgresRetrievalProvider):
        def search(self, *args, **kwargs):
            if failure_at == "search":
                raise RuntimeError(secret)
            return super().search(*args, **kwargs)

        def render_private_evidence(self, *args, **kwargs):
            if failure_at == "render":
                raise RuntimeError(secret)
            return super().render_private_evidence(*args, **kwargs)

        def safe_view(self, *args, **kwargs):
            if failure_at == "safe_view":
                raise RuntimeError(secret)
            return super().safe_view(*args, **kwargs)

    before = _side_effects(fixture)
    result = execute_collaboration_reads(
        fixture.uow,
        _command(fixture),
        fixture.actor,
        deps=Stage08CollaborationReadDependencies(
            retrieval_provider=FailingRetrievalProvider()
        ),
        now=NOW,
    )
    safe = result.safe_view()

    assert safe.status == "internal_evidence"
    assert safe.read_child_count == 2
    assert "retrieval_unavailable" in safe.degradation_codes
    assert secret not in repr(result) + safe.model_dump_json()
    assert _side_effects(fixture) == before


def test_compression_revalidates_mapping_after_provider_returns_digest() -> None:
    fixture = _fixture()
    for index in range(49):
        marker = f"revoke-after-plan-{index:02d}-"
        _projection(fixture, marker + ("x" * (500 - len(marker))), minutes_ago=index)

    class MappingMutatingCompressor:
        def compress(self, material, *, budget: CollaborationBudget):
            del material, budget
            fixture.mapping.mapping_version += 1
            return CompressionOutcome(
                status="available",
                reason_code="none",
                digest=Stage08CollaborationContractFactory.compressed_digest(
                    text="不应被接受的摘要"
                ),
            )

    retrieval_calls: list[str] = []

    class RecordingRetrievalProvider(PostgresRetrievalProvider):
        def search(self, *args, **kwargs):
            del args, kwargs
            retrieval_calls.append("search")
            raise AssertionError("D4 must not run after group mapping drift")

    result = execute_collaboration_reads(
        fixture.uow,
        _command(fixture),
        fixture.actor,
        deps=Stage08CollaborationReadDependencies(
            context_compressor=MappingMutatingCompressor(),
            retrieval_provider=RecordingRetrievalProvider(),
        ),
        now=NOW,
    )

    assert result.safe_view().group_status == "compression_unavailable"
    assert "compression_unavailable" in result.safe_view().degradation_codes
    assert "retrieval_unavailable" in result.safe_view().degradation_codes
    assert retrieval_calls == []


@pytest.mark.parametrize("shape", ["object", "attribute_error", "invalid_digest"])
def test_compressor_shape_or_digest_drift_is_only_a_safe_group_degradation(
    shape: str,
) -> None:
    fixture = _fixture()
    for index in range(49):
        marker = f"compressor-shape-{index:02d}-"
        _projection(fixture, marker + ("x" * (500 - len(marker))), minutes_ago=index)

    class ShapeDriftCompressor:
        def compress(self, material, *, budget: CollaborationBudget):
            del material, budget
            if shape == "object":
                return object()
            if shape == "attribute_error":
                class Exploding:
                    @property
                    def status(self):
                        raise AttributeError("shape-secret")

                return Exploding()
            return CompressionOutcome.model_construct(
                status="available",
                reason_code="none",
                digest=object(),
            )

    result = execute_collaboration_reads(
        fixture.uow,
        _command(fixture),
        fixture.actor,
        deps=Stage08CollaborationReadDependencies(
            context_compressor=ShapeDriftCompressor()
        ),
        now=NOW,
    )

    safe = result.safe_view()
    assert safe.status == "internal_evidence"
    assert safe.group_status == "compression_unavailable"
    assert "compression_unavailable" in safe.degradation_codes
    assert "shape-secret" not in repr(result) + safe.model_dump_json()


def test_unknown_analysis_citation_is_denied_without_creating_a_draft() -> None:
    fixture = _fixture()
    fixture.employee.allowed_actions = ["query", "summarize", "draft_update"]
    command = Stage08CollaborationContractFactory.command(
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        actor_user_id=fixture.actor.actor_id,
        intent="business_fact",
        query="create a controlled draft",
        requested_action="draft_update",
        target_record_id=fixture.project.id,
        idempotency_key="e3-unknown-citation",
    )

    class UnknownCitationProvider:
        def analyse(self, material, command, *, budget):
            del material, command, budget
            from app.runtime.stage08_collaboration_contracts import (
                AnalysisDecision,
                AnalysisProviderOutcome,
            )

            return AnalysisProviderOutcome(
                status="available",
                reason_code="none",
                decision=AnalysisDecision(
                    answer="A controlled proposal is ready.",
                    citation_ordinals=(12,),
                    action="draft_update",
                    draft_intent=Stage08CollaborationContractFactory.draft_intent(
                        field_key="title",
                        value="E3 controlled",
                    ),
                ),
            )

    result = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=UnknownCitationProvider()
        ),
        now=NOW,
    )

    assert result.status == "denied"
    assert result.draft_id is None
    assert fixture.uow.record_change_drafts == []


def test_valid_draft_intent_uses_ticket_gateway_and_leaves_record_pending_confirmation() -> None:
    fixture = _fixture()
    fixture.employee.allowed_actions = ["query", "summarize", "draft_update"]
    command = Stage08CollaborationContractFactory.command(
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        actor_user_id=fixture.actor.actor_id,
        intent="business_fact",
        query="create a controlled draft",
        requested_action="draft_update",
        target_record_id=fixture.project.id,
        idempotency_key="e3-valid-draft",
    )

    class ValidDraftProvider:
        def analyse(self, material, command, *, budget):
            del material, command, budget
            from app.runtime.stage08_collaboration_contracts import (
                AnalysisDecision,
                AnalysisProviderOutcome,
            )

            return AnalysisProviderOutcome(
                status="available",
                reason_code="none",
                decision=AnalysisDecision(
                    answer="A controlled proposal is ready.",
                        citation_ordinals=(),
                    action="draft_update",
                    draft_intent=Stage08CollaborationContractFactory.draft_intent(
                        field_key="title",
                        value="E3 controlled",
                    ),
                ),
                )

    result = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=ValidDraftProvider()
        ),
        now=NOW,
    )

    assert result.status == "draft_pending"
    assert result.draft_id is not None
    assert len(fixture.uow.record_change_drafts) == 1
    assert fixture.uow.record_change_drafts[0].status == "pending_confirmation"
    assert fixture.project.values == {"title": "E2 launch", "customer": [str(fixture.customer.id)]}
    assert len(fixture.uow.execution_tickets) == 1
    assert fixture.uow.execution_tickets[0].status == "succeeded"
    terminal_text = json.dumps(
        [
            fixture.uow.agent_runs[-1].input_summary,
            fixture.uow.agent_runs[-1].output_summary,
            fixture.uow.agent_runs[-1].tool_calls,
            fixture.uow.audit_events[-1].after_state,
        ],
        default=str,
    )
    assert "create a controlled draft" not in terminal_text
    assert "A controlled proposal is ready." not in terminal_text
    assert "Create a confirmation draft" not in terminal_text


class _ControlledDraftProvider:
    def __init__(self, *, on_analyse=None) -> None:
        self.on_analyse = on_analyse

    def analyse(self, material, command, *, budget):
        del material, command, budget
        if self.on_analyse is not None:
            self.on_analyse()
        return AnalysisProviderOutcome(
            status="available",
            reason_code="none",
            decision=AnalysisDecision(
                answer="A controlled proposal is ready.",
                citation_ordinals=(),
                action="draft_update",
                draft_intent=Stage08CollaborationContractFactory.draft_intent(
                    field_key="title",
                    value="E3 controlled",
                ),
            ),
        )


class _CountingGateway(Stage08ToolGateway):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.calls = 0
        self.fail = fail

    def execute_plan(self, uow, ticket, invocations, *, safe_context=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic_gateway_failure")
        return super().execute_plan(
            uow,
            ticket,
            invocations,
            safe_context=safe_context,
        )


def _safe_draft_command(fixture, *, idempotency_key: str):
    fixture.employee.allowed_actions = ["query", "summarize", "draft_update"]
    return Stage08CollaborationContractFactory.command(
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        actor_user_id=fixture.actor.actor_id,
        intent="business_fact",
        query="create a controlled draft",
        requested_action="draft_update",
        target_record_id=fixture.project.id,
        idempotency_key=idempotency_key,
    )


def _persistent_trace_text(fixture, command) -> str:
    trace_hash = collaboration._trace_hash(command)
    return json.dumps(
        {
            "audits": [
                {
                    "actor_type": event.actor_type,
                    "actor_id": event.actor_id,
                    "entity_id": event.entity_id,
                    "before": event.before_state,
                    "after": event.after_state,
                    "permission": event.permission_snapshot,
                }
                for event in fixture.uow.audit_events
                if event.trace_id == trace_hash
            ],
            "runs": [
                {
                    "input": run.input_summary,
                    "output": run.output_summary,
                    "tools": run.tool_calls,
                    "refs": run.created_entity_refs,
                }
                for run in fixture.uow.agent_runs
                if run.trace_id == trace_hash
            ],
            "tickets": [
                ticket.tool_summary
                for ticket in fixture.uow.execution_tickets
                if ticket.trace_id == trace_hash
            ],
            "outbox": [
                event.payload
                for event in fixture.uow.outbox_events
                if event.trace_id == trace_hash
            ],
        },
        default=str,
        sort_keys=True,
    )


def _assert_trace_is_redacted(fixture, command) -> None:
    persisted = _persistent_trace_text(fixture, command)
    assert re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        persisted,
        flags=re.IGNORECASE,
    ) is None
    for forbidden in (
        "create a controlled draft",
        "A controlled proposal is ready.",
        "E3 controlled",
        '"title"',
        fixture.actor.actor_id,
    ):
        assert forbidden not in persisted


def test_safe_draft_uses_sealed_intent_and_leaves_source_record_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    before_values = dict(fixture.project.values)
    gateway = _CountingGateway()
    ticks = iter((10.0, 10.125))
    monkeypatch.setattr(collaboration, "monotonic", lambda: next(ticks))
    command = _safe_draft_command(fixture, idempotency_key="e3-safe-intent")

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=_ControlledDraftProvider(),
            tool_gateway=gateway,
        ),
        now=NOW,
    )

    assert view.status == "draft_pending"
    assert gateway.calls == 1
    assert len(fixture.uow.record_change_drafts) == 1
    assert fixture.uow.record_change_drafts[0].proposed_values == {
        "title": "E3 controlled"
    }
    assert fixture.project.values == before_values
    assert fixture.uow.agent_runs[-1].latency_ms == 125
    _assert_trace_is_redacted(fixture, command)


def test_safe_gateway_failure_rolls_back_ticket_idempotency_draft_and_internal_trace() -> None:
    fixture = _fixture()
    before_audits = len(fixture.uow.audit_events)
    before_runs = len(fixture.uow.agent_runs)
    gateway = _CountingGateway(fail=True)
    command = _safe_draft_command(fixture, idempotency_key="e3-safe-rollback")

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=_ControlledDraftProvider(),
            tool_gateway=gateway,
        ),
        now=NOW,
    )

    assert view.status == "failed"
    assert gateway.calls == 1
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.record_change_drafts == []
    assert len(fixture.uow.agent_runs) == before_runs + 1
    assert len(fixture.uow.audit_events) == before_audits + 1
    _assert_trace_is_redacted(fixture, command)


def test_safe_revoke_before_gateway_denies_without_draft_or_orphan() -> None:
    fixture = _fixture()
    gateway = _CountingGateway()
    original_lock = fixture.uow.lock_workspace_for_stage08_execution

    def revoke_mapping_when_execution_starts(workspace_id):
        fixture.mapping.status = "inactive"
        return original_lock(workspace_id)

    fixture.uow.lock_workspace_for_stage08_execution = (
        revoke_mapping_when_execution_starts
    )
    command = _safe_draft_command(fixture, idempotency_key="e3-safe-revoke")

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=_ControlledDraftProvider(),
            tool_gateway=gateway,
        ),
        now=NOW,
    )

    assert view.status == "denied"
    assert gateway.calls == 0
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.record_change_drafts == []
    _assert_trace_is_redacted(fixture, command)


def test_safe_same_key_revalidates_then_replays_same_draft_without_gateway() -> None:
    fixture = _fixture()
    gateway = _CountingGateway()
    command = _safe_draft_command(fixture, idempotency_key="e3-safe-replay")
    dependencies = collaboration.Stage08CollaborationDependencies(
        analysis_provider=_ControlledDraftProvider(),
        tool_gateway=gateway,
    )

    first = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        dependencies,
        now=NOW,
    )
    replay = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        dependencies,
        now=NOW,
    )

    assert replay == first
    assert replay.status == "draft_pending"
    assert gateway.calls == 1
    assert len(fixture.uow.execution_tickets) == 1
    assert len(fixture.uow.idempotency_records) == 1
    assert len(fixture.uow.record_change_drafts) == 1
    _assert_trace_is_redacted(fixture, command)


def test_unavailable_analysis_is_degraded_without_gateway_or_network() -> None:
    fixture = _fixture()
    gateway = _CountingGateway()
    command = _safe_draft_command(fixture, idempotency_key="e3-unavailable")

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(tool_gateway=gateway),
        now=NOW,
    )

    assert view.status == "degraded"
    assert view.answer is None
    assert view.citations == ()
    assert view.degradation_codes == ("analysis_unavailable",)
    assert view.draft_id is None
    assert gateway.calls == 0
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.record_change_drafts == []
    _assert_trace_is_redacted(fixture, command)


@pytest.mark.parametrize("mode", ["shape_drift", "forged", "exception"])
def test_invalid_or_raising_analysis_remains_failed_without_gateway(mode: str) -> None:
    fixture = _fixture()
    gateway = _CountingGateway()
    command = _safe_draft_command(fixture, idempotency_key=f"e3-invalid-{mode}")

    class InvalidProvider:
        def analyse(self, material, command, *, budget):
            del material, command, budget
            if mode == "exception":
                raise RuntimeError("private_provider_failure")
            if mode == "forged":
                return AnalysisProviderOutcome.model_construct(
                    status="unavailable",
                    reason_code="none",
                    decision=None,
                )
            return SimpleNamespace(
                status="unavailable",
                reason_code="analysis_provider_unavailable",
                decision=None,
            )

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=InvalidProvider(),
            tool_gateway=gateway,
        ),
        now=NOW,
    )

    assert view.status == "failed"
    assert view.answer is None
    assert view.citations == ()
    assert view.degradation_codes == ("analysis_unavailable",)
    assert view.draft_id is None
    assert gateway.calls == 0
    _assert_trace_is_redacted(fixture, command)


class _E5ReadOnlyProvider:
    def __init__(self, *, on_analyse=None) -> None:
        self.calls = 0
        self.on_analyse = on_analyse

    def analyse(self, material, command, *, budget):
        del material, command, budget
        self.calls += 1
        if self.on_analyse is not None:
            self.on_analyse()
        return AnalysisProviderOutcome(
            status="available",
            reason_code="none",
            decision=AnalysisDecision(
                answer="Current controlled material was analysed.",
                citation_ordinals=(),
                action="read_only",
            ),
        )


def test_terminal_run_and_audit_record_only_safe_resolved_skill_metadata() -> None:
    fixture = _fixture()
    query = "private query that must not persist"
    command = Stage08CollaborationContractFactory.command(
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        actor_user_id=fixture.actor.actor_id,
        intent="business_fact",
        query=query,
        requested_action="read_only",
        target_record_id=None,
        idempotency_key="stage09-skill-audit",
        skill_profile=Stage08CollaborationContractFactory.resolved_skill_profile(
            manifest_version="stage06-larksuite-skills-v1",
            primary_skill_id="platform-tabular-analysis",
            source_skill="lark-sheets",
            selection_mode="explicit",
            supporting_skill_ids=("platform-base", "platform-shared-policy"),
            allowed_intents=("business_fact", "mixed"),
            allowed_provider_actions=("read_only",),
            manifest_allowed_actions=("record.query", "table.summarize"),
            output_contract="analysis_answer_with_citations",
            confirmation_policy="read_only",
            safe_label="汇总分析",
        ),
    )

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=_E5ReadOnlyProvider()
        ),
        now=NOW,
    )

    expected = {
        "skill_manifest_version": "stage06-larksuite-skills-v1",
        "primary_skill_id": "platform-tabular-analysis",
        "skill_selection_mode": "explicit",
        "supporting_skill_ids": ["platform-base", "platform-shared-policy"],
    }
    assert view.skill.model_dump() == {
        "skill_id": "platform-tabular-analysis",
        "label": "汇总分析",
        "manifest_version": "stage06-larksuite-skills-v1",
        "selection_mode": "explicit",
    }
    assert expected.items() <= fixture.uow.agent_runs[-1].input_summary.items()
    assert expected.items() <= fixture.uow.agent_runs[-1].output_summary.items()
    assert expected.items() <= fixture.uow.audit_events[-1].after_state.items()
    persisted = json.dumps(
        [
            fixture.uow.agent_runs[-1].input_summary,
            fixture.uow.agent_runs[-1].output_summary,
            fixture.uow.audit_events[-1].after_state,
        ],
        ensure_ascii=False,
    )
    assert query not in persisted
    assert "lark-sheets" not in persisted


def test_runtime_control_is_opaque_and_not_serializable() -> None:
    runtime_control = collaboration._create_stage08_runtime_control()

    assert repr(runtime_control) == "<Stage08CollaborationRuntimeControl opaque>"
    with pytest.raises(TypeError):
        json.dumps(runtime_control)
    with pytest.raises(TypeError):
        pickle.dumps(runtime_control)


def test_production_read_nodes_execute_real_branches_and_fan_in_never_calls_legacy_io(
    monkeypatch,
) -> None:
    fixture = _fixture()
    branches: list[str] = []

    def legacy_io_forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("fan_in_must_not_execute_legacy_read_io")

    monkeypatch.setattr(collaboration, "execute_collaboration_reads", legacy_io_forbidden)
    runtime_control = collaboration._create_stage08_runtime_control(
        branch_probe=lambda branch, session_identity: branches.append(branch)
    )

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        _command(fixture),
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=_E5ReadOnlyProvider()
        ),
        now=NOW,
        runtime_control=runtime_control,
    )

    assert view.status == "completed"
    assert sorted(branches) == [
        "composite_context",
        "general_advice",
        "retrieval",
    ]


@pytest.mark.parametrize("cancel_at", ["before", "during_reads"])
def test_production_cancellation_skips_analysis_policy_and_gateway(
    cancel_at: str,
    monkeypatch,
) -> None:
    fixture = _fixture()
    cancelled = Event()
    if cancel_at == "before":
        cancelled.set()
    provider = _E5ReadOnlyProvider()
    gateway = _CountingGateway()
    policy_calls: list[str] = []
    original_policy = collaboration._policy_gate_state

    def recording_policy(*args, **kwargs):
        policy_calls.append("policy")
        return original_policy(*args, **kwargs)

    monkeypatch.setattr(collaboration, "_policy_gate_state", recording_policy)
    runtime_control = collaboration._create_stage08_runtime_control(
        cancellation_probe=cancelled.is_set,
        branch_probe=(
            lambda branch, session_identity: cancelled.set()
            if branch == "composite_context"
            else None
        ),
    )
    command = _command(fixture)

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=provider,
            tool_gateway=gateway,
        ),
        now=NOW,
        runtime_control=runtime_control,
    )

    assert view.status == "cancelled"
    assert provider.calls == 0
    assert policy_calls == []
    assert gateway.calls == 0
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.record_change_drafts == []
    _assert_trace_is_redacted(fixture, command)


def test_slow_analysis_crossing_provider_budget_times_out_before_policy_or_gateway(
    monkeypatch,
) -> None:
    fixture = _fixture()

    class ManualClock:
        value = 0.0

        @classmethod
        def now(cls) -> float:
            return cls.value

        @classmethod
        def advance_provider_budget(cls) -> None:
            cls.value += 21.0

    provider = _E5ReadOnlyProvider(on_analyse=ManualClock.advance_provider_budget)
    gateway = _CountingGateway()
    policy_calls: list[str] = []
    original_policy = collaboration._policy_gate_state

    def recording_policy(*args, **kwargs):
        policy_calls.append("policy")
        return original_policy(*args, **kwargs)

    monkeypatch.setattr(collaboration, "_policy_gate_state", recording_policy)
    runtime_control = collaboration._create_stage08_runtime_control(
        monotonic_now=ManualClock.now
    )
    command = _command(fixture)

    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=provider,
            tool_gateway=gateway,
        ),
        now=NOW,
        runtime_control=runtime_control,
    )

    assert view.status == "timed_out"
    assert provider.calls == 1
    assert policy_calls == []
    assert gateway.calls == 0
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.record_change_drafts == []
    _assert_trace_is_redacted(fixture, command)


def test_cancellation_during_gateway_rolls_back_ticket_idempotency_and_draft() -> None:
    fixture = _fixture()
    fixture.employee.allowed_actions = ["query", "summarize", "draft_update"]
    cancelled = Event()

    class CancellingGateway(Stage08ToolGateway):
        def execute_plan(self, uow, ticket, invocations, *, safe_context=None):
            completed = super().execute_plan(
                uow,
                ticket,
                invocations,
                safe_context=safe_context,
            )
            cancelled.set()
            return completed

    command = _safe_draft_command(
        fixture,
        idempotency_key="e5-cancel-during-gateway",
    )
    view = collaboration.run_stage08_collaboration(
        fixture.uow,
        command,
        fixture.actor,
        collaboration.Stage08CollaborationDependencies(
            analysis_provider=_ControlledDraftProvider(),
            tool_gateway=CancellingGateway(),
        ),
        now=NOW,
        runtime_control=collaboration._create_stage08_runtime_control(
            cancellation_probe=cancelled.is_set
        ),
    )

    assert view.status == "cancelled"
    assert fixture.uow.execution_tickets == []
    assert fixture.uow.idempotency_records == []
    assert fixture.uow.record_change_drafts == []
    _assert_trace_is_redacted(fixture, command)
