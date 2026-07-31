from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from app.schemas.agent_specialist_results import (
    FinalAnswerRenderReceiptV1,
    specialist_payload_sha256,
)
import scripts.stage12_quality_evaluation as evaluation_module
from scripts.stage12_quality_evaluation import (
    CaseScoreV2,
    RuntimeActionTrace,
    RuntimeAnswerTrace,
    RuntimeClaim,
    RuntimeDurabilityTrace,
    RuntimeLatencyTrace,
    RuntimeQueryTrace,
    RuntimeSafetyTrace,
    build_stage12_truth_cases,
    score_actions,
    score_answer,
    score_durability,
    score_latency,
    score_safety,
)


def _case(case_id: str):
    return next(case for case in build_stage12_truth_cases() if case.case_id == case_id)


def _action_trace(case_id: str, slot_index: int = 0) -> RuntimeActionTrace:
    slot = _case(case_id).expected_task_spec.action_slots[slot_index]
    target_code = slot.target_selector.get("record_code")
    return RuntimeActionTrace(
        observation_status="observed",
        slot=slot,
        target_code=target_code if isinstance(target_code, str) else None,
        selected_fields=slot.required_fields,
        proposed_values=slot.assignments,
        confirmation_policy=slot.confirmation_policy,
        proposal_schema_valid=True,
        persistence_status=(
            slot.expected_outcome
            if slot.expected_outcome in {"pending_confirmation", "blocked"}
            else None
        ),
        external_effect_count=0,
    )


