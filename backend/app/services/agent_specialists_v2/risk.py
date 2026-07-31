from __future__ import annotations

from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_risk_policy import AuthorizedRiskPolicyV1
from app.services.agent_specialists_v2.base import (
    SpecialistExecutionContextV2,
    SpecialistHandlerResultV2,
)


class RiskSpecialistV2:
    capability_id = "platform.risk.analyse"
    input_schema_version = "objective-specialist-input.v1"
    output_schema_version = "risk-assessment-set.v1"
    allowed_ports = frozenset(
        {"artifact_reader", "risk_policy_reader", "model_gateway", "clock", "metrics"}
    )

    def execute(
        self,
        command: ObjectiveSpecialistInputV1,
        context: SpecialistExecutionContextV2,
    ) -> SpecialistHandlerResultV2:
        if command.capability_id != self.capability_id:
            raise ValueError("risk_specialist_capability_mismatch")
        artifacts = tuple(
            context.artifact_reader(ref) for ref in command.input_artifact_refs
        )
        facts = tuple(
            item for item in artifacts if isinstance(item, StructuredFactSetV1)
        )
        if len(facts) != 1 or context.risk_policy_reader is None:
            raise ValueError("risk_specialist_input_shape_invalid")
        fact_set = facts[0]
        policy = context.risk_policy_reader(command.objective_id)
        if not isinstance(policy, AuthorizedRiskPolicyV1):
            raise TypeError("risk_specialist_policy_invalid")
        if (
            fact_set.scope_hash != command.scope_hash
            or policy.scope_hash != command.scope_hash
        ):
            raise ValueError("risk_specialist_scope_mismatch")
        assessments: list[dict[str, object]] = []
        for record in fact_set.records:
            values = {item.field_id: item.value for item in record.values}
            for rule in policy.rules:
                if _matches(
                    rule.operator, values.get(rule.field_id), rule.expected_value
                ):
                    assessments.append(
                        {
                            "assessment_id": f"risk:{rule.rule_id}:{record.record_id}",
                            "subject_ref": str(record.record_id),
                            "severity": rule.severity,
                            "reason_codes": (rule.reason_code,),
                            "evidence_ids": fact_set.evidence_refs,
                        }
                    )
        assessments.sort(key=lambda item: str(item["assessment_id"]))
        values = {
            "version": "risk-assessment-set.v1",
            "objective_id": command.objective_id,
            "fact_set_hash": fact_set.content_hash,
            "policy_version": policy.policy_version,
            "available_evidence_ids": fact_set.evidence_refs,
            "assessments": tuple(assessments),
            "scope_hash": command.scope_hash,
            "provider_call_count": 0,
        }
        values["content_hash"] = specialist_payload_sha256(values)
        result = RiskAssessmentSetV1.model_validate(values)
        metrics = {
            "assessments": len(result.assessments),
            "provider_calls": 0,
        }
        for key, value in metrics.items():
            context.metrics(key, value)
        return SpecialistHandlerResultV2(
            payload=result,
            safe_summary="风险评估已生成",
            metrics=metrics,
        )


def _matches(operator: str, actual: object, expected: object) -> bool:
    if operator == "exists":
        return actual is not None
    if operator == "eq":
        return actual == expected
    return isinstance(expected, list) and actual in expected


__all__ = ["RiskSpecialistV2"]
