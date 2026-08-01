"""Authorized enum-only risk policy for the isolated Stage12 workspace."""

from __future__ import annotations

from app.schemas.agent_task_spec_v2 import AuthorizedSchemaSnapshot
from app.services.agent_risk_policy import (
    AuthorizedRiskPolicyV1,
    risk_policy_sha256,
)


def build_stage12_isolated_risk_policy(
    snapshot: AuthorizedSchemaSnapshot,
) -> AuthorizedRiskPolicyV1:
    rules: list[dict[str, object]] = []
    for table in snapshot.tables:
        for field in table.fields:
            choices = {value.casefold(): value for value in field.choices}
            for value, severity in (
                ("critical", "critical"),
                ("high", "high"),
                ("medium", "medium"),
                ("low", "low"),
            ):
                expected = choices.get(value)
                if expected is not None:
                    rules.append(
                        {
                            "rule_id": f"{table.key}.{field.key}.{value}",
                            "field_id": field.field_id,
                            "operator": "eq",
                            "expected_value": expected,
                            "severity": severity,
                            "reason_code": f"authorized_enum_{value}",
                        }
                    )
            blocked = choices.get("blocked")
            if blocked is not None:
                rules.append(
                    {
                        "rule_id": f"{table.key}.{field.key}.blocked",
                        "field_id": field.field_id,
                        "operator": "eq",
                        "expected_value": blocked,
                        "severity": "high",
                        "reason_code": "authorized_status_blocked",
                    }
                )
    values: dict[str, object] = {
        "version": "authorized-risk-policy.v1",
        "policy_version": "stage12-isolated-enum.v1",
        "rules": tuple(rules),
        "scope_hash": snapshot.scope_hash,
    }
    values["content_hash"] = risk_policy_sha256(values)
    return AuthorizedRiskPolicyV1.model_validate(values)


__all__ = ["build_stage12_isolated_risk_policy"]
