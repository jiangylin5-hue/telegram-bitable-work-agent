from __future__ import annotations

from datetime import datetime
import json

import pytest
from pydantic import ValidationError

from scripts.stage12_quality_evaluation import (
    EVALUATION_CLOCK,
    EVALUATION_TIMEZONE,
    EvaluationCaseV2,
    ExpectedActionSlot,
    ExpectedDependencyEdge,
    ExpectedObjective,
    ExpectedPredicate,
    ExpectedQueryResult,
    ExpectedTaskSpec,
    GoldAudit,
    RuntimeAnswerTrace,
    RuntimeQueryTrace,
    RuntimeRetrievalTrace,
    RuntimeSpecialistTraceV1,
    RuntimeTraceV2,
    canonical_sha256,
)


@pytest.mark.parametrize(
    ("answer_source", "provider_result_status"),
    (
        ("real_provider", "schema_failed"),
        ("deterministic_fallback", "completed"),
    ),
)
def test_runtime_answer_source_must_match_provider_status(
    answer_source: str, provider_result_status: str
) -> None:
    with pytest.raises(ValidationError, match="runtime_answer_source_mismatch"):
        RuntimeAnswerTrace(
            observation_status="observed",
            rendered_answer="安全回答。",
            claims=(),
            answer_source=answer_source,
            provider_result_status=provider_result_status,
        )


def _objective(objective_id: str = "obj-01") -> ExpectedObjective:
    return ExpectedObjective(
        objective_id=objective_id,
        kind="fact_query",
        required=True,
        entity_scope=("PRJ-ATLAS",),
        output_contract="structured_facts",
        predicates=(
            ExpectedPredicate(
                table_key="work_items",
                field_key="status",
                field_type="status",
                operator="eq",
                value="blocked",
            ),
        ),
        group_by=(),
        relation_paths=(("work_items.project_link",),),
    )


def _task_spec() -> ExpectedTaskSpec:
    return ExpectedTaskSpec(
        version="task-spec.v2",
        objectives=(_objective(),),
        dependency_edges=(),
        action_slots=(),
    )


def _query_result() -> ExpectedQueryResult:
    return ExpectedQueryResult(
        required_result_records=("MT-001",),
        allowed_evidence_records=("PRJ-ATLAS",),
        forbidden_result_records=("MT-004",),
        aggregates=(),
        relation_paths=(("work_items.project_link",),),
    )


def _audit() -> GoldAudit:
    return GoldAudit(
        source_fixture_hash="1" * 64,
        legacy_case_hash="2" * 64,
        v2_case_hash="3" * 64,
        reviewer="codex-source-audit",
        review_method="manual_source_audit",
        reviewed_at="2026-07-29T00:00:00+08:00",
        change_reason="converted_and_source_checked",
        status="agent_audited_pending_human_signoff",
    )


def _case() -> EvaluationCaseV2:
    return EvaluationCaseV2(
        version="evaluation-case.v2",
        case_id="join_01",
        category="multi_table",
        query="列出 Atlas 项目下阻塞的工作项。",
        schema_version="stage11.fixture.v1",
        timezone=EVALUATION_TIMEZONE,
        evaluation_clock=EVALUATION_CLOCK,
        expected_task_spec=_task_spec(),
        expected_query_result=_query_result(),
        expected_permission_outcome="allowed",
        gold_audit=_audit(),
    )


def test_contracts_are_strict_frozen_and_reject_extra_fields() -> None:
    case = _case()

    with pytest.raises(ValidationError, match="frozen"):
        case.case_id = "join_02"  # type: ignore[misc]

    payload = case.model_dump(mode="json")
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        EvaluationCaseV2.model_validate(payload)


def test_task_spec_rejects_duplicate_ids_and_unknown_dependency_references() -> None:
    with pytest.raises(ValidationError, match="evaluation_objective_ids_duplicate"):
        ExpectedTaskSpec(
            version="task-spec.v2",
            objectives=(_objective(), _objective()),
            dependency_edges=(),
            action_slots=(),
        )

    with pytest.raises(
        ValidationError, match="evaluation_dependency_reference_invalid"
    ):
        ExpectedTaskSpec(
            version="task-spec.v2",
            objectives=(_objective(),),
            dependency_edges=(
                ExpectedDependencyEdge(
                    from_objective_id="obj-01",
                    to_objective_id="obj-99",
                    required=True,
                ),
            ),
            action_slots=(),
        )


def test_predicate_operator_must_match_field_type() -> None:
    with pytest.raises(ValidationError, match="evaluation_predicate_operator_invalid"):
        ExpectedPredicate(
            table_key="work_items",
            field_key="priority",
            field_type="number",
            operator="contains",
            value="high",
        )


def test_query_truth_sets_must_be_disjoint() -> None:
    with pytest.raises(ValidationError, match="evaluation_query_truth_sets_overlap"):
        ExpectedQueryResult(
            required_result_records=("MT-001",),
            allowed_evidence_records=("MT-001",),
            forbidden_result_records=(),
            aggregates=(),
            relation_paths=(),
        )


def test_action_slot_uses_canonical_action_kind() -> None:
    with pytest.raises(ValidationError):
        ExpectedActionSlot(
            slot_id="act-01",
            objective_id="obj-02",
            action_kind="create_task",  # type: ignore[arg-type]
            target_selector={"table_key": "tasks"},
            assignments={"title": "跟进"},
            required_fields=("title",),
            confirmation_policy="required",
            conflict_group=None,
            expected_outcome="pending_confirmation",
        )


