"""Canonical, authorization-filtered Stage12-D retrieval projections."""

from __future__ import annotations

from hashlib import sha256
import json
import math
import unicodedata
from typing import Mapping, Protocol
from uuid import UUID

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
)
from app.schemas.authorized_query_plan import AuthorizedRelationSpec
from app.schemas.retrieval_v2 import (
    RetrievalChunkV2,
    RetrievalProjectionV2,
    RetrievalRelationEdgeProjectionV2,
    canonical_retrieval_sha256,
)
from app.services.authorized_query_records import AuthorizedRecord


_MAX_CHUNKS_PER_PROJECTION = 1_000
_MAX_KEYWORD_TERMS = 256
_MAX_KEYWORD_TERM_CODE_POINTS = 64
_NON_TEXT_FIELD_TYPES = frozenset({"linked_record", "json", "formula", "lookup"})


class TokenCounter(Protocol):
    def encode(self, text: str) -> tuple[int, ...]: ...

    def decode(self, token_ids: tuple[int, ...]) -> str: ...


def build_schema_projections(
    snapshot: AuthorizedSchemaSnapshot,
    *,
    retrieval_scope_hash: str,
    field_positions: Mapping[UUID, int],
    retrievable_field_ids: frozenset[UUID],
    source_version: int = 1,
) -> tuple[RetrievalProjectionV2, ...]:
    _positive_source_version(source_version)
    visible = _visible_retrievable_fields(snapshot, retrievable_field_ids)
    projections: list[RetrievalProjectionV2] = []
    for table in sorted(
        snapshot.tables, key=lambda item: (item.key, str(item.table_id))
    ):
        fields = tuple(
            sorted(
                (field for field in table.fields if field.field_id in visible),
                key=lambda item: _field_order(item, field_positions),
            )
        )
        visibility_hash = _visibility_profile_hash(
            snapshot, fields, retrieval_scope_hash=retrieval_scope_hash
        )
        table_lines = [f"[table] {table.name}", f"[table_key] {table.key}"]
        if table.aliases:
            table_lines.append(f"[aliases] {' '.join(table.aliases)}")
        for field in fields:
            table_lines.extend(_schema_field_lines(field))
        projections.append(
            _projection(
                source_type="schema_table",
                source_id=f"schema-table:{table.table_id}",
                source_version=source_version,
                snapshot=snapshot,
                table=table,
                record_id=None,
                field_ids=tuple(field.field_id for field in fields),
                visibility_profile_hash=visibility_hash,
                retrieval_scope_hash=retrieval_scope_hash,
                canonical_text="\n".join(table_lines),
            )
        )
        for field in fields:
            projections.append(
                _projection(
                    source_type="schema_field",
                    source_id=f"schema-field:{field.field_id}",
                    source_version=source_version,
                    snapshot=snapshot,
                    table=table,
                    record_id=None,
                    field_ids=(field.field_id,),
                    visibility_profile_hash=visibility_hash,
                    retrieval_scope_hash=retrieval_scope_hash,
                    canonical_text="\n".join(
                        (f"[table] {table.name}", *_schema_field_lines(field))
                    ),
                )
            )
    return tuple(projections)


def build_record_projection(
    snapshot: AuthorizedSchemaSnapshot,
    record: AuthorizedRecord,
    *,
    retrieval_scope_hash: str,
    retrievable_field_ids: frozenset[UUID],
    long_text_field_ids: frozenset[UUID],
    field_positions: Mapping[UUID, int],
) -> RetrievalProjectionV2:
    table = _table(snapshot, record.table_id)
    fields = _table_field_map(table)
    values = {item.field_id: item.value for item in record.values}
    allowed = _record_allowed_fields(
        table,
        retrievable_field_ids=retrievable_field_ids,
        long_text_field_ids=long_text_field_ids,
    )
    ordered = sorted(allowed, key=lambda item: _field_order(item, field_positions))
    identity = _record_identity(table, values)
    lines = [f"[table] {table.name}", f"[record] {identity}"]
    rendered_field_ids: list[UUID] = []
    for field in ordered:
        if field.field_id not in values or field.field_id not in fields:
            continue
        rendered = _render_field_value(values[field.field_id])
        if rendered is None:
            continue
        lines.append(f"[{field.name}] {rendered}")
        rendered_field_ids.append(field.field_id)
    visibility_hash = _visibility_profile_hash(
        snapshot, allowed, retrieval_scope_hash=retrieval_scope_hash
    )
    return _projection(
        source_type="record",
        source_id=f"record:{record.record_id}",
        source_version=record.version,
        snapshot=snapshot,
        table=table,
        record_id=record.record_id,
        field_ids=tuple(rendered_field_ids),
        visibility_profile_hash=visibility_hash,
        retrieval_scope_hash=retrieval_scope_hash,
        canonical_text="\n".join(lines),
    )


