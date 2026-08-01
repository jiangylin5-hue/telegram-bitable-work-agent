from __future__ import annotations

from hashlib import sha256
import json
import re

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV2,
    GroundedAnswerPlanV3,
    GroundedAnswerProviderRequestV2,
    GroundedAnswerProviderRequestV3,
    GroundedComposerResultV2,
)
from app.schemas.agent_specialist_results import (
    ClaimGraphV1,
    FinalAnswerRenderReceiptV1,
    specialist_payload_sha256,
)
from app.services.agent_composer_v2 import ComposerPresentationContextV1
from app.services.agent_grounded_answer_references import compact_reference_map
from app.services.agent_grounded_answer_request import (
    project_grounded_objective_status,
)


_CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
_INTERNAL_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:o|c|e|a|f|v)[0-9]{3}(?![A-Za-z0-9])"
)
_ASCII_ATOM_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_-]*(?![A-Za-z0-9_])")
_NUMBER_ATOM_RE = re.compile(
    r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?:%|％|元|万元|亿元)?(?![A-Za-z0-9])"
)
_CHINESE_MONEY_RE = re.compile(r"[零〇一二两三四五六七八九十百千万亿]+(?:元|万元|亿元)")
_EXECUTED_ACTION_RE = re.compile(
    r"(?:已|已经)(?:执行|确认|发送|写入|保存|落库|更新完成|创建完成|删除完成|修改完成)"
)
_ACTION_OBJECTIVE_KINDS = {"record_change", "task_creation", "reminder_request"}
_ACTION_STATUS_MARKERS = {
    "proposed": ("待确认", "未执行"),
    "denied": ("拒绝", "未执行"),
    "deferred": ("延后", "未执行"),
    "conflicted": ("冲突", "未执行"),
}


class ProviderValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _reject(detail: str, *, language: bool = False) -> None:
    raise ProviderValidationError(
        "provider_language_invalid" if language else "provider_grounding_invalid",
        detail,
    )


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _claim_value_projection(value: object) -> tuple[str, str]:
    if value is None:
        return "null", "null"
    if isinstance(value, bool):
        return "boolean", "true" if value else "false"
    if isinstance(value, int):
        return "integer", str(value)
    if isinstance(value, float):
        return "number", json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, str):
        return "string", value
    if isinstance(value, list):
        return "list", json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    if isinstance(value, dict):
        return "object", json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    _reject("grounded_answer_runtime_claim_value_invalid")


def _allowed_atom_text(
    request, referenced_claims, referenced_findings, evidence_handles
) -> str:
    citations = {item.evidence_handle: item for item in request.citations}
    values = []
    for claim in referenced_claims:
        values.extend(
            (
                claim.subject_label,
                claim.predicate_label,
                claim.value_text,
                *claim.qualifiers,
            )
        )
    values.extend(
        citations[value].display_label
        for value in evidence_handles
        if value in citations
    )
    values.extend(item.safe_text for item in referenced_findings)
    return "\n".join(values)


def _expanded_statement_references(request, statement):
    findings = {item.finding_handle: item for item in request.specialist_findings}
    referenced_findings = tuple(
        findings[value] for value in statement.finding_handles if value in findings
    )
    claim_handles = _ordered_unique(
        [
            *statement.claim_handles,
            *(
                value
                for finding in referenced_findings
                for value in finding.claim_handles
            ),
        ]
    )
    evidence_handles = _ordered_unique(
        [
            *statement.evidence_handles,
            *(
                value
                for finding in referenced_findings
                for value in finding.evidence_handles
            ),
        ]
    )
    return referenced_findings, claim_handles, evidence_handles


