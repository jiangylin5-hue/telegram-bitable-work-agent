from __future__ import annotations

from uuid import UUID

import pytest

from app.schemas.agent_grounded_answer_v2 import (
    GroundedActionCandidateV2,
    GroundedAnswerPlanV2,
    GroundedAnswerProviderRequestV2,
    GroundedAnswerSectionV2,
    GroundedAnswerStatementV2,
    GroundedAnswerPlanV3,
    GroundedAnswerProviderRequestV3,
    GroundedClaimCandidateV2,
    GroundedEvidenceCandidateV2,
    GroundedObjectiveCandidateV2,
    GroundedPresentationPolicyV2,
    GroundedRenderSlotTextV1,
    GroundedRenderSlotV1,
)
from app.schemas.agent_specialist_results import (
    ClaimGraphV1,
    specialist_payload_sha256,
)
from app.services.agent_composer_v2 import (
    ComposerObjectiveContextV1,
    ComposerPresentationContextV1,
)
from app.services.agent_grounded_answer_validation import (
    ProviderValidationError,
    render_grounded_answer,
    validate_grounded_answer_plan,
)


SCOPE_HASH = "a" * 64
SUBJECT_REF = "record:51000000-0000-4000-8000-000000000002"
PREDICATE_REF = "field:51000000-0000-4000-8000-000000000003"
CLAIM_ID = "claim:canonical-status"
EVIDENCE_ID = "evidence:status-source"
OBJECTIVE_ID = "obj-facts"
ACTION_ID = "slot-update"


OBJECTIVE_HANDLE = "o001"
CLAIM_HANDLE = "c001"
EVIDENCE_HANDLE = "e001"
EXTRA_EVIDENCE_HANDLE = "e002"
ACTION_HANDLE = "a001"