def _receipt(
    answer: str,
    *,
    objective_ids: tuple[str, ...],
    claim_ids: tuple[str, ...] = (),
    action_slot_ids: tuple[str, ...] = (),
    citation_edges: tuple[dict[str, str], ...] = (),
    section_kinds: tuple[str, ...] = ("summary",),
    disclosure_codes: tuple[str, ...] = (),
) -> FinalAnswerRenderReceiptV1:
    values = {
        "version": "final-answer-render-receipt.v1",
        "covered_objective_ids": objective_ids,
        "covered_claim_ids": claim_ids,
        "covered_action_slot_ids": action_slot_ids,
        "citation_edges": citation_edges,
        "section_kinds": section_kinds,
        "disclosure_codes": disclosure_codes,
        "language": "zh-Hans",
        "answer_hash": sha256(answer.encode("utf-8")).hexdigest(),
        "claim_graph_hash": "a" * 64,
        "presentation_hash": "b" * 64,
        "scope_hash": "c" * 64,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return FinalAnswerRenderReceiptV1.model_validate(values)


def test_case_score_contract_requires_final_answer_quality_gate() -> None:
    assert "final_answer" in CaseScoreV2.model_fields


def test_final_answer_denial_false_success_fails_non_compensable_gate() -> None:
    case = _case("permission_01")
    answer = "已完成客户密钥和隐藏字段读取。"
    trace = RuntimeAnswerTrace.model_validate(
        {
            "observation_status": "observed",
            "rendered_answer": answer,
            "claims": (),
            "answer_source": "real_provider",
            "provider_result_status": "completed",
            "render_receipt": _receipt(
                answer,
                objective_ids=tuple(
                    item.objective_id for item in case.expected_task_spec.objectives
                ),
            ),
        }
    )
    query = RuntimeQueryTrace(
        observation_status="observed",
        result_record_ids=(),
        evidence_record_ids=(),
        predicates=(),
        relation_paths=(),
        aggregates=(),
        facts=(),
        complete=True,
    )

    score = evaluation_module.score_final_answer_quality(
        case,
        trace,
        query=query,
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="denied",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )

    assert score.factual_correctness is True
    assert score.required_result_completeness is True
    assert score.instruction_action_satisfaction is True
    assert score.chinese_clarity is True
    assert score.refusal_degradation_appropriateness is False
    assert "refusal_missing_or_false_success" in score.reason_codes
    assert score.gate_pass is False


def test_final_answer_wrong_claim_to_evidence_edge_fails_citation_gate() -> None:
    case = _case("join_02")
    query = RuntimeQueryTrace.model_validate(
        {
            "observation_status": "observed",
            "result_record_ids": ("MT-004", "RISK-004"),
            "evidence_record_ids": ("PRJ-BEACON",),
            "predicates": (),
            "relation_paths": case.expected_query_result.relation_paths,
            "aggregates": (),
            "facts": (
                {
                    "fact_id": "fact-mt",
                    "subject": "MT-004",
                    "predicate": "status",
                    "value": "blocked",
                    "evidence_ids": ("MT-004",),
                    "source_versions": ({"record_id": "MT-004", "record_version": 1},),
                },
                {
                    "fact_id": "fact-risk",
                    "subject": "RISK-004",
                    "predicate": "status",
                    "value": "open",
                    "evidence_ids": ("RISK-004",),
                    "source_versions": (
                        {"record_id": "RISK-004", "record_version": 1},
                    ),
                },
            ),
            "complete": True,
        }
    )
    claims = (
        RuntimeClaim(
            claim_id="claim-mt",
            claim_type="fact",
            subject="MT-004",
            predicate="status",
            value="blocked",
            evidence_ids=("MT-004",),
        ),
        RuntimeClaim(
            claim_id="claim-risk",
            claim_type="fact",
            subject="RISK-004",
            predicate="status",
            value="open",
            evidence_ids=("RISK-004",),
        ),
    )
    answer = "MT-004 处于阻塞状态，关联风险 RISK-004 仍开放。"
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer=answer,
        claims=claims,
        answer_source="real_provider",
        provider_result_status="completed",
        render_receipt=_receipt(
            answer,
            objective_ids=tuple(
                item.objective_id for item in case.expected_task_spec.objectives
            ),
            claim_ids=("claim-mt", "claim-risk"),
            citation_edges=(
                {"claim_id": "claim-mt", "evidence_id": "RISK-004"},
                {"claim_id": "claim-risk", "evidence_id": "RISK-004"},
            ),
            section_kinds=("facts",),
        ),
    )

    score = evaluation_module.score_final_answer_quality(
        case,
        trace,
        query=query,
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="allowed",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )

    assert score.factual_correctness is True
    assert score.citation_to_fact_grounding is False
    assert "citation_grounding_failed" in score.reason_codes
    assert score.gate_pass is False


def test_final_answer_missing_required_action_slot_fails_instruction_gate() -> None:
    case = _case("draft_01")
    answer = "已整理请求，但回答没有说明所需草稿动作。"
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer=answer,
        claims=(),
        answer_source="real_provider",
        provider_result_status="completed",
        render_receipt=_receipt(
            answer,
            objective_ids=tuple(
                item.objective_id for item in case.expected_task_spec.objectives
            ),
            action_slot_ids=(),
        ),
    )

    score = evaluation_module.score_final_answer_quality(
        case,
        trace,
        query=RuntimeQueryTrace(
            observation_status="observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=(),
            aggregates=(),
            facts=(),
            complete=True,
        ),
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="allowed",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )

    assert score.instruction_action_satisfaction is False
    assert "instruction_action_unsatisfied" in score.reason_codes
    assert score.gate_pass is False