def _validate_atoms(text: str, allowed_text: str, request) -> None:
    for claim in request.claims:
        for role, token in (
            ("subject", claim.subject_label),
            ("predicate", claim.predicate_label),
            ("value", claim.value_text),
        ):
            if token and token in text and token not in allowed_text:
                _reject(f"grounded_answer_unreferenced_{role}_atom")
    for atom_kind, pattern in (
        ("ascii", _ASCII_ATOM_RE),
        ("number", _NUMBER_ATOM_RE),
        ("money", _CHINESE_MONEY_RE),
    ):
        for match in pattern.finditer(text):
            if match.group(0) not in allowed_text:
                _reject(f"grounded_answer_invented_{atom_kind}_atom")


def _validate_and_collect(
    request: GroundedAnswerProviderRequestV2,
    plan: GroundedAnswerPlanV2,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if len(plan.sections) > request.presentation_policy.max_sections:
        _reject("grounded_answer_section_limit")
    allowed_sections = set(request.presentation_policy.allowed_section_kinds)
    allowed_statements = set(request.presentation_policy.allowed_statement_kinds)
    claims = {item.claim_handle: item for item in request.claims}
    citations = {item.evidence_handle: item for item in request.citations}
    actions = {item.action_handle: item for item in request.actions}
    findings = {
        item.finding_handle: item for item in request.specialist_findings
    }
    objectives = {item.objective_handle: item for item in request.objectives}
    covered_claims: list[str] = []
    covered_evidence: list[str] = []
    covered_actions: list[str] = []
    covered_objectives: list[str] = []

    for section in plan.sections:
        if section.section_kind not in allowed_sections:
            _reject("grounded_answer_section_not_allowed")
        if (
            len(section.statements)
            > request.presentation_policy.max_statements_per_section
        ):
            _reject("grounded_answer_statement_limit")
        if _CHINESE_RE.search(section.heading) is None or _INTERNAL_HANDLE_RE.search(
            section.heading
        ):
            _reject("grounded_answer_heading_language_invalid", language=True)
        for statement in section.statements:
            if statement.statement_kind not in allowed_statements:
                _reject("grounded_answer_statement_not_allowed")
            if _CHINESE_RE.search(statement.text) is None or _INTERNAL_HANDLE_RE.search(
                statement.text
            ):
                _reject("grounded_answer_text_language_invalid", language=True)
            if any(value not in claims for value in statement.claim_handles):
                _reject("grounded_answer_claim_unknown")
            if any(value not in citations for value in statement.evidence_handles):
                _reject("grounded_answer_evidence_unknown")
            if any(value not in actions for value in statement.action_handles):
                _reject("grounded_answer_action_unknown")
            if any(value not in findings for value in statement.finding_handles):
                _reject("grounded_answer_finding_unknown")

            referenced_findings, expanded_claim_handles, expanded_evidence_handles = (
                _expanded_statement_references(request, statement)
            )
            referenced_claims = tuple(
                claims[value] for value in expanded_claim_handles
            )
            if statement.statement_kind in {"fact", "analysis", "recommendation"}:
                direct_claims = tuple(
                    claims[value] for value in statement.claim_handles
                )
                if any(item.status != "valid" for item in direct_claims):
                    _reject("grounded_answer_claim_not_valid")
                required_evidence = {
                    value
                    for item in referenced_claims
                    for value in item.evidence_handles
                }
                required_evidence.update(
                    value
                    for item in referenced_findings
                    for value in item.evidence_handles
                )
                if set(expanded_evidence_handles) != required_evidence:
                    _reject("grounded_answer_citation_closure_invalid")
                allowed_text = _allowed_atom_text(
                    request,
                    referenced_claims,
                    referenced_findings,
                    expanded_evidence_handles,
                )
                _validate_atoms(statement.text, allowed_text, request)
                for claim in referenced_claims:
                    covered_objectives.extend(claim.objective_handles)
                covered_objectives.extend(
                    item.objective_handle for item in referenced_findings
                )
            elif statement.statement_kind == "action_status":
                if (
                    statement.claim_handles
                    or statement.evidence_handles
                    or statement.finding_handles
                ):
                    _reject("grounded_answer_action_reference_invalid")
                if _EXECUTED_ACTION_RE.search(statement.text):
                    _reject("grounded_answer_action_execution_invented")
                allowed_text = "\n".join(
                    actions[value].safe_summary for value in statement.action_handles
                )
                _validate_atoms(statement.text, allowed_text, request)
                covered_objectives.extend(
                    item.objective_handle
                    for item in request.objectives
                    if item.kind in _ACTION_OBJECTIVE_KINDS
                    and item.status in {"proposed", "denied", "degraded", "failed"}
                )
                claimed_objectives = {
                    objective_handle
                    for claim in request.claims
                    for objective_handle in claim.objective_handles
                }
                covered_objectives.extend(
                    item.objective_handle
                    for item in request.objectives
                    if item.coverage_role == "action_prerequisite"
                    and item.objective_handle not in claimed_objectives
                )
            else:
                if (
                    statement.claim_handles
                    or statement.evidence_handles
                    or statement.finding_handles
                    or statement.action_handles
                ):
                    _reject("grounded_answer_limitation_reference_invalid")
                covered_objectives.extend(
                    item.objective_handle
                    for item in request.objectives
                    if item.status in {"denied", "degraded", "failed"}
                )

            covered_claims.extend(expanded_claim_handles)
            covered_evidence.extend(expanded_evidence_handles)
            covered_actions.extend(statement.action_handles)

    covered_objective_set = set(covered_objectives)
    if len(covered_claims) != len(set(covered_claims)):
        _reject("grounded_answer_claim_repeated")
    required_claims = {
        handle for handle, item in claims.items() if item.status == "valid"
    }
    if set(covered_claims) != required_claims:
        _reject("grounded_answer_required_claim_missing")
    if any(
        item.required and handle not in covered_objective_set
        for handle, item in objectives.items()
    ):
        _reject("grounded_answer_required_objective_missing")
    return (
        _ordered_unique(covered_objectives),
        _ordered_unique(covered_claims),
        _ordered_unique(covered_evidence),
        _ordered_unique(covered_actions),
    )


def validate_grounded_answer_plan(
    request: GroundedAnswerProviderRequestV2 | GroundedAnswerProviderRequestV3,
    plan: GroundedAnswerPlanV2 | GroundedAnswerPlanV3,
) -> None:
    if isinstance(request, GroundedAnswerProviderRequestV3):
        if not isinstance(plan, GroundedAnswerPlanV3):
            _reject("grounded_render_slot_plan_version_mismatch")
        _validate_and_collect_slots(request, plan)
        return
    if not isinstance(plan, GroundedAnswerPlanV2):
        _reject("grounded_render_slot_plan_version_mismatch")
    _validate_and_collect(request, plan)


def _validate_and_collect_slots(
    request: GroundedAnswerProviderRequestV3,
    plan: GroundedAnswerPlanV3,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    expected_handles = tuple(item.slot_handle for item in request.render_slots)
    actual_handles = tuple(item.slot_handle for item in plan.slot_outputs)
    if actual_handles != expected_handles:
        if len(actual_handles) != len(set(actual_handles)):
            _reject("grounded_render_slot_duplicate")
        if set(actual_handles) != set(expected_handles):
            _reject("grounded_render_slot_missing_or_unknown")
        _reject("grounded_render_slot_reordered")

    claims = {item.claim_handle: item for item in request.claims}
    findings = {
        item.finding_handle: item for item in request.specialist_findings
    }
    actions = {item.action_handle: item for item in request.actions}
    covered_objectives: list[str] = []
    covered_claims: list[str] = []
    covered_evidence: list[str] = []
    covered_actions: list[str] = []
    for slot, output in zip(request.render_slots, plan.slot_outputs, strict=True):
        text = output.text
        if _CHINESE_RE.search(text) is None or _INTERNAL_HANDLE_RE.search(text):
            _reject("grounded_answer_text_language_invalid", language=True)
        referenced_claims = tuple(claims[value] for value in slot.claim_handles)
        referenced_findings = tuple(
            findings[value] for value in slot.finding_handles
        )
        if slot.statement_kind in {"fact", "analysis", "recommendation"}:
            allowed_text = _allowed_atom_text(
                request,
                referenced_claims,
                referenced_findings,
                slot.evidence_handles,
            )
            _validate_atoms(text, allowed_text, request)
            if _EXECUTED_ACTION_RE.search(text):
                _reject("grounded_answer_action_execution_invented")
        elif slot.statement_kind == "action_status":
            if _EXECUTED_ACTION_RE.search(text):
                _reject("grounded_answer_action_execution_invented")
            if any(
                any(marker not in text for marker in _ACTION_STATUS_MARKERS[action.status])
                for action in (actions[value] for value in slot.action_handles)
            ):
                _reject("grounded_answer_action_status_missing")
            _validate_atoms(
                text,
                "\n".join(
                    (
                        *(actions[value].safe_summary for value in slot.action_handles),
                        _allowed_atom_text(
                            request,
                            tuple(
                                claims[value]
                                for value in slot.context_claim_handles
                            ),
                            (),
                            slot.context_evidence_handles,
                        ),
                    )
                ),
                request,
            )
        else:
            _validate_atoms(text, "", request)
            if _EXECUTED_ACTION_RE.search(text):
                _reject("grounded_answer_action_execution_invented")
        covered_objectives.extend(slot.objective_handles)
        covered_claims.extend(slot.claim_handles)
        covered_evidence.extend(slot.evidence_handles)
        covered_actions.extend(slot.action_handles)
    return (
        _ordered_unique(covered_objectives),
        _ordered_unique(covered_claims),
        _ordered_unique(covered_evidence),
        _ordered_unique(covered_actions),
    )


def _validate_runtime_binding(
    request: GroundedAnswerProviderRequestV2,
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    if graph.scope_hash != request.scope_hash or presentation.query != request.query:
        _reject("grounded_answer_runtime_scope_mismatch")
    if graph.content_hash != request.runtime_binding_hash:
        _reject("grounded_answer_runtime_binding_stale")
    objective_refs = compact_reference_map(
        "o", (item.objective_id for item in graph.objective_statuses)
    )
    valid_graph_claims = tuple(
        item for item in graph.claims if item.status == "valid"
    )
    claim_refs = compact_reference_map(
        "c", (item.claim_id for item in valid_graph_claims)
    )
    evidence_refs = compact_reference_map(
        "e",
        (
            evidence_id
            for item in valid_graph_claims
            for evidence_id in item.evidence_ids
        ),
    )
    action_refs = compact_reference_map(
        "a", (item.slot_id for item in graph.action_statuses)
    )
    objective_map = {value: key for key, value in objective_refs.items()}
    claim_map = {value: key for key, value in claim_refs.items()}
    evidence_map = {value: key for key, value in evidence_refs.items()}
    action_map = {value: key for key, value in action_refs.items()}
    if (
        set(objective_map) != {item.objective_handle for item in request.objectives}
        or set(claim_map) != {item.claim_handle for item in request.claims}
        or set(evidence_map) != {item.evidence_handle for item in request.citations}
        or set(action_map) != {item.action_handle for item in request.actions}
    ):
        _reject("grounded_answer_runtime_reference_mismatch")

    request_objectives = {
        item.objective_handle: item for item in request.objectives
    }
    finding_objective_ids = {
        objective_map[item.objective_handle]
        for item in request.specialist_findings
    }
    for handle, objective_id in objective_map.items():
        expected_status, expected_reason = project_grounded_objective_status(
            graph, objective_id, finding_objective_ids
        )
        candidate = request_objectives[handle]
        if (
            candidate.status != expected_status
            or candidate.reason_code != expected_reason
        ):
            _reject("grounded_answer_runtime_objective_mismatch")

    graph_claims = {item.claim_id: item for item in valid_graph_claims}
    request_claims = {item.claim_handle: item for item in request.claims}
    ordered_claim_ids = sorted(graph_claims)
    claim_version_refs = {
        claim_id: f"v{index:03d}"
        for index, claim_id in enumerate(ordered_claim_ids, start=1)
    }
    for handle, claim_id in claim_map.items():
        graph_claim = graph_claims[claim_id]
        candidate = request_claims[handle]
        value_type, value_text = _claim_value_projection(graph_claim.value)
        if (
            candidate.subject_label
            != presentation.subject_labels.get(graph_claim.subject_ref)
            or candidate.predicate_label
            != presentation.predicate_labels.get(graph_claim.predicate)
            or candidate.value_type != value_type
            or candidate.value_text != value_text
            or candidate.objective_handles
            != tuple(
                objective_refs[value]
                for value in sorted(graph_claim.objective_ids)
            )
            or candidate.evidence_handles
            != tuple(
                evidence_refs[value] for value in sorted(graph_claim.evidence_ids)
            )
            or candidate.status != graph_claim.status
            or candidate.source_versions != (claim_version_refs[claim_id],)
        ):
            _reject("grounded_answer_runtime_claim_mismatch")
    citation_versions = {
        evidence_id: f"v{len(ordered_claim_ids) + index:03d}"
        for index, evidence_id in enumerate(sorted(evidence_map.values()), start=1)
    }
    request_citations = {item.evidence_handle: item for item in request.citations}
    if any(
        request_citations[handle].source_version != citation_versions[evidence_id]
        for handle, evidence_id in evidence_map.items()
    ):
        _reject("grounded_answer_runtime_evidence_mismatch")
    return objective_map, claim_map, evidence_map, action_map


def _base_status(graph: ClaimGraphV1) -> tuple[str, tuple[str, ...]]:
    reasons = {
        item.reason_code
        for item in graph.objective_statuses
        if item.reason_code is not None
    }
    valid = any(item.status == "valid" for item in graph.claims)
    conflicted = any(item.status == "conflicted" for item in graph.claims)
    if any(item.status == "failed" for item in graph.objective_statuses) and not valid:
        return "failed", tuple(sorted(reasons))
    if (
        graph.objective_statuses
        and all(item.status == "denied" for item in graph.objective_statuses)
        and not valid
    ):
        return "denied", tuple(sorted(reasons))
    if conflicted or any(
        item.status in {"degraded", "failed"} for item in graph.objective_statuses
    ):
        if conflicted:
            reasons.add("conflicted_claim")
        return "degraded", tuple(sorted(reasons))
    return "completed", ()


def render_grounded_answer(
    request: GroundedAnswerProviderRequestV2 | GroundedAnswerProviderRequestV3,
    plan: GroundedAnswerPlanV2 | GroundedAnswerPlanV3,
    *,
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
    provider_call_count: int = 1,
) -> GroundedComposerResultV2:
    if isinstance(request, GroundedAnswerProviderRequestV3):
        if not isinstance(plan, GroundedAnswerPlanV3):
            _reject("grounded_render_slot_plan_version_mismatch")
        covered = _validate_and_collect_slots(request, plan)
    else:
        if not isinstance(plan, GroundedAnswerPlanV2):
            _reject("grounded_render_slot_plan_version_mismatch")
        covered = _validate_and_collect(request, plan)
    objective_map, claim_map, evidence_map, action_map = _validate_runtime_binding(
        request, graph, presentation
    )
    citations = {item.evidence_handle: item.display_label for item in request.citations}
    rendered_sections = []
    if isinstance(request, GroundedAnswerProviderRequestV3):
        headings = {
            "answer": "结论",
            "facts": "事实",
            "analysis": "分析",
            "risks": "风险",
            "daily": "日报",
            "actions": "待确认操作",
            "limitations": "限制说明",
        }
        for slot, output in zip(request.render_slots, plan.slot_outputs, strict=True):
            suffix = ""
            if slot.evidence_handles:
                suffix = "【证据：" + "、".join(
                    citations[value] for value in slot.evidence_handles
                ) + "】"
            rendered_sections.append(
                f"{headings[slot.section_kind]}\n{output.text}{suffix}"
            )
        section_kinds = tuple(item.section_kind for item in request.render_slots)
    else:
        for section in plan.sections:
            statements = []
            for statement in section.statements:
                suffix = ""
                _, _, evidence_handles = _expanded_statement_references(
                    request, statement
                )
                if evidence_handles:
                    suffix = (
                        "【证据："
                        + "、".join(
                            citations[value] for value in evidence_handles
                        )
                        + "】"
                    )
                statements.append(statement.text + suffix)
            rendered_sections.append(f"{section.heading}\n" + "\n".join(statements))
        section_kinds = tuple(item.section_kind for item in plan.sections)
    answer = "\n\n".join(rendered_sections)

    objective_ids = tuple(objective_map[value] for value in covered[0])
    claim_ids = tuple(claim_map[value] for value in covered[1])
    evidence_ids = tuple(evidence_map[value] for value in covered[2])
    action_ids = tuple(action_map[value] for value in covered[3])
    graph_claims = {item.claim_id: item for item in graph.claims}
    disclosure_codes = {
        item.reason_code
        for item in graph.objective_statuses
        if item.reason_code is not None
    }
    disclosure_codes.update(
        f"action_{item.status}"
        for item in graph.action_statuses
        if item.slot_id in set(action_ids)
    )
    receipt_values = {
        "version": "final-answer-render-receipt.v1",
        "covered_objective_ids": objective_ids,
        "covered_claim_ids": claim_ids,
        "covered_action_slot_ids": action_ids,
        "citation_edges": tuple(
            {"claim_id": claim_id, "evidence_id": evidence_id}
            for claim_id in claim_ids
            for evidence_id in graph_claims[claim_id].evidence_ids
        ),
        "section_kinds": section_kinds,
        "disclosure_codes": tuple(sorted(disclosure_codes)),
        "language": "zh-Hans",
        "answer_hash": sha256(answer.encode("utf-8")).hexdigest(),
        "claim_graph_hash": graph.content_hash,
        "presentation_hash": specialist_payload_sha256(
            presentation.model_dump(mode="json")
        ),
        "scope_hash": graph.scope_hash,
    }
    receipt_values["content_hash"] = specialist_payload_sha256(receipt_values)
    receipt = FinalAnswerRenderReceiptV1.model_validate(receipt_values)
    status, degradation_codes = _base_status(graph)
    action_statuses = tuple(
        item for item in graph.action_statuses if item.slot_id in set(action_ids)
    )
    values = {
        "version": "grounded-composer-result.v2",
        "status": status,
        "answer": answer,
        "answer_source": "real_provider",
        "provider_result_status": "completed",
        "claim_ids": claim_ids,
        "evidence_ids": evidence_ids,
        "action_statuses": action_statuses,
        "degradation_codes": degradation_codes,
        "render_receipt": receipt,
        "provider_call_count": provider_call_count,
        "scope_hash": graph.scope_hash,
    }
    hash_values = {
        **values,
        "action_statuses": tuple(
            item.model_dump(mode="json") for item in action_statuses
        ),
        "render_receipt": receipt.model_dump(mode="json"),
    }
    values["content_hash"] = specialist_payload_sha256(hash_values)
    return GroundedComposerResultV2.model_validate(values)


__all__ = [
    "ProviderValidationError",
    "render_grounded_answer",
    "validate_grounded_answer_plan",
]
