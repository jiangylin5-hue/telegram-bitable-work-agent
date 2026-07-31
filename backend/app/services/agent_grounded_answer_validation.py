from __future__ import annotations

from hashlib import sha256
import json
import re

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV2,
    GroundedAnswerProviderRequestV2,
    GroundedComposerResultV2,
)
from app.schemas.agent_specialist_results import (
    ClaimGraphV1,
    FinalAnswerRenderReceiptV1,
    specialist_payload_sha256,
)
from app.services.agent_composer_v2 import ComposerPresentationContextV1


_CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
_INTERNAL_HANDLE_RE = re.compile(
    r"(?:claim|evidence|action|objective|finding):sha256:[0-9a-f]{64}"
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


def _handle(kind: str, value: object) -> str:
    return f"{kind}:sha256:{specialist_payload_sha256({'kind': kind, 'value': value})}"


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


def _allowed_atom_text(request, referenced_claims, evidence_handles) -> str:
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
    return "\n".join(values)


def _validate_atoms(text: str, allowed_text: str, request) -> None:
    for claim in request.claims:
        for token in (claim.subject_label, claim.predicate_label, claim.value_text):
            if token and token in text and token not in allowed_text:
                _reject("grounded_answer_unreferenced_atom")
    for pattern in (_ASCII_ATOM_RE, _NUMBER_ATOM_RE, _CHINESE_MONEY_RE):
        for match in pattern.finditer(text):
            if match.group(0) not in allowed_text:
                _reject("grounded_answer_invented_atom")


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

            referenced_claims = tuple(
                claims[value] for value in statement.claim_handles
            )
            if statement.statement_kind in {"fact", "analysis", "recommendation"}:
                if any(item.status != "valid" for item in referenced_claims):
                    _reject("grounded_answer_claim_not_valid")
                required_evidence = {
                    value
                    for item in referenced_claims
                    for value in item.evidence_handles
                }
                if set(statement.evidence_handles) != required_evidence:
                    _reject("grounded_answer_citation_closure_invalid")
                allowed_text = _allowed_atom_text(
                    request, referenced_claims, statement.evidence_handles
                )
                _validate_atoms(statement.text, allowed_text, request)
                for claim in referenced_claims:
                    covered_objectives.extend(claim.objective_handles)
            elif statement.statement_kind == "action_status":
                if statement.claim_handles or statement.evidence_handles:
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
            else:
                if (
                    statement.claim_handles
                    or statement.evidence_handles
                    or statement.action_handles
                ):
                    _reject("grounded_answer_limitation_reference_invalid")
                covered_objectives.extend(
                    item.objective_handle
                    for item in request.objectives
                    if item.status in {"denied", "degraded", "failed"}
                )

            covered_claims.extend(statement.claim_handles)
            covered_evidence.extend(statement.evidence_handles)
            covered_actions.extend(statement.action_handles)

    covered_objective_set = set(covered_objectives)
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
    request: GroundedAnswerProviderRequestV2,
    plan: GroundedAnswerPlanV2,
) -> None:
    _validate_and_collect(request, plan)


def _validate_runtime_binding(
    request: GroundedAnswerProviderRequestV2,
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    if graph.scope_hash != request.scope_hash or presentation.query != request.query:
        _reject("grounded_answer_runtime_scope_mismatch")
    objective_map = {
        _handle("objective", item.objective_id): item.objective_id
        for item in graph.objective_statuses
    }
    claim_map = {
        _handle("claim", item.claim_id): item.claim_id for item in graph.claims
    }
    evidence_map = {
        _handle("evidence", evidence_id): evidence_id
        for item in graph.claims
        for evidence_id in item.evidence_ids
    }
    action_map = {
        _handle("action", item.slot_id): item.slot_id for item in graph.action_statuses
    }
    if (
        set(objective_map) != {item.objective_handle for item in request.objectives}
        or set(claim_map) != {item.claim_handle for item in request.claims}
        or set(evidence_map) != {item.evidence_handle for item in request.citations}
        or set(action_map) != {item.action_handle for item in request.actions}
    ):
        _reject("grounded_answer_runtime_reference_mismatch")

    graph_claims = {item.claim_id: item for item in graph.claims}
    request_claims = {item.claim_handle: item for item in request.claims}
    for handle, claim_id in claim_map.items():
        graph_claim = graph_claims[claim_id]
        candidate = request_claims[handle]
        value_type, value_text = _claim_value_projection(graph_claim.value)
        expected_source = _handle(
            "record-version",
            {
                "subject": graph_claim.subject_ref,
                "predicate": graph_claim.predicate,
                "version": graph_claim.source_version,
            },
        )
        if (
            candidate.subject_label
            != presentation.subject_labels.get(graph_claim.subject_ref)
            or candidate.predicate_label
            != presentation.predicate_labels.get(graph_claim.predicate)
            or candidate.value_type != value_type
            or candidate.value_text != value_text
            or candidate.objective_handles
            != tuple(
                _handle("objective", value)
                for value in sorted(graph_claim.objective_ids)
            )
            or candidate.evidence_handles
            != tuple(
                _handle("evidence", value) for value in sorted(graph_claim.evidence_ids)
            )
            or candidate.status != graph_claim.status
            or candidate.source_versions != (expected_source,)
        ):
            _reject("grounded_answer_runtime_claim_mismatch")
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
    request: GroundedAnswerProviderRequestV2,
    plan: GroundedAnswerPlanV2,
    *,
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
    provider_call_count: int = 1,
) -> GroundedComposerResultV2:
    covered = _validate_and_collect(request, plan)
    objective_map, claim_map, evidence_map, action_map = _validate_runtime_binding(
        request, graph, presentation
    )
    citations = {item.evidence_handle: item.display_label for item in request.citations}
    rendered_sections = []
    for section in plan.sections:
        statements = []
        for statement in section.statements:
            suffix = ""
            if statement.evidence_handles:
                suffix = (
                    "【证据："
                    + "、".join(
                        citations[value] for value in statement.evidence_handles
                    )
                    + "】"
                )
            statements.append(statement.text + suffix)
        rendered_sections.append(f"{section.heading}\n" + "\n".join(statements))
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
        "section_kinds": tuple(item.section_kind for item in plan.sections),
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
