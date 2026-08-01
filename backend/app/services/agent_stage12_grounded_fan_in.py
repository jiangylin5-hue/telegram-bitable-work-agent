from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Protocol
from uuid import UUID

from app.core.config import Settings
from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV3,
    GroundedComposerResultV2,
    ProviderResultStatus,
)
from app.schemas.agent_specialist_results import (
    ClaimGraphV1,
    DailyBriefV1,
    FinalAnswerRenderReceiptV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import AuthorizedSchemaSnapshot, TaskSpecV2
from app.services.agent_composer_v2 import (
    ComposerObjectiveContextV1,
    ComposerPresentationContextV1,
    compose_claim_graph,
)
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderAdapterV2,
    build_grounded_composer_profile,
)
from app.services.agent_grounded_answer_request import build_grounded_answer_request
from app.services.agent_grounded_answer_validation import render_grounded_answer
from app.services.agent_model_gateway import ModelGatewayV1


_PUBLIC_ANSWER_MAX_LENGTH = 2_000
_SpecialistFinding = StructuredFactSetV1 | RiskAssessmentSetV1 | DailyBriefV1


class GroundedProvider(Protocol):
    slot_observations: tuple[object, ...]

    def __call__(self, request: object) -> GroundedAnswerPlanV3: ...


def build_stage12_grounded_provider(
    settings: Settings,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> GroundedAnswerProviderAdapterV2:
    profile = build_grounded_composer_profile(max_attempts=2)
    gateway = ModelGatewayV1(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        profiles={"composer": profile},
        now=now,
    )
    return GroundedAnswerProviderAdapterV2(gateway=gateway, now=now)


def build_stage12_presentation(
    *,
    query: str,
    task_spec: TaskSpecV2,
    claim_graph: ClaimGraphV1,
    authorized_schema: AuthorizedSchemaSnapshot,
    specialist_findings: Sequence[_SpecialistFinding],
    record_labels: Mapping[UUID, str] | None = None,
) -> ComposerPresentationContextV1:
    field_by_id = {
        field.field_id: field
        for table in authorized_schema.tables
        for field in table.fields
    }
    table_by_id = {table.table_id: table for table in authorized_schema.tables}
    subject_labels: dict[str, str] = {}
    predicate_labels: dict[str, str] = {}
    record_labels = record_labels or {}
    for finding in specialist_findings:
        if not isinstance(finding, StructuredFactSetV1):
            continue
        for record in finding.records:
            table = table_by_id.get(record.table_id)
            values = {item.field_id: item.value for item in record.values}
            label_value = None
            if table is not None:
                for field_id in (table.label_field_id, table.identity_field_id):
                    if field_id is not None and values.get(field_id) not in (None, ""):
                        label_value = values[field_id]
                        break
            subject_labels[f"record:{record.record_id}"] = record_labels.get(
                record.record_id,
                _safe_label(label_value)
                if label_value is not None
                else "已授权记录",
            )
    for claim in claim_graph.claims:
        if claim.subject_ref.startswith("aggregate:"):
            subject_labels.setdefault(claim.subject_ref, "汇总结果")
        elif claim.subject_ref.startswith("record:"):
            subject_labels.setdefault(claim.subject_ref, "已授权记录")
        if claim.predicate.startswith("field:"):
            try:
                field_id = UUID(claim.predicate.removeprefix("field:"))
            except ValueError:
                predicate_labels.setdefault(claim.predicate, "已授权字段")
            else:
                field = field_by_id.get(field_id)
                predicate_labels[claim.predicate] = (
                    field.name if field is not None else "已授权字段"
                )
        elif claim.predicate == "risk_severity":
            predicate_labels[claim.predicate] = "风险等级"
        elif claim.predicate == "value":
            predicate_labels[claim.predicate] = "统计值"
        else:
            predicate_labels.setdefault(claim.predicate, "分析结果")
    optional_targets = {
        edge.to_objective_id for edge in task_spec.dependency_edges if not edge.required
    }
    return ComposerPresentationContextV1(
        query=query,
        objectives=tuple(
            ComposerObjectiveContextV1(
                objective_id=objective.objective_id,
                kind=objective.kind,
                required=(
                    objective.required
                    and objective.objective_id not in optional_targets
                ),
            )
            for objective in task_spec.objectives
        ),
        subject_labels=subject_labels,
        predicate_labels=predicate_labels,
    )


def compose_stage12_grounded_result(
    *,
    query: str,
    task_spec: TaskSpecV2,
    claim_graph: ClaimGraphV1,
    authorized_schema: AuthorizedSchemaSnapshot,
    presentation: ComposerPresentationContextV1,
    specialist_findings: Sequence[_SpecialistFinding],
    provider: GroundedProvider,
) -> GroundedComposerResultV2:
    required_objective_ids = {
        objective.objective_id
        for objective in task_spec.objectives
        if objective.required
    }
    if any(
        objective.objective_id in required_objective_ids
        and objective.status == "failed"
        for objective in claim_graph.objective_statuses
    ):
        return build_stage12_safe_fallback(
            claim_graph=claim_graph,
            presentation=presentation,
            status="grounding_failed",
            provider_call_count=0,
            extra_degradation_code="required_specialist_failed",
        )
    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=claim_graph,
        authorized_schema=authorized_schema,
        presentation=presentation,
        specialist_findings=specialist_findings,
    )
    provider_called = False
    try:
        provider_called = True
        plan = provider(request)
        provider_call_count = _provider_call_count(provider, called=True)
        result = render_grounded_answer(
            request,
            plan,
            graph=claim_graph,
            presentation=presentation,
            provider_call_count=provider_call_count,
        )
        if len(result.answer) > _PUBLIC_ANSWER_MAX_LENGTH:
            raise _Stage12ProviderResultError("provider_schema_invalid")
        return result
    except Exception as exc:
        return build_stage12_safe_fallback(
            claim_graph=claim_graph,
            presentation=presentation,
            status=_provider_result_status(exc),
            provider_call_count=_provider_call_count(
                provider,
                called=provider_called,
            ),
            extra_degradation_code=_safe_provider_error_code(exc),
        )