def _request(
    *, claim_status: str = "valid", include_extra_evidence: bool = False
) -> GroundedAnswerProviderRequestV2:
    citations = [
        GroundedEvidenceCandidateV2(
            evidence_handle=EVIDENCE_HANDLE,
            display_label="证据 1",
            source_version="v002",
        )
    ]
    if include_extra_evidence:
        citations.append(
            GroundedEvidenceCandidateV2(
                evidence_handle=EXTRA_EVIDENCE_HANDLE,
                display_label="证据 2",
                source_version="v003",
            )
        )
    values = {
        "version": "grounded-answer-provider-request.v2",
        "language": "zh-CN",
        "query": "Atlas 项目的任务状态是什么？",
        "objectives": (
            GroundedObjectiveCandidateV2(
                objective_handle=OBJECTIVE_HANDLE,
                kind="fact_query",
                status="completed",
                required=True,
                reason_code=None,
            ),
        ),
        "claims": (
            GroundedClaimCandidateV2(
                claim_handle=CLAIM_HANDLE,
                objective_handles=(OBJECTIVE_HANDLE,),
                subject_label="Atlas 项目",
                predicate_label="任务状态",
                value_type="string",
                value_text="blocked",
                qualifiers=(),
                evidence_handles=(EVIDENCE_HANDLE,),
                source_versions=("v001",),
                status=claim_status,
            ),
        ),
        "specialist_findings": (),
        "actions": (),
        "citations": tuple(citations),
        "presentation_policy": GroundedPresentationPolicyV2(
            max_sections=7,
            max_statements_per_section=12,
            allowed_section_kinds=(
                "answer",
                "facts",
                "analysis",
                "risks",
                "daily",
                "actions",
                "limitations",
            ),
            allowed_statement_kinds=(
                "fact",
                "analysis",
                "recommendation",
                "action_status",
                "limitation",
            ),
            require_chinese=True,
            require_objective_coverage=True,
        ),
        "scope_hash": SCOPE_HASH,
        "schema_hash": "b" * 64,
        "field_policy_version": "stage12-field-policy.v2",
        "field_policy_hash": "c" * 64,
        "runtime_binding_hash": _graph().content_hash,
    }
    hash_values = {
        **values,
        "objectives": tuple(
            item.model_dump(mode="json") for item in values["objectives"]
        ),
        "claims": tuple(item.model_dump(mode="json") for item in values["claims"]),
        "citations": tuple(
            item.model_dump(mode="json") for item in values["citations"]
        ),
        "presentation_policy": values["presentation_policy"].model_dump(mode="json"),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerProviderRequestV2.model_validate(values)


def _action_request() -> GroundedAnswerProviderRequestV2:
    base = _request().model_dump(mode="python")
    base["objectives"] = (
        GroundedObjectiveCandidateV2(
            objective_handle=OBJECTIVE_HANDLE,
            kind="record_change",
            status="proposed",
            required=True,
            reason_code=None,
        ),
    )
    base["claims"] = ()
    base["citations"] = ()
    base["actions"] = (
        GroundedActionCandidateV2(
            action_handle=ACTION_HANDLE,
            action_kind="record.update",
            status="proposed",
            safe_summary="已生成待确认提议，尚未执行。",
            reason_code=None,
        ),
    )
    hash_values = {key: value for key, value in base.items() if key != "content_hash"}
    hash_values["objectives"] = tuple(
        item.model_dump(mode="json") for item in base["objectives"]
    )
    hash_values["actions"] = tuple(
        item.model_dump(mode="json") for item in base["actions"]
    )
    base["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerProviderRequestV2.model_validate(base)


def _finding_request() -> GroundedAnswerProviderRequestV2:
    base = _request().model_dump(mode="python")
    base["specialist_findings"] = (
        {
            "finding_handle": "f001",
            "objective_handle": OBJECTIVE_HANDLE,
            "finding_kind": "daily",
            "safe_text": "Atlas 项目的任务状态为 blocked。",
            "claim_handles": (CLAIM_HANDLE,),
            "evidence_handles": (EVIDENCE_HANDLE,),
        },
    )
    base["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in base.items() if key != "content_hash"}
    )
    return GroundedAnswerProviderRequestV2.model_validate(base)


def _multi_claim_request() -> GroundedAnswerProviderRequestV2:
    base = _request(include_extra_evidence=True).model_dump(mode="python")
    base["claims"] = (
        base["claims"][0],
        {
            "claim_handle": "c002",
            "objective_handles": (OBJECTIVE_HANDLE,),
            "subject_label": "Atlas 项目",
            "predicate_label": "负责人",
            "value_type": "string",
            "value_text": "王明",
            "qualifiers": (),
            "evidence_handles": (EXTRA_EVIDENCE_HANDLE,),
            "source_versions": ("v002",),
            "status": "valid",
        },
    )
    base["citations"] = (
        {
            **base["citations"][0],
            "source_version": "v003",
        },
        {
            **base["citations"][1],
            "source_version": "v004",
        },
    )
    base["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in base.items() if key != "content_hash"}
    )
    return GroundedAnswerProviderRequestV2.model_validate(base)


def _zero_claim_action_request(
    *, prerequisite_role: str
) -> GroundedAnswerProviderRequestV2:
    base = _action_request().model_dump(mode="python")
    base["objectives"] = (
        {
            "objective_handle": "o001",
            "kind": "fact_query",
            "status": "completed",
            "required": True,
            "reason_code": None,
            "coverage_role": prerequisite_role,
        },
        {
            "objective_handle": "o002",
            "kind": "record_change",
            "status": "proposed",
            "required": True,
            "reason_code": None,
            "coverage_role": "user_result",
        },
    )
    base["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in base.items() if key != "content_hash"}
    )
    return GroundedAnswerProviderRequestV2.model_validate(base)


def _plan(
    *,
    text: str = "Atlas 项目的任务状态为 blocked。",
    claim_handles: tuple[str, ...] = (CLAIM_HANDLE,),
    evidence_handles: tuple[str, ...] = (EVIDENCE_HANDLE,),
    action_handles: tuple[str, ...] = (),
    statement_kind: str = "fact",
    section_kind: str = "answer",
) -> GroundedAnswerPlanV2:
    return GroundedAnswerPlanV2(
        sections=(
            GroundedAnswerSectionV2(
                section_kind=section_kind,
                heading="结论",
                statements=(
                    GroundedAnswerStatementV2(
                        statement_kind=statement_kind,
                        text=text,
                        claim_handles=claim_handles,
                        evidence_handles=evidence_handles,
                        action_handles=action_handles,
                    ),
                ),
            ),
        )
    )


def _graph() -> ClaimGraphV1:
    values = {
        "version": "claim-graph.v1",
        "claims": (
            {
                "claim_id": CLAIM_ID,
                "subject_ref": SUBJECT_REF,
                "predicate": PREDICATE_REF,
                "value": "blocked",
                "evidence_ids": (EVIDENCE_ID,),
                "objective_ids": (OBJECTIVE_ID,),
                "source_version": 7,
                "status": "valid",
            },
        ),
        "objective_statuses": (
            {
                "objective_id": OBJECTIVE_ID,
                "status": "completed",
                "reason_code": None,
            },
        ),
        "action_statuses": (),
        "scope_hash": SCOPE_HASH,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ClaimGraphV1.model_validate(values)


def _mixed_status_graph() -> ClaimGraphV1:
    values = _graph().model_dump(mode="python")
    values["claims"] = (
        values["claims"][0],
        {
            **values["claims"][0],
            "claim_id": "claim:conflicted-risk",
            "predicate": "risk_severity",
            "value": "high",
            "evidence_ids": ("evidence:conflicted-risk",),
            "status": "conflicted",
        },
    )
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    return ClaimGraphV1.model_validate(values)


def _presentation() -> ComposerPresentationContextV1:
    return ComposerPresentationContextV1(
        query="Atlas 项目的任务状态是什么？",
        objectives=(
            ComposerObjectiveContextV1(
                objective_id=OBJECTIVE_ID,
                kind="fact_query",
                required=True,
            ),
        ),
        subject_labels={SUBJECT_REF: "Atlas 项目"},
        predicate_labels={PREDICATE_REF: "任务状态"},
    )


def _assert_invalid(request, plan, code: str = "provider_grounding_invalid"):
    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(request, plan)
    assert captured.value.code == code


def _render_slot_request() -> GroundedAnswerProviderRequestV3:
    values = _request().model_dump(mode="python")
    values["version"] = "grounded-answer-provider-request.v3"
    values["render_slots"] = (
        GroundedRenderSlotV1(
            slot_handle="s001",
            section_kind="answer",
            statement_kind="fact",
            objective_handles=(OBJECTIVE_HANDLE,),
            claim_handles=(CLAIM_HANDLE,),
            evidence_handles=(EVIDENCE_HANDLE,),
            finding_handles=(),
            action_handles=(),
            required=True,
        ),
    )
    hash_values = {key: value for key, value in values.items() if key != "content_hash"}
    hash_values["render_slots"] = tuple(
        item.model_dump(mode="json") for item in values["render_slots"]
    )
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerProviderRequestV3.model_validate(values)


def _render_slot_plan(
    *outputs: tuple[str, str],
) -> GroundedAnswerPlanV3:
    if not outputs:
        outputs = (("s001", "Atlas 项目的任务状态为 blocked。"),)
    return GroundedAnswerPlanV3(
        slot_outputs=tuple(
            GroundedRenderSlotTextV1(slot_handle=handle, text=text)
            for handle, text in outputs
        )
    )


@pytest.mark.parametrize(
    "outputs",
    (
        (("s999", "Atlas 项目的任务状态为 blocked。"),),
        (
            ("s001", "Atlas 项目的任务状态为 blocked。"),
            ("s001", "Atlas 项目的任务状态仍为 blocked。"),
        ),
    ),
)
def test_render_slots_reject_unknown_or_duplicate_handles(outputs) -> None:
    _assert_invalid(_render_slot_request(), _render_slot_plan(*outputs))


def _two_render_slot_request():
    from tests.unit.test_agent_grounded_answer_request import _action_fixture
    from app.services.agent_grounded_answer_request import build_grounded_answer_request

    query, task_spec, graph, schema, presentation, findings = _action_fixture()
    return build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=findings,
    )


def _action_context_request() -> GroundedAnswerProviderRequestV3:
    request = _two_render_slot_request()
    values = request.model_dump(mode="python")
    claim = values["claims"][0]
    action_slot = values["render_slots"][1]
    action_slot["objective_handles"] = tuple(
        dict.fromkeys((*action_slot["objective_handles"], *claim["objective_handles"]))
    )
    action_slot["context_claim_handles"] = (claim["claim_handle"],)
    action_slot["context_evidence_handles"] = claim["evidence_handles"]
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    return GroundedAnswerProviderRequestV3.model_validate(values)


@pytest.mark.parametrize(
    "outputs",
    (
        (("s001", "Atlas 项目的任务状态为 blocked。"),),
        (
            ("s002", "授权结果如下。"),
            ("s001", "授权结果如下。"),
        ),
    ),
)
def test_render_slots_reject_missing_or_reordered_handles(outputs) -> None:
    _assert_invalid(_two_render_slot_request(), _render_slot_plan(*outputs))


def test_action_render_slot_must_express_its_sealed_pending_status() -> None:
    _assert_invalid(
        _two_render_slot_request(),
        _render_slot_plan(
            ("s001", "Atlas 项目的任务状态为 blocked。"),
            ("s002", "授权结果如下。"),
        ),
    )


def test_action_render_slot_cannot_borrow_subject_from_fact_slot() -> None:
    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(
            _two_render_slot_request(),
            _render_slot_plan(
                ("s001", "Atlas 项目的任务状态为 blocked。"),
                ("s002", "Atlas 项目已生成待确认提议，尚未执行。"),
            ),
        )

    assert captured.value.detail == "grounded_answer_unreferenced_subject_atom"


def test_action_render_slot_may_use_backend_sealed_prerequisite_context() -> None:
    validate_grounded_answer_plan(
        _action_context_request(),
        _render_slot_plan(
            ("s001", "Atlas 项目的任务状态为 blocked。"),
            ("s002", "Atlas 项目已生成待确认提议，尚未执行。"),
        ),
    )


def test_render_slot_text_cannot_tamper_with_the_sealed_claim_closure() -> None:
    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(
            _render_slot_request(),
            _render_slot_plan(("s001", "Atlas 项目的预算为 9 亿元。")),
        )

    assert captured.value.detail == "grounded_answer_invented_number_atom"


@pytest.mark.parametrize(
    ("text", "detail"),
    (
        ("blocked.", "grounded_answer_text_chinese_missing"),
        ("结论来自 c001。", "grounded_answer_internal_handle_exposed"),
    ),
)
def test_render_slot_language_failure_has_sanitized_specific_detail(
    text: str, detail: str
) -> None:
    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(
            _render_slot_request(),
            _render_slot_plan(("s001", text)),
        )

    assert captured.value.code == "provider_language_invalid"
    assert captured.value.detail == detail


def test_render_slot_receipt_comes_from_backend_owned_slot_closure() -> None:
    request = _render_slot_request()
    plan = _render_slot_plan(("s001", "Atlas 项目的任务状态仍为 blocked。"))

    result = render_grounded_answer(
        request,
        plan,
        graph=_graph(),
        presentation=_presentation(),
    )

    assert "Atlas 项目的任务状态仍为 blocked。" in result.answer
    assert result.claim_ids == (CLAIM_ID,)
    assert result.evidence_ids == (EVIDENCE_ID,)
    assert result.render_receipt.covered_claim_ids == (CLAIM_ID,)


def test_render_slot_result_accepts_three_slots_with_one_repair_each() -> None:
    result = render_grounded_answer(
        _render_slot_request(),
        _render_slot_plan(),
        graph=_graph(),
        presentation=_presentation(),
        provider_call_count=6,
    )

    assert result.provider_call_count == 6


def test_valid_grounded_plan_passes() -> None:
    validate_grounded_answer_plan(_request(), _plan())


def test_typed_finding_reference_expands_to_canonical_receipt_closure() -> None:
    request = _finding_request()
    plan = GroundedAnswerPlanV2.model_validate(
        {
            "version": "grounded-answer-plan.v2",
            "sections": (
                {
                    "section_kind": "daily",
                    "heading": "日报",
                    "statements": (
                        {
                            "statement_kind": "analysis",
                            "text": "Atlas 项目的任务状态为 blocked。",
                            "claim_handles": (),
                            "evidence_handles": (),
                            "finding_handles": ("f001",),
                            "action_handles": (),
                        },
                    ),
                },
            ),
        }
    )

    result = render_grounded_answer(
        request,
        plan,
        graph=_graph(),
        presentation=_presentation(),
    )

    assert result.render_receipt.covered_objective_ids == (OBJECTIVE_ID,)
    assert result.render_receipt.covered_claim_ids == (CLAIM_ID,)
    assert result.evidence_ids == (EVIDENCE_ID,)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("claim_handles", ("c999",)),
        ("evidence_handles", ("e999",)),
    ),
)
def test_request_rejects_unknown_finding_closure_reference(
    field: str, replacement: tuple[str, ...]
) -> None:
    values = _finding_request().model_dump(mode="python")
    values["specialist_findings"][0][field] = replacement
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )

    with pytest.raises(ValueError, match="grounded_request_finding_reference_unknown"):
        GroundedAnswerProviderRequestV2.model_validate(values)


