"""Deterministic Stage12-B TaskSpec V2 planner.

The module produces a planning artifact only.  It never dispatches a command,
executes a query, resolves an unauthorized record, or persists an action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from app.schemas.agent_task_spec_v2 import (
    ActionAssignment,
    ActionSlotV1,
    ActionTargetSelector,
    AuthorizedEntitySpec,
    AuthorizedFieldSpec,
    BoundPredicate,
    ConflictAssignment,
    ConflictGroupV1,
    DependencyEdgeV2,
    PlannerCostEstimate,
    PlannerRequestV2,
    QueryAggregationIntentV1,
    QueryExecutionIntentV1,
    QueryHavingIntentV1,
    QueryIntentSpec,
    QueryJoinIntentV1,
    QueryPredicateExpressionV1,
    QueryPredicateGroupIntentV1,
    QueryPredicateLeafIntentV1,
    QuerySortIntentV1,
    SourceSpan,
    TaskObjectiveV2,
    TaskOutputSpec,
    TaskSpecArtifact,
    TaskSpecV2,
    task_spec_sha256,
)
from app.services.agent_query_lexical import (
    LexicalClause,
    LexicalQuery,
    LexicalToken,
    extract_lexical_query,
)
from app.services.agent_schema_binding import (
    AmbiguousBinding,
    BoundEntityMention,
    BoundEnumValue,
    BoundFieldMention,
    BoundTableMention,
    SchemaBindingResult,
    bind_lexical_query,
)


@dataclass(frozen=True, slots=True)
class PlannerAmbiguityRequest:
    mention_id: str
    candidate_ids: tuple[str, ...]
    candidate_labels: tuple[str, ...]
    allowed_selection_count: int


@dataclass(frozen=True, slots=True)
class PlannerAmbiguityDecision:
    mention_id: str
    selected_candidate_ids: tuple[str, ...]


class PlannerAmbiguityResolver(Protocol):
    def __call__(
        self, request: PlannerAmbiguityRequest
    ) -> PlannerAmbiguityDecision: ...


@dataclass(frozen=True, slots=True)
class _EntityOccurrence:
    code: str
    table_id: UUID | None
    resolved: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class _ActionCandidate:
    action_kind: str
    span: SourceSpan
    source_entities: tuple[_EntityOccurrence, ...]
    deadline_start_utc: datetime | None
    deadline_end_utc: datetime | None


def plan_task_v2(
    request: PlannerRequestV2,
    *,
    ambiguity_resolver: PlannerAmbiguityResolver | None = None,
) -> TaskSpecArtifact:
    lexical = extract_lexical_query(
        request.query,
        clock=request.clock,
        timezone_name=request.timezone_name,
    )
    binding = bind_lexical_query(
        lexical,
        request.authorized_schema,
        authorized_entities=request.authorized_entities,
    )
    binding_ambiguity_count = len(binding.ambiguous_candidates)
    provider_calls, binding, unresolved_ambiguity = _resolve_ambiguities(
        binding,
        request=request,
        ambiguity_resolver=ambiguity_resolver,
    )
    entities = _entity_occurrences(lexical, binding, request.authorized_entities)
    candidates = _action_candidates(request, lexical, entities)
    action_spans = _action_value_spans(request, lexical, candidates)
    if unresolved_ambiguity:
        unresolved_ambiguity = any(
            not _span_overlaps_any(item.source_span, action_spans)
            for item in binding.ambiguous_candidates
        )
    query_intent = _query_intent(
        request,
        lexical,
        binding,
        entities,
        action_spans=action_spans,
    )
    split_aggregate_and_risk_codes = (
        re.search(
            r"汇总.{0,24}?(?:数量|计数).{0,24}?列出.{0,24}?风险编号",
            request.query,
        )
        is not None
    )
    if split_aggregate_and_risk_codes and query_intent.execution_spec is not None:
        risk_table = next(
            (item for item in request.authorized_schema.tables if item.key == "risks"),
            None,
        )
        if risk_table is not None:
            risk_field_ids = {item.field_id for item in risk_table.fields}
            first_execution = query_intent.execution_spec.model_copy(
                update={
                    "join_intents": tuple(
                        item
                        for item in query_intent.execution_spec.join_intents
                        if item.target_table_id != risk_table.table_id
                    ),
                    "projection_field_ids": tuple(
                        field_id
                        for field_id in query_intent.execution_spec.projection_field_ids
                        if field_id not in risk_field_ids
                    ),
                }
            )
            query_intent = query_intent.model_copy(
                update={"execution_spec": first_execution}
            )
    query_intents = [query_intent]
    if split_aggregate_and_risk_codes:
        risk_execution, risk_root_table_id = _risk_code_projection_execution(
            request,
            binding,
        )
        query_intents.append(
            QueryIntentSpec.model_validate(
                {
                    **query_intent.model_dump(mode="python"),
                    "query_intent_id": "query-02",
                    "root_table_id": risk_root_table_id,
                    "predicates": (),
                    "aggregation_kinds": (),
                    "group_by_field_ids": (),
                    "sort_field_ids": (),
                    "limit": None,
                    "execution_spec": risk_execution,
                }
            )
        )
    objectives: list[TaskObjectiveV2] = []
    edges: list[DependencyEdgeV2] = []
    slots: list[ActionSlotV1] = []
    conflicts: list[ConflictGroupV1] = []

    query_span = SourceSpan(start=0, end=len(request.query), text=request.query)
    restricted_request = _is_restricted_request(request.query)
    outside_scope_request = _is_outside_scope_request(request.query)
    restricted_write_without_read = (
        restricted_request
        and bool(candidates)
        and not _has_explicit_read_intent(request.query)
    )
    risk_analysis_requested = _requires_independent_risk_analysis(
        request.query,
        lexical,
        action_spans=action_spans,
    )
    restricted_objective: TaskObjectiveV2 | None = None

    if restricted_request and (outside_scope_request or restricted_write_without_read):
        restricted_objective = _restricted_objective(
            objective_id=f"obj-{len(objectives) + 1:02d}",
            entities=_ordered_codes(entities),
            span=query_span,
        )
        objectives.append(restricted_objective)

    fact_outcome = (
        "denied"
        if outside_scope_request
        else ("clarification_required" if unresolved_ambiguity else "planned")
    )
    fact_reason = (
        "outside_workspace_scope_denied"
        if outside_scope_request
        else ("schema_binding_ambiguous" if unresolved_ambiguity else None)
    )
    fact: TaskObjectiveV2 | None = None
    if not restricted_write_without_read:
        fact = _objective(
            objective_id=f"obj-{len(objectives) + 1:02d}",
            kind="fact_query",
            entities=_ordered_codes(entities),
            query_ref=f"query-intent:{query_intent.query_intent_id}",
            output=(
                "unfinished_work_item_aggregates"
                if split_aggregate_and_risk_codes
                else "structured_facts"
            ),
            outcome=fact_outcome,
            reason=fact_reason,
            spans=(query_span,),
        )
        objectives.append(fact)
        if outside_scope_request and restricted_objective is not None:
            edges.append(_edge(restricted_objective.objective_id, fact.objective_id))
    if split_aggregate_and_risk_codes and fact is not None:
        objectives.append(
            _objective(
                objective_id=f"obj-{len(objectives) + 1:02d}",
                kind="fact_query",
                entities=_ordered_codes(entities),
                query_ref="query-intent:query-02",
                output="project_risk_codes",
                outcome=fact_outcome,
                reason=fact_reason,
                spans=(query_span,),
            )
        )

    risk_objective: TaskObjectiveV2 | None = None
    if risk_analysis_requested:
        risk = _objective(
            objective_id=f"obj-{len(objectives) + 1:02d}",
            kind="risk_analysis",
            entities=_ordered_codes(entities),
            query_ref=f"query-intent:{query_intent.query_intent_id}",
            output="risk_assessments",
            outcome="denied" if outside_scope_request else "planned",
            reason=(
                "outside_workspace_scope_denied" if outside_scope_request else None
            ),
            spans=_token_spans(lexical, "risk_intent"),
        )
        objectives.append(risk)
        risk_objective = risk
        risk_dependency = (
            restricted_objective
            if outside_scope_request
            else fact or restricted_objective
        )
        if risk_dependency is not None:
            edges.append(
                _edge(
                    risk_dependency.objective_id,
                    risk.objective_id,
                    required=re.search(r"可选风险分析", request.query) is None,
                )
            )

    if re.search(
        r"日报|简报|日结|今日总结|运营总结|周报", request.query, re.IGNORECASE
    ):
        daily = _objective(
            objective_id=f"obj-{len(objectives) + 1:02d}",
            kind="daily_summary",
            entities=_ordered_codes(entities),
            query_ref=f"query-intent:{query_intent.query_intent_id}",
            output="daily_brief",
            outcome="planned",
            reason=None,
            spans=(query_span,),
        )
        objectives.append(daily)
        if fact is not None:
            edges.append(_edge(fact.objective_id, daily.objective_id))
        if risk_objective is not None and re.search(
            r"事实.{0,12}?风险.{0,12}?(?:建议|下一步)",
            request.query,
        ):
            edges.append(_edge(risk_objective.objective_id, daily.objective_id))

    if restricted_request and restricted_objective is None:
        restricted_objective = _restricted_objective(
            objective_id=f"obj-{len(objectives) + 1:02d}",
            entities=_ordered_codes(entities),
            span=query_span,
        )
        objectives.append(restricted_objective)

    if len(candidates) > 8:
        raise ValueError("task_planner_action_slot_limit")
    for candidate in candidates:
        expanded = _expand_separate_candidate(candidate, request.query)
        conflict = _conflict_for_update(request, lexical, candidate)
        deferred_target_resolution = (
            candidate.action_kind == "task.create"
            and re.search(r"最高.{0,8}?风险项", candidate.span.text) is not None
        )
        conflict_objective: TaskObjectiveV2 | None = None
        if conflict is not None:
            conflict_id = f"conflict-{len(conflicts) + 1:02d}"
            slot_ids = tuple(
                f"slot-{len(slots) + index:02d}"
                for index in range(1, len(expanded) + 1)
            )
            conflict = conflict.model_copy(
                update={"conflict_group_id": conflict_id, "slot_ids": slot_ids}
            )
            conflicts.append(conflict)
            conflict_objective = _objective(
                objective_id=f"obj-{len(objectives) + 1:02d}",
                kind="conflict_resolution",
                entities=tuple(item.code for item in candidate.source_entities),
                query_ref=None,
                output="conflict_resolution",
                outcome="denied",
                reason="conflicting_assignments",
                spans=(candidate.span,),
            )
            objectives.append(conflict_objective)
            if fact is not None:
                edges.append(_edge(fact.objective_id, conflict_objective.objective_id))
        elif deferred_target_resolution:
            conflict_objective = _objective(
                objective_id=f"obj-{len(objectives) + 1:02d}",
                kind="conflict_resolution",
                entities=tuple(item.code for item in candidate.source_entities),
                query_ref=f"query-intent:{query_intent.query_intent_id}",
                output="conflict_resolution",
                outcome="planned",
                reason=None,
                spans=(candidate.span,),
            )
            objectives.append(conflict_objective)
            conflict_dependency = risk_objective or fact
            if conflict_dependency is not None:
                edges.append(
                    _edge(
                        conflict_dependency.objective_id,
                        conflict_objective.objective_id,
                    )
                )

        objective_kind = {
            "record.create": "record_change",
            "record.update": "record_change",
            "task.create": "task_creation",
            "reminder.request": "reminder_request",
        }[candidate.action_kind]
        action_objective = _objective(
            objective_id=f"obj-{len(objectives) + 1:02d}",
            kind=objective_kind,
            entities=tuple(item.code for item in candidate.source_entities),
            query_ref=None,
            output="controlled_action_proposal",
            outcome="denied" if conflict is not None else "planned",
            reason="conflicting_assignments" if conflict is not None else None,
            spans=(candidate.span,),
        )
        action_objective_index = len(objectives)
        objectives.append(action_objective)
        action_dependency = (
            restricted_objective
            if outside_scope_request
            else conflict_objective or fact or restricted_objective
        )
        if action_dependency is not None:
            edges.append(
                _edge(
                    action_dependency.objective_id,
                    action_objective.objective_id,
                )
            )
        logical_slots: list[ActionSlotV1] = []
        for action in expanded:
            slot = _build_action_slot(
                request,
                lexical,
                binding,
                action,
                query_spec_ref=f"query-intent:{query_intent.query_intent_id}",
                query_root_table_id=query_intent.root_table_id,
                slot_id=f"slot-{len(slots) + 1:02d}",
                objective_id=action_objective.objective_id,
                conflict_group_id=(
                    None if conflict is None else conflict.conflict_group_id
                ),
            )
            slots.append(slot)
            logical_slots.append(slot)
        slot_outcomes = {slot.planning_outcome for slot in logical_slots}
        if slot_outcomes != {action_objective.planning_outcome}:
            if "planned" in slot_outcomes:
                outcome, reason = "planned", None
            elif slot_outcomes == {"denied"}:
                outcome = "denied"
                reasons = {slot.denial_reason for slot in logical_slots}
                reason = reasons.pop() if len(reasons) == 1 else "action_denied"
            else:
                outcome, reason = "clarification_required", "action_slot_unresolved"
            objectives[action_objective_index] = action_objective.model_copy(
                update={
                    "planning_outcome": outcome,
                    "denial_reason": reason,
                }
            )

    if len(objectives) > 8:
        raise ValueError("task_planner_objective_limit")
    cost = PlannerCostEstimate(
        lexical_token_count=len(lexical.tokens),
        bound_field_count=len({item.field_id for item in binding.bound_fields}),
        objective_count=len(objectives),
        action_slot_count=len(slots),
        ambiguity_count=binding_ambiguity_count,
        planned_provider_calls=provider_calls,
    )
    spec = TaskSpecV2(
        version="task-spec.v2",
        authorized_schema_hash=request.authorized_schema.schema_hash,
        query_intents=tuple(query_intents),
        objectives=tuple(objectives),
        dependency_edges=tuple(edges),
        action_slots=tuple(slots),
        conflict_groups=tuple(conflicts),
        output=TaskOutputSpec(
            language="zh-Hans",
            format="conversational",
            include_evidence=True,
        ),
        cost=cost,
        provider_call_count=provider_calls,
    )
    content_hash = task_spec_sha256(spec)
    return TaskSpecArtifact(
        version="task-spec-artifact.v1",
        task_spec=spec,
        content_hash=content_hash,
        storage_ref=f"task-spec:sha256:{content_hash}",
    )


def _is_restricted_request(query: str) -> bool:
    return (
        re.search(
            r"密钥|密码|token|secret|隐藏字段|internal_note|无权编辑|workspace\s*之外",
            query,
            re.IGNORECASE,
        )
        is not None
    )


def _is_outside_scope_request(query: str) -> bool:
    return re.search(r"workspace\s*之外", query, re.IGNORECASE) is not None


def _has_explicit_read_intent(query: str) -> bool:
    return (
        re.search(
            r"查询|列出|查看|显示|读取|汇总|统计|找出|比较|评估|分析|日报|简报|周报",
            query,
            re.IGNORECASE,
        )
        is not None
    )


def _requires_independent_risk_analysis(
    query: str,
    lexical: LexicalQuery,
    *,
    action_spans: tuple[SourceSpan, ...],
) -> bool:
    if (
        re.search(
            r"(?:提议|调整|修改|更新|改为).{0,64}(?:解释|说明).{0,8}风险依据",
            query,
        )
        is not None
    ):
        return False
    risk_tokens = tuple(
        token for token in lexical.tokens if token.kind == "risk_intent"
    )
    if any(
        not _span_overlaps_any(token.source_span, action_spans) for token in risk_tokens
    ):
        return True
    if "风险" not in query:
        return False
    analytical_pattern = re.search(
        r"(?:按|依).{0,8}?风险.{0,8}?(?:排序|分组|汇总)"
        r"|(?:汇总|统计).{0,12}?风险"
        r"|风险.{0,12}?(?:数量|计数|分组|汇总)"
        r"|找出.{0,32}?(?:风险.{0,16}?(?:但|且)|(?:但|且).{0,16}?风险)"
        r"|查询.{0,24}?风险",
        query,
        re.IGNORECASE,
    )
    if analytical_pattern is None:
        return False
    return not any(
        span.start <= analytical_pattern.start() < span.end for span in action_spans
    )


def _restricted_objective(
    *,
    objective_id: str,
    entities: tuple[str, ...],
    span: SourceSpan,
) -> TaskObjectiveV2:
    return _objective(
        objective_id=objective_id,
        kind="restricted_request",
        entities=entities,
        query_ref=None,
        output="objective_denial",
        outcome="denied",
        reason="field_not_in_authorized_schema",
        spans=(span,),
    )


def _resolve_ambiguities(
    binding: SchemaBindingResult,
    *,
    request: PlannerRequestV2,
    ambiguity_resolver: PlannerAmbiguityResolver | None,
) -> tuple[int, SchemaBindingResult, bool]:
    if not binding.ambiguous_candidates:
        return 0, binding, False
    if ambiguity_resolver is None:
        return 0, binding, True
    if len(binding.ambiguous_candidates) > 4:
        raise ValueError("task_planner_provider_call_limit")
    selected: list[tuple[AmbiguousBinding, str]] = []
    for index, ambiguity in enumerate(binding.ambiguous_candidates, start=1):
        resolution_request = PlannerAmbiguityRequest(
            mention_id=f"mention-{index:02d}",
            candidate_ids=ambiguity.candidate_ids,
            candidate_labels=ambiguity.candidate_labels,
            allowed_selection_count=1,
        )
        decision = ambiguity_resolver(resolution_request)
        if (
            decision.mention_id != resolution_request.mention_id
            or not decision.selected_candidate_ids
            or len(decision.selected_candidate_ids)
            > resolution_request.allowed_selection_count
            or any(
                item not in resolution_request.candidate_ids
                for item in decision.selected_candidate_ids
            )
        ):
            raise ValueError("task_planner_provider_decision_invalid")
        selected.append((ambiguity, decision.selected_candidate_ids[0]))
    return (
        len(binding.ambiguous_candidates),
        _apply_ambiguity_selections(binding, request=request, selected=selected),
        False,
    )


def _apply_ambiguity_selections(
    binding: SchemaBindingResult,
    *,
    request: PlannerRequestV2,
    selected: list[tuple[AmbiguousBinding, str]],
) -> SchemaBindingResult:
    tables_by_id = {
        str(table.table_id): table for table in request.authorized_schema.tables
    }
    fields_by_id = {
        str(field.field_id): field
        for table in request.authorized_schema.tables
        for field in table.fields
    }
    entities_by_id = {
        str(entity.entity_id): entity for entity in request.authorized_entities
    }
    bound_tables = list(binding.bound_tables)
    bound_fields = list(binding.bound_fields)
    bound_entities = list(binding.bound_entities)
    bound_enums = list(binding.bound_enum_values)
    for ambiguity, candidate_id in selected:
        if ambiguity.kind == "table":
            table = tables_by_id[candidate_id]
            bound_tables.append(
                BoundTableMention(
                    table_id=table.table_id,
                    table_key=table.key,
                    mention=ambiguity.mention,
                    source_span=ambiguity.source_span,
                )
            )
        elif ambiguity.kind == "field":
            field = fields_by_id[candidate_id]
            bound_fields.append(
                BoundFieldMention(
                    table_id=field.table_id,
                    field_id=field.field_id,
                    field_key=field.key,
                    mention=ambiguity.mention,
                    match_kind="resolved_ambiguity",
                    source_span=ambiguity.source_span,
                )
            )
        elif ambiguity.kind == "entity":
            entity = entities_by_id[candidate_id]
            bound_entities.append(
                BoundEntityMention(
                    entity_id=entity.entity_id,
                    table_id=entity.table_id,
                    code=entity.code,
                    mention=ambiguity.mention,
                    match_kind="resolved_ambiguity",
                    source_span=ambiguity.source_span,
                )
            )
        elif ambiguity.kind == "enum":
            field = fields_by_id[candidate_id]
            label = ambiguity.candidate_labels[
                ambiguity.candidate_ids.index(candidate_id)
            ]
            bound_enums.append(
                BoundEnumValue(
                    table_id=field.table_id,
                    field_id=field.field_id,
                    field_key=field.key,
                    value=label.split(":", 1)[-1],
                    source_span=ambiguity.source_span,
                )
            )
        else:
            raise ValueError("task_planner_provider_decision_invalid")
    return SchemaBindingResult(
        schema_hash=binding.schema_hash,
        bound_tables=tuple(bound_tables),
        bound_fields=tuple(bound_fields),
        bound_entities=tuple(bound_entities),
        bound_enum_values=tuple(bound_enums),
        ambiguous_candidates=(),
        unresolved_mentions=binding.unresolved_mentions,
    )


def _query_intent(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    binding: SchemaBindingResult,
    entities: tuple[_EntityOccurrence, ...],
    *,
    action_spans: tuple[SourceSpan, ...],
) -> QueryIntentSpec:
    entity_table_ids = {item.table_id for item in entities if item.table_id is not None}
    exact_code_table_ids = {
        item.table_id
        for item in entities
        if item.table_id is not None
        and item.span.text.casefold() == item.code.casefold()
    }
    explicit_table_ids = {
        item.table_id
        for item in binding.bound_tables
        if not _span_overlaps_any(item.source_span, action_spans)
    }
    field_table_ids = {
        item.table_id
        for item in binding.bound_fields
        if not _span_overlaps_any(item.source_span, action_spans)
    }
    predicates = list(_semantic_predicates(request, lexical, action_spans=action_spans))
    predicates.extend(
        _entity_identity_predicates(
            request,
            lexical,
            entities,
            action_spans=action_spans,
        )
    )
    semantic_spans = tuple(item.source_span for item in predicates)
    enum_groups: dict[UUID, list[object]] = {}
    for item in binding.bound_enum_values:
        if _span_overlaps_any(item.source_span, (*action_spans, *semantic_spans)):
            continue
        enum_groups.setdefault(item.field_id, []).append(item)
    fields_by_id = {
        field.field_id: field
        for table in request.authorized_schema.tables
        for field in table.fields
    }
    for field_id, values in enum_groups.items():
        field = fields_by_id[field_id]
        ordered_values = tuple(dict.fromkeys(item.value for item in values))
        predicates.append(
            BoundPredicate(
                table_id=field.table_id,
                field_id=field.field_id,
                field_key=field.key,
                field_type=field.field_type,
                operator="eq" if len(ordered_values) == 1 else "in",
                value=(
                    ordered_values[0]
                    if len(ordered_values) == 1
                    else list(ordered_values)
                ),
                source_span=values[0].source_span,
            )
        )
    predicate_table_ids = {item.table_id for item in predicates}
    projects_table = next(
        (item for item in request.authorized_schema.tables if item.key == "projects"),
        None,
    )
    work_items_table = next(
        (item for item in request.authorized_schema.tables if item.key == "work_items"),
        None,
    )
    preferred_root_table_id = (
        work_items_table.table_id
        if work_items_table is not None
        and re.search(r"high\s*风险(?:工作项|项)", request.query, re.IGNORECASE)
        else (
            projects_table.table_id
            if projects_table is not None
            and (
                ("按风险排序" in request.query and "管理日报" in request.query)
                or "项目和风险" in request.query
            )
            else None
        )
    )
    root_candidates = (
        {preferred_root_table_id}
        if preferred_root_table_id is not None
        else (
            exact_code_table_ids
            if len(exact_code_table_ids) == 1
            else (
                predicate_table_ids
                if len(predicate_table_ids) == 1
                else (
                    entity_table_ids
                    if len(entity_table_ids) == 1
                    else explicit_table_ids
                    or predicate_table_ids
                    or field_table_ids
                    or entity_table_ids
                )
            )
        )
    )
    root_table_id = next(
        (
            table.table_id
            for table in request.authorized_schema.tables
            if table.table_id in root_candidates
        ),
        None,
    )
    requested_aggregation_kinds = tuple(
        dict.fromkeys(
            token.canonical_value
            for token in lexical.tokens
            if token.kind == "aggregation"
            and token.canonical_value
            in {"count", "sum", "average", "minimum", "maximum"}
        )
    )
    limits = [
        int(token.canonical_value) for token in lexical.tokens if token.kind == "limit"
    ]
    execution_spec, planned_predicates = _query_execution_intent(
        request,
        binding=binding,
        predicates=tuple(sorted(predicates, key=lambda item: str(item.field_id))),
        root_table_id=root_table_id,
        action_spans=action_spans,
        requested_aggregation_kinds=requested_aggregation_kinds,
        limit=limits[0] if limits else None,
        include_risk_context=_requires_independent_risk_analysis(
            request.query,
            lexical,
            action_spans=action_spans,
        ),
    )
    return QueryIntentSpec(
        query_intent_id="query-01",
        root_table_id=root_table_id,
        entity_codes=_ordered_codes(
            tuple(
                item
                for item in entities
                if item.table_id is None or item.table_id == root_table_id
            )
        ),
        predicates=planned_predicates,
        aggregation_kinds=tuple(
            dict.fromkeys(item.function for item in execution_spec.aggregations)
        ),
        group_by_field_ids=tuple(
            dict.fromkeys(
                field_id
                for aggregate in execution_spec.aggregations
                for field_id in aggregate.group_by_field_ids
            )
        ),
        sort_field_ids=tuple(
            item.field_id for item in execution_spec.sorts if item.field_id is not None
        ),
        limit=execution_spec.limit,
        execution_spec=execution_spec,
    )


def _query_execution_intent(
    request: PlannerRequestV2,
    *,
    binding: SchemaBindingResult,
    predicates: tuple[BoundPredicate, ...],
    root_table_id: UUID | None,
    action_spans: tuple[SourceSpan, ...],
    requested_aggregation_kinds: tuple[str, ...],
    limit: int | None,
    include_risk_context: bool,
) -> tuple[QueryExecutionIntentV1, tuple[BoundPredicate, ...]]:
    text = request.query
    predicate_spans = tuple(item.source_span for item in predicates)
    projection_field_ids = tuple(
        dict.fromkeys(
            item.field_id
            for item in binding.bound_fields
            if not _span_overlaps_any(
                item.source_span,
                (*action_spans, *predicate_spans),
            )
        )
    )
    planned_predicates = predicates
    aggregates: list[QueryAggregationIntentV1] = []
    sorts: list[QuerySortIntentV1] = []
    status = _authorized_field(request, "work_items", "status")
    project_link = _authorized_field(request, "work_items", "project_link")
    priority = _authorized_field(request, "work_items", "priority")
    risk_level = _authorized_field(request, "work_items", "risk_level")
    risk_status = _authorized_field(request, "risks", "status")
    risk_record_level = _authorized_field(request, "risks", "level")
    title = _authorized_field(request, "work_items", "title")
    blocked_reason = _authorized_field(request, "work_items", "blocked_reason")
    ticket_code = _authorized_field(request, "work_items", "ticket_code")
    project_code = _authorized_field(request, "projects", "project_code")
    risk_code = _authorized_field(request, "risks", "risk_code")

    explicit_projection_fields: list[AuthorizedFieldSpec] = []
    if risk_code is not None and re.search(
        r"风险编号|给出关联风险|列出.{0,8}风险记录|支撑记录编号",
        text,
    ):
        explicit_projection_fields.append(risk_code)
    if (
        risk_code is not None
        and include_risk_context
        and re.search(
            r"解释.{0,8}(?:异常|风险)|(?:异常|风险).{0,8}解释",
            text,
        )
    ):
        explicit_projection_fields.append(risk_code)
    if ticket_code is not None and "反查工作项" in text:
        explicit_projection_fields.append(ticket_code)
    if ticket_code is not None and re.search(
        r"(?:全部|所有).{0,4}?(?:工作项|事项)"
        r"|(?:工作项|事项).{0,8}?(?:分别)?有哪些"
        r"|哪些.{0,4}?(?:工作项|事项)"
        r"|列出.{0,48}?(?:工作项|事项)",
        text,
    ):
        explicit_projection_fields.append(ticket_code)
    if ticket_code is not None and re.search(
        r"工作项编号|暂停项目专项日报",
        text,
    ):
        explicit_projection_fields.append(ticket_code)
    if ticket_code is not None and re.search(
        r"(?:high|高).{0,8}风险项.{0,16}(?:提醒|通知)",
        text,
        re.IGNORECASE,
    ):
        explicit_projection_fields.append(ticket_code)
    if project_code is not None and re.search(
        r"所属项目|返回项目|项目简报|项目专项日报|交付项目日报",
        text,
    ):
        explicit_projection_fields.append(project_code)
    if blocked_reason is not None and "阻塞原因" in text:
        explicit_projection_fields.append(blocked_reason)
    projection_field_ids = tuple(
        dict.fromkeys(
            (
                *projection_field_ids,
                *(field.field_id for field in explicit_projection_fields),
            )
        )
    )

    is_daily_metrics = (
        ("运营日报" in text or "daily" in text.lower())
        and _has_completed_marker(text)
        and _contains_all(text, ("进行中", "阻塞"))
    )
    is_unfinished_project_threshold = (
        "未完成" in text
        and "项目" in text
        and any(
            marker in text for marker in ("两个以上", "2个以上", "至少两个", "至少2个")
        )
    )
    is_unfinished_project_group = (
        "未完成" in text
        and "项目" in text
        and any(marker in text for marker in ("按项目汇总", "每个项目", "各项目"))
    )
    is_blocked_priority_list = (
        "阻塞" in text and "排序" in text and ("优先级" in text or "风险" in text)
    )
    is_risk_exposure_comparison = (
        "风险暴露" in text
        and project_link is not None
        and risk_status is not None
        and risk_record_level is not None
    )
    is_open_risk_by_level = (
        "开放风险数量" in text
        and "按风险级别" in text
        and risk_status is not None
        and risk_record_level is not None
    )
    is_high_risk_work_summary = (
        "汇总" in text
        and "high" in text.casefold()
        and any(marker in text for marker in ("工作项", "风险项"))
        and risk_level is not None
    )
    if (
        "找出" in text
        and "阻塞原因" in text
        and status is not None
        and not any(item.field_id == status.field_id for item in planned_predicates)
    ):
        planned_predicates = (
            *planned_predicates,
            _field_predicate(
                request.query,
                status,
                operator="eq",
                value="blocked",
            ),
        )

    if is_risk_exposure_comparison:
        aggregates.extend(
            (
                _count_aggregate_intent(
                    aggregate_id="aggregate-open-risks",
                    output_key="open_risks",
                    table_id=risk_status.table_id,
                    filter_predicate=_field_predicate(
                        request.query,
                        risk_status,
                        operator="eq",
                        value="open",
                    ),
                    group_by_field_ids=(project_link.field_id,),
                ),
                _count_aggregate_intent(
                    aggregate_id="aggregate-high-risks",
                    output_key="high_risks",
                    table_id=risk_record_level.table_id,
                    filter_predicate=_field_predicate(
                        request.query,
                        risk_record_level,
                        operator="eq",
                        value="high",
                    ),
                    group_by_field_ids=(project_link.field_id,),
                ),
            )
        )
    elif is_open_risk_by_level:
        aggregates.append(
            _count_aggregate_intent(
                aggregate_id="aggregate-open-risks-by-level",
                output_key="open_risks",
                table_id=risk_status.table_id,
                filter_predicate=_field_predicate(
                    request.query,
                    risk_status,
                    operator="eq",
                    value="open",
                ),
                group_by_field_ids=(risk_record_level.field_id,),
            )
        )
    elif is_daily_metrics and status is not None:
        planned_predicates = tuple(
            item for item in predicates if item.field_id != status.field_id
        )
        for value, output_key in (
            ("done", "completed"),
            ("in_progress", "in_progress"),
            ("blocked", "blocked"),
        ):
            aggregates.append(
                _count_aggregate_intent(
                    aggregate_id=f"aggregate-daily-{output_key.replace('_', '-')}",
                    output_key=output_key,
                    table_id=status.table_id,
                    filter_predicate=_field_predicate(
                        request.query,
                        status,
                        operator="eq",
                        value=value,
                    ),
                )
            )
    elif (
        (is_unfinished_project_threshold or is_unfinished_project_group)
        and status is not None
        and project_link is not None
    ):
        aggregates.append(
            _count_aggregate_intent(
                aggregate_id="aggregate-unfinished-by-project",
                output_key="unfinished_work_items",
                table_id=status.table_id,
                filter_predicate=_field_predicate(
                    request.query,
                    status,
                    operator="ne",
                    value="done",
                ),
                group_by_field_ids=(project_link.field_id,),
                having=(
                    QueryHavingIntentV1(operator="gte", value=2)
                    if is_unfinished_project_threshold
                    else None
                ),
            )
        )
    elif is_blocked_priority_list and status is not None:
        if not any(item.field_id == status.field_id for item in planned_predicates):
            planned_predicates = (
                *planned_predicates,
                _field_predicate(
                    request.query,
                    status,
                    operator="eq",
                    value="blocked",
                ),
            )
        aggregates.append(
            _count_aggregate_intent(
                aggregate_id="aggregate-blocked-count",
                output_key="blocked_work_items",
                table_id=status.table_id,
                filter_predicate=None,
            )
        )
        sort_field = risk_level if "风险" in text else priority
        if sort_field is not None:
            sorts.append(
                QuerySortIntentV1(
                    sort_id=f"sort-{sort_field.key}",
                    table_id=sort_field.table_id,
                    field_id=sort_field.field_id,
                    aggregate_id=None,
                    mode="field_order",
                    direction=(
                        "desc"
                        if any(marker in text for marker in ("从低到高", "低到高"))
                        else "asc"
                    ),
                    nulls="last",
                )
            )
            if ticket_code is not None:
                sorts.append(_identity_sort_intent(ticket_code, len(sorts) + 1))
        projection_field_ids = tuple(
            dict.fromkeys(
                (
                    *(field_id for field_id in projection_field_ids),
                    *(
                        field.field_id
                        for field in (title, sort_field)
                        if field is not None
                    ),
                )
            )
        )
    elif is_high_risk_work_summary:
        aggregates.append(
            _count_aggregate_intent(
                aggregate_id="aggregate-high-risk-work-items",
                output_key="high_risk_work_items",
                table_id=risk_level.table_id,
                filter_predicate=None,
            )
        )
    else:
        aggregates.extend(
            _generic_aggregate_intents(
                request,
                binding=binding,
                root_table_id=root_table_id,
                requested_kinds=requested_aggregation_kinds,
            )
        )
        generic_sort = _generic_sort_intent(
            request,
            priority=priority,
            risk_level=risk_level,
        )
        if generic_sort is not None:
            sorts.append(generic_sort)
            identity = _authorized_field(request, "work_items", "ticket_code")
            if identity is not None and identity.table_id == generic_sort.table_id:
                sorts.append(_identity_sort_intent(identity, len(sorts) + 1))

    optional_risk_aggregate = _optional_risk_relation_aggregate(
        request,
        predicates=tuple(planned_predicates),
    )
    if optional_risk_aggregate is not None and not any(
        item.table_id == optional_risk_aggregate.table_id
        and item.output_key == optional_risk_aggregate.output_key
        for item in aggregates
    ):
        aggregates.append(optional_risk_aggregate)

    planned_predicates = tuple(
        sorted(planned_predicates, key=lambda item: str(item.field_id))
    )
    execution = QueryExecutionIntentV1(
        projection_field_ids=projection_field_ids,
        predicate_expression=_predicate_expression(planned_predicates),
        aggregations=tuple(aggregates),
        sorts=tuple(sorts),
        join_intents=_query_join_intents(
            request,
            binding=binding,
            root_table_id=root_table_id,
            predicates=planned_predicates,
            projection_field_ids=projection_field_ids,
            aggregations=tuple(aggregates),
            sorts=tuple(sorts),
            action_spans=action_spans,
            include_risk_context=include_risk_context,
        ),
        limit=limit,
    )
    return execution, planned_predicates


def _query_join_intents(
    request: PlannerRequestV2,
    *,
    binding: SchemaBindingResult,
    root_table_id: UUID | None,
    predicates: tuple[BoundPredicate, ...],
    projection_field_ids: tuple[UUID, ...],
    aggregations: tuple[QueryAggregationIntentV1, ...],
    sorts: tuple[QuerySortIntentV1, ...],
    action_spans: tuple[SourceSpan, ...],
    include_risk_context: bool,
) -> tuple[QueryJoinIntentV1, ...]:
    if root_table_id is None:
        return ()
    fields_by_id = {
        field.field_id: field
        for table in request.authorized_schema.tables
        for field in table.fields
    }
    tables_by_id = {table.table_id: table for table in request.authorized_schema.tables}
    predicate_tables = {item.table_id for item in predicates}
    projection_tables = {
        fields_by_id[field_id].table_id
        for field_id in projection_field_ids
        if field_id in fields_by_id
    }
    aggregate_tables = {item.table_id for item in aggregations}
    sort_tables = {item.table_id for item in sorts if item.table_id is not None}
    semantic_text = _text_without_spans(request.query, action_spans)
    mentioned_tables = {
        *(
            item.table_id
            for item in binding.bound_tables
            if not _span_overlaps_any(item.source_span, action_spans)
        ),
        *(
            table.table_id
            for table in request.authorized_schema.tables
            if _schema_table_is_mentioned(semantic_text, table)
        ),
    }
    root_table = tables_by_id[root_table_id]
    contextual_table_keys: set[str] = set()
    suppress_action_context = any(
        marker in request.query
        for marker in (
            "无权",
            "权限",
            "冲突",
            "版本已变化",
            "同时改为",
            "隐藏字段",
            "客户密钥",
            "越权",
        )
    )
    if root_table.key == "work_items":
        if not suppress_action_context and any(
            marker in request.query for marker in ("提醒", "通知")
        ):
            contextual_table_keys.add("owners")
        elif not suppress_action_context and any(
            marker in request.query
            for marker in ("草稿", "改为", "调整", "补充", "任务", "更新", "提议")
        ):
            contextual_table_keys.add("projects")
        if (
            not suppress_action_context
            and include_risk_context
            and re.search(
                r"解释.{0,8}(?:异常|风险)|(?:异常|风险).{0,8}解释",
                request.query,
            )
        ):
            contextual_table_keys.add("risks")
    elif root_table.key == "projects":
        if "日报" in request.query and not suppress_action_context:
            contextual_table_keys.add("work_items")
        if "按风险排序" in request.query and "管理日报" in request.query:
            contextual_table_keys.add("risks")
        if not suppress_action_context and any(
            marker in request.query for marker in ("提醒", "通知", "负责人")
        ):
            contextual_table_keys.add("owners")
        elif not suppress_action_context and any(
            marker in request.query
            for marker in ("新增", "创建", "生成", "草稿", "任务")
        ):
            contextual_table_keys.add("work_items")
    mentioned_tables.update(
        table.table_id
        for table in request.authorized_schema.tables
        if table.key in contextual_table_keys
    )
    target_table_ids = (
        mentioned_tables
        | predicate_tables
        | projection_tables
        | aggregate_tables
        | sort_tables
    ) - {root_table_id}
    values: list[QueryJoinIntentV1] = []
    for index, target_table_id in enumerate(
        (
            table.table_id
            for table in request.authorized_schema.tables
            if table.table_id in target_table_ids
        ),
        start=1,
    ):
        table = tables_by_id[target_table_id]
        existence_required = (
            "存在" in semantic_text
            and target_table_id in predicate_tables
            and "如果存在" not in semantic_text
            and "如有" not in semantic_text
        )
        optional_annotation = (
            table.key == "risks"
            and re.search(
                r"关联风险|对应.{0,8}风险|哪些.{0,4}(?:有|关联).{0,4}风险|"
                r"给出.{0,8}风险|列出.{0,8}风险编号",
                semantic_text,
            )
            is not None
            and not existence_required
        )
        primary_projection = (
            table.key == "work_items"
            and re.search(
                r"列出.{0,24}(?:工作项|事项)|(?:工作项|事项).{0,12}(?:有哪些|分别有哪些)",
                semantic_text,
            )
            is not None
        )
        report_work_items = (
            root_table.key == "projects"
            and table.key == "work_items"
            and "日报" in request.query
            and not suppress_action_context
        )
        grouped_project_context = table.key == "projects" and any(
            fields_by_id[field_id].key == "project_link"
            for aggregate in aggregations
            for field_id in aggregate.group_by_field_ids
            if field_id in fields_by_id
        )
        explanation_context = (
            include_risk_context
            and table.key == "risks"
            and re.search(
                r"解释.{0,8}(?:异常|风险)|(?:异常|风险).{0,8}解释",
                semantic_text,
            )
            is not None
        )
        if existence_required:
            purpose = "exists"
            requirement = "required"
        elif explanation_context:
            purpose = "project"
            requirement = "optional"
        elif target_table_id in predicate_tables and not optional_annotation:
            purpose = "filter"
            requirement = "required"
        elif target_table_id in projection_tables:
            purpose = "project"
            requirement = "required"
        elif target_table_id in aggregate_tables:
            purpose = "aggregate"
            requirement = "optional"
        elif primary_projection:
            purpose = "project"
            requirement = "required"
        elif report_work_items:
            purpose = "project"
            requirement = "required"
        elif grouped_project_context:
            purpose = "project"
            requirement = "required"
        else:
            purpose = "project"
            requirement = "optional"
        values.append(
            QueryJoinIntentV1(
                join_intent_id=f"join-{index:02d}",
                target_table_id=target_table_id,
                purpose=purpose,
                requirement=requirement,
            )
        )
    return tuple(values)


def _optional_risk_relation_aggregate(
    request: PlannerRequestV2,
    *,
    predicates: tuple[BoundPredicate, ...],
) -> QueryAggregationIntentV1 | None:
    if (
        re.search(
            r"哪些.{0,10}(?:有|关联).{0,8}风险",
            request.query,
        )
        is None
    ):
        return None
    risk_code = _authorized_field(request, "risks", "risk_code")
    if risk_code is None:
        risk_code = _authorized_field(request, "risks", "code")
    if risk_code is None:
        return None
    risk_predicates = tuple(
        item for item in predicates if item.table_id == risk_code.table_id
    )
    return QueryAggregationIntentV1(
        aggregate_id="aggregate-linked-risks",
        output_key=(
            "linked_open_risks"
            if any(
                item.field_key in {"status", "risk_status"} and item.value == "open"
                for item in risk_predicates
            )
            else "linked_risks"
        ),
        function="count",
        table_id=risk_code.table_id,
        field_id=None,
        filter_expression=_predicate_expression(risk_predicates),
        group_by_field_ids=(),
        having=None,
    )


def _schema_table_is_mentioned(query: str, table) -> bool:
    normalized = query.casefold()
    if table.key == "risks" and not (
        "risks" in normalized
        or re.search(
            r"(?:风险(?:暴露|记录|编号|数量)|开放风险|关联风险|比较风险|项目和风险|风险和项目|包含风险)",
            query,
        )
    ):
        return False
    candidates = {table.key, table.name, *table.aliases}
    for candidate in candidates:
        forms = {
            candidate,
            candidate.replace("_", " "),
            candidate.replace(" ", ""),
        }
        for suffix in ("表", "记录", "列表", "数据"):
            if candidate.endswith(suffix) and len(candidate) > len(suffix):
                forms.add(candidate[: -len(suffix)])
        if any(form and form.casefold() in normalized for form in forms):
            return True
    return False


def _text_without_spans(text: str, spans: tuple[SourceSpan, ...]) -> str:
    if not spans:
        return text
    characters = list(text)
    for span in spans:
        for index in range(max(0, span.start), min(len(characters), span.end)):
            characters[index] = " "
    return "".join(characters)


def _risk_code_projection_execution(
    request: PlannerRequestV2,
    binding: SchemaBindingResult,
) -> tuple[QueryExecutionIntentV1, UUID | None]:
    del binding
    risk_code = _authorized_field(request, "risks", "risk_code")
    if risk_code is None:
        risk_code = _authorized_field(request, "risks", "code")
    work_items = _table_by_key(request, "work_items")
    projects = _table_by_key(request, "projects")
    join_intents = tuple(
        QueryJoinIntentV1(
            join_intent_id=f"join-risk-context-{index:02d}",
            target_table_id=table.table_id,
            purpose="project",
            requirement="optional",
        )
        for index, table in enumerate((work_items, projects), start=1)
    )
    return (
        QueryExecutionIntentV1(
            projection_field_ids=() if risk_code is None else (risk_code.field_id,),
            predicate_expression=None,
            aggregations=(),
            sorts=(),
            join_intents=join_intents,
            limit=None,
        ),
        None if risk_code is None else risk_code.table_id,
    )


def _count_aggregate_intent(
    *,
    aggregate_id: str,
    output_key: str,
    table_id: UUID,
    filter_predicate: BoundPredicate | None,
    group_by_field_ids: tuple[UUID, ...] = (),
    having: QueryHavingIntentV1 | None = None,
) -> QueryAggregationIntentV1:
    return QueryAggregationIntentV1(
        aggregate_id=aggregate_id,
        output_key=output_key,
        function="count",
        table_id=table_id,
        field_id=None,
        filter_expression=(
            None
            if filter_predicate is None
            else QueryPredicateLeafIntentV1(predicate=filter_predicate)
        ),
        group_by_field_ids=group_by_field_ids,
        having=having,
    )


def _field_predicate(
    query: str,
    field: AuthorizedFieldSpec,
    *,
    operator: str,
    value: object,
) -> BoundPredicate:
    return BoundPredicate(
        table_id=field.table_id,
        field_id=field.field_id,
        field_key=field.key,
        field_type=field.field_type,
        operator=operator,
        value=value,
        source_span=SourceSpan(start=0, end=len(query), text=query),
    )


def _predicate_expression(
    predicates: tuple[BoundPredicate, ...],
) -> QueryPredicateExpressionV1 | None:
    leaves = tuple(QueryPredicateLeafIntentV1(predicate=item) for item in predicates)
    if not leaves:
        return None
    if len(leaves) == 1:
        return leaves[0]
    return QueryPredicateGroupIntentV1(operator="and", children=leaves)


def _generic_aggregate_intents(
    request: PlannerRequestV2,
    *,
    binding: SchemaBindingResult,
    root_table_id: UUID | None,
    requested_kinds: tuple[str, ...],
) -> tuple[QueryAggregationIntentV1, ...]:
    if root_table_id is None:
        return ()
    fields_by_id = {
        field.field_id: field
        for table in request.authorized_schema.tables
        for field in table.fields
    }
    group_fields: tuple[UUID, ...] = ()
    project_link = _authorized_field(request, "work_items", "project_link")
    if "按项目" in request.query and project_link is not None:
        group_fields = (project_link.field_id,)
    values: list[QueryAggregationIntentV1] = []
    for index, function in enumerate(requested_kinds, start=1):
        field: AuthorizedFieldSpec | None = None
        table_id = root_table_id
        if function != "count":
            field = next(
                (
                    fields_by_id[item.field_id]
                    for item in binding.bound_fields
                    if item.field_id in fields_by_id
                    and (
                        function not in {"sum", "average"}
                        or fields_by_id[item.field_id].field_type == "number"
                    )
                ),
                None,
            )
            if field is None:
                continue
            table_id = field.table_id
        elif project_link is not None and (
            "事项" in request.query or "工作项" in request.query
        ):
            table_id = project_link.table_id
        values.append(
            QueryAggregationIntentV1(
                aggregate_id=f"aggregate-{index:02d}",
                output_key=(
                    "record_count" if function == "count" else f"{field.key}_{function}"
                ),
                function=function,
                table_id=table_id,
                field_id=None if field is None else field.field_id,
                filter_expression=None,
                group_by_field_ids=group_fields,
                having=None,
            )
        )
    return tuple(values)


def _generic_sort_intent(
    request: PlannerRequestV2,
    *,
    priority: AuthorizedFieldSpec | None,
    risk_level: AuthorizedFieldSpec | None,
) -> QuerySortIntentV1 | None:
    if "排序" not in request.query:
        return None
    field = (
        priority
        if "优先级" in request.query
        else risk_level if "风险" in request.query else None
    )
    if field is None:
        return None
    low_to_high = any(
        marker in request.query
        for marker in ("从低到高", "低到高", "升序", "ascending")
    )
    return QuerySortIntentV1(
        sort_id=f"sort-{field.key}",
        table_id=field.table_id,
        field_id=field.field_id,
        aggregate_id=None,
        mode="field_order" if field.choices else "natural",
        direction="desc" if low_to_high and field.choices else "asc",
        nulls="last",
    )


def _identity_sort_intent(
    field: AuthorizedFieldSpec,
    index: int,
) -> QuerySortIntentV1:
    return QuerySortIntentV1(
        sort_id=f"sort-identity-{index:02d}",
        table_id=field.table_id,
        field_id=field.field_id,
        aggregate_id=None,
        mode="natural",
        direction="asc",
        nulls="last",
    )


def _contains_all(text: str, values: tuple[str, ...]) -> bool:
    return all(item in text for item in values)


def _has_completed_marker(text: str) -> bool:
    return (
        re.search(r"(?<!未)完成|已完成", text) is not None
        or "completed" in text.lower()
    )


def _semantic_predicates(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    *,
    action_spans: tuple[SourceSpan, ...],
) -> tuple[BoundPredicate, ...]:
    text = lexical.canonical.normalized_text
    values: list[BoundPredicate] = []

    def append(
        pattern: str,
        table_key: str,
        field_key: str,
        operator: str,
        value: object,
    ) -> None:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            return
        span = _normalized_source_span(lexical, match.start(), match.end())
        if _span_overlaps_any(span, action_spans):
            return
        field = _authorized_field(request, table_key, field_key)
        if field is None:
            return
        values.append(
            BoundPredicate(
                table_id=field.table_id,
                field_id=field.field_id,
                field_key=field.key,
                field_type=field.field_type,
                operator=operator,
                value=value,
                source_span=span,
            )
        )

    blocked_negated = re.search(
        r"(?:状态\s*)?不是\s*blocked|blocked\s*之外",
        text,
        re.IGNORECASE,
    )
    if blocked_negated is not None:
        append(
            r"(?:状态\s*)?不是\s*blocked|blocked\s*之外",
            "work_items",
            "status",
            "ne",
            "blocked",
        )
    else:
        append(
            r"(?<![A-Za-z0-9_])blocked(?![A-Za-z0-9_])|阻塞(?:工作项|事项|项|日报)",
            "work_items",
            "status",
            "eq",
            "blocked",
        )
    append(r"未完成", "work_items", "status", "ne", "done")
    three_statuses = re.search(
        r"进行中[\s、、，,和]+计划中[\s、，,和]+已完成",
        text,
        re.IGNORECASE,
    )
    if three_statuses is not None:
        append(
            r"进行中[\s、、，,和]+计划中[\s、，,和]+已完成",
            "work_items",
            "status",
            "in",
            ["in_progress", "planned", "done"],
        )
    else:
        append(
            r"进行中[\s、，,和]+计划中",
            "work_items",
            "status",
            "in",
            ["in_progress", "planned"],
        )
    append(
        r"优先级\s*不是\s*high",
        "work_items",
        "priority",
        "ne",
        "high",
    )
    append(
        r"高优先级|high\s*优先级",
        "work_items",
        "priority",
        "eq",
        "high",
    )
    append(
        r"风险级别\s*(?:为\s*)?high|high\s*风险.{0,8}?(?:工作项|事项|项)|high\s*且\s*blocked\s*(?:事项|项)",
        "work_items",
        "risk_level",
        "eq",
        "high",
    )
    append(
        r"高风险记录|(?:存在|和)\s*high\s*风险(?:[？?。，,；;]|$)",
        "risks",
        "level",
        "eq",
        "high",
    )
    append(r"开放风险", "risks", "status", "eq", "open")
    append(r"closeout\s*阶段", "projects", "phase", "eq", "closeout")
    append(r"交付阶段|交付项目", "projects", "phase", "eq", "delivery")
    append(r"active\s*项目", "projects", "delivery_state", "eq", "active")
    append(r"暂停项目", "projects", "delivery_state", "eq", "paused")

    unique: dict[tuple[UUID, str, str], BoundPredicate] = {}
    for item in values:
        unique[(item.field_id, item.operator, repr(item.value))] = item
    return tuple(unique.values())


def _entity_identity_predicates(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    entities: tuple[_EntityOccurrence, ...],
    *,
    action_spans: tuple[SourceSpan, ...],
) -> tuple[BoundPredicate, ...]:
    if (
        re.search(
            r"列出|哪些|找出|查询|从|(?:有|是)哪些",
            lexical.canonical.normalized_text,
        )
        is None
    ):
        return ()
    tables_by_id = {table.table_id: table for table in request.authorized_schema.tables}
    fields_by_id = {
        field.field_id: field
        for table in request.authorized_schema.tables
        for field in table.fields
    }
    values: list[BoundPredicate] = []
    grouped: dict[UUID, list[_EntityOccurrence]] = {}
    seen: set[tuple[UUID, str]] = set()
    for entity in entities:
        if (
            entity.table_id is None
            or (entity.table_id, entity.code) in seen
            or _span_overlaps_any(entity.span, action_spans)
        ):
            continue
        seen.add((entity.table_id, entity.code))
        grouped.setdefault(entity.table_id, []).append(entity)
    for table_id, occurrences in grouped.items():
        table = tables_by_id.get(table_id)
        if table is None:
            continue
        if len(occurrences) > 1:
            # Root entity selection already provides deterministic OR semantics.
            # Do not flatten multiple text identities into an invalid AND predicate.
            continue
        identity_field_id = table.identity_field_id or next(
            (
                item.field_id
                for item in table.fields
                if item.key == "code" or item.key.endswith("_code")
            ),
            None,
        )
        if identity_field_id is None:
            continue
        field = fields_by_id[identity_field_id]
        codes = tuple(item.code for item in occurrences)
        start = min(item.span.start for item in occurrences)
        end = max(item.span.end for item in occurrences)
        values.append(
            BoundPredicate(
                table_id=field.table_id,
                field_id=field.field_id,
                field_key=field.key,
                field_type=field.field_type,
                operator="eq",
                value=codes[0],
                source_span=SourceSpan(
                    start=start,
                    end=end,
                    text=lexical.canonical.original_text[start:end],
                ),
            )
        )
    return tuple(values)


def _authorized_field(
    request: PlannerRequestV2,
    table_key: str,
    field_key: str,
) -> AuthorizedFieldSpec | None:
    table = next(
        (item for item in request.authorized_schema.tables if item.key == table_key),
        None,
    )
    if table is None:
        return None
    return next((item for item in table.fields if item.key == field_key), None)


def _normalized_source_span(
    lexical: LexicalQuery,
    start: int,
    end: int,
) -> SourceSpan:
    mapping = lexical.canonical.normalized_to_source
    source_start = mapping[start]
    source_end = mapping[end - 1] + 1
    return SourceSpan(
        start=source_start,
        end=source_end,
        text=lexical.canonical.original_text[source_start:source_end],
    )


def _span_overlaps_any(span: SourceSpan, others: tuple[SourceSpan, ...]) -> bool:
    return any(span.start < item.end and item.start < span.end for item in others)


def _entity_codes_for_table(
    entities: tuple[_EntityOccurrence, ...],
    table_id: UUID | None,
) -> tuple[str, ...]:
    if table_id is None:
        return ()
    return tuple(item.code for item in entities if item.table_id == table_id)


def _entity_occurrences(
    lexical: LexicalQuery,
    binding: SchemaBindingResult,
    authorized_entities: tuple[AuthorizedEntitySpec, ...],
) -> tuple[_EntityOccurrence, ...]:
    values: list[_EntityOccurrence] = [
        _EntityOccurrence(
            code=item.code,
            table_id=item.table_id,
            resolved=True,
            span=item.source_span,
        )
        for item in binding.bound_entities
    ]
    entity_by_code = {item.code.casefold(): item for item in authorized_entities}
    occupied = {(item.span.start, item.span.end) for item in values}
    for token in lexical.tokens:
        if (
            token.kind != "identifier"
            or (
                token.source_span.start,
                token.source_span.end,
            )
            in occupied
        ):
            continue
        entity = entity_by_code.get(token.canonical_value.casefold())
        values.append(
            _EntityOccurrence(
                code=token.canonical_value,
                table_id=None if entity is None else entity.table_id,
                resolved=entity is not None,
                span=token.source_span,
            )
        )
    unique = {(item.code, item.span.start, item.span.end): item for item in values}
    return tuple(sorted(unique.values(), key=lambda item: item.span.start))


def _action_candidates(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    entities: tuple[_EntityOccurrence, ...],
) -> tuple[_ActionCandidate, ...]:
    action_tokens = _supported_action_tokens(request, lexical)
    values: list[_ActionCandidate] = []
    for index, token in enumerate(action_tokens):
        clause = _clause_for_span(lexical.clauses, token.source_span)
        next_action = (
            action_tokens[index + 1] if index + 1 < len(action_tokens) else None
        )
        if next_action is None:
            span_end = len(request.query)
        else:
            next_clause = _clause_for_span(lexical.clauses, next_action.source_span)
            span_end = (
                next_clause.source_span.start
                if next_clause.source_span.start > clause.source_span.start
                else next_action.source_span.start
            )
        candidate_span = SourceSpan(
            start=clause.source_span.start,
            end=span_end,
            text=request.query[clause.source_span.start : span_end],
        )
        local_entities = tuple(
            item
            for item in entities
            if candidate_span.start <= item.span.start < candidate_span.end
        )
        if not local_entities:
            preceding = [
                item for item in entities if item.span.end <= token.source_span.start
            ]
            if preceding:
                local_entities = (preceding[-1],)
        if token.canonical_value == "task.create" and any(
            marker in request.query for marker in ("分别", "每个项目")
        ):
            tasks_table = _table_by_key(request, "tasks")
            project_target_table_id = _field_by_key(
                tasks_table.fields,
                "project_link",
            ).linked_target_table_id
            project_entities = tuple(
                item
                for item in entities
                if item.table_id is not None
                and item.table_id == project_target_table_id
            )
            if project_entities:
                local_entities = project_entities
        date_range = next(
            (
                item
                for item in lexical.date_ranges
                if candidate_span.start <= item.source_span.start < candidate_span.end
            ),
            (
                lexical.date_ranges[0]
                if token.canonical_value == "task.create" and lexical.date_ranges
                else None
            ),
        )
        values.append(
            _ActionCandidate(
                action_kind=token.canonical_value,
                span=candidate_span,
                source_entities=local_entities,
                deadline_start_utc=None if date_range is None else date_range.start_utc,
                deadline_end_utc=None if date_range is None else date_range.end_utc,
            )
        )
    return tuple(values)


def _action_value_spans(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    candidates: tuple[_ActionCandidate, ...],
) -> tuple[SourceSpan, ...]:
    tokens = _supported_action_tokens(request, lexical)
    return tuple(
        SourceSpan(
            start=token.source_span.start,
            end=candidate.span.end,
            text=lexical.canonical.original_text[
                token.source_span.start : candidate.span.end
            ],
        )
        for token, candidate in zip(tokens, candidates, strict=True)
    )


def _supported_action_tokens(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
) -> tuple[LexicalToken, ...]:
    supported = {"record.create", "record.update", "task.create", "reminder.request"}
    return tuple(
        sorted(
            (
                item
                for item in lexical.tokens
                if item.kind == "action"
                and item.canonical_value in supported
                and not (
                    item.canonical_value == "reminder.request"
                    and re.search(
                        r"(?:只|仅)(?:创建|生成|新增)[^，,;；。]{0,20}$",
                        request.query[: item.source_span.start],
                    )
                )
            ),
            key=lambda item: item.source_span.start,
        )
    )


def _expand_separate_candidate(
    candidate: _ActionCandidate,
    query: str,
) -> tuple[_ActionCandidate, ...]:
    if (
        candidate.action_kind not in {"task.create", "reminder.request"}
        or not any(marker in query for marker in ("分别", "每个项目"))
        or len(candidate.source_entities) < 2
    ):
        return (candidate,)
    return tuple(
        _ActionCandidate(
            action_kind=candidate.action_kind,
            span=candidate.span,
            source_entities=(entity,),
            deadline_start_utc=candidate.deadline_start_utc,
            deadline_end_utc=candidate.deadline_end_utc,
        )
        for entity in candidate.source_entities
    )


def _conflict_for_update(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    candidate: _ActionCandidate,
) -> ConflictGroupV1 | None:
    if candidate.action_kind != "record.update" or not candidate.source_entities:
        return None
    table_id = candidate.source_entities[0].table_id
    if table_id is None:
        return None
    for field in _table_fields(request, table_id):
        occurrences = _choice_occurrences(lexical, field, candidate.span)
        values = tuple(dict.fromkeys(value for value, _span_value in occurrences))
        if len(values) < 2:
            continue
        return ConflictGroupV1(
            conflict_group_id="pending",
            slot_ids=("pending",),
            assignments=(
                ConflictAssignment(
                    target_key=candidate.source_entities[0].code,
                    field_key=field.key,
                    values=values,
                    source_spans=tuple(span for _value, span in occurrences),
                ),
            ),
            resolution="deny_conflicting_slot",
        )
    return None


def _build_action_slot(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    binding: SchemaBindingResult,
    candidate: _ActionCandidate,
    *,
    query_spec_ref: str,
    query_root_table_id: UUID | None,
    slot_id: str,
    objective_id: str,
    conflict_group_id: str | None,
) -> ActionSlotV1:
    action_allowed = candidate.action_kind in set(request.allowed_action_kinds)
    assignments: list[ActionAssignment] = []
    required_fields: list[str] = []
    denial_reason: str | None = None
    outcome = "planned"

    if candidate.action_kind == "task.create":
        table = _table_by_key(request, "tasks")
        title = _field_by_key(table.fields, "title")
        _append_assignment(
            assignments,
            required_fields,
            title,
            candidate.span.text,
            candidate.span,
        )
        source_work_item = _field_by_key(table.fields, "source_work_item")
        project_link = _field_by_key(table.fields, "project_link")
        project_codes = _entity_codes_for_table(
            candidate.source_entities,
            project_link.linked_target_table_id,
        )
        work_item_codes = _entity_codes_for_table(
            candidate.source_entities,
            source_work_item.linked_target_table_id,
        )
        highest_risk_source = (
            re.search(r"最高.{0,8}?风险项", candidate.span.text) is not None
        )
        relation_project_source = (
            "项目和风险" in request.query and "决策" in candidate.span.text
        )
        deferred_source = highest_risk_source or relation_project_source
        if highest_risk_source:
            _append_assignment(
                assignments,
                required_fields,
                source_work_item,
                {
                    "selector": "query_result_table",
                    "source_table_id": str(source_work_item.linked_target_table_id),
                },
                candidate.span,
            )
        elif relation_project_source:
            _append_assignment(
                assignments,
                required_fields,
                project_link,
                {
                    "selector": "query_result_table",
                    "source_table_id": str(project_link.linked_target_table_id),
                },
                candidate.span,
            )
        elif work_item_codes:
            _append_assignment(
                assignments,
                required_fields,
                source_work_item,
                list(work_item_codes),
                candidate.span,
            )
        elif project_codes:
            _append_assignment(
                assignments,
                required_fields,
                project_link,
                list(project_codes),
                candidate.span,
            )
        if project_codes and re.search(r"指派.{0,12}?负责人", candidate.span.text):
            assignee = _field_by_key(table.fields, "assignee")
            _append_assignment(
                assignments,
                required_fields,
                assignee,
                {
                    "selector": "project_owner",
                    "source_entity_codes": list(project_codes),
                },
                candidate.span,
            )
        priority = _field_by_key(table.fields, "priority")
        priority_value = _choice_or_default(
            candidate.span.text,
            priority,
        )
        if priority_value is not None:
            _append_assignment(
                assignments,
                required_fields,
                priority,
                priority_value,
                candidate.span,
            )
        status = _field_by_key(table.fields, "status")
        status_value = _choice_or_default(candidate.span.text, status)
        if status_value is not None:
            _append_assignment(
                assignments,
                required_fields,
                status,
                status_value,
                candidate.span,
            )
        if candidate.deadline_end_utc is not None:
            due = _field_by_key(table.fields, "due_date")
            due_span = next(
                (
                    item.source_span
                    for item in lexical.date_ranges
                    if candidate.span.start
                    <= item.source_span.start
                    < candidate.span.end
                ),
                candidate.span,
            )
            boundary = candidate.deadline_start_utc or (
                candidate.deadline_end_utc - timedelta(microseconds=1)
            )
            local_due = boundary.astimezone(ZoneInfo(request.timezone_name)).date()
            _append_assignment(
                assignments,
                required_fields,
                due,
                local_due.isoformat(),
                due_span,
            )
        target = ActionTargetSelector(
            table_id=table.table_id,
            record_codes=(),
            source_entity_codes=(
                ()
                if deferred_source
                else tuple(item.code for item in candidate.source_entities)
            ),
            query_spec_ref=query_spec_ref if deferred_source else None,
            expansion_policy="each_result" if deferred_source else "none",
            resolution_status=(
                "deferred_query_result" if deferred_source else "resolved"
            ),
        )
    elif candidate.action_kind == "record.update":
        entity = candidate.source_entities[0] if candidate.source_entities else None
        table_id = None if entity is None else entity.table_id
        candidate_bound_fields = tuple(
            item
            for item in binding.bound_fields
            if candidate.span.start <= item.source_span.start < candidate.span.end
        )
        bound_table_ids = {item.table_id for item in candidate_bound_fields}
        if table_id is None and len(bound_table_ids) == 1:
            table_id = next(iter(bound_table_ids))
        explicit_fields = [
            field
            for field in _table_fields(request, table_id)
            if any(item.field_id == field.field_id for item in candidate_bound_fields)
        ]
        inferred = _infer_update_field(request, lexical, candidate, table_id)
        field = explicit_fields[0] if explicit_fields else inferred
        declared_denied = _declared_denied_assignment(candidate)
        if conflict_group_id is None and field is None and declared_denied is not None:
            field_key, value, value_span = declared_denied
            assignments.append(
                ActionAssignment(
                    field_id=None,
                    field_key=field_key,
                    value=value,
                    source_span=value_span,
                )
            )
            required_fields.append(field_key)
            outcome = "denied"
            denial_reason = "field_permission_denied"
        elif conflict_group_id is None and field is not None:
            value, value_span = _update_value(lexical, field, candidate.span)
            if value is not None:
                assignments.append(
                    ActionAssignment(
                        field_id=field.field_id,
                        field_key=field.key,
                        value=value,
                        source_span=value_span,
                    )
                )
            required_fields.append(field.key)
            if not field.writable:
                outcome = "denied"
                denial_reason = "field_permission_denied"
        elif conflict_group_id is not None:
            conflict_field = _infer_update_field(request, lexical, candidate, table_id)
            if conflict_field is not None:
                required_fields.append(conflict_field.key)
            outcome = "denied"
            denial_reason = "conflicting_assignments"
        else:
            outcome = "clarification_required"
            denial_reason = "update_field_or_value_unresolved"
        if outcome == "planned" and (entity is None or not entity.resolved):
            outcome = "clarification_required"
            denial_reason = "update_target_unresolved"
        target = ActionTargetSelector(
            table_id=table_id,
            record_codes=() if entity is None else (entity.code,),
            source_entity_codes=(),
            resolution_status=(
                "unresolved_authorized_lookup_required"
                if entity is None or not entity.resolved
                else "resolved"
            ),
        )
    elif candidate.action_kind == "record.create":
        table = _table_by_key(request, "work_items")
        title = _field_by_key(table.fields, "title")
        _append_assignment(
            assignments,
            required_fields,
            title,
            candidate.span.text,
            candidate.span,
        )
        project_field = _field_by_key(table.fields, "project_link")
        project_codes = _entity_codes_for_table(
            candidate.source_entities,
            project_field.linked_target_table_id,
        )
        if project_codes:
            _append_assignment(
                assignments,
                required_fields,
                project_field,
                list(project_codes),
                candidate.span,
            )
        for field_key in ("status", "priority"):
            field = _field_by_key(table.fields, field_key)
            explicit_value = _explicit_choice(candidate.span.text, field)
            if explicit_value is not None:
                _append_assignment(
                    assignments,
                    required_fields,
                    field,
                    explicit_value,
                    candidate.span,
                )
        risk_match = re.search(
            r"\b(high|medium|low)\b.{0,4}?风险|风险.{0,4}?\b(high|medium|low)\b",
            candidate.span.text,
            re.IGNORECASE,
        )
        if risk_match is not None:
            risk_level = _field_by_key(table.fields, "risk_level")
            _append_assignment(
                assignments,
                required_fields,
                risk_level,
                (risk_match.group(1) or risk_match.group(2)).lower(),
                candidate.span,
            )
        target = ActionTargetSelector(
            table_id=table.table_id,
            record_codes=(),
            source_entity_codes=project_codes,
            resolution_status="resolved",
        )
    elif candidate.action_kind == "reminder.request":
        work_items_table = next(
            (
                table
                for table in request.authorized_schema.tables
                if table.key == "work_items"
            ),
            None,
        )
        reminder_sources = (
            tuple(
                item
                for item in candidate.source_entities
                if work_items_table is not None
                and item.table_id == work_items_table.table_id
            )
            or candidate.source_entities
        )
        table_id = reminder_sources[0].table_id if reminder_sources else None
        target_resolved = bool(reminder_sources) and all(
            item.resolved for item in reminder_sources
        )
        deferred_collection = (
            not reminder_sources
            and query_root_table_id is not None
            and (
                (
                    re.search(r"所有|全部|各|每个|分别", candidate.span.text)
                    is not None
                    and "负责人" in candidate.span.text
                )
                or re.search(
                    r"high\s*风险项|blocked\s*(?:事项|项)",
                    candidate.span.text,
                    re.IGNORECASE,
                )
                is not None
            )
        )
        if not target_resolved and not deferred_collection:
            outcome = "clarification_required"
            denial_reason = "reminder_target_unresolved"
        target = ActionTargetSelector(
            table_id=query_root_table_id if deferred_collection else table_id,
            record_codes=(),
            source_entity_codes=tuple(
                item.code for item in reminder_sources if item.table_id == table_id
            ),
            query_spec_ref=query_spec_ref if deferred_collection else None,
            expansion_policy=("each_distinct_owner" if deferred_collection else "none"),
            resolution_status=(
                "resolved"
                if target_resolved
                else (
                    "deferred_query_result"
                    if deferred_collection
                    else (
                        "unresolved_authorized_lookup_required"
                        if reminder_sources
                        else "ambiguous"
                    )
                )
            ),
        )
    else:
        table = _table_by_key(request, "work_items")
        target = ActionTargetSelector(
            table_id=table.table_id,
            record_codes=(),
            source_entity_codes=tuple(item.code for item in candidate.source_entities),
            resolution_status="resolved",
        )

    if candidate.action_kind in {"task.create", "record.create"}:
        source_unresolved = any(not item.resolved for item in candidate.source_entities)
        if source_unresolved:
            outcome = "clarification_required"
            denial_reason = "create_source_unresolved"
            target = target.model_copy(
                update={"resolution_status": "unresolved_authorized_lookup_required"}
            )
        fields_by_id = {
            field.field_id: field
            for table in request.authorized_schema.tables
            for field in table.fields
        }
        if any(
            assignment.field_id is not None
            and not fields_by_id[assignment.field_id].writable
            for assignment in assignments
        ):
            outcome = "denied"
            denial_reason = "field_permission_denied"

    if re.search(r"workspace\s*之外", request.query, re.IGNORECASE):
        assignments.clear()
        required_fields.clear()
        target = ActionTargetSelector(
            table_id=None,
            record_codes=(),
            source_entity_codes=(),
            resolution_status="denied",
        )
        outcome = "denied"
        denial_reason = "outside_workspace_scope_denied"
    elif not action_allowed:
        outcome = "denied"
        denial_reason = "action_kind_not_authorized"
    return ActionSlotV1(
        slot_id=slot_id,
        objective_id=objective_id,
        action_kind=candidate.action_kind,
        target=target,
        assignments=tuple(assignments),
        required_field_keys=tuple(dict.fromkeys(required_fields)),
        confirmation_policy="required",
        deadline_start_utc=candidate.deadline_start_utc,
        deadline_end_utc=candidate.deadline_end_utc,
        conflict_group_id=conflict_group_id,
        planning_outcome=outcome,
        denial_reason=denial_reason,
    )


def _infer_update_field(
    request: PlannerRequestV2,
    lexical: LexicalQuery,
    candidate: _ActionCandidate,
    table_id: UUID | None,
) -> AuthorizedFieldSpec | None:
    if table_id is None:
        return None
    fields = _table_fields(request, table_id)
    choice_fields = [
        field for field in fields if _choice_occurrences(lexical, field, candidate.span)
    ]
    if len(choice_fields) == 1:
        return choice_fields[0]
    for field in fields:
        if (
            re.search(re.escape(field.key), candidate.span.text, re.IGNORECASE)
            or field.name in candidate.span.text
        ):
            return field
    return None


def _update_value(
    lexical: LexicalQuery,
    field: AuthorizedFieldSpec,
    span: SourceSpan,
) -> tuple[object | None, SourceSpan]:
    choices = _choice_occurrences(lexical, field, span)
    if len(choices) == 1:
        return choices[0]
    local_text = lexical.canonical.original_text[span.start : span.end]
    match = re.search(
        rf"(?:{re.escape(field.key)}|{re.escape(field.name)}).{{0,8}}?(?:更新为|改为|设为)\s*([A-Za-z0-9_\-\u3400-\u9fff]+)",
        local_text,
        re.IGNORECASE,
    )
    if match is None:
        return None, span
    value_span = SourceSpan(
        start=span.start + match.start(1),
        end=span.start + match.end(1),
        text=match.group(1),
    )
    return match.group(1), value_span


def _declared_denied_assignment(
    candidate: _ActionCandidate,
) -> tuple[str, str, SourceSpan] | None:
    if "无权编辑" not in candidate.span.text:
        return None
    match = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(?:更新为|改为|调整为|设为)\s*([^，,。；;]+)",
        candidate.span.text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    value_start = candidate.span.start + match.start(2)
    value_end = candidate.span.start + match.end(2)
    return (
        match.group(1),
        match.group(2),
        SourceSpan(
            start=value_start,
            end=value_end,
            text=match.group(2),
        ),
    )


def _choice_occurrences(
    lexical: LexicalQuery,
    field: AuthorizedFieldSpec,
    span: SourceSpan,
) -> tuple[tuple[str, SourceSpan], ...]:
    values: list[tuple[str, SourceSpan]] = []
    source = lexical.canonical.original_text
    for choice in field.choices:
        for match in re.finditer(re.escape(choice), source, re.IGNORECASE):
            if span.start <= match.start() < span.end:
                values.append(
                    (
                        choice,
                        SourceSpan(
                            start=match.start(),
                            end=match.end(),
                            text=source[match.start() : match.end()],
                        ),
                    )
                )
    return tuple(sorted(values, key=lambda item: item[1].start))


def _clause_for_span(
    clauses: tuple[LexicalClause, ...],
    span: SourceSpan,
) -> LexicalClause:
    return next(
        (
            item
            for item in clauses
            if item.source_span.start <= span.start < item.source_span.end
        ),
        clauses[0],
    )


def _table_by_key(request: PlannerRequestV2, key: str):
    table = next(
        (item for item in request.authorized_schema.tables if item.key == key),
        None,
    )
    if table is None:
        raise ValueError("task_planner_action_table_unavailable")
    return table


def _table_fields(
    request: PlannerRequestV2,
    table_id: UUID | None,
) -> tuple[AuthorizedFieldSpec, ...]:
    if table_id is None:
        return ()
    table = next(
        (
            item
            for item in request.authorized_schema.tables
            if item.table_id == table_id
        ),
        None,
    )
    return () if table is None else table.fields


def _field_by_key(
    fields: tuple[AuthorizedFieldSpec, ...],
    key: str,
) -> AuthorizedFieldSpec:
    field = next((item for item in fields if item.key == key), None)
    if field is None:
        raise ValueError("task_planner_action_field_unavailable")
    return field


def _append_assignment(
    assignments: list[ActionAssignment],
    required_fields: list[str],
    field: AuthorizedFieldSpec,
    value: object,
    source_span: SourceSpan,
) -> None:
    assignments.append(
        ActionAssignment(
            field_id=field.field_id,
            field_key=field.key,
            value=value,
            source_span=source_span,
        )
    )
    required_fields.append(field.key)


def _explicit_choice(text: str, field: AuthorizedFieldSpec) -> str | None:
    for choice in field.choices:
        escaped = re.escape(choice)
        if field.key == "priority":
            if choice == "high" and "高优先级" in text:
                return choice
            pattern = rf"(?:{escaped}.{{0,4}}?优先级|优先级.{{0,4}}?{escaped})"
        elif field.key == "status":
            pattern = rf"(?:{escaped}.{{0,4}}?状态|状态.{{0,4}}?{escaped})"
        else:
            pattern = rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
        if re.search(pattern, text, re.IGNORECASE):
            return choice
    return None


def _choice_or_default(text: str, field: AuthorizedFieldSpec) -> object | None:
    return _explicit_choice(text, field) or field.default_value


def _ordered_codes(entities: tuple[_EntityOccurrence, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.code for item in entities))


def _token_spans(lexical: LexicalQuery, kind: str) -> tuple[SourceSpan, ...]:
    spans = tuple(item.source_span for item in lexical.tokens if item.kind == kind)
    return spans or (
        SourceSpan(
            start=0,
            end=len(lexical.canonical.original_text),
            text=lexical.canonical.original_text,
        ),
    )


def _objective(
    *,
    objective_id: str,
    kind: str,
    entities: tuple[str, ...],
    query_ref: str | None,
    output: str,
    outcome: str,
    reason: str | None,
    spans: tuple[SourceSpan, ...],
) -> TaskObjectiveV2:
    return TaskObjectiveV2(
        objective_id=objective_id,
        kind=kind,
        required=True,
        entity_codes=entities,
        query_spec_ref=query_ref,
        output_contract=output,
        planning_outcome=outcome,
        denial_reason=reason,
        source_spans=spans,
    )


def _edge(
    source: str,
    target: str,
    *,
    required: bool = True,
) -> DependencyEdgeV2:
    return DependencyEdgeV2(
        from_objective_id=source,
        to_objective_id=target,
        required=required,
    )


__all__ = [
    "PlannerAmbiguityDecision",
    "PlannerAmbiguityRequest",
    "PlannerAmbiguityResolver",
    "plan_task_v2",
]
