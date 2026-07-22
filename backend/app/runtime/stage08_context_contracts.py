from __future__ import annotations

import json
import math
import re
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)
from typing_extensions import TypeAliasType


JSONScalar: TypeAlias = str | int | float | bool | None
JsonValue = TypeAliasType(
    "JsonValue", JSONScalar | list["JsonValue"] | dict[str, "JsonValue"]
)

ContextIntent = Literal[
    "business_fact", "memory_lookup", "mixed", "general_advice"
]
ContextSourceKind = Literal["table_view", "business_memory", "general_advice"]
EvidenceLabel = Literal[
    "business_data",
    "confirmed_memory",
    "retrieved_material",
    "analysis_from_current_material",
    "general_advice",
]
EvidenceSourceType = Literal["platform_record", "memory_item", "policy_marker"]

_STRICT_CONFIG = ConfigDict(extra="forbid", strict=True, frozen=True)
_EVIDENCE_ID_RE = re.compile(
    r"^(business_data|confirmed_memory|general_advice):[0-9]{2}$"
)
_UUID_FRAGMENT_RE = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])"
)


class ContextBudget(BaseModel):
    model_config = _STRICT_CONFIG

    max_table_records: StrictInt = Field(ge=0, le=20)
    max_memory_items: StrictInt = Field(ge=0, le=12)
    max_evidence_items: StrictInt = Field(ge=1, le=24)
    max_item_chars: StrictInt = Field(ge=128, le=2000)
    max_total_chars: StrictInt = Field(ge=256, le=12000)


class ContextPlanningRequest(BaseModel):
    model_config = _STRICT_CONFIG

    workspace_id: UUID
    employee_id: UUID
    intent: ContextIntent
    view_ids: tuple[UUID, ...] = ()
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None
    allow_general_advice: StrictBool
    budget: ContextBudget

    @model_validator(mode="after")
    def validate_request_shape(self) -> "ContextPlanningRequest":
        if len(self.view_ids) > 3 or len(set(self.view_ids)) != len(self.view_ids):
            raise ValueError("context_view_ids_invalid")
        if self.intent in {"business_fact", "mixed"} and not self.view_ids:
            raise ValueError("context_intent_shape_invalid")
        if self.intent == "general_advice" and (
            self.view_ids
            or self.customer_record_id is not None
            or self.project_record_id is not None
        ):
            raise ValueError("context_intent_shape_invalid")
        if self.intent == "memory_lookup" and self.view_ids:
            raise ValueError("context_intent_shape_invalid")
        return self


class ResolvedBusinessScope(BaseModel):
    model_config = _STRICT_CONFIG

    workspace_id: UUID
    customer_record_id: UUID | None = None
    customer_version: StrictInt | None = Field(default=None, ge=1)
    project_record_id: UUID | None = None
    project_version: StrictInt | None = Field(default=None, ge=1)
    relation_kind: Literal["none", "single_record", "visible_linked_record"]

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "ResolvedBusinessScope":
        customer = self.customer_record_id is not None
        project = self.project_record_id is not None
        if customer != (self.customer_version is not None):
            raise ValueError("context_business_scope_shape_invalid")
        if project != (self.project_version is not None):
            raise ValueError("context_business_scope_shape_invalid")
        expected = (
            "visible_linked_record"
            if customer and project
            else "single_record"
            if customer or project
            else "none"
        )
        if self.relation_kind != expected:
            raise ValueError("context_business_scope_shape_invalid")
        return self


class ContextSourcePlan(BaseModel):
    model_config = _STRICT_CONFIG

    source_kind: ContextSourceKind
    priority: StrictInt = Field(ge=1, le=3)
    view_id: UUID | None = None
    source_version: StrictInt | None = Field(default=None, ge=1)
    max_items: StrictInt = Field(ge=0, le=20)
    reason_code: Literal[
        "business_fact_requested",
        "memory_requested",
        "general_advice_requested",
        "general_advice_fallback_allowed",
    ]

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ContextSourcePlan":
        expected_metadata = {
            "table_view": {(1, "business_fact_requested")},
            "business_memory": {(2, "memory_requested")},
            "general_advice": {
                (1, "general_advice_requested"),
                (3, "general_advice_fallback_allowed"),
            },
        }
        if (self.priority, self.reason_code) not in expected_metadata[self.source_kind]:
            raise ValueError("context_source_reason_mismatch")
        if self.source_kind == "table_view":
            if self.view_id is None or self.source_version is None:
                raise ValueError("context_source_shape_invalid")
        elif self.source_kind == "business_memory":
            if self.view_id is not None or self.source_version is not None:
                raise ValueError("context_source_shape_invalid")
            if self.max_items > 12:
                raise ValueError("context_source_shape_invalid")
        else:
            if (
                self.view_id is not None
                or self.source_version is not None
                or self.max_items != 1
            ):
                raise ValueError("context_source_shape_invalid")
        return self