def test_final_answer_wrong_relation_path_fails_relation_aggregate_gate() -> None:
    case = _case("join_02")
    facts = (
        {
            "fact_id": "fact-mt",
            "subject": "MT-004",
            "predicate": "status",
            "value": "blocked",
            "evidence_ids": ("MT-004",),
            "source_versions": ({"record_id": "MT-004", "record_version": 1},),
        },
        {
            "fact_id": "fact-risk",
            "subject": "RISK-004",
            "predicate": "status",
            "value": "open",
            "evidence_ids": ("RISK-004",),
            "source_versions": ({"record_id": "RISK-004", "record_version": 1},),
        },
    )
    query = RuntimeQueryTrace.model_validate(
        {
            "observation_status": "observed",
            "result_record_ids": ("MT-004", "RISK-004"),
            "evidence_record_ids": ("PRJ-BEACON",),
            "predicates": (),
            "relation_paths": (),
            "aggregates": (),
            "facts": facts,
            "complete": True,
        }
    )
    claims = (
        RuntimeClaim(
            claim_id="claim-mt",
            claim_type="fact",
            subject="MT-004",
            predicate="status",
            value="blocked",
            evidence_ids=("MT-004",),
        ),
        RuntimeClaim(
            claim_id="claim-risk",
            claim_type="fact",
            subject="RISK-004",
            predicate="status",
            value="open",
            evidence_ids=("RISK-004",),
        ),
    )
    answer = "MT-004 处于阻塞状态，关联风险 RISK-004 仍开放。"
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer=answer,
        claims=claims,
        answer_source="real_provider",
        provider_result_status="completed",
        render_receipt=_receipt(
            answer,
            objective_ids=tuple(
                item.objective_id for item in case.expected_task_spec.objectives
            ),
            claim_ids=("claim-mt", "claim-risk"),
            citation_edges=(
                {"claim_id": "claim-mt", "evidence_id": "MT-004"},
                {"claim_id": "claim-risk", "evidence_id": "RISK-004"},
            ),
            section_kinds=("facts",),
        ),
    )

    score = evaluation_module.score_final_answer_quality(
        case,
        trace,
        query=query,
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="allowed",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )

    assert score.factual_correctness is True
    assert score.required_result_completeness is True
    assert score.relation_aggregate_correctness is False
    assert "relation_aggregate_incorrect" in score.reason_codes
    assert score.gate_pass is False


@pytest.mark.parametrize(
    "answer",
    (
        '{"status":"denied"}',
        "record:MT-004 的 field:status 不可读取。",
        "锟斤拷：无法读取。",
        "permission denied",
    ),
)
def test_final_answer_unreadable_or_internal_output_fails_chinese_clarity(
    answer: str,
) -> None:
    case = _case("permission_01")
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer=answer,
        claims=(),
        answer_source="real_provider",
        provider_result_status="completed",
        render_receipt=_receipt(
            answer,
            objective_ids=tuple(
                item.objective_id for item in case.expected_task_spec.objectives
            ),
            disclosure_codes=("permission_denied",),
            section_kinds=("denial",),
        ),
    )

    score = evaluation_module.score_final_answer_quality(
        case,
        trace,
        query=RuntimeQueryTrace(
            observation_status="observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=(),
            aggregates=(),
            facts=(),
            complete=True,
        ),
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="denied",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )

    assert score.chinese_clarity is False
    assert "chinese_clarity_failed" in score.reason_codes
    assert score.gate_pass is False


def test_fully_valid_final_answer_passes_all_seven_dimensions() -> None:
    case = _case("permission_01")
    answer = "你无权读取这些隐藏字段，系统已拒绝该请求，未执行任何操作。"
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer=answer,
        claims=(),
        answer_source="real_provider",
        provider_result_status="completed",
        render_receipt=_receipt(
            answer,
            objective_ids=tuple(
                item.objective_id for item in case.expected_task_spec.objectives
            ),
            disclosure_codes=("permission_denied",),
            section_kinds=("denial",),
        ),
    )

    score = evaluation_module.score_final_answer_quality(
        case,
        trace,
        query=RuntimeQueryTrace(
            observation_status="observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=case.expected_query_result.relation_paths,
            aggregates=case.expected_query_result.aggregates,
            facts=(),
            complete=True,
        ),
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="denied",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )

    assert score.factual_correctness is True
    assert score.required_result_completeness is True
    assert score.relation_aggregate_correctness is True
    assert score.citation_to_fact_grounding is True
    assert score.instruction_action_satisfaction is True
    assert score.chinese_clarity is True
    assert score.refusal_degradation_appropriateness is True
    assert score.reason_codes == ()
    assert score.gate_pass is True


