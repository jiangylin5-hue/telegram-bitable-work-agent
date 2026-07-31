"""Effective Stage12 Retrieval V2 authority-scope proof."""

from __future__ import annotations

import re
from uuid import UUID

from app.schemas.retrieval_v2 import canonical_retrieval_sha256
from app.services.authorized_query_records import AuthorizedQueryContext


class EffectiveRetrievalScopeError(ValueError):
    """The view/whole-table scope cannot form a valid retrieval authority."""


def build_effective_retrieval_scope_hash(
    *,
    schema_scope_hash: str,
    scope_view_ids: tuple[UUID, ...],
    allow_whole_table: bool,
) -> str:
    if not isinstance(schema_scope_hash, str) or re.fullmatch(
        r"[0-9a-f]{64}", schema_scope_hash
    ) is None:
        raise EffectiveRetrievalScopeError("retrieval_scope_schema_hash_invalid")
    if type(allow_whole_table) is not bool or any(
        not isinstance(view_id, UUID) for view_id in scope_view_ids
    ):
        raise EffectiveRetrievalScopeError("retrieval_scope_contract_invalid")
    if len(set(scope_view_ids)) != len(scope_view_ids):
        raise EffectiveRetrievalScopeError("retrieval_scope_view_duplicate")
    if allow_whole_table == bool(scope_view_ids):
        raise EffectiveRetrievalScopeError("retrieval_scope_boundary_invalid")
    ordered_view_ids = tuple(sorted(scope_view_ids, key=str))
    return canonical_retrieval_sha256(
        {
            "version": "effective-retrieval-scope.v1",
            "schema_scope_hash": schema_scope_hash,
            "scope_view_ids": ordered_view_ids,
            "allow_whole_table": allow_whole_table,
        }
    )


def effective_retrieval_scope_hash(context: AuthorizedQueryContext) -> str:
    return build_effective_retrieval_scope_hash(
        schema_scope_hash=context.snapshot.scope_hash,
        scope_view_ids=context.scope_view_ids,
        allow_whole_table=context.allow_whole_table,
    )


__all__ = [
    "EffectiveRetrievalScopeError",
    "build_effective_retrieval_scope_hash",
    "effective_retrieval_scope_hash",
]
