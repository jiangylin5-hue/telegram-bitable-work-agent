from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.agent_event_runtime import (
    AgentArtifact,
    AgentEvent,
    AgentRunCheckpoint,
    AgentWorkflowRun,
)
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from scripts.stage12_stage11_trace_adapter import collect_stage11_runtime_trace


def _runtime_fixture():
    now = datetime(2026, 7, 29, tzinfo=UTC)
    run_id = uuid4()
    artifact_id = uuid4()
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = AgentWorkflowRun(
        id=run_id,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        target_record_id=None,
        parent_run_id=None,
        workflow_version="stage11.v1",
        status="completed",
        scope_hash="a" * 64,
        data_version_hash="b" * 64,
        deadline_at=now + timedelta(minutes=5),
        lease_owner=None,
        lease_expires_at=None,
        idempotency_key_hash="c" * 64,
        safe_result_ref=artifact_id,
        version=4,
    )
    artifact = AgentArtifact(
        id=artifact_id,
        run_id=run_id,
        kind="assistant_safe_view",
        storage_ref="stage08-idempotency:test-result",
        content_hash="d" * 64,
        visibility_scope_hash="a" * 64,
        validation_status="validated",
        expires_at=None,
    )
    checkpoint = AgentRunCheckpoint(
        id=uuid4(),
        run_id=run_id,
        checkpoint_no=1,
        node_key="run_completed",
        status="completed",
        control_json={"retry_count": 0},
        authorization_hash="a" * 64,
        data_version_hash="b" * 64,
    )
    event = AgentEvent(
        id=uuid4(),
        run_id=run_id,
        command_id=None,
        event_type="run.completed",
        sequence=1,
        causation_id=run_id,
        correlation_id=run_id,
        source_role="supervisor",
        source_capability=None,
        status="completed",
        safe_summary="完成",
        artifact_ref=artifact_id,
        metrics_json={
            "planner_ms": 12,
            "provider_ms": 30,
            "external_send_count": 0,
            "unauthorized_effect_count": 0,
            "duplicate_effect_count": 0,
        },
    )
    uow.runs.append(run)
    uow.artifacts.append(artifact)
    uow.checkpoints.append(checkpoint)
    uow.events.append(event)
    return uow, run_id, artifact_id


def test_adapter_maps_durable_terminal_safety_latency_and_safe_answer() -> None:
    uow, run_id, artifact_id = _runtime_fixture()

    trace = collect_stage11_runtime_trace(
        run_id,
        uow=uow,
        case_id="join_02",
        round_id="round-01",
        permission_outcome="allowed",
        resolve_safe_view=lambda value: (
            {
                "answer": "MT-004 对应 RISK-004。",
                "citations": [{"record_id": "MT-004"}],
            }
            if value == artifact_id
            else None
        ),
    )

    assert trace.case_id == "join_02"
    assert trace.answer.observation_status == "observed"
    assert trace.answer.rendered_answer == "MT-004 对应 RISK-004。"
    assert trace.answer.claims == ()
    assert trace.safety.external_send_count == 0
    assert trace.safety.unauthorized_effect_count == 0
    assert trace.durability.terminal is True
    assert trace.durability.idempotent is True
    assert trace.durability.duplicate_effect_count == 0
    assert trace.latency.segments_ms == {"planner": 12, "provider": 30}


def test_adapter_does_not_promote_safe_citations_or_answer_codes_to_candidates() -> (
    None
):
    uow, run_id, artifact_id = _runtime_fixture()

    trace = collect_stage11_runtime_trace(
        run_id,
        uow=uow,
        case_id="join_02",
        round_id="round-01",
        permission_outcome="allowed",
        resolve_safe_view=lambda value: (
            {
                "answer": "答案里出现 MT-004、RISK-004 和伪造 MT-999。",
                "citations": [
                    {"record_id": "MT-004"},
                    {"record_id": "RISK-004"},
                ],
            }
            if value == artifact_id
            else None
        ),
    )

    assert trace.planner is None
    assert trace.query.observation_status == "not_observed"
    assert trace.retrieval.observation_status == "not_observed"
    assert trace.retrieval.candidate_record_ids == ()
    assert trace.retrieval.selected_evidence_record_ids == ()
    assert trace.query.result_record_ids == ()
    assert trace.query.complete is False


def test_adapter_marks_missing_safe_artifact_as_not_observed() -> None:
    uow, run_id, _ = _runtime_fixture()

    trace = collect_stage11_runtime_trace(
        run_id,
        uow=uow,
        case_id="join_02",
        round_id="round-01",
        permission_outcome="allowed",
        resolve_safe_view=lambda _value: None,
    )

    assert trace.answer.observation_status == "not_observed"
    assert trace.answer.rendered_answer == ""
    assert trace.answer.claims == ()