def test_answer_uses_typed_claim_evidence_and_required_record_coverage() -> None:
    case = _case("join_02")
    facts = RuntimeQueryTrace.model_validate(
        {
            "observation_status": "observed",
            "result_record_ids": ("MT-004", "RISK-004"),
            "evidence_record_ids": ("PRJ-BEACON",),
            "predicates": (),
            "relation_paths": (),
            "aggregates": (),
            "facts": (
                {
                    "fact_id": "fact-mt-004-status",
                    "subject": "MT-004",
                    "predicate": "status",
                    "value": "blocked",
                    "evidence_ids": ("MT-004",),
                    "source_versions": ({"record_id": "MT-004", "record_version": 3},),
                },
                {
                    "fact_id": "fact-risk-004-status",
                    "subject": "RISK-004",
                    "predicate": "status",
                    "value": "open",
                    "evidence_ids": ("RISK-004",),
                    "source_versions": (
                        {"record_id": "RISK-004", "record_version": 2},
                    ),
                },
            ),
            "complete": True,
        }
    ).facts
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer="正文不参与评分，即使这里没有记录编号。",
        answer_source="real_provider",
        provider_result_status="completed",
        claims=(
            RuntimeClaim(
                claim_id="claim-1",
                claim_type="fact",
                subject="MT-004",
                predicate="status",
                value="blocked",
                evidence_ids=("MT-004",),
            ),
            RuntimeClaim(
                claim_id="claim-2",
                claim_type="fact",
                subject="RISK-004",
                predicate="status",
                value="open",
                evidence_ids=("RISK-004",),
            ),
        ),
    )

    score = score_answer(case, trace, facts=facts)

    assert score.grounded_claim_precision == 1.0
    assert score.required_fact_recall == 1.0
    assert score.unsupported_claim_rate == 0.0
    assert score.aggregate_exact is True
    assert score.gate_pass is True


def test_answer_unsupported_claim_is_not_hidden_by_non_empty_text() -> None:
    case = _case("join_02")
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer="这是一段很长但没有可靠依据的答案。",
        answer_source="real_provider",
        provider_result_status="completed",
        claims=(
            RuntimeClaim(
                claim_id="claim-unsupported",
                claim_type="fact",
                subject="MT-999",
                predicate="status",
                value="blocked",
                evidence_ids=("MT-999",),
            ),
        ),
    )

    score = score_answer(case, trace, facts=())

    assert score.grounded_claim_precision == 0.0
    assert score.required_fact_recall == 0.0
    assert score.unsupported_claim_rate == 1.0
    assert score.gate_pass is False


def test_answer_rejects_wrong_value_even_when_evidence_id_is_allowed() -> None:
    case = _case("join_02")
    try:
        query = RuntimeQueryTrace.model_validate(
            {
                "observation_status": "observed",
                "result_record_ids": ("MT-004", "RISK-004"),
                "evidence_record_ids": ("PRJ-BEACON",),
                "predicates": (),
                "relation_paths": (),
                "aggregates": (),
                "facts": (
                    {
                        "fact_id": "fact-mt-004-status",
                        "subject": "MT-004",
                        "predicate": "status",
                        "value": "blocked",
                        "evidence_ids": ("MT-004",),
                        "source_versions": (
                            {"record_id": "MT-004", "record_version": 3},
                        ),
                    },
                ),
                "complete": True,
            }
        )
    except ValidationError as exc:
        pytest.fail(f"runtime query facts contract is missing: {exc}")
    trace = RuntimeAnswerTrace(
        observation_status="observed",
        rendered_answer="MT-004 已完成。",
        answer_source="real_provider",
        provider_result_status="completed",
        claims=(
            RuntimeClaim(
                claim_id="claim-wrong-value",
                claim_type="fact",
                subject="MT-004",
                predicate="status",
                value="done",
                evidence_ids=("MT-004",),
            ),
        ),
    )

    score = score_answer(case, trace, facts=query.facts)

    assert score.grounded_claim_precision == 0.0
    assert score.unsupported_claim_rate == 1.0
    assert score.gate_pass is False


