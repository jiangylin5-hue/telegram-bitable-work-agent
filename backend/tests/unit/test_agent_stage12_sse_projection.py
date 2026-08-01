from datetime import UTC, datetime, timedelta
from uuid import uuid4

import app.api.routes.agent_runs as agent_run_routes
from app.models.agent_event_runtime import AgentArtifact
from app.schemas.agent_event_runtime import AgentEventEnvelope
from app.schemas.agent_grounded_answer_v2 import GroundedComposerResultV2
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    append_agent_runtime_event,
    create_agent_run,
)
from app.services.agent_sse_projection import (
    project_grounded_safe_view,
    project_safe_run_events,
)


NOW = datetime(2026, 8, 1, 10, tzinfo=UTC)


def _grounded(*, answer_source: str = "real_provider"):
    return GroundedComposerResultV2.model_construct(
        status="completed" if answer_source == "real_provider" else "degraded",
        answer="当前证据支持该结论。",
        answer_source=answer_source,
        provider_result_status=(
            "completed" if answer_source == "real_provider" else "schema_failed"
        ),
        claim_ids=(),
        evidence_ids=tuple(f"evidence-{index}" for index in range(1, 15)),
        action_statuses=(),
        degradation_codes=(),
        render_receipt=None,
        provider_call_count=1,
        scope_hash="a" * 64,
        content_hash="b" * 64,
    )


def test_grounded_projection_exposes_only_safe_bounded_fields() -> None:
    view = project_grounded_safe_view(_grounded())

    payload = view.model_dump(mode="json")
    assert payload["answer_source"] == "real_provider"
    assert payload["provider_result_status"] == "completed"
    assert len(payload["citations"]) == 12
    assert "claim_ids" not in payload
    assert "evidence_ids" not in payload
    assert "content_hash" not in payload


def test_route_resolves_persisted_grounded_artifact_without_provider_call(
    monkeypatch,
) -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=1),
        now=NOW,
        workflow_version="stage12.quality-v2.runtime.v1",
    ).run
    artifact = AgentArtifact(
        id=uuid4(),
        run_id=run.id,
        kind="grounded_composer_result",
        storage_ref=f"stage08-idempotency:{uuid4()}",
        content_hash="c" * 64,
        visibility_scope_hash=run.scope_hash,
        validation_status="validated",
        expires_at=None,
    )
    uow.add_artifact(artifact)
    reads = 0

    def read(*_args, **_kwargs):
        nonlocal reads
        reads += 1
        return _grounded()

    monkeypatch.setattr(agent_run_routes, "read_typed_artifact", read)

    view = agent_run_routes._resolve_safe_view(uow, object(), artifact.id)

    assert reads == 1
    assert view.answer_source == "real_provider"
    assert view.provider_result_status == "completed"


def test_persisted_stage12_result_projects_before_done_and_replays() -> None:
    uow = InMemoryAgentEventRuntimeUnitOfWork()
    run = create_agent_run(
        uow,
        workspace_id=uuid4(),
        root_employee_id=uuid4(),
        scope_hash="a" * 64,
        idempotency_key_hash="b" * 64,
        deadline_at=NOW + timedelta(minutes=1),
        now=NOW,
    ).run
    artifact = AgentArtifact(
        id=uuid4(),
        run_id=run.id,
        kind="grounded_composer_result",
        storage_ref=f"stage08-idempotency:{uuid4()}",
        content_hash="c" * 64,
        visibility_scope_hash=run.scope_hash,
        validation_status="validated",
        expires_at=None,
    )
    uow.add_artifact(artifact)
    append_agent_runtime_event(
        uow,
        AgentEventEnvelope(
            event_id=uuid4(),
            run_id=run.id,
            causation_id=run.id,
            correlation_id=run.id,
            sequence=2,
            event_type="result.available",
            status="running",
            source_role="supervisor",
            safe_summary="回答已生成",
            artifact_ref=artifact.id,
            occurred_at=NOW,
        ),
        authorization_hash=run.scope_hash,
    )
    append_agent_runtime_event(
        uow,
        AgentEventEnvelope(
            event_id=uuid4(),
            run_id=run.id,
            causation_id=run.id,
            correlation_id=run.id,
            sequence=3,
            event_type="run.completed",
            status="completed",
            source_role="supervisor",
            safe_summary="完成",
            artifact_ref=artifact.id,
            occurred_at=NOW,
        ),
        authorization_hash=run.scope_hash,
        update_run_status="completed",
    )
    calls = 0

    def resolve(_artifact_ref):
        nonlocal calls
        calls += 1
        return project_grounded_safe_view(_grounded())

    first = project_safe_run_events(
        uow,
        run_id=run.id,
        authorization_hash=run.scope_hash,
        after_sequence=1,
        resolve_safe_view=resolve,
    )
    replay = project_safe_run_events(
        uow,
        run_id=run.id,
        authorization_hash=run.scope_hash,
        after_sequence=1,
        resolve_safe_view=resolve,
    )

    assert [item.event for item in first] == ["result", "done"]
    assert [item.model_dump(mode="json") for item in replay] == [
        item.model_dump(mode="json") for item in first
    ]
    assert calls == 2