def test_unknown_claim_and_inexact_citation_closure_are_rejected() -> None:
    _assert_invalid(
        _request(),
        _plan(claim_handles=("c999",)),
    )
    _assert_invalid(
        _request(include_extra_evidence=True),
        _plan(evidence_handles=(EVIDENCE_HANDLE, EXTRA_EVIDENCE_HANDLE)),
    )


def test_stale_claim_cannot_be_presented_as_fact() -> None:
    _assert_invalid(_request(claim_status="stale"), _plan())


@pytest.mark.parametrize(
    "text",
    (
        "Atlas 项目的预算为 9 亿元。",
        "Beta 项目的任务状态为 blocked。",
        "Atlas 项目的任务状态为 done。",
    ),
)
def test_canonical_atom_validation_rejects_invented_fact(text: str) -> None:
    _assert_invalid(_request(), _plan(text=text))


def test_pending_action_cannot_be_described_as_executed() -> None:
    plan = _plan(
        text="记录已经更新完成。",
        claim_handles=(),
        evidence_handles=(),
        action_handles=(ACTION_HANDLE,),
        statement_kind="action_status",
        section_kind="actions",
    )
    _assert_invalid(_action_request(), plan)


def test_action_status_covers_only_explicit_zero_claim_prerequisite() -> None:
    plan = _plan(
        text="已生成待确认提议，尚未执行。",
        claim_handles=(),
        evidence_handles=(),
        action_handles=(ACTION_HANDLE,),
        statement_kind="action_status",
        section_kind="actions",
    )

    validate_grounded_answer_plan(
        _zero_claim_action_request(prerequisite_role="action_prerequisite"),
        plan,
    )
    _assert_invalid(
        _zero_claim_action_request(prerequisite_role="user_result"),
        plan,
    )


