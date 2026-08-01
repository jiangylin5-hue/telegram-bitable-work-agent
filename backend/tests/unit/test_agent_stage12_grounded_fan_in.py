from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV3,
    GroundedRenderSlotTextV1,
)
from app.schemas.agent_specialist_results import (
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import (
    AuthorizedSchemaSnapshot,
    PlannerCostEstimate,
    SourceSpan,
    TaskObjectiveV2,
    TaskOutputSpec,
    TaskSpecV2,
    authorized_schema_sha256,
)
from app.services.agent_claim_graph import (
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
)
from app.services.agent_composer_v2 import (
    ComposerObjectiveContextV1,
    ComposerPresentationContextV1,
)
from app.services.agent_stage12_grounded_fan_in import (
    compose_stage12_grounded_result,
)


SCOPE_HASH = "a" * 64
TABLE_ID = UUID("75000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("75000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("75000000-0000-4000-8000-000000000003")


def _schema() -> AuthorizedSchemaSnapshot:
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": UUID("75000000-0000-4000-8000-000000000004"),
        "employee_id": UUID("75000000-0000-4000-8000-000000000005"),
        "scope_hash": SCOPE_HASH,
        "tables": (),
        "field_policy_version": "stage12-field-policy.v2",
        "field_policy_hash": "b" * 64,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _task_spec(schema_hash: str) -> TaskSpecV2:
    return TaskSpecV2(
        version="task-spec.v2",
        authorized_schema_hash=schema_hash,
        query_intents=(),
        objectives=(
            TaskObjectiveV2(
                objective_id="obj-facts",
                kind="fact_query",
                required=True,
                entity_codes=("Atlas",),
                query_spec_ref=None,
                output_contract="structured_facts",
                planning_outcome="planned",
                denial_reason=None,
                source_spans=(SourceSpan(start=0, end=5, text="Atlas"),),
            ),
        ),
        dependency_edges=(),
        action_slots=(),
        conflict_groups=(),
        output=TaskOutputSpec(
            language="zh-Hans",
            format="conversational",
            include_evidence=True,
        ),
        cost=PlannerCostEstimate(
            lexical_token_count=5,
            bound_field_count=1,
            objective_count=1,
            action_slot_count=0,
            ambiguity_count=0,
            planned_provider_calls=0,
        ),
        provider_call_count=0,
    )


def _facts(schema_hash: str) -> StructuredFactSetV1:
    values = {
        "version": "structured-fact-set.v1",
        "objective_id": "obj-facts",
        "records": (
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            {"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": 7},
        ),
        "evidence_refs": ("ev-status",),
        "scope_hash": SCOPE_HASH,
        "schema_hash": schema_hash,
        "complete": True,
        "truncated": False,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return StructuredFactSetV1.model_validate(values)


def _fixture():
    schema = _schema()
    facts = _facts(schema.schema_hash)
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="obj-facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-status",),
                source_version=7,
            ),
        ),
        outcomes=(ObjectiveOutcomeInputV1("obj-facts", "completed", True),),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=(facts,),
    )
    presentation = ComposerPresentationContextV1(
        query="列出 Atlas 未完成任务",
        objectives=(
            ComposerObjectiveContextV1(
                objective_id="obj-facts",
                kind="fact_query",
                required=True,
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "Atlas 项目"},
        predicate_labels={f"field:{FIELD_ID}": "任务状态"},
    )
    return schema, _task_spec(schema.schema_hash), facts, graph, presentation


class _SuccessfulProvider:
    observations = (SimpleNamespace(attempt=1),)
    slot_observations = (SimpleNamespace(attempt_count=1),)

    def __call__(self, request):
        assert request.version == "grounded-answer-provider-request.v3"
        return GroundedAnswerPlanV3(
            slot_outputs=tuple(
                GroundedRenderSlotTextV1(
                    slot_handle=slot.slot_handle,
                    text=(
                        "当前存在无法完成的部分，未提供未经验证的结论。"
                        if slot.statement_kind == "limitation"
                        else "Atlas 项目的任务状态为 blocked。"
                    ),
                )
                for slot in request.render_slots
            )
        )


class _FailingProvider:
    observations = (SimpleNamespace(attempt=1),)
    slot_observations = (SimpleNamespace(attempt_count=1),)

    def __init__(self, code: str) -> None:
        self.code = code

    def __call__(self, _request):
        error = RuntimeError("raw-secret-provider-response")
        error.code = self.code
        raise error


def test_real_provider_result_is_authoritative() -> None:
    schema, task_spec, facts, graph, presentation = _fixture()

    result = compose_stage12_grounded_result(
        query=presentation.query,
        task_spec=task_spec,
        claim_graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(facts,),
        provider=_SuccessfulProvider(),
    )

    assert result.answer_source == "real_provider"
    assert result.provider_result_status == "completed"
    assert result.provider_call_count == 1
    assert "Atlas 项目" in result.answer


@pytest.mark.parametrize(
    ("failure_code", "expected_status"),
    (
        ("provider_http_error", "transport_failed"),
        ("provider_schema_invalid", "schema_failed"),
        ("provider_grounding_invalid", "grounding_failed"),
        ("provider_language_invalid", "language_failed"),
    ),
)
def test_provider_failure_is_visible_and_raw_output_is_not_retained(
    failure_code: str,
    expected_status: str,
) -> None:
    schema, task_spec, facts, graph, presentation = _fixture()

    result = compose_stage12_grounded_result(
        query=presentation.query,
        task_spec=task_spec,
        claim_graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(facts,),
        provider=_FailingProvider(failure_code),
    )

    assert result.answer_source == "deterministic_fallback"
    assert result.provider_result_status == expected_status
    assert result.status == "degraded"
    assert "raw-secret-provider-response" not in result.model_dump_json()


def test_required_specialist_failure_prevents_provider_call() -> None:
    schema, task_spec, facts, _graph, presentation = _fixture()
    graph = build_claim_graph(
        claims=(),
        outcomes=(
            ObjectiveOutcomeInputV1(
                "obj-facts", "failed", True, "specialist_failed"
            ),
        ),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=(),
    )
    provider = _SuccessfulProvider()

    result = compose_stage12_grounded_result(
        query=presentation.query,
        task_spec=task_spec,
        claim_graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(facts,),
        provider=provider,
    )

    assert result.answer_source == "deterministic_fallback"
    assert result.provider_result_status == "grounding_failed"
    assert result.provider_call_count == 0
    assert result.status == "failed"


def test_optional_specialist_failure_keeps_visible_degraded_result() -> None:
    schema, task_spec, facts, graph, presentation = _fixture()
    optional = TaskObjectiveV2(
        objective_id="obj-optional",
        kind="risk_analysis",
        required=False,
        entity_codes=("Atlas",),
        query_spec_ref=None,
        output_contract="risk_assessment",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(SourceSpan(start=0, end=5, text="Atlas"),),
    )
    task_values = task_spec.model_dump(mode="python")
    task_values["objectives"] = (*task_spec.objectives, optional)
    task_values["cost"]["objective_count"] = 2
    task_spec = TaskSpecV2.model_validate(task_values)
    graph = build_claim_graph(
        claims=tuple(
            ClaimInputV1(
                objective_id=next(iter(claim.objective_ids)),
                subject_ref=claim.subject_ref,
                predicate=claim.predicate,
                value=claim.value,
                evidence_ids=claim.evidence_ids,
                source_version=claim.source_version,
            )
            for claim in graph.claims
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-facts", "completed", True),
            ObjectiveOutcomeInputV1(
                "obj-optional", "failed", False, "specialist_failed"
            ),
        ),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=(facts,),
    )
    presentation = presentation.model_copy(
        update={
            "objectives": (
                *presentation.objectives,
                ComposerObjectiveContextV1(
                    objective_id="obj-optional",
                    kind="risk_analysis",
                    required=False,
                ),
            )
        }
    )

    result = compose_stage12_grounded_result(
        query=presentation.query,
        task_spec=task_spec,
        claim_graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(facts,),
        provider=_SuccessfulProvider(),
    )

    assert result.answer_source == "real_provider"
    assert result.provider_result_status == "completed"
    assert result.status == "degraded"
    assert "specialist_failed" in result.degradation_codes


def test_oversize_provider_answer_becomes_schema_fallback(monkeypatch) -> None:
    schema, task_spec, facts, graph, presentation = _fixture()
    monkeypatch.setattr(
        "app.services.agent_stage12_grounded_fan_in.render_grounded_answer",
        lambda *_args, **_kwargs: SimpleNamespace(answer="中" * 2001),
    )

    result = compose_stage12_grounded_result(
        query=presentation.query,
        task_spec=task_spec,
        claim_graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(facts,),
        provider=_SuccessfulProvider(),
    )

    assert result.answer_source == "deterministic_fallback"
    assert result.provider_result_status == "schema_failed"
    assert len(result.answer) <= 2000