def test_action_slot_deadlines_must_be_utc_and_ordered() -> None:
    values = {
        "slot_id": "act-01",
        "objective_id": "obj-02",
        "action_kind": "reminder.request",
        "target_selector": {"record_code": "MT-001"},
        "assignments": {},
        "required_fields": (),
        "confirmation_policy": "required",
        "deadline_start_utc": datetime.fromisoformat("2026-07-28T16:00:00+00:00"),
        "deadline_end_utc": datetime.fromisoformat("2026-07-29T16:00:00+00:00"),
        "conflict_group": None,
        "expected_outcome": "blocked",
    }

    slot = ExpectedActionSlot(**values)
    assert slot.deadline_start_utc == values["deadline_start_utc"]
    assert slot.deadline_end_utc == values["deadline_end_utc"]

    with pytest.raises(
        ValidationError, match="evaluation_action_deadline_utc_required"
    ):
        ExpectedActionSlot(
            **{
                **values,
                "deadline_start_utc": datetime.fromisoformat(
                    "2026-07-29T00:00:00+08:00"
                ),
            }
        )

    with pytest.raises(
        ValidationError, match="evaluation_action_deadline_range_invalid"
    ):
        ExpectedActionSlot(
            **{
                **values,
                "deadline_start_utc": datetime.fromisoformat(
                    "2026-07-30T16:00:00+00:00"
                ),
            }
        )


def test_action_slot_allows_one_sided_utc_deadline() -> None:
    slot = ExpectedActionSlot(
        slot_id="act-01",
        objective_id="obj-02",
        action_kind="task.create",
        target_selector={"table_key": "tasks"},
        assignments={},
        required_fields=(),
        confirmation_policy="required",
        deadline_start_utc=None,
        deadline_end_utc=datetime.fromisoformat("2026-07-29T16:00:00+00:00"),
        conflict_group=None,
        expected_outcome="pending_confirmation",
    )

    assert slot.deadline_start_utc is None
    assert slot.deadline_end_utc is not None


def test_hashes_are_lowercase_sha256() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )

    payload = _audit().model_dump(mode="json")
    payload["v2_case_hash"] = "A" * 64
    with pytest.raises(ValidationError):
        GoldAudit.model_validate(payload)


def test_case_requires_fixed_timezone_and_clock() -> None:
    payload = _case().model_dump(mode="json")
    payload["timezone"] = "UTC"
    with pytest.raises(ValidationError, match="literal_error"):
        EvaluationCaseV2.model_validate(payload)

    payload = _case().model_dump(mode="json")
    payload["evaluation_clock"] = "2026-07-29T00:00:00Z"
    with pytest.raises(ValidationError, match="literal_error"):
        EvaluationCaseV2.model_validate(payload)


def test_contract_json_round_trip_is_stable() -> None:
    case = _case()
    rendered = case.model_dump_json()
    restored = EvaluationCaseV2.model_validate_json(rendered)

    assert restored == case
    assert json.loads(restored.model_dump_json()) == json.loads(rendered)


def test_runtime_trace_does_not_derive_candidates_from_answer() -> None:
    trace = RuntimeTraceV2(
        version="runtime-trace.v2",
        case_id="join_01",
        round_id="deterministic-01",
        provider=None,
        planner=None,
        specialists=(),
        query=RuntimeQueryTrace(
            observation_status="not_observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=(),
            aggregates=(),
            facts=(),
            complete=False,
        ),
        retrieval=RuntimeRetrievalTrace(
            observation_status="not_observed",
            candidate_record_ids=(),
            selected_evidence_record_ids=(),
            candidate_table_by_record={},
            relation_paths=(),
            complete=False,
        ),
        answer={
            "observation_status": "observed",
            "rendered_answer": "结果为 MT-001。",
            "claims": (),
            "answer_source": "real_provider",
            "provider_result_status": "completed",
        },
        actions=(),
        safety={
            "permission_outcome": "allowed",
            "unauthorized_effect_count": 0,
            "external_send_count": 0,
        },
        durability={
            "terminal": True,
            "recovery_expectation": "required",
            "recovered": True,
            "idempotent": True,
            "duplicate_effect_count": 0,
        },
        latency={"segments_ms": {"total": 10}},
    )

    assert trace.retrieval.candidate_record_ids == ()
    assert trace.retrieval.selected_evidence_record_ids == ()


def test_specialist_trace_owns_derived_facts_and_rejects_duplicate_identity() -> None:
    fact = {
        "fact_id": "specialist-fact-01",
        "subject": "MT-004",
        "predicate": "risk_severity",
        "value": "high",
        "evidence_ids": ("MT-004",),
        "source_versions": ({"record_id": "MT-004", "record_version": 3},),
    }

    trace = RuntimeSpecialistTraceV1(
        objective_id="obj-risk",
        capability_id="platform.risk.analyse",
        artifact_kind="risk_assessment_set",
        artifact_version="risk-assessment-set.v1",
        artifact_hash="a" * 64,
        status="completed",
        derived_facts=(fact,),
    )

    assert trace.derived_facts[0].predicate == "risk_severity"
    with pytest.raises(
        ValidationError, match="runtime_specialist_fact_identity_duplicate"
    ):
        RuntimeSpecialistTraceV1(
            objective_id="obj-risk",
            capability_id="platform.risk.analyse",
            artifact_kind="risk_assessment_set",
            artifact_version="risk-assessment-set.v1",
            artifact_hash="a" * 64,
            status="completed",
            derived_facts=(fact, fact),
        )
