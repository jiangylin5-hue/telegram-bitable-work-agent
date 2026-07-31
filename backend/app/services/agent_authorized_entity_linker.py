"""Generic, authorization-first entity candidates for Stage12 Planner V2."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from app.schemas.agent_task_spec_v2 import (
    AuthorizedEntitySpec,
    AuthorizedSchemaSnapshot,
)
from app.services.authorized_query_records import (
    AuthorizedQueryDenied,
    build_authorized_query_context,
    scan_authorized_records,
)
from app.services.permissions import Actor
from app.services.stage06_platform import Stage06PlatformUnitOfWork


_MAX_ENTITY_CANDIDATES = 128


def build_authorized_entity_candidates(
    uow: Stage06PlatformUnitOfWork,
    *,
    query: str,
    actor: Actor,
    workspace_id: UUID,
    base_id: UUID,
    employee_id: UUID,
    snapshot: AuthorizedSchemaSnapshot,
    chat_authorized_view_ids: tuple[UUID, ...] | None,
    allow_whole_table: bool,
    max_candidates: int = _MAX_ENTITY_CANDIDATES,
) -> tuple[AuthorizedEntitySpec, ...]:
    """Return only query-mentioned entities visible in the effective scope."""

    if not query or query != query.strip() or max_candidates < 1 or max_candidates > 512:
        raise AuthorizedQueryDenied("authorized_entity_linker_request_invalid")
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace_id,
        base_id=base_id,
        employee_id=employee_id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=chat_authorized_view_ids,
        allow_whole_table=allow_whole_table,
    )
    normalized_query = query.casefold()
    candidates: list[AuthorizedEntitySpec] = []
    for table in snapshot.tables:
        if table.identity_field_id is None:
            continue
        label_field_id = table.label_field_id or table.identity_field_id
        required_field_ids = tuple(
            sorted(
                {
                    table.identity_field_id,
                    label_field_id,
                    *table.alias_field_ids,
                },
                key=str,
            )
        )
        records = scan_authorized_records(
            context=context,
            table_id=table.table_id,
            required_field_ids=required_field_ids,
        )
        for record in records.records:
            values = {item.field_id: item.value for item in record.values}
            code = _scalar_identity(values.get(table.identity_field_id))
            if code is None:
                continue
            label = _scalar_identity(values.get(label_field_id)) or code
            aliases = tuple(
                dict.fromkeys(
                    alias
                    for field_id in table.alias_field_ids
                    for alias in _alias_values(values.get(field_id))
                    if alias not in {code, label}
                )
            )
            if not any(
                _query_mentions(normalized_query, value)
                for value in (code, label, *aliases)
            ):
                continue
            candidates.append(
                AuthorizedEntitySpec(
                    entity_id=record.record_id,
                    table_id=table.table_id,
                    code=code,
                    label=label,
                    aliases=aliases,
                )
            )
            if len(candidates) > max_candidates:
                raise AuthorizedQueryDenied(
                    "authorized_entity_linker_candidate_budget_exceeded"
                )
    return tuple(
        sorted(candidates, key=lambda item: (item.code.casefold(), str(item.entity_id)))
    )


def _scalar_identity(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _alias_values(value: object) -> Iterable[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return () if not stripped else (stripped,)
    if isinstance(value, (list, tuple)):
        return tuple(
            stripped
            for item in value
            if isinstance(item, str) and (stripped := item.strip())
        )
    return ()


def _query_mentions(normalized_query: str, value: str) -> bool:
    normalized = value.casefold().strip()
    return len(normalized) >= 2 and normalized in normalized_query


__all__ = ["build_authorized_entity_candidates"]