def test_required_objective_must_be_covered() -> None:
    plan = _plan(
        text="当前无法提供可验证结果。",
        claim_handles=(),
        evidence_handles=(),
        statement_kind="limitation",
        section_kind="limitations",
    )
    _assert_invalid(_request(), plan)


def test_every_visible_valid_claim_must_be_covered() -> None:
    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(_multi_claim_request(), _plan())

    assert captured.value.code == "provider_grounding_invalid"
    assert captured.value.detail == "grounded_answer_required_claim_missing"


def test_every_visible_valid_claim_covered_exactly_once_passes() -> None:
    plan = GroundedAnswerPlanV2(
        sections=(
            GroundedAnswerSectionV2(
                section_kind="answer",
                heading="结论",
                statements=(
                    _plan().sections[0].statements[0],
                    GroundedAnswerStatementV2(
                        statement_kind="fact",
                        text="Atlas 项目的负责人为王明。",
                        claim_handles=("c002",),
                        evidence_handles=(EXTRA_EVIDENCE_HANDLE,),
                        action_handles=(),
                    ),
                ),
            ),
        )
    )

    validate_grounded_answer_plan(_multi_claim_request(), plan)


def test_claim_cannot_be_covered_by_multiple_statements() -> None:
    plan = GroundedAnswerPlanV2(
        sections=(
            GroundedAnswerSectionV2(
                section_kind="answer",
                heading="结论",
                statements=(
                    _plan().sections[0].statements[0],
                    _plan(text="Atlas 项目的任务状态仍为 blocked。")
                    .sections[0]
                    .statements[0],
                ),
            ),
        )
    )

    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(_request(), plan)

    assert captured.value.code == "provider_grounding_invalid"
    assert captured.value.detail == "grounded_answer_claim_repeated"


