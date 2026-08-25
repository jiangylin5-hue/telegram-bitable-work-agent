"""Permission-filtered schema snapshot and deterministic Planner V2 binding."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from uuid import UUID

from app.schemas.agent_task_spec_v2 import (
    AuthorizedEntitySpec,
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    SourceSpan,
    authorized_schema_sha256,
)
from app.schemas.authorized_query_plan import AuthorizedRelationSpec
from app.services.agent_field_policy_v2 import (
    Stage12FieldPolicyError,
    parse_stage12_field_policy_v2,
)
from app.services.agent_query_lexical import LexicalQuery
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    can_actor_write_record_fields,
    get_table_schema,
)


_TABLE_ALIASES: dict[str, tuple[str, ...]] = {
    "projects": ("项目", "项目表"),
    "work_items": ("工作项", "事项", "工作项表"),
    "risks": ("风险记录", "风险表"),
    "tasks": ("任务", "任务表"),
    "owners": ("负责人", "负责人表"),
    "daily_metrics": ("日报指标", "日报指标表"),
    "interactions": ("互动记录", "互动表"),
}


@dataclass(frozen=True, slots=True)
class BoundTableMention:
    table_id: UUID
    table_key: str
    mention: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class BoundFieldMention:
    table_id: UUID
    field_id: UUID
    field_key: str
    mention: str
    match_kind: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class BoundEntityMention:
    entity_id: UUID
    table_id: UUID
    code: str
    mention: str
    match_kind: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class BoundEnumValue:
    table_id: UUID
    field_id: UUID
    field_key: str
    value: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class AmbiguousBinding:
    mention: str
    kind: str
    candidate_ids: tuple[str, ...]
    candidate_labels: tuple[str, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class UnresolvedMention:
    text: str
    reason: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class SchemaBindingResult:
    schema_hash: str
    bound_tables: tuple[BoundTableMention, ...]
    bound_fields: tuple[BoundFieldMention, ...]
    bound_entities: tuple[BoundEntityMention, ...]
    bound_enum_values: tuple[BoundEnumValue, ...]
    ambiguous_candidates: tuple[AmbiguousBinding, ...]
    unresolved_mentions: tuple[UnresolvedMention, ...]


def _authorized_link_target(field: object, table_ids: set[UUID]) -> UUID | None:
    if getattr(field, "field_type", None) != "linked_record":
        return None
    raw_target = (getattr(field, "options", None) or {}).get("target_table_id")
    try:
        target = UUID(str(raw_target))
    except (TypeError, ValueError, AttributeError):
        return None
    return target if target in table_ids else None


def build_authorized_schema_snapshot(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
    require_field_policy_v2: bool = False,
) -> AuthorizedSchemaSnapshot:
    workspace = uow.get_workspace(workspace_id)
    employee = uow.get_digital_employee(employee_id)
    if workspace is None or workspace.status != "active":
        raise PlatformValidationError("workspace_not_found", "workspace")
    if (
        employee is None
        or employee.workspace_id != workspace_id
        or employee.status != "active"
    ):
        raise PlatformValidationError("digital_employee_scope_denied", "employee")
    base = uow.get_base(employee.base_id)
    if base is None or base.workspace_id != workspace_id or base.status != "active":
        raise PlatformValidationError("digital_employee_scope_denied", "base")

    field_policy = None
    if require_field_policy_v2:
        try:
            field_policy = parse_stage12_field_policy_v2(employee.field_policy)
        except Stage12FieldPolicyError as exc:
            raise PlatformValidationError(str(exc), str(exc)) from exc

    accessible_ids: set[UUID] = set()
    for raw_id in employee.accessible_tables:
        try:
            accessible_ids.add(UUID(str(raw_id)))
        except ValueError as exc:
            raise PlatformValidationError(
                "digital_employee_scope_invalid", "accessible_tables"
            ) from exc

    authorized_tables: list[object] = []
    for table_id in accessible_ids:
        table = uow.get_table(table_id)
        if table is None or table.base_id != base.id or table.status != "active":
            raise PlatformValidationError(
                "digital_employee_scope_denied", str(table_id)
            )
        authorized_tables.append(table)
    if field_policy is not None:
        configured_field_ids = {
            field.id
            for table in authorized_tables
            for field in uow.list_fields(table.id)
        }
        policy_field_ids = {
            *field_policy.readable_field_ids,
            *field_policy.writable_field_ids,
            *field_policy.redacted_field_ids,
        }
        if not policy_field_ids.issubset(configured_field_ids):
            raise PlatformValidationError(
                "digital_employee_field_policy_v2_stale",
                "digital_employee_field_policy_v2_stale",
            )

    tables: list[AuthorizedTableSpec] = []
    for table in authorized_tables:
        safe_schema = get_table_schema(uow, table.id, actor=actor)
        safe_fields = tuple(safe_schema["fields"])
        if field_policy is not None:
            effective_readable = set(field_policy.readable_field_ids) - set(
                field_policy.redacted_field_ids
            )
            safe_fields = tuple(
                item
                for item in safe_fields
                if UUID(item["id"]) in effective_readable
            )
        visible_field_ids = {UUID(item["id"]) for item in safe_fields}
        visible_fields = {
            item.id: item
            for item in uow.list_fields(table.id)
            if item.id in visible_field_ids
        }
        fields: list[AuthorizedFieldSpec] = []
        for raw_field in safe_fields:
            options = raw_field.get("options")
            safe_options = options if isinstance(options, dict) else {}
            stored_field = visible_fields[UUID(raw_field["id"])]
            aliases = _string_tuple((stored_field.options or {}).get("aliases"))
            choices = _string_tuple(safe_options.get("choices"))
            fields.append(
                AuthorizedFieldSpec(
                    field_id=UUID(raw_field["id"]),
                    table_id=table.id,
                    key=raw_field["key"],
                    name=raw_field["name"],
                    field_type=raw_field["field_type"],
                    aliases=aliases,
                    choices=choices,
                    writable=(
                        can_actor_write_record_fields(
                            uow,
                            table.id,
                            (raw_field["key"],),
                            actor=actor,
                        )
                        and (
                            field_policy is None
                            or UUID(raw_field["id"])
                            in set(field_policy.writable_field_ids)
                        )
                    ),
                    default_value=(stored_field.options or {}).get("default"),
                    linked_target_table_id=_authorized_link_target(
                        stored_field,
                        accessible_ids,
                    ),
                )
            )
        configured_aliases = _string_tuple((table.settings or {}).get("aliases"))
        aliases = tuple(
            dict.fromkeys((*configured_aliases, *_TABLE_ALIASES.get(table.key, ())))
        )
        configured_identity_key = (table.settings or {}).get("identity_field_key")
        identity_field_id = (
            table.primary_field_id
            if table.primary_field_id in visible_field_ids
            else next(
                (
                    UUID(item["id"])
                    for item in safe_fields
                    if isinstance(configured_identity_key, str)
                    and item["key"] == configured_identity_key
                ),
                None,
            )
        )
        if identity_field_id is None:
            identity_field_id = next(
                (
                    UUID(item["id"])
                    for item in safe_fields
                    if item["key"] == "code" or item["key"].endswith("_code")
                ),
                None,
            )
        if identity_field_id is None and safe_fields:
            identity_field_id = UUID(safe_fields[0]["id"])
        configured_label_key = (table.settings or {}).get("entity_label_field_key")
        label_field_id = next(
            (
                UUID(item["id"])
                for item in safe_fields
                if isinstance(configured_label_key, str)
                and item["key"] == configured_label_key
            ),
            identity_field_id,
        )
        configured_alias_keys = _string_tuple(
            (table.settings or {}).get("entity_alias_field_keys")
        )
        alias_field_ids = tuple(
            sorted(
                (
                    UUID(item["id"])
                    for item in safe_fields
                    if item["key"] in set(configured_alias_keys)
                ),
                key=str,
            )
        )
        tables.append(
            AuthorizedTableSpec(
                table_id=table.id,
                base_id=table.base_id,
                key=table.key,
                name=table.name,
                aliases=aliases,
                fields=tuple(
                    sorted(fields, key=lambda item: (item.key, str(item.field_id)))
                ),
                identity_field_id=identity_field_id,
                label_field_id=label_field_id,
                alias_field_ids=alias_field_ids,
            )
        )
    ordered_tables = tuple(
        sorted(tables, key=lambda item: (item.key, str(item.table_id)))
    )
    scope_hash = _schema_scope_hash(
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
        table_ids=tuple(item.table_id for item in ordered_tables),
        employee_version=employee.version,
        field_policy_version=(None if field_policy is None else field_policy.version),
        field_policy_hash=(None if field_policy is None else field_policy.policy_hash),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": workspace_id,
        "employee_id": employee_id,
        "scope_hash": scope_hash,
        "tables": ordered_tables,
        "field_policy_version": (
            None if field_policy is None else field_policy.version
        ),
        "field_policy_hash": None if field_policy is None else field_policy.policy_hash,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def build_authorized_relation_catalog(
    uow: Stage06PlatformUnitOfWork,
    snapshot: AuthorizedSchemaSnapshot,
) -> tuple[AuthorizedRelationSpec, ...]:
    """Return only link edges already proven visible by the schema snapshot."""

    authorized_table_ids = {item.table_id for item in snapshot.tables}
    relations: list[AuthorizedRelationSpec] = []
    for table in snapshot.tables:
        for field in table.fields:
            if field.field_type != "linked_record":
                continue
            stored = uow.get_field(field.field_id)
            if (
                stored is None
                or stored.status != "active"
                or stored.table_id != table.table_id
                or stored.field_type != "linked_record"
            ):
                continue
            raw_target = (stored.options or {}).get("target_table_id")
            try:
                target_table_id = UUID(str(raw_target))
            except (TypeError, ValueError, AttributeError):
                continue
            if target_table_id not in authorized_table_ids:
                continue
            target_table = uow.get_table(target_table_id)
            if target_table is None or target_table.status != "active":
                continue
            relations.append(
                AuthorizedRelationSpec(
                    relation_id=f"relation:{field.field_id}",
                    link_source_table_id=table.table_id,
                    link_field_id=field.field_id,
                    link_target_table_id=target_table_id,
                )
            )
    return tuple(
        sorted(
            relations,
            key=lambda item: (
                str(item.link_source_table_id),
                str(item.link_field_id),
                str(item.link_target_table_id),
            ),
        )
    )


def bind_lexical_query(
    lexical: LexicalQuery,
    snapshot: AuthorizedSchemaSnapshot,
    *,
    authorized_entities: tuple[AuthorizedEntitySpec, ...] = (),
) -> SchemaBindingResult:
    table_by_id = {item.table_id: item for item in snapshot.tables}
    if any(item.table_id not in table_by_id for item in authorized_entities):
        raise ValueError("schema_binding_entity_scope_invalid")
    bound_tables, table_ambiguities = _bind_tables(lexical, snapshot.tables)
    bound_entities, entity_ambiguities, unresolved_identifiers = _bind_entities(
        lexical,
        authorized_entities,
    )
    context_table_ids = {
        *(item.table_id for item in bound_tables),
        *(item.table_id for item in bound_entities),
    }
    bound_fields, field_ambiguities = _bind_fields(
        lexical,
        snapshot.tables,
        context_table_ids=context_table_ids,
    )
    bound_enums, enum_ambiguities = _bind_enums(
        lexical,
        snapshot.tables,
        context_table_ids=context_table_ids,
        bound_tables=bound_tables,
    )
    unresolved_fields = _unresolved_field_phrases(
        lexical,
        bound_fields=bound_fields,
        ambiguities=field_ambiguities,
    )
    return SchemaBindingResult(
        schema_hash=snapshot.schema_hash,
        bound_tables=bound_tables,
        bound_fields=bound_fields,
        bound_entities=bound_entities,
        bound_enum_values=bound_enums,
        ambiguous_candidates=tuple(
            sorted(
                (
                    *table_ambiguities,
                    *entity_ambiguities,
                    *field_ambiguities,
                    *enum_ambiguities,
                ),
                key=lambda item: (item.source_span.start, item.kind),
            )
        ),
        unresolved_mentions=tuple(
            sorted(
                (*unresolved_identifiers, *unresolved_fields),
                key=lambda item: item.source_span.start,
            )
        ),
    )


def _bind_tables(
    lexical: LexicalQuery,
    tables: tuple[AuthorizedTableSpec, ...],
) -> tuple[tuple[BoundTableMention, ...], tuple[AmbiguousBinding, ...]]:
    candidates: dict[tuple[int, int, str], list[AuthorizedTableSpec]] = {}
    for table in tables:
        for term in dict.fromkeys((table.key, table.name, *table.aliases)):
            for start, end in _term_matches(lexical, term):
                candidates.setdefault((start, end, term.casefold()), []).append(table)
        if table.key == "risks":
            for start, end in _coordinated_risk_table_matches(lexical):
                candidates.setdefault((start, end, "风险"), []).append(table)
    bound: list[BoundTableMention] = []
    ambiguous: list[AmbiguousBinding] = []
    for (start, end, _term), raw_candidates in candidates.items():
        unique = {item.table_id: item for item in raw_candidates}
        ordered = sorted(unique.values(), key=lambda item: str(item.table_id))
        span = _span(lexical, start, end)
        if len(ordered) == 1:
            table = ordered[0]
            bound.append(
                BoundTableMention(
                    table_id=table.table_id,
                    table_key=table.key,
                    mention=span.text,
                    source_span=span,
                )
            )
        else:
            ambiguous.append(
                AmbiguousBinding(
                    mention=span.text,
                    kind="table",
                    candidate_ids=tuple(str(item.table_id) for item in ordered),
                    candidate_labels=tuple(
                        f"{item.key}:{item.name}" for item in ordered
                    ),
                    source_span=span,
                )
            )
    return (
        tuple(sorted(bound, key=lambda item: (item.source_span.start, item.table_key))),
        tuple(sorted(ambiguous, key=lambda item: item.source_span.start)),
    )


def _coordinated_risk_table_matches(
    lexical: LexicalQuery,
) -> tuple[tuple[int, int], ...]:
    pattern = re.compile(
        r"(?:和|及|以及)\s*(?:high|medium|low)\s*(?:的\s*)?(风险)",
        re.IGNORECASE,
    )
    return tuple(match.span(1) for match in pattern.finditer(lexical.canonical.normalized_text))


def _bind_fields(
    lexical: LexicalQuery,
    tables: tuple[AuthorizedTableSpec, ...],
    *,
    context_table_ids: set[UUID],
) -> tuple[tuple[BoundFieldMention, ...], tuple[AmbiguousBinding, ...]]:
    candidates: dict[tuple[int, int, str], list[tuple[AuthorizedFieldSpec, str]]] = {}
    for table in tables:
        for field in table.fields:
            terms = (
                (field.key, "key"),
                (field.name, "name"),
                *((alias, "alias") for alias in field.aliases),
            )
            for term, match_kind in terms:
                for start, end in _term_matches(lexical, term):
                    candidates.setdefault((start, end, term.casefold()), []).append(
                        (field, match_kind)
                    )
    bound: list[BoundFieldMention] = []
    ambiguous: list[AmbiguousBinding] = []
    for (start, end, _term), raw_candidates in candidates.items():
        unique = {item[0].field_id: item for item in raw_candidates}
        narrowed = [
            item for item in unique.values() if item[0].table_id in context_table_ids
        ]
        selected = narrowed if len(narrowed) == 1 else list(unique.values())
        span = _span(lexical, start, end)
        if len(selected) == 1:
            field, match_kind = selected[0]
            bound.append(
                BoundFieldMention(
                    table_id=field.table_id,
                    field_id=field.field_id,
                    field_key=field.key,
                    mention=span.text,
                    match_kind=match_kind,
                    source_span=span,
                )
            )
        else:
            ordered = sorted(
                (item[0] for item in selected), key=lambda item: str(item.field_id)
            )
            ambiguous.append(
                AmbiguousBinding(
                    mention=span.text,
                    kind="field",
                    candidate_ids=tuple(str(item.field_id) for item in ordered),
                    candidate_labels=tuple(item.name for item in ordered),
                    source_span=span,
                )
            )
    return (
        tuple(
            sorted(bound, key=lambda item: (item.source_span.start, str(item.field_id)))
        ),
        tuple(sorted(ambiguous, key=lambda item: item.source_span.start)),
    )


def _bind_enums(
    lexical: LexicalQuery,
    tables: tuple[AuthorizedTableSpec, ...],
    *,
    context_table_ids: set[UUID],
    bound_tables: tuple[BoundTableMention, ...],
) -> tuple[tuple[BoundEnumValue, ...], tuple[AmbiguousBinding, ...]]:
    candidates: dict[tuple[int, int, str], list[AuthorizedFieldSpec]] = {}
    for table in tables:
        for field in table.fields:
            for choice in field.choices:
                for start, end in _term_matches(lexical, choice):
                    candidates.setdefault((start, end, choice), []).append(field)
    bound: list[BoundEnumValue] = []
    ambiguous: list[AmbiguousBinding] = []
    for (start, end, choice), raw_fields in candidates.items():
        unique = {item.field_id: item for item in raw_fields}
        narrowed = [
            item for item in unique.values() if item.table_id in context_table_ids
        ]
        span = _span(lexical, start, end)
        selected = narrowed if len(narrowed) == 1 else list(unique.values())
        if len(selected) > 1:
            nearest = _nearest_mentioned_table_fields(
                span,
                tuple(selected),
                bound_tables,
            )
            if len(nearest) == 1:
                selected = list(nearest)
        if len(selected) == 1:
            field = selected[0]
            bound.append(
                BoundEnumValue(
                    table_id=field.table_id,
                    field_id=field.field_id,
                    field_key=field.key,
                    value=choice,
                    source_span=span,
                )
            )
        else:
            ordered = sorted(selected, key=lambda item: str(item.field_id))
            ambiguous.append(
                AmbiguousBinding(
                    mention=span.text,
                    kind="enum",
                    candidate_ids=tuple(str(item.field_id) for item in ordered),
                    candidate_labels=tuple(f"{item.key}:{choice}" for item in ordered),
                    source_span=span,
                )
            )
    return (
        tuple(
            sorted(bound, key=lambda item: (item.source_span.start, str(item.field_id)))
        ),
        tuple(sorted(ambiguous, key=lambda item: item.source_span.start)),
    )


def _nearest_mentioned_table_fields(
    enum_span: SourceSpan,
    fields: tuple[AuthorizedFieldSpec, ...],
    bound_tables: tuple[BoundTableMention, ...],
) -> tuple[AuthorizedFieldSpec, ...]:
    score_by_table: dict[UUID, tuple[int, int]] = {}
    candidate_table_ids = {item.table_id for item in fields}
    for mention in bound_tables:
        if mention.table_id not in candidate_table_ids:
            continue
        if mention.source_span.start >= enum_span.end:
            score = (mention.source_span.start - enum_span.end, 0)
        elif enum_span.start >= mention.source_span.end:
            score = (enum_span.start - mention.source_span.end, 1)
        else:
            score = (0, 0)
        previous = score_by_table.get(mention.table_id)
        if previous is None or score < previous:
            score_by_table[mention.table_id] = score
    if not score_by_table:
        return fields
    nearest_score = min(score_by_table.values())
    nearest_table_ids = {
        table_id
        for table_id, score in score_by_table.items()
        if score == nearest_score
    }
    if len(nearest_table_ids) != 1:
        return fields
    nearest_table_id = next(iter(nearest_table_ids))
    return tuple(item for item in fields if item.table_id == nearest_table_id)


def _bind_entities(
    lexical: LexicalQuery,
    entities: tuple[AuthorizedEntitySpec, ...],
) -> tuple[
    tuple[BoundEntityMention, ...],
    tuple[AmbiguousBinding, ...],
    tuple[UnresolvedMention, ...],
]:
    by_code: dict[str, list[AuthorizedEntitySpec]] = {}
    for entity in entities:
        by_code.setdefault(entity.code.casefold(), []).append(entity)
    bound: list[BoundEntityMention] = []
    ambiguous: list[AmbiguousBinding] = []
    unresolved: list[UnresolvedMention] = []
    occupied: set[tuple[int, int]] = {
        (token.source_span.start, token.source_span.end)
        for token in lexical.tokens
        if token.kind == "identifier"
    }
    for token in lexical.tokens:
        if token.kind != "identifier":
            continue
        code_candidates = by_code.get(token.canonical_value.casefold(), [])
        if not code_candidates:
            unresolved.append(
                UnresolvedMention(
                    text=token.source_span.text,
                    reason="unresolved_authorized_lookup_required",
                    source_span=token.source_span,
                )
            )
            continue
        elif len(code_candidates) == 1:
            entity = code_candidates[0]
            bound.append(
                BoundEntityMention(
                    entity_id=entity.entity_id,
                    table_id=entity.table_id,
                    code=entity.code,
                    mention=token.source_span.text,
                    match_kind="code",
                    source_span=token.source_span,
                )
            )
        else:
            ordered = sorted(code_candidates, key=lambda item: str(item.entity_id))
            ambiguous.append(
                AmbiguousBinding(
                    mention=token.source_span.text,
                    kind="entity",
                    candidate_ids=tuple(str(item.entity_id) for item in ordered),
                    candidate_labels=tuple(
                        f"{item.code}:{item.label}" for item in ordered
                    ),
                    source_span=token.source_span,
                )
            )

    alias_candidates: dict[
        tuple[int, int, str], list[tuple[AuthorizedEntitySpec, str]]
    ] = {}
    for entity in entities:
        for term, match_kind in (
            (entity.label, "label"),
            *((alias, "alias") for alias in entity.aliases),
        ):
            for start, end in _term_matches(lexical, term):
                span = _span(lexical, start, end)
                if any(
                    span.start < occupied_end and occupied_start < span.end
                    for occupied_start, occupied_end in occupied
                ):
                    continue
                alias_candidates.setdefault((start, end, term.casefold()), []).append(
                    (entity, match_kind)
                )
    for (start, end, _term), raw_candidates in alias_candidates.items():
        unique = {item[0].entity_id: item for item in raw_candidates}
        ordered = sorted(unique.values(), key=lambda item: str(item[0].entity_id))
        span = _span(lexical, start, end)
        if len(ordered) == 1:
            entity, match_kind = ordered[0]
            bound.append(
                BoundEntityMention(
                    entity_id=entity.entity_id,
                    table_id=entity.table_id,
                    code=entity.code,
                    mention=span.text,
                    match_kind=match_kind,
                    source_span=span,
                )
            )
        else:
            ambiguous.append(
                AmbiguousBinding(
                    mention=span.text,
                    kind="entity",
                    candidate_ids=tuple(str(item[0].entity_id) for item in ordered),
                    candidate_labels=tuple(
                        f"{item[0].code}:{item[0].label}" for item in ordered
                    ),
                    source_span=span,
                )
            )
    unique = {
        (item.entity_id, item.source_span.start, item.source_span.end): item
        for item in bound
    }
    return (
        tuple(sorted(unique.values(), key=lambda item: item.source_span.start)),
        tuple(sorted(ambiguous, key=lambda item: item.source_span.start)),
        tuple(unresolved),
    )


def _unresolved_field_phrases(
    lexical: LexicalQuery,
    *,
    bound_fields: tuple[BoundFieldMention, ...],
    ambiguities: tuple[AmbiguousBinding, ...],
) -> tuple[UnresolvedMention, ...]:
    occupied = {
        (item.source_span.start, item.source_span.end)
        for item in (*bound_fields, *ambiguities)
    }
    values: list[UnresolvedMention] = []
    pattern = re.compile(r"(?:(?<=和)|(?<=及)|(?<=、)|^)([^\s,;，；。和及]{1,12}字段)")
    for match in pattern.finditer(lexical.canonical.normalized_text):
        start, end = match.span(1)
        span = _span(lexical, start, end)
        if (span.start, span.end) in occupied:
            continue
        values.append(
            UnresolvedMention(
                text=span.text,
                reason="field_not_in_authorized_schema",
                source_span=span,
            )
        )
    return tuple(values)


def _term_matches(lexical: LexicalQuery, term: str) -> tuple[tuple[int, int], ...]:
    if not term:
        return ()
    boundary = r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])"
    pattern = (
        boundary.format(re.escape(term))
        if re.fullmatch(r"[A-Za-z0-9_]+", term)
        else re.escape(term)
    )
    return tuple(
        match.span()
        for match in re.finditer(
            pattern,
            lexical.canonical.normalized_text,
            re.IGNORECASE,
        )
    )


def _span(lexical: LexicalQuery, start: int, end: int) -> SourceSpan:
    mapping = lexical.canonical.normalized_to_source
    source_start = mapping[start]
    source_end = mapping[end - 1] + 1
    return SourceSpan(
        start=source_start,
        end=source_end,
        text=lexical.canonical.original_text[source_start:source_end],
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        dict.fromkeys(item for item in value if isinstance(item, str) and item)
    )


def _schema_scope_hash(
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
    table_ids: tuple[UUID, ...],
    employee_version: int,
    field_policy_version: str | None,
    field_policy_hash: str | None,
) -> str:
    payload = json.dumps(
        {
            "actor_id": actor.actor_id,
            "actor_role": actor.role,
            "employee_id": str(employee_id),
            "employee_version": employee_version,
            "field_policy_hash": field_policy_hash,
            "field_policy_version": field_policy_version,
            "table_ids": [str(item) for item in table_ids],
            "workspace_id": str(workspace_id),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


__all__ = [
    "AmbiguousBinding",
    "BoundEntityMention",
    "BoundEnumValue",
    "BoundFieldMention",
    "BoundTableMention",
    "SchemaBindingResult",
    "UnresolvedMention",
    "bind_lexical_query",
    "build_authorized_schema_snapshot",
    "build_authorized_relation_catalog",
]