def build_stage12_safe_fallback(
    *,
    claim_graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
    status: ProviderResultStatus,
    provider_call_count: int,
    extra_degradation_code: str | None = None,
) -> GroundedComposerResultV2:
    if status == "completed":
        raise ValueError("stage12_fallback_status_invalid")
    claim_subjects = {claim.subject_ref for claim in claim_graph.claims}
    claim_predicates = {claim.predicate for claim in claim_graph.claims}
    fallback_presentation = presentation.model_copy(
        update={
            "subject_labels": {
                key: value
                for key, value in presentation.subject_labels.items()
                if key in claim_subjects
            },
            "predicate_labels": {
                key: value
                for key, value in presentation.predicate_labels.items()
                if key in claim_predicates
            },
        }
    )
    deterministic = compose_claim_graph(
        claim_graph,
        presentation=fallback_presentation,
    )
    answer = deterministic.answer
    receipt = deterministic.render_receipt
    claim_ids = deterministic.claim_ids
    evidence_ids = deterministic.evidence_ids
    action_statuses = deterministic.action_statuses
    if len(answer) > _PUBLIC_ANSWER_MAX_LENGTH:
        answer = "模型回答失败，安全结果超过公开长度限制，未返回不完整内容。"
        claim_ids = ()
        evidence_ids = ()
        action_statuses = ()
        receipt = _empty_fallback_receipt(
            answer=answer,
            claim_graph=claim_graph,
            presentation=fallback_presentation,
            status=status,
        )
    degradation_codes = set(deterministic.degradation_codes)
    degradation_codes.add(status)
    if extra_degradation_code is not None:
        degradation_codes.add(extra_degradation_code)
    result_status = (
        deterministic.status
        if deterministic.status in {"failed", "denied"}
        else "degraded"
    )
    values: dict[str, object] = {
        "version": "grounded-composer-result.v2",
        "status": result_status,
        "answer": answer,
        "answer_source": "deterministic_fallback",
        "provider_result_status": status,
        "claim_ids": claim_ids,
        "evidence_ids": evidence_ids,
        "action_statuses": action_statuses,
        "degradation_codes": tuple(sorted(degradation_codes)),
        "render_receipt": receipt,
        "provider_call_count": min(max(provider_call_count, 0), 6),
        "scope_hash": claim_graph.scope_hash,
    }
    values["content_hash"] = specialist_payload_sha256(
        {
            **values,
            "action_statuses": tuple(
                item.model_dump(mode="json") for item in action_statuses
            ),
            "render_receipt": receipt.model_dump(mode="json"),
        }
    )
    return GroundedComposerResultV2.model_validate(values)


class _Stage12ProviderResultError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _provider_result_status(exc: Exception) -> ProviderResultStatus:
    code = getattr(exc, "code", None)
    if code == "provider_schema_invalid":
        return "schema_failed"
    if code in {
        "provider_grounding_invalid",
        "provider_semantic_invalid",
        "provider_citation_invalid",
    } or str(exc).startswith("grounded_request_"):
        return "grounding_failed"
    if code == "provider_language_invalid":
        return "language_failed"
    return "transport_failed"


def _provider_call_count(provider: object, *, called: bool) -> int:
    if not called:
        return 0
    observations = getattr(provider, "slot_observations", ())
    count = sum(
        int(getattr(observation, "attempt_count", 0))
        for observation in observations
    )
    return max(1, min(count, 6))


def _safe_provider_error_code(exc: Exception) -> str | None:
    detail = str(exc)
    if re.fullmatch(r"(?:grounded|provider)_[a-z0-9_]{1,100}", detail):
        return detail
    return None


def _safe_label(value: object) -> str:
    if isinstance(value, str):
        return value[:120] or "已授权记录"
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return rendered[:120] or "已授权记录"


def _empty_fallback_receipt(
    *,
    answer: str,
    claim_graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
    status: ProviderResultStatus,
) -> FinalAnswerRenderReceiptV1:
    values: dict[str, object] = {
        "version": "final-answer-render-receipt.v1",
        "covered_objective_ids": (),
        "covered_claim_ids": (),
        "covered_action_slot_ids": (),
        "citation_edges": (),
        "section_kinds": ("limitations",),
        "disclosure_codes": (status,),
        "language": "zh-Hans",
        "answer_hash": sha256(answer.encode("utf-8")).hexdigest(),
        "claim_graph_hash": claim_graph.content_hash,
        "presentation_hash": specialist_payload_sha256(
            presentation.model_dump(mode="json")
        ),
        "scope_hash": claim_graph.scope_hash,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return FinalAnswerRenderReceiptV1.model_validate(values)


__all__ = [
    "build_stage12_grounded_provider",
    "build_stage12_presentation",
    "build_stage12_safe_fallback",
    "compose_stage12_grounded_result",
]
