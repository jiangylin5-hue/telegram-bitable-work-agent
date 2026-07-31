from __future__ import annotations

from uuid import UUID

import pytest

from app.schemas.agent_grounded_answer_v2 import (
    GroundedActionCandidateV2,
    GroundedAnswerPlanV2,
    GroundedAnswerProviderRequestV2,
    GroundedAnswerSectionV2,
    GroundedAnswerStatementV2,
    GroundedClaimCandidateV2,
    GroundedEvidenceCandidateV2,
    GroundedObjectiveCandidateV2,
    GroundedPresentationPolicyV2,
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


def _handle(kind: str, value: object) -> str:
    return f"{kind}:sha256:{specialist_payload_sha256({'kind': kind, 'value': value})}"


OBJECTIVE_HANDLE = _handle("objective", OBJECTIVE_ID)
CLAIM_HANDLE = _handle("claim", CLAIM_ID)
EVIDENCE_HANDLE = _handle("evidence", EVIDENCE_ID)
EXTRA_EVIDENCE_HANDLE = _handle("evidence", "evidence:other-source")
ACTION_HANDLE = _handle("action", ACTION_ID)


def _request(
    *, claim_status: str = "valid", include_extra_evidence: bool = False
) -> GroundedAnswerProviderRequestV2:
    citations = [
        GroundedEvidenceCandidateV2(
            evidence_handle=EVIDENCE_HANDLE,
            display_label="证据 1",
            source_version=_handle(
                "record-version", ((SUBJECT_REF, PREDICATE_REF, 7),)
            ),
        )
    ]
    if include_extra_evidence:
        citations.append(
            GroundedEvidenceCandidateV2(
                evidence_handle=EXTRA_EVIDENCE_HANDLE,
                display_label="证据 2",
                source_version="record-version:sha256:" + "5" * 64,
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
                source_versions=(
                    _handle(
                        "record-version",
                        {
                            "subject": SUBJECT_REF,
                            "predicate": PREDICATE_REF,
                            "version": 7,
                        },
                    ),
                ),
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


def test_valid_grounded_plan_passes() -> None:
    validate_grounded_answer_plan(_request(), _plan())


def test_unknown_claim_and_inexact_citation_closure_are_rejected() -> None:
    _assert_invalid(
        _request(),
        _plan(claim_handles=("claim:sha256:" + "9" * 64,)),
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


def test_required_objective_must_be_covered() -> None:
    plan = _plan(
        text="当前无法提供可验证结果。",
        claim_handles=(),
        evidence_handles=(),
        statement_kind="limitation",
        section_kind="limitations",
    )
    _assert_invalid(_request(), plan)


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
