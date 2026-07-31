from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
import json

from app.schemas.agent_grounded_answer_v2 import (
    GroundedActionCandidateV2,
    GroundedAnswerProviderRequestV2,
    GroundedClaimCandidateV2,
    GroundedEvidenceCandidateV2,
    GroundedObjectiveCandidateV2,
    GroundedPresentationPolicyV2,
    GroundedSpecialistFindingV2,
)
from app.schemas.agent_specialist_results import (
    ClaimGraphV1,
    DailyBriefV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import AuthorizedSchemaSnapshot, TaskSpecV2
from app.services.agent_composer_v2 import ComposerPresentationContextV1


SpecialistFinding = StructuredFactSetV1 | RiskAssessmentSetV1 | DailyBriefV1

_FORBIDDEN_EVALUATION_MARKERS = (
    "case_id",
    "gold_truth",
    "expected_answer",
    "expected_action",
    "expected_target",
)


def _opaque_handle(kind: str, value: object) -> str:
    digest = specialist_payload_sha256({"kind": kind, "value": value})
    return f"{kind}:sha256:{digest}"


def _value_projection(value: object) -> tuple[str, str]:
    if value is None:
        return "null", "null"
    if isinstance(value, bool):
        return "boolean", "true" if value else "false"
    if isinstance(value, int):
        return "integer", str(value)
    if isinstance(value, float):
        return "number", json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, datetime):
        return "datetime", value.isoformat()
    if isinstance(value, date):
        return "date", value.isoformat()
    if isinstance(value, str):
        return "string", value
    if isinstance(value, list):
        return (
            "list",
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        )
    if isinstance(value, dict):
        return (
            "object",
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        )
    raise ValueError("grounded_request_claim_value_invalid")


def _validate_safe_text(text: str, private_tokens: set[str]) -> str:
    if not text.strip() or any(
        marker in text.lower() for marker in _FORBIDDEN_EVALUATION_MARKERS
    ):
        raise ValueError("grounded_request_safe_text_invalid")
    if any(token and token in text for token in private_tokens):
        raise ValueError("grounded_request_private_token_leak")
    return text