class ContextPlan(BaseModel):
    model_config = _STRICT_CONFIG

    contract_version: Literal["stage08-context-plan.v1"]
    workspace_id: UUID
    employee_id: UUID
    actor_user_id: StrictStr
    intent: ContextIntent
    business_scope: ResolvedBusinessScope
    budget: ContextBudget
    sources: tuple[ContextSourcePlan, ...]

    @model_validator(mode="after")
    def validate_plan_shape(self) -> "ContextPlan":
        if not self.actor_user_id:
            raise ValueError("context_actor_invalid")
        if self.business_scope.workspace_id != self.workspace_id:
            raise ValueError("context_business_scope_invalid")
        kinds = [source.source_kind for source in self.sources]
        if kinds.count("business_memory") > 1 or kinds.count("general_advice") > 1:
            raise ValueError("context_plan_sources_invalid")
        table_views = [source.view_id for source in self.sources if source.view_id]
        if len(table_views) > 3 or len(set(table_views)) != len(table_views):
            raise ValueError("context_plan_sources_invalid")
        if kinds != sorted(kinds, key={"table_view": 0, "business_memory": 1, "general_advice": 2}.get):
            raise ValueError("context_plan_sources_invalid")
        kind_set = set(kinds)
        if self.intent == "business_fact" and (
            not table_views or not kind_set.issubset(
                {"table_view", "business_memory", "general_advice"}
            )
        ):
            raise ValueError("context_plan_sources_invalid")
        if self.intent == "memory_lookup" and (
            "business_memory" not in kind_set
            or not kind_set.issubset({"business_memory", "general_advice"})
        ):
            raise ValueError("context_plan_sources_invalid")
        if self.intent == "mixed" and (
            not table_views
            or "business_memory" not in kind_set
            or not kind_set.issubset(
                {"table_view", "business_memory", "general_advice"}
            )
        ):
            raise ValueError("context_plan_sources_invalid")
        if self.intent == "general_advice" and kinds != ["general_advice"]:
            raise ValueError("context_plan_sources_invalid")
        advice = next(
            (source for source in self.sources if source.source_kind == "general_advice"),
            None,
        )
        if advice is not None and (
            (self.intent == "general_advice" and advice.reason_code != "general_advice_requested")
            or (
                self.intent != "general_advice"
                and advice.reason_code != "general_advice_fallback_allowed"
            )
        ):
            raise ValueError("context_plan_sources_invalid")
        if sum(
            source.max_items
            for source in self.sources
            if source.source_kind == "table_view"
        ) > self.budget.max_table_records or sum(
            source.max_items
            for source in self.sources
            if source.source_kind == "business_memory"
        ) > self.budget.max_memory_items:
            raise ValueError("context_plan_budget_invalid")
        return self


class EvidenceScope(BaseModel):
    model_config = _STRICT_CONFIG

    workspace_id: UUID
    base_id: UUID | None = None
    table_id: UUID | None = None
    view_id: UUID | None = None
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None


class EvidenceVersion(BaseModel):
    model_config = _STRICT_CONFIG

    kind: Literal["record", "memory", "contract"]
    value: StrictInt = Field(ge=1)