def build_record_field_projections(
    snapshot: AuthorizedSchemaSnapshot,
    record: AuthorizedRecord,
    *,
    retrieval_scope_hash: str,
    retrievable_field_ids: frozenset[UUID],
    long_text_field_ids: frozenset[UUID],
) -> tuple[RetrievalProjectionV2, ...]:
    table = _table(snapshot, record.table_id)
    field_map = _table_field_map(table)
    values = {item.field_id: item.value for item in record.values}
    identity = _record_identity(table, values)
    allowed_ids = retrievable_field_ids & long_text_field_ids & set(field_map)
    visibility_hash = _visibility_profile_hash(
        snapshot,
        tuple(field_map[field_id] for field_id in allowed_ids),
        retrieval_scope_hash=retrieval_scope_hash,
    )
    projections: list[RetrievalProjectionV2] = []
    for field_id in sorted(allowed_ids, key=str):
        field = field_map[field_id]
        if field.field_type != "text":
            continue
        rendered = _render_field_value(values.get(field_id))
        if rendered is None:
            continue
        projections.append(
            _projection(
                source_type="record_field",
                source_id=f"record-field:{record.record_id}:{field_id}",
                source_version=record.version,
                snapshot=snapshot,
                table=table,
                record_id=record.record_id,
                field_ids=(field_id,),
                visibility_profile_hash=visibility_hash,
                retrieval_scope_hash=retrieval_scope_hash,
                canonical_text=(
                    f"[table] {table.name}\n"
                    f"[record] {identity}\n"
                    f"[field] {field.name}\n"
                    f"{rendered}"
                ),
            )
        )
    return tuple(projections)


def build_relation_projections(
    snapshot: AuthorizedSchemaSnapshot,
    *,
    retrieval_scope_hash: str,
    records: tuple[AuthorizedRecord, ...],
    catalog: tuple[AuthorizedRelationSpec, ...],
) -> tuple[RetrievalRelationEdgeProjectionV2, ...]:
    table_ids = {table.table_id for table in snapshot.tables}
    record_by_id = {record.record_id: record for record in records}
    records_by_table: dict[UUID, list[AuthorizedRecord]] = {}
    for record in records:
        if record.table_id in table_ids:
            records_by_table.setdefault(record.table_id, []).append(record)
    visibility_hash = _relation_visibility_profile_hash(
        snapshot, catalog, retrieval_scope_hash=retrieval_scope_hash
    )
    edges: list[RetrievalRelationEdgeProjectionV2] = []
    for relation in sorted(catalog, key=lambda item: item.relation_id):
        if (
            relation.link_source_table_id not in table_ids
            or relation.link_target_table_id not in table_ids
        ):
            continue
        for source in sorted(
            records_by_table.get(relation.link_source_table_id, ()),
            key=lambda item: str(item.record_id),
        ):
            values = {item.field_id: item.value for item in source.values}
            for target_id in _linked_record_ids(values.get(relation.link_field_id)):
                target = record_by_id.get(target_id)
                if target is None or target.table_id != relation.link_target_table_id:
                    continue
                values_without_hash: dict[str, object] = {
                    "version": "retrieval-relation-edge.v2",
                    "relation_id": relation.relation_id,
                    "source_table_id": source.table_id,
                    "source_record_id": source.record_id,
                    "link_field_id": relation.link_field_id,
                    "target_table_id": target.table_id,
                    "target_record_id": target.record_id,
                    "direction": "forward",
                    "source_version": source.version,
                    "target_version": target.version,
                    "visibility_profile_hash": visibility_hash,
                    "scope_hash": retrieval_scope_hash,
                }
                edges.append(
                    RetrievalRelationEdgeProjectionV2(
                        **values_without_hash,
                        edge_hash=canonical_retrieval_sha256(values_without_hash),
                    )
                )
    return tuple(
        sorted(
            edges,
            key=lambda item: (
                item.relation_id,
                str(item.source_record_id),
                str(item.target_record_id),
            ),
        )
    )