@pytest.mark.parametrize(
    ("text", "code"),
    (
        (CLAIM_HANDLE, "provider_language_invalid"),
        ("No grounded answer.", "provider_language_invalid"),
    ),
)
def test_internal_handles_and_non_chinese_output_are_rejected(
    text: str, code: str
) -> None:
    _assert_invalid(_request(), _plan(text=text), code)


def test_render_uses_model_authored_text_and_seals_exact_receipt() -> None:
    request = _request()
    plan = _plan(text="Atlas 项目的任务状态仍为 blocked。")

    result = render_grounded_answer(
        request,
        plan,
        graph=_graph(),
        presentation=_presentation(),
    )

    assert "Atlas 项目的任务状态仍为 blocked。" in result.answer
    assert result.answer_source == "real_provider"
    assert result.provider_result_status == "completed"
    assert result.claim_ids == (CLAIM_ID,)
    assert result.evidence_ids == (EVIDENCE_ID,)
    assert result.render_receipt.covered_objective_ids == (OBJECTIVE_ID,)
    assert result.render_receipt.covered_claim_ids == (CLAIM_ID,)
    assert result.render_receipt.citation_edges[0].evidence_id == EVIDENCE_ID


def test_render_rejects_claim_value_drift_from_sealed_graph() -> None:
    values = _request().model_dump(mode="python")
    values["claims"][0]["value_text"] = "done"
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    drifted_request = GroundedAnswerProviderRequestV2.model_validate(values)

    with pytest.raises(ProviderValidationError) as captured:
        render_grounded_answer(
            drifted_request,
            _plan(text="Atlas 项目的任务状态为 done。"),
            graph=_graph(),
            presentation=_presentation(),
        )

    assert captured.value.code == "provider_grounding_invalid"


