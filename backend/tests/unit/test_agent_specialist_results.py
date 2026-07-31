from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.agent_specialist_results import (
    AuthorizedCandidateSetV1,
    ClaimGraphV1,
    ComposerResultV1,
    ControlledActionProposalV1,
    DailyBriefV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
    validate_controlled_action_proposal,
)


TABLE_ID = UUID("30000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("30000000-0000-4000-8000-000000000002")
OTHER_RECORD_ID = UUID("30000000-0000-4000-8000-000000000003")
FIELD_ID = UUID("30000000-0000-4000-8000-000000000004")
HASH = "a" * 64


def _with_hash(payload: dict[str, object], field: str) -> dict[str, object]:
    result = dict(payload)
    result[field] = specialist_payload_sha256(result)
    return result


def _fact_payload() -> dict[str, object]:
    return _with_hash(
        {
            "version": "structured-fact-set.v1",
            "objective_id": "obj-01",
            "records": (
                {
                    "record_id": RECORD_ID,
                    "table_id": TABLE_ID,
                    "values": ({"field_id": FIELD_ID, "value": "阻塞"},),
                },
            ),
            "groups": (),
            "aggregates": (
                {"aggregate_id": "agg-count", "group_key": None, "value": 1},
            ),
            "relation_paths": (),
            "source_versions": (
                {
                    "table_id": TABLE_ID,
                    "record_id": RECORD_ID,
                    "record_version": 3,
                },
            ),
            "evidence_refs": ("ev-01",),
            "scope_hash": HASH,
            "schema_hash": HASH,
            "complete": True,
            "truncated": False,
        },
        "content_hash",
    )


def _candidate_payload() -> dict[str, object]:
    return _with_hash(
        {
            "version": "authorized-candidate-set.v1",
            "objective_id": "obj-action",
            "slot_id": "slot-01",
            "candidates": (
                {
                    "table_id": TABLE_ID,
                    "record_id": RECORD_ID,
                    "record_version": 3,
                    "writable_field_ids": (FIELD_ID,),
                },
            ),
            "scope_hash": HASH,
            "complete": True,
        },
        "candidate_set_hash",
    )


def test_fact_set_is_strict_frozen_and_hash_validated() -> None:
    facts = StructuredFactSetV1.model_validate(_fact_payload())
    assert facts.aggregates[0].value == 1

    with pytest.raises(ValidationError, match="specialist_fact_hash_mismatch"):
        StructuredFactSetV1.model_validate(
            {**_fact_payload(), "content_hash": "b" * 64}
        )
    with pytest.raises(ValidationError):
        StructuredFactSetV1.model_validate({**_fact_payload(), "private": "x"})
    with pytest.raises(ValidationError, match="specialist_fact_completeness_invalid"):
        payload = _fact_payload()
        payload.update(complete=True, truncated=True)
        payload["content_hash"] = specialist_payload_sha256(
            {key: value for key, value in payload.items() if key != "content_hash"}
        )
        StructuredFactSetV1.model_validate(payload)


def test_grouped_aggregates_use_aggregate_id_and_group_key_as_identity() -> None:
    payload = _fact_payload()
    payload["aggregates"] = (
        {"aggregate_id": "agg-count", "group_key": ["high"], "value": 3},
        {"aggregate_id": "agg-count", "group_key": ["medium"], "value": 2},
    )
    payload["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )

    facts = StructuredFactSetV1.model_validate(payload)

    assert [item.value for item in facts.aggregates] == [3, 2]

    payload["aggregates"] = (
        {"aggregate_id": "agg-count", "group_key": ["high"], "value": 3},
        {"aggregate_id": "agg-count", "group_key": ["high"], "value": 2},
    )
    payload["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )
    with pytest.raises(ValidationError, match="specialist_fact_identity_duplicate"):
        StructuredFactSetV1.model_validate(payload)


def test_risk_assessment_rejects_unknown_evidence() -> None:
    payload = {
        "version": "risk-assessment-set.v1",
        "objective_id": "obj-risk",
        "fact_set_hash": _fact_payload()["content_hash"],
        "policy_version": "risk-policy.v1",
        "available_evidence_ids": ("ev-01",),
        "assessments": (
            {
                "assessment_id": "risk-01",
                "subject_ref": str(RECORD_ID),
                "severity": "high",
                "reason_codes": ("blocked",),
                "evidence_ids": ("ev-99",),
            },
        ),
        "scope_hash": HASH,
        "provider_call_count": 0,
    }
    payload = _with_hash(payload, "content_hash")
    with pytest.raises(ValidationError, match="specialist_risk_evidence_unknown"):
        RiskAssessmentSetV1.model_validate(payload)


def test_daily_brief_labels_recommendations_and_rejects_unknown_evidence() -> None:
    payload = {
        "version": "daily-brief.v1",
        "objective_id": "obj-daily",
        "fact_set_hash": _fact_payload()["content_hash"],
        "risk_set_hash": None,
        "available_evidence_ids": ("ev-01",),
        "statements": (
            {
                "statement_id": "daily-01",
                "kind": "recommendation",
                "text": "建议优先确认阻塞项",
                "evidence_ids": ("ev-01",),
                "aggregate_id": None,
            },
        ),
        "as_of_utc": datetime(2026, 7, 30, tzinfo=UTC),
        "scope_hash": HASH,
        "provider_call_count": 0,
    }
    payload = _with_hash(payload, "content_hash")
    assert DailyBriefV1.model_validate(payload).statements[0].kind == "recommendation"

    payload["statements"][0]["evidence_ids"] = ("ev-99",)
    payload["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in payload.items() if key != "content_hash"}
    )
    with pytest.raises(ValidationError, match="specialist_daily_evidence_unknown"):
        DailyBriefV1.model_validate(payload)


def test_action_proposal_cannot_expand_authorized_candidates() -> None:
    candidates = AuthorizedCandidateSetV1.model_validate(_candidate_payload())
    proposal_payload = {
        "version": "controlled-action-proposal.v1",
        "objective_id": "obj-action",
        "slot_id": "slot-01",
        "status": "proposed",
        "action_kind": "record.update",
        "target_record_ids": (OTHER_RECORD_ID,),
        "assignments": (
            {
                "record_id": OTHER_RECORD_ID,
                "field_id": FIELD_ID,
                "value": "处理中",
            },
        ),
        "evidence_ids": ("ev-01",),
        "candidate_set_hash": candidates.candidate_set_hash,
        "confirmation_policy": "required",
        "execution_status": "not_executed",
        "denial_reason": None,
        "scope_hash": HASH,
        "provider_call_count": 0,
    }
    proposal = ControlledActionProposalV1.model_validate(
        _with_hash(proposal_payload, "content_hash")
    )
    with pytest.raises(ValueError, match="specialist_action_candidate_invalid"):
        validate_controlled_action_proposal(proposal, candidates)


def test_action_deny_cannot_carry_proposal_payload() -> None:
    candidates = AuthorizedCandidateSetV1.model_validate(_candidate_payload())
    payload = {
        "version": "controlled-action-proposal.v1",
        "objective_id": "obj-action",
        "slot_id": "slot-01",
        "status": "denied",
        "action_kind": "record.update",
        "target_record_ids": (RECORD_ID,),
        "assignments": (),
        "evidence_ids": (),
        "candidate_set_hash": candidates.candidate_set_hash,
        "confirmation_policy": "required",
        "execution_status": "not_executed",
        "denial_reason": "field_not_allowed",
        "scope_hash": HASH,
        "provider_call_count": 0,
    }
    with pytest.raises(
        ValidationError, match="specialist_action_denial_payload_invalid"
    ):
        ControlledActionProposalV1.model_validate(_with_hash(payload, "content_hash"))


def test_claim_graph_requires_same_version_conflicts_to_be_explicit() -> None:
    payload = {
        "version": "claim-graph.v1",
        "claims": (
            {
                "claim_id": "claim-01",
                "subject_ref": str(RECORD_ID),
                "predicate": "status",
                "value": "阻塞",
                "evidence_ids": ("ev-01",),
                "objective_ids": ("obj-01",),
                "source_version": 3,
                "status": "valid",
            },
            {
                "claim_id": "claim-02",
                "subject_ref": str(RECORD_ID),
                "predicate": "status",
                "value": "完成",
                "evidence_ids": ("ev-02",),
                "objective_ids": ("obj-02",),
                "source_version": 3,
                "status": "valid",
            },
        ),
        "objective_statuses": (
            {"objective_id": "obj-01", "status": "completed", "reason_code": None},
            {"objective_id": "obj-02", "status": "completed", "reason_code": None},
        ),
        "action_statuses": (),
        "scope_hash": HASH,
    }
    with pytest.raises(ValidationError, match="specialist_claim_conflict_unmarked"):
        ClaimGraphV1.model_validate(_with_hash(payload, "content_hash"))


def test_composer_result_requires_chinese_and_known_claims() -> None:
    answer = "One blocked item."
    receipt = {
        "version": "final-answer-render-receipt.v1",
        "covered_objective_ids": ("obj-01",),
        "covered_claim_ids": ("claim-01",),
        "covered_action_slot_ids": (),
        "citation_edges": ({"claim_id": "claim-01", "evidence_id": "ev-01"},),
        "section_kinds": ("facts",),
        "disclosure_codes": (),
        "language": "zh-Hans",
        "answer_hash": sha256(answer.encode("utf-8")).hexdigest(),
        "claim_graph_hash": HASH,
        "presentation_hash": HASH,
        "scope_hash": HASH,
    }
    receipt["content_hash"] = specialist_payload_sha256(receipt)
    payload = {
        "version": "composer-result.v1",
        "status": "completed",
        "answer": answer,
        "claim_ids": ("claim-01",),
        "evidence_ids": ("ev-01",),
        "action_statuses": (),
        "degradation_codes": (),
        "render_receipt": receipt,
        "provider_call_count": 1,
        "scope_hash": HASH,
    }
    with pytest.raises(ValidationError, match="specialist_composer_language_invalid"):
        ComposerResultV1.model_validate(_with_hash(payload, "content_hash"))
