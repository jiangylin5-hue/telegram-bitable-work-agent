from __future__ import annotations

from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictStr,
    model_validator,
)


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AuthorizedRiskRuleV1(_StrictFrozenModel):
    rule_id: NonEmptyStr
    field_id: UUID
    operator: Literal["eq", "in", "exists"]
    expected_value: JsonValue
    severity: Literal["low", "medium", "high", "critical"]
    reason_code: NonEmptyStr

    @model_validator(mode="after")
    def validate_expected_value(self) -> "AuthorizedRiskRuleV1":
        if self.operator == "exists" and self.expected_value is not None:
            raise ValueError("risk_policy_exists_value_invalid")
        if self.operator == "in" and not isinstance(self.expected_value, list):
            raise ValueError("risk_policy_in_value_invalid")
        return self


class AuthorizedRiskPolicyV1(_StrictFrozenModel):
    version: Literal["authorized-risk-policy.v1"]
    policy_version: NonEmptyStr
    rules: tuple[AuthorizedRiskRuleV1, ...]
    scope_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_policy(self) -> "AuthorizedRiskPolicyV1":
        rule_ids = tuple(item.rule_id for item in self.rules)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("risk_policy_rule_duplicate")
        expected = risk_policy_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("risk_policy_hash_mismatch")
        return self


def risk_policy_sha256(value: BaseModel | dict[str, object]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


__all__ = ["AuthorizedRiskPolicyV1", "AuthorizedRiskRuleV1", "risk_policy_sha256"]
