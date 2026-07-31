"""Versioned, fail-closed field policy for Stage12 execution paths."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID


FIELD_POLICY_VERSION = "stage12-field-policy.v2"
_MAX_FIELDS = 4096


class Stage12FieldPolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Stage12MaskingRuleV2:
    field_id: UUID
    mode: Literal["redact"]


@dataclass(frozen=True, slots=True)
class Stage12FieldPolicyV2:
    version: Literal["stage12-field-policy.v2"]
    readable_field_ids: tuple[UUID, ...]
    writable_field_ids: tuple[UUID, ...]
    masking_rules: tuple[Stage12MaskingRuleV2, ...]
    policy_hash: str

    @property
    def redacted_field_ids(self) -> frozenset[UUID]:
        return frozenset(item.field_id for item in self.masking_rules)


def build_stage12_field_policy_v2(
    *,
    readable_field_ids: tuple[UUID, ...],
    writable_field_ids: tuple[UUID, ...],
    redacted_field_ids: tuple[UUID, ...] = (),
) -> dict[str, object]:
    """Build the persisted JSON shape and validate it through the same parser."""

    value: dict[str, object] = {
        "version": FIELD_POLICY_VERSION,
        "readable_field_ids": [str(item) for item in readable_field_ids],
        "writable_field_ids": [str(item) for item in writable_field_ids],
        "masking_rules": [
            {"field_id": str(item), "mode": "redact"}
            for item in redacted_field_ids
        ],
    }
    parse_stage12_field_policy_v2(value)
    return value


def parse_stage12_field_policy_v2(value: object) -> Stage12FieldPolicyV2:
    if not isinstance(value, dict) or set(value) != {
        "version",
        "readable_field_ids",
        "writable_field_ids",
        "masking_rules",
    }:
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_required")
    if value.get("version") != FIELD_POLICY_VERSION:
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_required")
    readable = _uuid_tuple(value.get("readable_field_ids"), "readable")
    writable = _uuid_tuple(value.get("writable_field_ids"), "writable")
    rules = _masking_rules(value.get("masking_rules"))
    readable_set = set(readable)
    writable_set = set(writable)
    redacted_set = {item.field_id for item in rules}
    if not writable_set.issubset(readable_set):
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
    if not redacted_set.issubset(readable_set) or redacted_set & writable_set:
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
    canonical = {
        "version": FIELD_POLICY_VERSION,
        "readable_field_ids": sorted(str(item) for item in readable),
        "writable_field_ids": sorted(str(item) for item in writable),
        "masking_rules": [
            {"field_id": str(item.field_id), "mode": item.mode}
            for item in sorted(rules, key=lambda rule: str(rule.field_id))
        ],
    }
    policy_hash = sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return Stage12FieldPolicyV2(
        version=FIELD_POLICY_VERSION,
        readable_field_ids=readable,
        writable_field_ids=writable,
        masking_rules=rules,
        policy_hash=policy_hash,
    )


def build_stage12_action_scope_hash(
    *,
    schema_scope_hash: str,
    target_record_id: UUID | None,
) -> str:
    if len(schema_scope_hash) != 64 or any(
        item not in "0123456789abcdef" for item in schema_scope_hash
    ):
        raise Stage12FieldPolicyError("stage12_schema_scope_hash_invalid")
    payload = json.dumps(
        {
            "schema_scope_hash": schema_scope_hash,
            "target_record_id": (
                None if target_record_id is None else str(target_record_id)
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _uuid_tuple(value: object, label: str) -> tuple[UUID, ...]:
    if not isinstance(value, list) or len(value) > _MAX_FIELDS:
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
    parsed: list[UUID] = []
    for item in value:
        if not isinstance(item, str) or item != item.strip():
            raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
        try:
            parsed.append(UUID(item))
        except ValueError as exc:
            raise Stage12FieldPolicyError(
                "digital_employee_field_policy_v2_invalid"
            ) from exc
    if len(set(parsed)) != len(parsed):
        raise Stage12FieldPolicyError(
            f"digital_employee_field_policy_v2_{label}_duplicate"
        )
    return tuple(parsed)


def _masking_rules(value: object) -> tuple[Stage12MaskingRuleV2, ...]:
    if not isinstance(value, list) or len(value) > _MAX_FIELDS:
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
    parsed: list[Stage12MaskingRuleV2] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"field_id", "mode"}:
            raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
        raw_id = item.get("field_id")
        if not isinstance(raw_id, str) or item.get("mode") != "redact":
            raise Stage12FieldPolicyError("digital_employee_field_policy_v2_invalid")
        try:
            field_id = UUID(raw_id)
        except ValueError as exc:
            raise Stage12FieldPolicyError(
                "digital_employee_field_policy_v2_invalid"
            ) from exc
        parsed.append(Stage12MaskingRuleV2(field_id=field_id, mode="redact"))
    if len({item.field_id for item in parsed}) != len(parsed):
        raise Stage12FieldPolicyError("digital_employee_field_policy_v2_mask_duplicate")
    return tuple(parsed)


__all__ = [
    "FIELD_POLICY_VERSION",
    "Stage12FieldPolicyError",
    "Stage12FieldPolicyV2",
    "build_stage12_action_scope_hash",
    "build_stage12_field_policy_v2",
    "parse_stage12_field_policy_v2",
]