def chunk_projection(
    projection: RetrievalProjectionV2,
    *,
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int = 32,
) -> tuple[RetrievalChunkV2, ...]:
    if (
        isinstance(max_tokens, bool)
        or not isinstance(max_tokens, int)
        or max_tokens < 1
        or isinstance(overlap_tokens, bool)
        or not isinstance(overlap_tokens, int)
        or overlap_tokens < 0
        or overlap_tokens >= max_tokens
    ):
        raise ValueError("retrieval_chunk_budget_invalid")
    token_ids = token_counter.encode(projection.canonical_text)
    if not token_ids:
        raise ValueError("retrieval_chunk_tokens_empty")
    step = max_tokens - overlap_tokens
    chunk_count = (
        1
        if len(token_ids) <= max_tokens
        else math.ceil((len(token_ids) - max_tokens) / step) + 1
    )
    if chunk_count > _MAX_CHUNKS_PER_PROJECTION:
        raise ValueError("retrieval_chunk_count_exceeded")
    chunks: list[RetrievalChunkV2] = []
    for ordinal in range(chunk_count):
        start = ordinal * step
        end = min(start + max_tokens, len(token_ids))
        chunk_text = _canonical_text(token_counter.decode(token_ids[start:end]))
        chunks.append(
            RetrievalChunkV2(
                version="retrieval-chunk.v2",
                source_type=projection.source_type,
                source_id=projection.source_id,
                source_version=projection.source_version,
                ordinal=ordinal,
                chunk_kind=(
                    "long_field"
                    if projection.source_type == "record_field"
                    else "canonical"
                ),
                table_id=projection.table_id,
                record_id=projection.record_id,
                field_ids=projection.field_ids,
                start_token=start,
                end_token=end,
                visibility_profile_hash=projection.visibility_profile_hash,
                scope_hash=projection.scope_hash,
                content_hash=sha256(chunk_text.encode("utf-8")).hexdigest(),
                chunk_text=chunk_text,
                keyword_terms=_keyword_terms(chunk_text),
            )
        )
    return tuple(chunks)


def _projection(
    *,
    source_type: str,
    source_id: str,
    source_version: int,
    snapshot: AuthorizedSchemaSnapshot,
    table: AuthorizedTableSpec,
    record_id: UUID | None,
    field_ids: tuple[UUID, ...],
    visibility_profile_hash: str,
    retrieval_scope_hash: str,
    canonical_text: str,
) -> RetrievalProjectionV2:
    canonical = _canonical_text(canonical_text)
    return RetrievalProjectionV2(
        version="retrieval-projection.v2",
        source_type=source_type,
        source_id=source_id,
        source_version=source_version,
        workspace_id=snapshot.workspace_id,
        base_id=table.base_id,
        table_id=table.table_id,
        record_id=record_id,
        field_ids=tuple(sorted(set(field_ids), key=str)),
        visibility_profile_hash=visibility_profile_hash,
        scope_hash=retrieval_scope_hash,
        content_hash=sha256(canonical.encode("utf-8")).hexdigest(),
        canonical_text=canonical,
    )


def _visible_retrievable_fields(
    snapshot: AuthorizedSchemaSnapshot,
    retrievable_field_ids: frozenset[UUID],
) -> frozenset[UUID]:
    visible = {field.field_id for table in snapshot.tables for field in table.fields}
    return frozenset(visible & retrievable_field_ids)


def _record_allowed_fields(
    table: AuthorizedTableSpec,
    *,
    retrievable_field_ids: frozenset[UUID],
    long_text_field_ids: frozenset[UUID],
) -> tuple[AuthorizedFieldSpec, ...]:
    return tuple(
        field
        for field in table.fields
        if field.field_id in retrievable_field_ids
        and field.field_id not in long_text_field_ids
        and field.field_type not in _NON_TEXT_FIELD_TYPES
    )


def _schema_field_lines(field: AuthorizedFieldSpec) -> tuple[str, ...]:
    lines = [
        f"[field] {field.name}",
        f"[field_key] {field.key}",
        f"[field_type] {field.field_type}",
    ]
    if field.aliases:
        lines.append(f"[field_aliases] {' '.join(field.aliases)}")
    if field.choices:
        lines.append(f"[enum_values] {' '.join(field.choices)}")
    return tuple(lines)


def _field_order(
    field: AuthorizedFieldSpec,
    positions: Mapping[UUID, int],
) -> tuple[int, str, str]:
    position = positions.get(field.field_id)
    if isinstance(position, bool) or not isinstance(position, int) or position < 0:
        position = 2**31 - 1
    return position, field.key, str(field.field_id)