def test_render_binding_ignores_non_valid_graph_claims_but_keeps_graph_hash() -> None:
    graph = _mixed_status_graph()
    values = _request().model_dump(mode="python")
    values["runtime_binding_hash"] = graph.content_hash
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    request = GroundedAnswerProviderRequestV2.model_validate(values)

    result = render_grounded_answer(
        request,
        _plan(),
        graph=graph,
        presentation=_presentation(),
    )

    assert result.claim_ids == (CLAIM_ID,)
    assert result.evidence_ids == (EVIDENCE_ID,)


def test_render_rejects_tampered_projected_objective_status() -> None:
    values = _request().model_dump(mode="python")
    values["objectives"][0]["status"] = "degraded"
    values["objectives"][0]["reason_code"] = "conflicted_claim"
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    request = GroundedAnswerProviderRequestV2.model_validate(values)

    with pytest.raises(ProviderValidationError) as captured:
        render_grounded_answer(
            request,
            _plan(),
            graph=_graph(),
            presentation=_presentation(),
        )

    assert captured.value.detail == "grounded_answer_runtime_objective_mismatch"


def test_render_rejects_stale_canonical_record_version_binding() -> None:
    values = _graph().model_dump(mode="python")
    values["claims"][0]["source_version"] = 8
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    stale_graph = ClaimGraphV1.model_validate(values)

    with pytest.raises(ProviderValidationError) as captured:
        render_grounded_answer(
            _request(),
            _plan(),
            graph=stale_graph,
            presentation=_presentation(),
        )

    assert captured.value.code == "provider_grounding_invalid"
    assert captured.value.detail == "grounded_answer_runtime_binding_stale"


@pytest.mark.parametrize(
    ("field", "replacement", "error"),
    (
        ("claim_handle", "c002", "grounded_request_reference_order"),
        ("objective_handle", "o002", "grounded_request_reference_order"),
        ("source_version", "v003", "grounded_request_version_reference_order"),
    ),
)
def test_request_rejects_tampered_request_local_reference_binding(
    field: str, replacement: str, error: str
) -> None:
    values = _request().model_dump(mode="python")
    if field == "claim_handle":
        values["claims"][0]["claim_handle"] = replacement
    elif field == "objective_handle":
        values["objectives"][0]["objective_handle"] = replacement
        values["claims"][0]["objective_handles"] = (replacement,)
    else:
        values["claims"][0]["source_versions"] = (replacement,)
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )

    with pytest.raises(ValueError, match=error):
        GroundedAnswerProviderRequestV2.model_validate(values)


def test_request_contract_rejects_reordered_compact_aliases() -> None:
    values = _request(include_extra_evidence=True).model_dump(mode="python")
    values["citations"] = tuple(reversed(values["citations"]))
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )

    with pytest.raises(ValueError, match="grounded_request_reference_order"):
        GroundedAnswerProviderRequestV2.model_validate(values)