class EvidenceItem(BaseModel):
    model_config = _STRICT_CONFIG

    evidence_id: StrictStr
    label: EvidenceLabel
    source_type: EvidenceSourceType
    scope: EvidenceScope
    version: EvidenceVersion
    source_version: StrictInt | None = Field(default=None, ge=1)
    content: dict[str, JsonValue]
    truncated: StrictBool
    truncated_paths: tuple[StrictStr, ...]

    @model_validator(mode="after")
    def validate_evidence(self) -> "EvidenceItem":
        pair = {
            "platform_record": ("business_data", "record"),
            "memory_item": ("confirmed_memory", "memory"),
            "policy_marker": ("general_advice", "contract"),
        }[self.source_type]
        if self.label != pair[0]:
            raise ValueError("context_evidence_label_mismatch")
        if self.version.kind != pair[1]:
            raise ValueError("context_evidence_version_mismatch")
        if (self.source_type == "platform_record") != (
            self.source_version is not None
        ):
            raise ValueError("context_evidence_version_mismatch")
        if not _EVIDENCE_ID_RE.fullmatch(self.evidence_id):
            raise ValueError("context_evidence_id_invalid")
        if not self.evidence_id.startswith(f"{self.label}:"):
            raise ValueError("context_evidence_id_invalid")
        if self.truncated != bool(self.truncated_paths):
            raise ValueError("context_evidence_truncation_invalid")
        _validate_json_value(self.content)
        _validate_evidence_content(self.content)
        return self


class ContextOmission(BaseModel):
    model_config = _STRICT_CONFIG

    source_kind: ContextSourceKind
    reason_code: Literal[
        "authority_changed",
        "business_scope_changed",
        "view_version_changed",
        "source_revalidation_failed",
        "scope_mismatch",
        "group_source_deferred",
        "source_limit_reached",
        "item_budget_exceeded",
        "total_budget_exceeded",
    ]
    count: StrictInt = Field(ge=1)


class ContextBudgetUsage(BaseModel):
    model_config = _STRICT_CONFIG

    table_records_considered: StrictInt = Field(ge=0)
    table_records_selected: StrictInt = Field(ge=0)
    memory_items_considered: StrictInt = Field(ge=0)
    memory_items_selected: StrictInt = Field(ge=0)
    evidence_items: StrictInt = Field(ge=0, le=24)
    content_chars: StrictInt = Field(ge=0, le=12000)
    truncated_items: StrictInt = Field(ge=0)
    omitted_items: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def validate_usage(self) -> "ContextBudgetUsage":
        if (
            self.table_records_selected > self.table_records_considered
            or self.memory_items_selected > self.memory_items_considered
            or self.truncated_items > self.evidence_items
        ):
            raise ValueError("context_pack_usage_invalid")
        return self


