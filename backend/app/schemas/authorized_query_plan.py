"""Strict Stage12-C contracts for authorized deterministic table queries."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_task_spec_v2 import JsonValue, PredicateOperatorV2


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AuthorizedRelationSpec(_StrictFrozenModel):
    relation_id: NonEmptyStr
    link_source_table_id: UUID
    link_field_id: UUID
    link_target_table_id: UUID


class QueryPredicateLeaf(_StrictFrozenModel):
    kind: Literal["leaf"] = "leaf"
    predicate_id: NonEmptyStr
    table_id: UUID
    field_id: UUID
    operator: PredicateOperatorV2
    value: JsonValue


class QueryPredicateGroup(_StrictFrozenModel):
    kind: Literal["group"] = "group"
    predicate_id: NonEmptyStr
    operator: Literal["and", "or"]
    children: tuple["QueryPredicateNode", ...] = Field(min_length=1, max_length=16)


QueryPredicateNode: TypeAlias = QueryPredicateLeaf | QueryPredicateGroup


class QueryTraversalSpec(_StrictFrozenModel):
    traversal_id: NonEmptyStr
    relation_id: NonEmptyStr
    link_source_table_id: UUID
    link_field_id: UUID
    link_target_table_id: UUID
    direction: Literal["forward", "reverse"]
    max_expansion: StrictInt = Field(ge=1, le=1000)


class QueryTraversalPathSpec(_StrictFrozenModel):
    path_id: NonEmptyStr
    target_table_id: UUID
    purpose: Literal["project", "filter", "exists", "aggregate"]
    join_mode: Literal["inner", "left", "semi"]
    steps: tuple[QueryTraversalSpec, ...] = Field(min_length=1, max_length=2)
    predicate: QueryPredicateNode | None = None

    @model_validator(mode="after")
    def validate_join_mode(self) -> "QueryTraversalPathSpec":
        if (self.purpose == "exists") != (self.join_mode == "semi"):
            raise ValueError("authorized_query_traversal_mode_invalid")
        return self


class QueryHavingSpec(_StrictFrozenModel):
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte"]
    value: StrictInt | StrictFloat


class QueryAggregateSpec(_StrictFrozenModel):
    aggregate_id: NonEmptyStr
    output_key: NonEmptyStr
    function: Literal[
        "count",
        "count_non_null",
        "count_distinct",
        "sum",
        "average",
        "minimum",
        "maximum",
    ]
    table_id: UUID
    field_id: UUID | None
    filter_predicate: QueryPredicateNode | None
    group_by_field_ids: tuple[UUID, ...]
    having: QueryHavingSpec | None

    @model_validator(mode="after")
    def validate_input_shape(self) -> "QueryAggregateSpec":
        if self.function == "count" and self.field_id is not None:
            raise ValueError("authorized_query_count_field_invalid")
        if self.function != "count" and self.field_id is None:
            raise ValueError("authorized_query_aggregate_field_required")
        if len(set(self.group_by_field_ids)) != len(self.group_by_field_ids):
            raise ValueError("authorized_query_plan_duplicate")
        return self


class QuerySortSpec(_StrictFrozenModel):
    sort_id: NonEmptyStr
    table_id: UUID | None
    field_id: UUID | None
    aggregate_id: NonEmptyStr | None
    mode: Literal["natural", "field_order"]
    direction: Literal["asc", "desc"]
    nulls: Literal["first", "last"]

    @model_validator(mode="after")
    def validate_target(self) -> "QuerySortSpec":
        field_target = self.table_id is not None and self.field_id is not None
        aggregate_target = self.aggregate_id is not None
        if (
            field_target == aggregate_target
            or (self.table_id is None) != (self.field_id is None)
            or (aggregate_target and self.mode != "natural")
        ):
            raise ValueError("authorized_query_sort_target_invalid")
        return self


class AuthorizedQueryPlanV1(_StrictFrozenModel):
    version: Literal["authorized-query-plan.v1"]
    query_intent_id: NonEmptyStr
    root_table_id: UUID
    authorized_view_ids: tuple[UUID, ...]
    entity_codes: tuple[NonEmptyStr, ...]
    predicate: QueryPredicateNode | None
    traversals: tuple[QueryTraversalSpec, ...]
    projection_field_ids: tuple[UUID, ...]
    group_by_field_ids: tuple[UUID, ...]
    aggregates: tuple[QueryAggregateSpec, ...]
    sort_rules: tuple[QuerySortSpec, ...]
    limit: StrictInt | None = Field(default=None, ge=1, le=5000)
    max_scan_rows: StrictInt = Field(default=5000, ge=1, le=5000)
    max_relation_expansions: StrictInt = Field(default=1000, ge=1, le=1000)
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    traversal_paths: tuple[QueryTraversalPathSpec, ...] = ()

    @model_validator(mode="after")
    def validate_unique_collections(self) -> "AuthorizedQueryPlanV1":
        collections = (
            self.authorized_view_ids,
            self.entity_codes,
            self.projection_field_ids,
            self.group_by_field_ids,
        )
        if any(len(set(items)) != len(items) for items in collections):
            raise ValueError("authorized_query_plan_duplicate")
        aggregate_ids = tuple(item.aggregate_id for item in self.aggregates)
        aggregate_outputs = tuple(item.output_key for item in self.aggregates)
        sort_ids = tuple(item.sort_id for item in self.sort_rules)
        path_ids = tuple(item.path_id for item in self.traversal_paths)
        path_targets = tuple(item.target_table_id for item in self.traversal_paths)
        if (
            len(set(aggregate_ids)) != len(aggregate_ids)
            or len(set(aggregate_outputs)) != len(aggregate_outputs)
            or len(set(sort_ids)) != len(sort_ids)
            or len(set(path_ids)) != len(path_ids)
            or len(set(path_targets)) != len(path_targets)
        ):
            raise ValueError("authorized_query_plan_duplicate")
        if self.traversals and self.traversal_paths:
            raise ValueError("authorized_query_traversal_contract_ambiguous")
        return self


class StructuredFieldValue(_StrictFrozenModel):
    field_id: UUID
    value: JsonValue


class StructuredRecord(_StrictFrozenModel):
    record_id: UUID
    table_id: UUID
    values: tuple[StructuredFieldValue, ...]

    @model_validator(mode="after")
    def validate_values(self) -> "StructuredRecord":
        field_ids = tuple(item.field_id for item in self.values)
        if len(set(field_ids)) != len(field_ids):
            raise ValueError("structured_record_field_duplicate")
        if field_ids != tuple(sorted(field_ids, key=str)):
            raise ValueError("structured_record_field_order_invalid")
        return self


class StructuredGroup(_StrictFrozenModel):
    group_key: tuple[JsonValue, ...]
    record_ids: tuple[UUID, ...]


class StructuredAggregate(_StrictFrozenModel):
    aggregate_id: NonEmptyStr
    group_key: JsonValue = None
    value: JsonValue


class RelationPathProof(_StrictFrozenModel):
    traversal_id: NonEmptyStr
    relation_id: NonEmptyStr
    direction: Literal["forward", "reverse"]
    link_source_table_id: UUID
    link_source_record_id: UUID
    link_field_id: UUID
    link_target_table_id: UUID
    link_target_record_id: UUID


class SourceRecordVersion(_StrictFrozenModel):
    table_id: UUID
    record_id: UUID
    record_version: StrictInt = Field(ge=1)


class StructuredQueryResultV1(_StrictFrozenModel):
    version: Literal["structured-query-result.v1"]
    query_plan_version: Literal["authorized-query-plan.v1"]
    plan_hash: Sha256Hex
    records: tuple[StructuredRecord, ...]
    groups: tuple[StructuredGroup, ...]
    aggregates: tuple[StructuredAggregate, ...]
    relation_paths: tuple[RelationPathProof, ...]
    source_versions: tuple[SourceRecordVersion, ...]
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    scanned_record_count: StrictInt = Field(ge=0, le=5000)
    traversed_edge_count: StrictInt = Field(ge=0, le=1000)
    truncated: StrictBool
    result_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_hash(self) -> "StructuredQueryResultV1":
        expected = structured_query_result_sha256(
            self.model_dump(mode="json", exclude={"result_hash"})
        )
        if self.result_hash != expected:
            raise ValueError("structured_query_result_hash_mismatch")
        return self


class StructuredQueryArtifactV1(_StrictFrozenModel):
    version: Literal["structured-query-artifact.v1"]
    plan: AuthorizedQueryPlanV1
    plan_hash: Sha256Hex
    result: StructuredQueryResultV1

    @model_validator(mode="after")
    def validate_plan_identity(self) -> "StructuredQueryArtifactV1":
        if self.plan_hash != authorized_query_plan_sha256(self.plan):
            raise ValueError("authorized_query_plan_hash_mismatch")
        if self.result.plan_hash != self.plan_hash:
            raise ValueError("structured_query_plan_hash_mismatch")
        return self


def canonical_query_sha256(value: BaseModel | dict[str, object]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def authorized_query_plan_sha256(plan: AuthorizedQueryPlanV1) -> str:
    return canonical_query_sha256(plan)


def structured_query_result_sha256(values: dict[str, object]) -> str:
    return canonical_query_sha256(values)


QueryPredicateGroup.model_rebuild()