def _table(
    snapshot: AuthorizedSchemaSnapshot,
    table_id: UUID,
) -> AuthorizedTableSpec:
    table = next(
        (item for item in snapshot.tables if item.table_id == table_id),
        None,
    )
    if table is None:
        raise ValueError("retrieval_projection_table_unknown")
    return table


def _table_field_map(table: AuthorizedTableSpec) -> dict[UUID, AuthorizedFieldSpec]:
    return {field.field_id: field for field in table.fields}


def _record_identity(
    table: AuthorizedTableSpec,
    values: Mapping[UUID, object],
) -> str:
    raw = values.get(table.identity_field_id) if table.identity_field_id else None
    identity = _render_field_value(raw)
    return identity if identity is not None else "authorized-record"


def _render_field_value(value: object) -> str | None:
    if value is None or isinstance(value, UUID):
        return None
    if isinstance(value, str):
        rendered = _canonical_inline_text(value)
        try:
            UUID(rendered)
        except (ValueError, AttributeError):
            return rendered or None
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    if isinstance(value, (tuple, list)):
        parts = tuple(
            rendered
            for item in value
            if (rendered := _render_field_value(item)) is not None
        )
        return ", ".join(parts) if parts else None
    return None


def _linked_record_ids(value: object) -> tuple[UUID, ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    result: set[UUID] = set()
    for item in value:
        raw_id = item.get("id") if isinstance(item, Mapping) else item
        try:
            result.add(UUID(str(raw_id)))
        except (TypeError, ValueError, AttributeError):
            continue
    return tuple(sorted(result, key=str))


def _visibility_profile_hash(
    snapshot: AuthorizedSchemaSnapshot,
    fields: tuple[AuthorizedFieldSpec, ...],
    *,
    retrieval_scope_hash: str,
) -> str:
    return canonical_retrieval_sha256(
        {
            "workspace_id": snapshot.workspace_id,
            "employee_id": snapshot.employee_id,
            "scope_hash": retrieval_scope_hash,
            "field_ids": tuple(sorted((field.field_id for field in fields), key=str)),
        }
    )


def _relation_visibility_profile_hash(
    snapshot: AuthorizedSchemaSnapshot,
    catalog: tuple[AuthorizedRelationSpec, ...],
    *,
    retrieval_scope_hash: str,
) -> str:
    return canonical_retrieval_sha256(
        {
            "workspace_id": snapshot.workspace_id,
            "employee_id": snapshot.employee_id,
            "scope_hash": retrieval_scope_hash,
            "relation_ids": tuple(sorted(item.relation_id for item in catalog)),
        }
    )


def _canonical_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("retrieval_projection_text_invalid")
    normalized = unicodedata.normalize(
        "NFC",
        text.replace("\r\n", "\n").replace("\r", "\n"),
    )
    safe = "".join(
        character
        for character in normalized
        if ord(character) >= 0x20 or character in {"\n", "\t"}
    ).strip()
    if not safe:
        raise ValueError("retrieval_projection_text_empty")
    return safe


def _canonical_inline_text(text: str) -> str:
    return " ".join(_canonical_text(text).split())


def _keyword_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    index = 0
    while index < len(text) and len(terms) < _MAX_KEYWORD_TERMS:
        character = text[index]
        if _is_cjk(character):
            end = index + 1
            while end < len(text) and _is_cjk(text[end]):
                end += 1
            sequence = text[index:end]
            for offset in range(len(sequence) - 1):
                _append_term(sequence[offset : offset + 2], terms, seen)
            index = end
            continue
        if _is_latin_or_digit(character):
            end = index + 1
            while end < len(text) and _is_latin_or_digit(text[end]):
                end += 1
            _append_term(
                text[index:end].casefold()[:_MAX_KEYWORD_TERM_CODE_POINTS],
                terms,
                seen,
            )
            index = end
            continue
        index += 1
    return tuple(terms)


def _append_term(term: str, terms: list[str], seen: set[str]) -> None:
    if term and term not in seen and len(terms) < _MAX_KEYWORD_TERMS:
        terms.append(term)
        seen.add(term)


def _is_cjk(character: str) -> bool:
    code_point = ord(character)
    return (
        0x3400 <= code_point <= 0x4DBF
        or 0x4E00 <= code_point <= 0x9FFF
        or 0xF900 <= code_point <= 0xFAFF
        or 0x20000 <= code_point <= 0x2FA1F
        or 0x30000 <= code_point <= 0x323AF
    )


def _is_latin_or_digit(character: str) -> bool:
    return character.isdecimal() or "LATIN" in unicodedata.name(character, "")


def _positive_source_version(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("retrieval_projection_source_version_invalid")