def build_grounded_answer_request(
    *,
    query: str,
    task_spec: TaskSpecV2,
    graph: ClaimGraphV1,
    authorized_schema: AuthorizedSchemaSnapshot,
    presentation: ComposerPresentationContextV1,
    specialist_findings: Sequence[SpecialistFinding],
) -> GroundedAnswerProviderRequestV2:
    if not query.strip() or query != presentation.query:
        raise ValueError("grounded_request_query_mismatch")
    if any(marker in query.lower() for marker in _FORBIDDEN_EVALUATION_MARKERS):
        raise ValueError("grounded_request_query_invalid")
    if (
        authorized_schema.field_policy_version != "stage12-field-policy.v2"
        or authorized_schema.field_policy_hash is None
    ):
        raise ValueError("grounded_request_field_policy_required")
    if graph.scope_hash != authorized_schema.scope_hash:
        raise ValueError("grounded_request_scope_mismatch")
    if task_spec.authorized_schema_hash != authorized_schema.schema_hash:
        raise ValueError("grounded_request_schema_mismatch")

    objectives_by_id = {item.objective_id: item for item in task_spec.objectives}
    graph_objectives = {item.objective_id: item for item in graph.objective_statuses}
    presentation_objectives = {
        item.objective_id: item for item in presentation.objectives
    }
    if (
        len(objectives_by_id) != len(task_spec.objectives)
        or len(presentation_objectives) != len(presentation.objectives)
        or set(objectives_by_id) != set(graph_objectives)
        or set(objectives_by_id) != set(presentation_objectives)
    ):
        raise ValueError("grounded_request_objective_mismatch")
    for objective_id, objective in objectives_by_id.items():
        shown = presentation_objectives[objective_id]
        if shown.kind != objective.kind or shown.required != objective.required:
            raise ValueError("grounded_request_objective_mismatch")

    findings = tuple(specialist_findings)
    fact_hashes = {
        item.content_hash for item in findings if isinstance(item, StructuredFactSetV1)
    }
    risk_hashes = {
        item.content_hash for item in findings if isinstance(item, RiskAssessmentSetV1)
    }
    for finding in findings:
        if finding.scope_hash != authorized_schema.scope_hash:
            raise ValueError("grounded_request_scope_mismatch")
        if isinstance(finding, StructuredFactSetV1) and (
            finding.schema_hash != authorized_schema.schema_hash
        ):
            raise ValueError("grounded_request_schema_mismatch")
        if finding.objective_id not in objectives_by_id:
            raise ValueError("grounded_request_objective_mismatch")
        if isinstance(finding, RiskAssessmentSetV1) and (
            finding.fact_set_hash not in fact_hashes
        ):
            raise ValueError("grounded_request_specialist_binding_mismatch")
        if isinstance(finding, DailyBriefV1) and (
            finding.fact_set_hash not in fact_hashes
            or (
                finding.risk_set_hash is not None
                and finding.risk_set_hash not in risk_hashes
            )
        ):
            raise ValueError("grounded_request_specialist_binding_mismatch")

    objective_handles = {
        objective_id: _opaque_handle("objective", objective_id)
        for objective_id in sorted(objectives_by_id)
    }
    claim_handles = {
        item.claim_id: _opaque_handle("claim", item.claim_id) for item in graph.claims
    }
    evidence_ids = sorted(
        {evidence_id for item in graph.claims for evidence_id in item.evidence_ids}
    )
    evidence_handles = {
        evidence_id: _opaque_handle("evidence", evidence_id)
        for evidence_id in evidence_ids
    }
    action_handles = {
        item.slot_id: _opaque_handle("action", item.slot_id)
        for item in graph.action_statuses
    }

    private_tokens = (
        {item.claim_id for item in graph.claims}
        | {item.subject_ref for item in graph.claims}
        | {item.predicate for item in graph.claims}
        | set(evidence_ids)
        | set(action_handles)
    )

    claims = []
    for item in graph.claims:
        subject_label = presentation.subject_labels.get(item.subject_ref)
        predicate_label = presentation.predicate_labels.get(item.predicate)
        if not subject_label or not predicate_label:
            raise ValueError("grounded_request_safe_label_missing")
        _validate_safe_text(subject_label, private_tokens)
        _validate_safe_text(predicate_label, private_tokens)
        value_type, value_text = _value_projection(item.value)
        source_version = _opaque_handle(
            "record-version",
            {
                "subject": item.subject_ref,
                "predicate": item.predicate,
                "version": item.source_version,
            },
        )
        claims.append(
            GroundedClaimCandidateV2(
                claim_handle=claim_handles[item.claim_id],
                objective_handles=tuple(
                    objective_handles[value] for value in sorted(item.objective_ids)
                ),
                subject_label=subject_label,
                predicate_label=predicate_label,
                value_type=value_type,
                value_text=value_text,
                qualifiers=(),
                evidence_handles=tuple(
                    evidence_handles[value] for value in sorted(item.evidence_ids)
                ),
                source_versions=(source_version,),
                status=item.status,
            )
        )

    available_evidence = set(evidence_ids)
    projected_findings = []
    for finding in findings:
        finding_evidence = (
            set(finding.evidence_refs)
            if isinstance(finding, StructuredFactSetV1)
            else set(finding.available_evidence_ids)
        )
        if not finding_evidence.issubset(available_evidence):
            raise ValueError("grounded_request_evidence_unknown")
        linked_claims = tuple(
            item
            for item in graph.claims
            if finding.objective_id in item.objective_ids
            and set(item.evidence_ids).issubset(finding_evidence)
        )
        if not linked_claims:
            continue
        linked_claim_handles = tuple(
            claim_handles[item.claim_id]
            for item in sorted(linked_claims, key=lambda x: x.claim_id)
        )
        linked_evidence_handles = tuple(
            evidence_handles[value]
            for value in sorted(
                {value for item in linked_claims for value in item.evidence_ids}
            )
        )
        if isinstance(finding, StructuredFactSetV1):
            safe_texts = (
                (
                    "授权结构化查询结果完整。"
                    if finding.complete and not finding.truncated
                    else "授权结构化查询结果不完整，回答必须说明限制。"
                ),
            )
            finding_kind = "tabular"
        elif isinstance(finding, RiskAssessmentSetV1):
            safe_texts = tuple(
                f"风险评估等级为 {item.severity}。" for item in finding.assessments
            )
            finding_kind = "risk"
        else:
            safe_texts = tuple(item.text for item in finding.statements)
            finding_kind = "daily"
        for index, safe_text in enumerate(safe_texts):
            safe_text = _validate_safe_text(safe_text, private_tokens)
            projected_findings.append(
                GroundedSpecialistFindingV2(
                    finding_handle=_opaque_handle(
                        "finding",
                        {
                            "artifact": finding.content_hash,
                            "index": index,
                            "text": safe_text,
                        },
                    ),
                    finding_kind=finding_kind,
                    safe_text=safe_text,
                    claim_handles=linked_claim_handles,
                    evidence_handles=linked_evidence_handles,
                )
            )

    slots_by_id = {item.slot_id: item for item in task_spec.action_slots}
    actions = []
    for status in graph.action_statuses:
        slot = slots_by_id.get(status.slot_id)
        if slot is None:
            raise ValueError("grounded_request_action_unknown")
        summary = {
            "proposed": "已生成待确认提议，尚未执行。",
            "denied": "提议已拒绝，未执行。",
            "deferred": "提议已延后，未执行。",
            "conflicted": "提议存在冲突，未执行。",
        }[status.status]
        actions.append(
            GroundedActionCandidateV2(
                action_handle=action_handles[status.slot_id],
                action_kind=slot.action_kind,
                status=status.status,
                safe_summary=summary,
                reason_code=status.reason_code,
            )
        )

    citations = []
    for index, evidence_id in enumerate(evidence_ids, start=1):
        versions = tuple(
            sorted(
                {
                    (item.subject_ref, item.predicate, item.source_version)
                    for item in graph.claims
                    if evidence_id in item.evidence_ids
                }
            )
        )
        citations.append(
            GroundedEvidenceCandidateV2(
                evidence_handle=evidence_handles[evidence_id],
                display_label=f"证据 {index}",
                source_version=_opaque_handle("record-version", versions),
            )
        )

    values = {
        "version": "grounded-answer-provider-request.v2",
        "language": "zh-CN",
        "query": query,
        "objectives": tuple(
            GroundedObjectiveCandidateV2(
                objective_handle=objective_handles[objective_id],
                kind=objectives_by_id[objective_id].kind,
                status=graph_objectives[objective_id].status,
                required=objectives_by_id[objective_id].required,
                reason_code=graph_objectives[objective_id].reason_code,
            )
            for objective_id in sorted(objectives_by_id)
        ),
        "claims": tuple(claims),
        "specialist_findings": tuple(projected_findings),
        "actions": tuple(actions),
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
        "scope_hash": authorized_schema.scope_hash,
        "schema_hash": authorized_schema.schema_hash,
        "field_policy_version": authorized_schema.field_policy_version,
        "field_policy_hash": authorized_schema.field_policy_hash,
    }
    hash_values = {
        **values,
        "objectives": tuple(
            item.model_dump(mode="json") for item in values["objectives"]
        ),
        "claims": tuple(item.model_dump(mode="json") for item in claims),
        "specialist_findings": tuple(
            item.model_dump(mode="json") for item in projected_findings
        ),
        "actions": tuple(item.model_dump(mode="json") for item in actions),
        "citations": tuple(item.model_dump(mode="json") for item in citations),
        "presentation_policy": values["presentation_policy"].model_dump(mode="json"),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerProviderRequestV2.model_validate(values)


__all__ = ["build_grounded_answer_request"]