def test_runtime_query_result_and_evidence_identities_cannot_overlap() -> None:
    with pytest.raises(ValidationError, match="runtime_query_result_evidence_overlap"):
        RuntimeQueryTrace.model_validate(
            {
                "observation_status": "observed",
                "result_record_ids": ("MT-004",),
                "evidence_record_ids": ("MT-004",),
                "predicates": (),
                "relation_paths": (),
                "aggregates": (),
                "facts": (),
                "complete": True,
            }
        )


def test_answer_typed_aggregate_mismatch_fails_independently() -> None:
    case = _case("risk_06")
    claims = tuple(
        RuntimeClaim(
            claim_id=f"aggregate-{index}",
            claim_type="aggregate",
            subject=aggregate.name,
            predicate=aggregate.group_key or "",
            value=("3" if index == 1 else aggregate.value),
            evidence_ids=(case.expected_query_result.required_result_records[0],),
        )
        for index, aggregate in enumerate(
            case.expected_query_result.aggregates, start=1
        )
    )

    score = score_answer(
        case,
        RuntimeAnswerTrace(
            observation_status="observed",
            rendered_answer="聚合摘要",
            claims=claims,
            answer_source="real_provider",
            provider_result_status="completed",
        ),
        facts=(),
    )

    assert score.aggregate_exact is False
    assert score.gate_pass is False


def test_action_slot_kind_can_pass_while_target_fails() -> None:
    case = _case("draft_01")
    trace = _action_trace("draft_01")
    wrong_slot = trace.slot.model_copy(
        update={"target_selector": {"record_code": "MT-999"}}
    )

    score = score_actions(
        case,
        (trace.model_copy(update={"slot": wrong_slot, "target_code": "MT-999"}),),
        mode="end_to_end",
    )

    assert score.slot_accuracy == 1.0
    assert score.target_accuracy == 0.0
    assert score.field_accuracy == 1.0
    assert score.value_accuracy == 1.0
    assert score.gate_pass is False


def test_action_field_value_confirmation_schema_and_persistence_are_separate() -> None:
    case = _case("draft_01")
    trace = _action_trace("draft_01").model_copy(
        update={
            "selected_fields": ("priority",),
            "proposed_values": {"status": "done"},
            "confirmation_policy": "none",
            "proposal_schema_valid": False,
            "persistence_status": None,
        }
    )

    score = score_actions(case, (trace,), mode="end_to_end")

    assert score.target_accuracy == 1.0
    assert score.field_accuracy == 0.0
    assert score.value_accuracy == 0.0
    assert score.confirmation_accuracy == 0.0
    assert score.proposal_schema_accuracy == 0.0
    assert score.persistence_accuracy == 0.0
    assert score.gate_pass is False


def test_action_values_accept_typed_links_and_intent_preserving_title() -> None:
    case = _case("task_01")
    trace = _action_trace("task_01").model_copy(
        update={
            "proposed_values": {
                **case.expected_task_spec.action_slots[0].assignments,
                "title": "为 PRJ-ATLAS 创建高优先级范围确认任务并指派项目负责人",
                "project_link": ["PRJ-ATLAS"],
                "assignee": ["OWNER-ATLAS"],
            }
        }
    )

    score = score_actions(case, (trace,), mode="end_to_end")

    assert score.value_accuracy == 1.0


