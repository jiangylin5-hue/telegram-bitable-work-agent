from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
import json

from app.schemas.agent_grounded_answer_v2 import (
    GroundedActionCandidateV2,
    GroundedAnswerProviderRequestV3,
    GroundedClaimCandidateV2,
    GroundedEvidenceCandidateV2,
    GroundedObjectiveCandidateV2,
    GroundedPresentationPolicyV2,
    GroundedRenderSlotV1,
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
from app.services.agent_grounded_answer_references import (
    compact_reference,
    compact_reference_map,
)


SpecialistFinding = StructuredFactSetV1 | RiskAssessmentSetV1 | DailyBriefV1

_FORBIDDEN_EVALUATION_MARKERS = (
    "case_id",
    "gold_truth",
    "expected_answer",
    "expected_action",
    "expected_target",
)


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


def _claim_identity(
    *, subject_ref: str, predicate: str, value: object
) -> tuple[str, str, str, str]:
    value_type, value_text = _value_projection(value)
    return subject_ref, predicate, value_type, value_text


def _graph_claim_identity(item: object) -> tuple[str, str, str, str]:
    return _claim_identity(
        subject_ref=item.subject_ref,
        predicate=item.predicate,
        value=item.value,
    )


def _fact_claim_identities(
    finding: StructuredFactSetV1,
) -> set[tuple[str, str, str, str]]:
    identities = {
        _claim_identity(
            subject_ref=f"record:{record.record_id}",
            predicate=f"field:{field.field_id}",
            value=field.value,
        )
        for record in finding.records
        for field in record.values
    }
    identities.update(
        _claim_identity(
            subject_ref=f"aggregate:{aggregate.aggregate_id}",
            predicate=(
                "group:"
                + json.dumps(
                    aggregate.group_key,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            value=aggregate.value,
        )
        for aggregate in finding.aggregates
    )
    return identities


def _risk_claim_identities(
    finding: RiskAssessmentSetV1,
) -> set[tuple[str, str, str, str]]:
    return {
        _claim_identity(
            subject_ref=f"record:{assessment.subject_ref}",
            predicate="risk_severity",
            value=assessment.severity,
        )
        for assessment in finding.assessments
    }


def project_grounded_objective_status(
    graph: ClaimGraphV1,
    objective_id: str,
    finding_objective_ids: set[str],
) -> tuple[str, str | None]:
    current = next(
        item for item in graph.objective_statuses if item.objective_id == objective_id
    )
    objective_claims = tuple(
        item for item in graph.claims if objective_id in item.objective_ids
    )
    if (
        current.status == "completed"
        and objective_id not in finding_objective_ids
        and objective_claims
        and not any(item.status == "valid" for item in objective_claims)
    ):
        reason_code = (
            "conflicted_claim"
            if any(item.status == "conflicted" for item in objective_claims)
            else "stale_claim"
        )
        return "degraded", reason_code
    return current.status, current.reason_code


def build_grounded_answer_request(
    *,
    query: str,
    task_spec: TaskSpecV2,
    graph: ClaimGraphV1,
    authorized_schema: AuthorizedSchemaSnapshot,
    presentation: ComposerPresentationContextV1,
    specialist_findings: Sequence[SpecialistFinding],
) -> GroundedAnswerProviderRequestV3:
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
        or not set(presentation_objectives).issubset(objectives_by_id)
    ):
        raise ValueError("grounded_request_objective_mismatch")
    for objective_id, shown in presentation_objectives.items():
        objective = objectives_by_id[objective_id]
        if shown.kind != objective.kind:
            raise ValueError("grounded_request_objective_mismatch")

    findings = tuple(specialist_findings)
    facts_by_hash = {
        item.content_hash: item
        for item in findings
        if isinstance(item, StructuredFactSetV1)
    }
    risks_by_hash = {
        item.content_hash: item
        for item in findings
        if isinstance(item, RiskAssessmentSetV1)
    }
    fact_hashes = set(facts_by_hash)
    risk_hashes = set(risks_by_hash)
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

    ordered_claims = tuple(
        sorted(
            (item for item in graph.claims if item.status == "valid"),
            key=lambda item: item.claim_id,
        )
    )
    ordered_actions = tuple(sorted(graph.action_statuses, key=lambda item: item.slot_id))
    objective_handles = compact_reference_map("o", objectives_by_id)
    action_objective_ids = {item.objective_id for item in task_spec.action_slots}
    action_prerequisite_ids = {
        item.from_objective_id
        for item in task_spec.dependency_edges
        if item.required and item.to_objective_id in action_objective_ids
    }
    claim_handles = compact_reference_map(
        "c", (item.claim_id for item in ordered_claims)
    )
    evidence_ids = sorted(
        {evidence_id for item in ordered_claims for evidence_id in item.evidence_ids}
    )
    graph_evidence_ids = {
        evidence_id for item in graph.claims for evidence_id in item.evidence_ids
    }
    evidence_handles = compact_reference_map("e", evidence_ids)
    action_handles = compact_reference_map(
        "a", (item.slot_id for item in ordered_actions)
    )
    claim_version_handles = {
        item.claim_id: compact_reference("v", index)
        for index, item in enumerate(ordered_claims, start=1)
    }
    citation_version_handles = {
        evidence_id: compact_reference("v", len(ordered_claims) + index)
        for index, evidence_id in enumerate(evidence_ids, start=1)
    }

    private_tokens = (
        {item.claim_id for item in graph.claims}
        | {item.subject_ref for item in graph.claims}
        | {item.predicate for item in graph.claims}
        | graph_evidence_ids
        | set(action_handles)
    )

    claims = []
    for item in ordered_claims:
        subject_label = presentation.subject_labels.get(item.subject_ref)
        predicate_label = presentation.predicate_labels.get(item.predicate)
        if not subject_label or not predicate_label:
            raise ValueError("grounded_request_safe_label_missing")
        _validate_safe_text(subject_label, private_tokens)
        _validate_safe_text(predicate_label, private_tokens)
        value_type, value_text = _value_projection(item.value)
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
                source_versions=(claim_version_handles[item.claim_id],),
                status=item.status,
            )
        )

    projected_findings = []
    daily_fact_hashes = {
        item.fact_set_hash for item in findings if isinstance(item, DailyBriefV1)
    }
    daily_risk_hashes = {
        item.risk_set_hash
        for item in findings
        if isinstance(item, DailyBriefV1) and item.risk_set_hash is not None
    }
    empty_risk_fact_hashes = {
        item.fact_set_hash
        for item in findings
        if isinstance(item, RiskAssessmentSetV1) and not item.assessments
    }

    def append_finding(
        *,
        finding_kind: str,
        objective_id: str,
        safe_text: str | None,
        identities: set[tuple[str, str, str, str]],
        finding_evidence: set[str],
    ) -> None:
        linked_claims = tuple(
            item
            for item in ordered_claims
            if _graph_claim_identity(item) in identities
            and set(item.evidence_ids).issubset(finding_evidence)
        )
        if not linked_claims:
            return
        linked_claim_handles = tuple(
            claim_handles[item.claim_id]
            for item in sorted(linked_claims, key=lambda value: value.claim_id)
        )
        linked_evidence_handles = tuple(
            evidence_handles[value]
            for value in sorted(
                {value for item in linked_claims for value in item.evidence_ids}
            )
        )
        if safe_text is None:
            safe_text = "；".join(
                (
                    f"{presentation.subject_labels[item.subject_ref]}的"
                    f"{presentation.predicate_labels[item.predicate]}为"
                    f"{_value_projection(item.value)[1]}"
                )
                for item in linked_claims
            ) + "。"
        if any(
            item.finding_kind == finding_kind
            and item.objective_handle == objective_handles[objective_id]
            and item.safe_text == safe_text
            and item.claim_handles == linked_claim_handles
            and item.evidence_handles == linked_evidence_handles
            for item in projected_findings
        ):
            return
        projected_findings.append(
            GroundedSpecialistFindingV2(
                finding_handle=compact_reference(
                    "f", len(projected_findings) + 1
                ),
                objective_handle=objective_handles[objective_id],
                finding_kind=finding_kind,
                safe_text=_validate_safe_text(safe_text, private_tokens),
                claim_handles=linked_claim_handles,
                evidence_handles=linked_evidence_handles,
            )
        )

    for finding in findings:
        finding_evidence = (
            set(finding.evidence_refs)
            if isinstance(finding, StructuredFactSetV1)
            else set(finding.available_evidence_ids)
        )
        if not ordered_claims:
            continue
        if not finding_evidence.issubset(graph_evidence_ids):
            raise ValueError("grounded_request_evidence_unknown")
        if isinstance(finding, StructuredFactSetV1):
            if finding.content_hash in daily_fact_hashes | empty_risk_fact_hashes:
                continue
            append_finding(
                finding_kind="tabular",
                objective_id=finding.objective_id,
                safe_text=(
                    "授权结构化查询结果完整。"
                    if finding.complete and not finding.truncated
                    else "授权结构化查询结果不完整，回答必须说明限制。"
                ),
                identities=_fact_claim_identities(finding),
                finding_evidence=finding_evidence,
            )
        elif isinstance(finding, RiskAssessmentSetV1):
            if finding.content_hash in daily_risk_hashes:
                continue
            if finding.assessments:
                for assessment in finding.assessments:
                    append_finding(
                        finding_kind="risk",
                        objective_id=finding.objective_id,
                        safe_text=f"风险评估等级为 {assessment.severity}。",
                        identities={
                            _claim_identity(
                                subject_ref=f"record:{assessment.subject_ref}",
                                predicate="risk_severity",
                                value=assessment.severity,
                            )
                        },
                        finding_evidence=set(assessment.evidence_ids),
                    )
            else:
                facts = facts_by_hash[finding.fact_set_hash]
                append_finding(
                    finding_kind="risk",
                    objective_id=finding.objective_id,
                    safe_text="授权风险评估已完成，未发现需要列出的风险。",
                    identities=_fact_claim_identities(facts),
                    finding_evidence=finding_evidence,
                )
        else:
            identities = _fact_claim_identities(facts_by_hash[finding.fact_set_hash])
            if finding.risk_set_hash is not None:
                identities.update(
                    _risk_claim_identities(risks_by_hash[finding.risk_set_hash])
                )
            append_finding(
                finding_kind="daily",
                objective_id=finding.objective_id,
                safe_text=(
                    None
                    if finding.statements
                    else "授权日报已完成，当前没有额外可展示条目。"
                ),
                identities=identities,
                finding_evidence=finding_evidence,
            )

    slots_by_id = {item.slot_id: item for item in task_spec.action_slots}
    actions = []
    for status in ordered_actions:
        slot = slots_by_id.get(status.slot_id) or slots_by_id.get(
            status.slot_id.split(":", 1)[0]
        )
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
        citations.append(
            GroundedEvidenceCandidateV2(
                evidence_handle=evidence_handles[evidence_id],
                display_label=f"证据 {index}",
                source_version=citation_version_handles[evidence_id],
            )
        )

    finding_objective_ids = {
        objective_id
        for objective_id, handle in objective_handles.items()
        if any(item.objective_handle == handle for item in projected_findings)
    }

    objectives = tuple(
        GroundedObjectiveCandidateV2(
            objective_handle=objective_handles[objective_id],
            kind=objectives_by_id[objective_id].kind,
            status=project_grounded_objective_status(
                graph, objective_id, finding_objective_ids
            )[0],
            required=objectives_by_id[objective_id].required,
            reason_code=project_grounded_objective_status(
                graph, objective_id, finding_objective_ids
            )[1],
            coverage_role=(
                "action_prerequisite"
                if objective_id in action_prerequisite_ids
                else "user_result"
            ),
        )
        for objective_id in sorted(objectives_by_id)
    )
    render_slots = []
    if claims:
        factual_objectives = tuple(
            dict.fromkeys(
                [
                    handle
                    for claim in claims
                    for handle in claim.objective_handles
                ]
                + [item.objective_handle for item in projected_findings]
            )
        )
        finding_kinds = {item.finding_kind for item in projected_findings}
        render_slots.append(
            GroundedRenderSlotV1(
                slot_handle=compact_reference("s", len(render_slots) + 1),
                section_kind="answer",
                statement_kind=(
                    "analysis" if finding_kinds & {"risk", "daily"} else "fact"
                ),
                objective_handles=factual_objectives,
                claim_handles=tuple(item.claim_handle for item in claims),
                evidence_handles=tuple(item.evidence_handle for item in citations),
                finding_handles=tuple(
                    item.finding_handle for item in projected_findings
                ),
                action_handles=(),
                required=True,
            )
        )
    if actions:
        action_slot_objectives = tuple(
            item.objective_handle
            for item in objectives
            if item.kind in {"record_change", "task_creation", "reminder_request"}
            or item.coverage_role == "action_prerequisite"
        )
        if not action_slot_objectives:
            raise ValueError("grounded_render_slot_action_objective_missing")
        action_context_claims = tuple(
            item
            for item in claims
            if set(item.objective_handles).intersection(action_slot_objectives)
        )
        action_context_evidence = tuple(
            dict.fromkeys(
                value
                for item in action_context_claims
                for value in item.evidence_handles
            )
        )
        render_slots.append(
            GroundedRenderSlotV1(
                slot_handle=compact_reference("s", len(render_slots) + 1),
                section_kind="actions",
                statement_kind="action_status",
                objective_handles=action_slot_objectives,
                claim_handles=(),
                evidence_handles=(),
                finding_handles=(),
                action_handles=tuple(item.action_handle for item in actions),
                context_claim_handles=tuple(
                    item.claim_handle for item in action_context_claims
                ),
                context_evidence_handles=action_context_evidence,
                required=True,
            )
        )
    limited_objectives = tuple(
        item.objective_handle
        for item in objectives
        if item.status in {"denied", "degraded", "failed"}
    )
    if limited_objectives:
        render_slots.append(
            GroundedRenderSlotV1(
                slot_handle=compact_reference("s", len(render_slots) + 1),
                section_kind="limitations",
                statement_kind="limitation",
                objective_handles=limited_objectives,
                claim_handles=(),
                evidence_handles=(),
                finding_handles=(),
                action_handles=(),
                required=True,
            )
        )
    if not render_slots:
        raise ValueError("grounded_render_slot_plan_empty")

    values = {
        "version": "grounded-answer-provider-request.v3",
        "language": "zh-CN",
        "query": query,
        "objectives": objectives,
        "claims": tuple(claims),
        "specialist_findings": tuple(projected_findings),
        "actions": tuple(actions),
        "citations": tuple(citations),
        "render_slots": tuple(render_slots),
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
        "runtime_binding_hash": graph.content_hash,
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
        "render_slots": tuple(
            item.model_dump(mode="json") for item in render_slots
        ),
        "presentation_policy": values["presentation_policy"].model_dump(mode="json"),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedAnswerProviderRequestV3.model_validate(values)


__all__ = ["build_grounded_answer_request", "project_grounded_objective_status"]
