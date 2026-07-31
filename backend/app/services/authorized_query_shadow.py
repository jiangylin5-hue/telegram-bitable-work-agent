"""Default-off, allowlisted and sanitized Stage12-C shadow observation."""

from __future__ import annotations

from time import perf_counter_ns
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from app.core.config import Settings
from app.schemas.agent_task_spec_v2 import Sha256Hex, TaskSpecArtifact
from app.services.agent_schema_binding import build_authorized_relation_catalog
from app.services.authorized_query_compiler import compile_authorized_query_plan
from app.services.authorized_table_query import execute_authorized_query
from app.services.permissions import Actor
from app.services.stage06_platform import Stage06PlatformUnitOfWork


_SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")


class AuthorizedQueryShadowObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["authorized-query-shadow-observation.v1"]
    status: Literal["observed", "shadow_failed"]
    task_spec_hash: Sha256Hex
    plan_hashes: tuple[Sha256Hex, ...]
    result_hashes: tuple[Sha256Hex, ...]
    query_intent_count: StrictInt
    result_record_count: StrictInt
    group_count: StrictInt
    aggregate_count: StrictInt
    relation_path_count: StrictInt
    source_version_count: StrictInt
    scanned_record_count: StrictInt
    traversed_edge_count: StrictInt
    duration_ms: StrictInt
    error_code: StrictStr | None
    scope_hash: Sha256Hex


def authorized_query_shadow_enabled(
    settings: Settings,
    workspace_id: UUID,
) -> bool:
    return settings.authorized_query_engine_v1_mode == "shadow" and str(
        workspace_id
    ) in set(settings.authorized_query_engine_v1_workspace_allowlist)


def run_authorized_query_shadow(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    workspace_id: UUID,
    employee_id: UUID,
    snapshot: object,
    task_artifact: TaskSpecArtifact,
    authorized_view_ids: tuple[UUID, ...],
) -> AuthorizedQueryShadowObservationV1:
    """Compile and execute V2 query intents without exposing result content."""

    started = perf_counter_ns()
    query_intents = task_artifact.task_spec.query_intents
    try:
        relations = build_authorized_relation_catalog(uow, snapshot)
        artifacts = tuple(
            execute_authorized_query(
                uow,
                actor=actor,
                workspace_id=workspace_id,
                employee_id=employee_id,
                chat_view_ids=authorized_view_ids,
                snapshot=snapshot,
                plan=compile_authorized_query_plan(
                    task_spec=task_artifact.task_spec,
                    query_intent_id=intent.query_intent_id,
                    snapshot=snapshot,
                    relations=relations,
                    authorized_view_ids=authorized_view_ids,
                ),
                allow_whole_table=False,
            )
            for intent in query_intents
        )
        results = tuple(item.result for item in artifacts)
        return AuthorizedQueryShadowObservationV1(
            version="authorized-query-shadow-observation.v1",
            status="observed",
            task_spec_hash=task_artifact.content_hash,
            plan_hashes=tuple(item.plan_hash for item in artifacts),
            result_hashes=tuple(item.result_hash for item in results),
            query_intent_count=len(query_intents),
            result_record_count=sum(len(item.records) for item in results),
            group_count=sum(len(item.groups) for item in results),
            aggregate_count=sum(len(item.aggregates) for item in results),
            relation_path_count=sum(len(item.relation_paths) for item in results),
            source_version_count=sum(len(item.source_versions) for item in results),
            scanned_record_count=sum(item.scanned_record_count for item in results),
            traversed_edge_count=sum(item.traversed_edge_count for item in results),
            duration_ms=_elapsed_ms(started),
            error_code=None,
            scope_hash=snapshot.scope_hash,
        )
    except Exception as exc:  # Shadow failure cannot affect authoritative dispatch.
        return AuthorizedQueryShadowObservationV1(
            version="authorized-query-shadow-observation.v1",
            status="shadow_failed",
            task_spec_hash=task_artifact.content_hash,
            plan_hashes=(),
            result_hashes=(),
            query_intent_count=len(query_intents),
            result_record_count=0,
            group_count=0,
            aggregate_count=0,
            relation_path_count=0,
            source_version_count=0,
            scanned_record_count=0,
            traversed_edge_count=0,
            duration_ms=_elapsed_ms(started),
            error_code=_safe_error_code(exc),
            scope_hash=snapshot.scope_hash,
        )


def _safe_error_code(exc: Exception) -> str:
    candidate = getattr(exc, "code", None)
    if not isinstance(candidate, str):
        candidate = str(exc)
    return (
        candidate
        if _SAFE_ERROR_CODE.fullmatch(candidate)
        else "authorized_query_shadow_failure"
    )


def _elapsed_ms(started: int) -> int:
    return max(0, (perf_counter_ns() - started) // 1_000_000)


__all__ = [
    "AuthorizedQueryShadowObservationV1",
    "authorized_query_shadow_enabled",
    "run_authorized_query_shadow",
]