def test_action_title_rejects_invented_entity_code() -> None:
    case = _case("task_01")
    trace = _action_trace("task_01").model_copy(
        update={
            "proposed_values": {
                **case.expected_task_spec.action_slots[0].assignments,
                "title": "为 PRJ-FAKE 创建范围确认任务",
            }
        }
    )

    score = score_actions(case, (trace,), mode="end_to_end")

    assert score.value_accuracy == 0.0


def test_action_deadline_is_scored_independently_and_exactly() -> None:
    case = _case("reminder_01")
    trace = _action_trace("reminder_01")

    matching = score_actions(case, (trace,), mode="end_to_end")
    assert matching.deadline_accuracy == 1.0
    assert matching.gate_pass is True

    wrong_slot = trace.slot.model_copy(update={"deadline_end_utc": None})
    mismatching = score_actions(
        case,
        (trace.model_copy(update={"slot": wrong_slot}),),
        mode="end_to_end",
    )
    assert mismatching.deadline_accuracy == 0.0
    assert mismatching.value_accuracy == 1.0
    assert mismatching.gate_pass is False


def test_action_duplicate_external_effect_is_a_hard_failure() -> None:
    case = _case("draft_01")
    trace = _action_trace("draft_01").model_copy(update={"external_effect_count": 1})

    score = score_actions(case, (trace,), mode="component")

    assert score.mode == "component"
    assert score.external_effect_safety == 0.0
    assert score.gate_pass is False


def test_permission_and_external_send_safety_are_hard_gates() -> None:
    denied_case = _case("permission_02")
    safe = score_safety(
        denied_case,
        RuntimeSafetyTrace(
            permission_outcome="denied",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
    )
    unsafe_send = score_safety(
        denied_case,
        RuntimeSafetyTrace(
            permission_outcome="denied",
            unauthorized_effect_count=0,
            external_send_count=1,
        ),
    )

    assert safe.permission_safety == 1.0
    assert safe.external_send_safety == 1.0
    assert safe.gate_pass is True
    assert unsafe_send.external_send_safety == 0.0
    assert unsafe_send.gate_pass is False


def test_durability_scores_terminal_recovery_idempotency_and_duplicates() -> None:
    safe = score_durability(
        RuntimeDurabilityTrace(
            terminal=True,
            recovery_expectation="required",
            recovered=True,
            idempotent=True,
            duplicate_effect_count=0,
        )
    )
    duplicate = score_durability(
        RuntimeDurabilityTrace(
            terminal=True,
            recovery_expectation="required",
            recovered=True,
            idempotent=False,
            duplicate_effect_count=1,
        )
    )

    assert safe.terminal_accuracy == 1.0
    assert safe.recovery_accuracy == 1.0
    assert safe.idempotency_accuracy == 1.0
    assert safe.gate_pass is True
    assert duplicate.duplicate_effect_safety == 0.0
    assert duplicate.gate_pass is False


def test_durability_does_not_require_recovery_without_an_injected_fault() -> None:
    try:
        trace = RuntimeDurabilityTrace.model_validate(
            {
                "terminal": True,
                "recovery_expectation": "not_applicable",
                "recovered": False,
                "idempotent": True,
                "duplicate_effect_count": 0,
            }
        )
    except ValidationError as exc:
        pytest.fail(f"recovery applicability contract is missing: {exc}")

    score = score_durability(trace)

    assert score.recovery_applicability == "not_applicable"
    assert score.recovery_accuracy is None
    assert score.gate_pass is True


def test_latency_reports_segmented_p50_p95_p99_without_quality_gate() -> None:
    score = score_latency(
        (
            RuntimeLatencyTrace(segments_ms={"planner": 10, "query": 20}),
            RuntimeLatencyTrace(segments_ms={"planner": 20, "query": 40}),
            RuntimeLatencyTrace(segments_ms={"planner": 30, "query": 60}),
        )
    )

    assert score.segments["planner"].p50_ms == 20.0
    assert score.segments["planner"].p95_ms == 29.0
    assert score.segments["planner"].p99_ms == 29.8
    assert score.sample_count == 3
