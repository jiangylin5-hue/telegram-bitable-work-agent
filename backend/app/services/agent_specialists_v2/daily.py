from __future__ import annotations

import json

from app.schemas.agent_specialist_results import (
    DailyBriefV1,
    ObjectiveSpecialistInputV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_specialists_v2.base import (
    SpecialistExecutionContextV2,
    SpecialistHandlerResultV2,
)


class DailySpecialistV2:
    capability_id = "platform.daily.summarise"
    input_schema_version = "objective-specialist-input.v1"
    output_schema_version = "daily-brief.v1"
    allowed_ports = frozenset({"artifact_reader", "model_gateway", "clock", "metrics"})

    def execute(
        self,
        command: ObjectiveSpecialistInputV1,
        context: SpecialistExecutionContextV2,
    ) -> SpecialistHandlerResultV2:
        if command.capability_id != self.capability_id:
            raise ValueError("daily_specialist_capability_mismatch")
        artifacts = tuple(
            context.artifact_reader(ref) for ref in command.input_artifact_refs
        )
        facts = tuple(
            item for item in artifacts if isinstance(item, StructuredFactSetV1)
        )
        risks = tuple(
            item for item in artifacts if isinstance(item, RiskAssessmentSetV1)
        )
        if len(facts) != 1 or len(risks) > 1:
            raise ValueError("daily_specialist_input_shape_invalid")
        fact_set = facts[0]
        risk_set = risks[0] if risks else None
        if fact_set.scope_hash != command.scope_hash or (
            risk_set is not None and risk_set.scope_hash != command.scope_hash
        ):
            raise ValueError("daily_specialist_scope_mismatch")
        available = list(fact_set.evidence_refs)
        statements: list[dict[str, object]] = []
        for aggregate in sorted(
            fact_set.aggregates,
            key=lambda item: (
                item.aggregate_id,
                _render_value(item.group_key),
            ),
        ):
            group_identity = specialist_payload_sha256(
                {
                    "aggregate_id": aggregate.aggregate_id,
                    "group_key": aggregate.group_key,
                }
            )[:12]
            group_text = (
                ""
                if aggregate.group_key is None
                else f"（分组 {_render_value(aggregate.group_key)}）"
            )
            statements.append(
                {
                    "statement_id": (
                        f"daily:aggregate:{aggregate.aggregate_id}:{group_identity}"
                    ),
                    "kind": "fact",
                    "text": (
                        f"聚合 {aggregate.aggregate_id}{group_text}："
                        f"{_render_value(aggregate.value)}"
                    ),
                    "evidence_ids": fact_set.evidence_refs,
                    "aggregate_id": aggregate.aggregate_id,
                }
            )
        if risk_set is not None:
            for assessment in risk_set.assessments:
                available.extend(assessment.evidence_ids)
                statements.append(
                    {
                        "statement_id": f"daily:risk:{assessment.assessment_id}",
                        "kind": "risk",
                        "text": f"风险 {assessment.subject_ref}：{assessment.severity}",
                        "evidence_ids": assessment.evidence_ids,
                        "aggregate_id": None,
                    }
                )
            high_risks = tuple(
                item
                for item in risk_set.assessments
                if item.severity in {"high", "critical"}
            )
            if high_risks:
                evidence_ids = tuple(
                    dict.fromkeys(
                        evidence_id
                        for item in high_risks
                        for evidence_id in item.evidence_ids
                    )
                )
                statements.append(
                    {
                        "statement_id": "daily:recommendation:high-risk",
                        "kind": "recommendation",
                        "text": "建议优先处理高风险事项；该建议尚未执行。",
                        "evidence_ids": evidence_ids,
                        "aggregate_id": None,
                    }
                )
        values = {
            "version": "daily-brief.v1",
            "objective_id": command.objective_id,
            "fact_set_hash": fact_set.content_hash,
            "risk_set_hash": None if risk_set is None else risk_set.content_hash,
            "available_evidence_ids": tuple(dict.fromkeys(available)),
            "statements": tuple(statements),
            "as_of_utc": context.clock(),
            "scope_hash": command.scope_hash,
            "provider_call_count": 0,
        }
        values["content_hash"] = specialist_payload_sha256(values)
        result = DailyBriefV1.model_validate(values)
        metrics = {"statements": len(result.statements), "provider_calls": 0}
        for key, value in metrics.items():
            context.metrics(key, value)
        return SpecialistHandlerResultV2(
            payload=result,
            safe_summary="日报摘要已生成",
            metrics=metrics,
        )


def _render_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = ["DailySpecialistV2"]