class ContextPack(BaseModel):
    model_config = _STRICT_CONFIG

    plan: ContextPlan
    status: Literal["internal_evidence", "general_advice_only", "no_evidence"]
    evidence: tuple[EvidenceItem, ...]
    omissions: tuple[ContextOmission, ...]
    usage: ContextBudgetUsage

    @model_validator(mode="after")
    def validate_pack(self) -> "ContextPack":
        labels = [item.label for item in self.evidence]
        table_sources = {
            source.view_id: source
            for source in self.plan.sources
            if source.source_kind == "table_view"
        }
        memory_source = next(
            (
                source
                for source in self.plan.sources
                if source.source_kind == "business_memory"
            ),
            None,
        )
        advice_source = next(
            (
                source
                for source in self.plan.sources
                if source.source_kind == "general_advice"
            ),
            None,
        )
        table_counts: dict[UUID, int] = {}
        memory_count = 0
        for item in self.evidence:
            if item.scope.workspace_id != self.plan.workspace_id:
                raise ValueError("context_pack_source_invalid")
            if item.source_type == "platform_record":
                source = table_sources.get(item.scope.view_id)
                if (
                    source is None
                    or item.scope.base_id is None
                    or item.scope.table_id is None
                    or item.scope.view_id is None
                    or item.source_version != source.source_version
                    or item.scope.customer_record_id
                    != self.plan.business_scope.customer_record_id
                    or item.scope.project_record_id
                    != self.plan.business_scope.project_record_id
                ):
                    raise ValueError("context_pack_source_invalid")
                table_counts[item.scope.view_id] = (
                    table_counts.get(item.scope.view_id, 0) + 1
                )
                if table_counts[item.scope.view_id] > source.max_items:
                    raise ValueError("context_pack_source_invalid")
            elif item.source_type == "memory_item":
                memory_count += 1
                if (
                    memory_source is None
                    or memory_count > memory_source.max_items
                    or item.scope.customer_record_id
                    != self.plan.business_scope.customer_record_id
                    or item.scope.project_record_id
                    != self.plan.business_scope.project_record_id
                ):
                    raise ValueError("context_pack_source_invalid")
            elif item.source_type == "policy_marker":
                scope = item.scope.model_dump(mode="python")
                if (
                    advice_source is None
                    or any(
                        value is not None
                        for key, value in scope.items()
                        if key != "workspace_id"
                    )
                    or item.version.value != 1
                    or item.content != {"internal_evidence": False}
                    or item.truncated
                    or item.truncated_paths
                ):
                    raise ValueError("context_pack_source_invalid")
            else:
                raise ValueError("context_pack_source_invalid")
        if any(
            item.evidence_id != f"{item.label}:{index:02d}"
            for index, item in enumerate(self.evidence, start=1)
        ):
            raise ValueError("context_pack_source_invalid")
        if "general_advice" in labels and len(labels) != 1:
            raise ValueError("context_pack_source_invalid")
        expected_status = (
            "internal_evidence"
            if any(label != "general_advice" for label in labels)
            else "general_advice_only"
            if labels
            else "no_evidence"
        )
        content_chars = sum(
            len(
                json.dumps(
                    item.content,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
            )
            for item in self.evidence
        )
        table_selected = sum(
            item.source_type == "platform_record" for item in self.evidence
        )
        memory_selected = sum(
            item.source_type == "memory_item" for item in self.evidence
        )
        truncated_items = sum(item.truncated for item in self.evidence)
        if (
            self.status != expected_status
            or self.usage.table_records_selected != table_selected
            or self.usage.memory_items_selected != memory_selected
            or self.usage.evidence_items != len(self.evidence)
            or self.usage.content_chars != content_chars
            or any(
                len(
                    json.dumps(
                        item.content,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                )
                > self.plan.budget.max_item_chars
                for item in self.evidence
            )
            or self.usage.truncated_items != truncated_items
            or self.usage.content_chars > self.plan.budget.max_total_chars
            or len(self.evidence) > self.plan.budget.max_evidence_items
            or self.usage.omitted_items != sum(item.count for item in self.omissions)
        ):
            raise ValueError("context_pack_usage_invalid")
        return self


def validate_context_request(request: ContextPlanningRequest) -> ContextPlanningRequest:
    return ContextPlanningRequest.model_validate(request.model_dump(mode="python"))


def validate_context_plan(plan: ContextPlan) -> ContextPlan:
    return ContextPlan.model_validate(plan.model_dump(mode="python"))


def validate_context_pack(pack: ContextPack) -> ContextPack:
    return ContextPack.model_validate(pack.model_dump(mode="python"))


def _validate_json_value(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("context_json_value_invalid")
    if isinstance(value, dict):
        for nested in value.values():
            _validate_json_value(nested)
    elif isinstance(value, list):
        for nested in value:
            _validate_json_value(nested)


def _validate_evidence_content(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if (
                _is_sensitive_metadata_key(key)
                or _is_internal_identifier_key(key)
                or _UUID_FRAGMENT_RE.search(key)
            ):
                raise ValueError("context_evidence_content_forbidden")
            _validate_evidence_content(nested)
    elif isinstance(value, list):
        for nested in value:
            _validate_evidence_content(nested)
    elif isinstance(value, str) and _UUID_FRAGMENT_RE.search(value):
        raise ValueError("context_evidence_content_forbidden")


def _is_sensitive_metadata_key(key: str) -> bool:
    canonical = re.sub(r"[^a-z0-9]", "", key.casefold())
    return (
        "token" in canonical
        or "permission" in canonical
        or "identity" in canonical
        or (
            canonical.startswith("source")
            and ("ref" in canonical or canonical.endswith("id"))
        )
        or canonical in {
            "sourceref",
            "sourcerefs",
            "sourceid",
            "actoruserid",
            "fieldpolicy",
            "accessibletables",
            "accessibleviews",
            "groupchatref",
            "bindingid",
            "audit",
            "ticket",
        }
    )


def _is_internal_identifier_key(key: str) -> bool:
    canonical = re.sub(r"[^a-z0-9]", "", key.casefold())
    return canonical in {"id", "recordid", "memoryid"}
