from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from typing import Literal
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import and_, cast, or_, select

from app.models.stage06_platform import (
    BitableBase,
    PlatformField,
    PlatformRecord,
    PlatformTable,
    PlatformView,
    RecordLink,
    ViewMemberGrant,
    Workspace,
    WorkspaceMember,
)
from app.models.stage06_runtime import DigitalEmployee, DigitalEmployeeMemberGrant
from app.models.stage08_knowledge import (
    Stage08KnowledgeChunk,
    Stage08KnowledgeSource,
)
from app.models.stage08_memory import Stage08MemoryItem
from app.runtime.stage08_context_contracts import ResolvedBusinessScope
from app.runtime.stage08_memory_contracts import MemoryScopeProjection, MemorySourceRef
from app.runtime.stage08_retrieval_contracts import (
    RetrievalSafeCitation,
    RetrievalSafeSourceView,
    RetrievalSafeView,
    RetrievalScopeCategory,
    RetrievalSourceTypeCategory,
    validate_retrieval_safe_citation,
    validate_retrieval_safe_view,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
    get_table_schema,
    get_view_presentation,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)
from app.services.stage08_context import resolve_business_scope
from app.services.stage08_memory import read_memory_projection
from app.services.stage08_retrieval_chunking import (
    canonicalize_knowledge_text,
    chunk_knowledge_projection,
)
from app.services.stage08_retrieval_embeddings import (
    TEST_EMBEDDING_DIMENSION,
    TEST_EMBEDDING_PROFILE,
    TEST_EMBEDDING_VERSION,
    EmbeddingProvider,
    EmbeddingProviderUnavailable,
)


_AUTHORITY_ISSUER = object()
_RESULT_ISSUER = object()
_EVIDENCE_ISSUER = object()
_SOURCE_TYPES = frozenset(
    {"memory_item", "document_projection", "approved_summary"}
)
_SCOPE_KEYS = frozenset(
    {
        "workspace_id",
        "base_id",
        "table_id",
        "view_id",
        "field_id",
        "customer_record_id",
        "project_record_id",
    }
)
_MEMORY_SOURCE_REF_KEYS = frozenset(
    {"memory_item_id", "memory_item_version"}
)


@dataclass(frozen=True, slots=True)
class _AuthoritySnapshot:
    workspace_id: UUID
    employee_id: UUID
    employee_version: int
    actor_id: str
    actor_role: str
    actor_customer_ids: frozenset[str]
    member_id: UUID
    member_version: int
    base_id: UUID
    table_ids: tuple[UUID, ...]
    view_versions: tuple[tuple[UUID, int], ...]
    access_mode: str
    grant_member_ids: tuple[UUID, ...]
    business_scope: ResolvedBusinessScope


@dataclass(frozen=True, slots=True)
class _ValidatedScope:
    category: RetrievalScopeCategory
    workspace_id: UUID
    base_id: UUID | None
    table_id: UUID | None
    view_id: UUID | None
    field_id: UUID | None
    customer_record_id: UUID | None
    project_record_id: UUID | None


class _HitSnapshot:
    __slots__ = (
        "source_id",
        "source_version",
        "source_hash",
        "chunk_id",
        "chunk_hash",
        "chunk_text",
        "source_type_category",
        "scope_category",
        "keyword_score",
        "vector_score",
        "combined_score",
        "stable_order",
    )

    def __init__(
        self,
        *,
        source_id: UUID,
        source_version: int,
        source_hash: str,
        chunk_id: UUID,
        chunk_hash: str,
        chunk_text: str,
        source_type_category: RetrievalSourceTypeCategory,
        scope_category: RetrievalScopeCategory,
        keyword_score: float,
        vector_score: float | None,
        combined_score: float,
        stable_order: tuple[str, ...],
    ) -> None:
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "source_version", source_version)
        object.__setattr__(self, "source_hash", source_hash)
        object.__setattr__(self, "chunk_id", chunk_id)
        object.__setattr__(self, "chunk_hash", chunk_hash)
        object.__setattr__(self, "chunk_text", chunk_text)
        object.__setattr__(self, "source_type_category", source_type_category)
        object.__setattr__(self, "scope_category", scope_category)
        object.__setattr__(self, "keyword_score", keyword_score)
        object.__setattr__(self, "vector_score", vector_score)
        object.__setattr__(self, "combined_score", combined_score)
        object.__setattr__(self, "stable_order", stable_order)

    def __repr__(self) -> str:
        return "<Stage08PrivateRetrievalHit opaque>"

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("retrieval_hit_opaque")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("retrieval_hit_unavailable")


@dataclass(frozen=True, slots=True)
class _ResultSnapshot:
    authority: _Stage08RetrievalAuthority
    hits: tuple[_HitSnapshot, ...]
    status: Literal["ready", "degraded", "unavailable", "empty", "failed"]
    degradation_code: Literal["none", "keyword_only", "embedding_unavailable"]
    error_code: Literal[
        "none",
        "retrieval_unavailable",
        "source_revalidation_failed",
        "authority_changed",
        "scope_mismatch",
        "index_unavailable",
    ]


class _Stage08RetrievalAuthority:
    """Opaque, non-serializable authority. Only the factory owns the seal."""

    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if cls is not _Stage08RetrievalAuthority or issuer is not _AUTHORITY_ISSUER:
            raise TypeError("retrieval_authority_unavailable")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name == "__class__":
            return _Stage08RetrievalAuthority
        raise AttributeError("retrieval_authority_opaque")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("retrieval_authority_opaque")

    def __repr__(self) -> str:
        return "<Stage08RetrievalAuthority opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("retrieval_authority_unavailable")


class _Stage08RetrievalResult:
    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if cls is not _Stage08RetrievalResult or issuer is not _RESULT_ISSUER:
            raise TypeError("retrieval_result_unavailable")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name == "__class__":
            return _Stage08RetrievalResult
        raise AttributeError("retrieval_result_opaque")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("retrieval_result_opaque")

    def __repr__(self) -> str:
        return "<Stage08RetrievalResult opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("retrieval_result_unavailable")


class _Stage08PrivateEvidence:
    __slots__ = ("_sealed_evidence",)

    def __new__(cls, issuer: object = None, evidence: object = None):
        if cls is not _Stage08PrivateEvidence or issuer is not _EVIDENCE_ISSUER:
            raise TypeError("retrieval_evidence_unavailable")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_evidence", evidence)
        return instance

    def __init__(self, issuer: object = None, evidence: object = None) -> None:
        del issuer, evidence

    def __getattribute__(self, name: str):
        if name == "__class__":
            return _Stage08PrivateEvidence
        raise AttributeError("retrieval_evidence_opaque")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("retrieval_evidence_opaque")

    def __repr__(self) -> str:
        return "<Stage08PrivateEvidence opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("retrieval_evidence_unavailable")


def _stage08_private_evidence_fragments(value: object) -> tuple[str, ...]:
    """F-provider-only process-local projection of already-authorized evidence."""

    if type(value) is not _Stage08PrivateEvidence:
        raise TypeError("retrieval_evidence_unavailable")
    try:
        evidence = object.__getattribute__(value, "_sealed_evidence")
    except (AttributeError, TypeError):
        raise TypeError("retrieval_evidence_unavailable") from None
    if (
        type(evidence) is not tuple
        or not 1 <= len(evidence) <= 12
        or any(
            type(fragment) is not str or not fragment.strip()
            for fragment in evidence
        )
    ):
        raise TypeError("retrieval_evidence_unavailable")
    return evidence


class Stage08RetrievalAuthorityFactory:
    @staticmethod
    def build(
        uow: Stage06PlatformUnitOfWork,
        *,
        actor: Actor,
        workspace_id: UUID,
        employee_id: UUID,
        customer_record_id: UUID | None = None,
        project_record_id: UUID | None = None,
    ) -> _Stage08RetrievalAuthority:
        try:
            snapshot = _build_authority_snapshot(
                uow,
                actor=actor,
                workspace_id=workspace_id,
                employee_id=employee_id,
                customer_record_id=customer_record_id,
                project_record_id=project_record_id,
            )
        except Exception:
            snapshot = None
        return _Stage08RetrievalAuthority(_AUTHORITY_ISSUER, snapshot)


class PostgresRetrievalProvider:
    """PostgreSQL-truth retrieval with an explicit test-only vector injection."""

    def __init__(self, *, embedding_provider: EmbeddingProvider | None = None) -> None:
        self._embedding_provider = embedding_provider

    def search(
        self,
        uow: Stage06PlatformUnitOfWork,
        authority: object,
        *,
        query: object,
        limit: object,
        now: datetime,
    ) -> _Stage08RetrievalResult:
        snapshot = _authority_snapshot(authority)
        if snapshot is None or _revalidate_authority(uow, snapshot) is None:
            return _result(
                authority,
                status="unavailable",
                degradation_code="none",
                error_code="authority_changed",
            )
        canonical_query = _validated_query(query)
        if canonical_query is None or not _valid_limit(limit) or not _valid_now(now):
            return _result(
                authority,
                status="failed",
                degradation_code="none",
                error_code="retrieval_unavailable",
            )
        query_terms = _query_terms(canonical_query)
        if not query_terms:
            return _result(
                authority,
                status="empty",
                degradation_code="keyword_only",
                error_code="none",
            )
        query_vector = _query_embedding(self._embedding_provider, canonical_query)
        candidates: list[_HitSnapshot] = []
        for source, chunk in _candidate_rows(
            uow,
            snapshot,
            now,
            query_terms=query_terms,
            query_vector=query_vector,
        ):
            try:
                validated = _validate_current_candidate(
                    uow,
                    snapshot,
                    source,
                    chunk,
                    now=now,
                )
            except Exception:
                validated = None
            if validated is None:
                continue
            scope, source_type_category = validated
            keyword_score = _keyword_score(query_terms, chunk.keyword_terms)
            vector_score = _vector_score(query_vector, chunk)
            if keyword_score <= 0.0 and vector_score is None:
                continue
            if query_vector is None:
                combined_score = keyword_score
            elif vector_score is None:
                combined_score = keyword_score * 0.60
            else:
                combined_score = keyword_score * 0.60 + vector_score * 0.40
            candidates.append(
                _HitSnapshot(
                    source_id=source.id,
                    source_version=source.content_version,
                    source_hash=source.projection_hash,
                    chunk_id=chunk.id,
                    chunk_hash=chunk.chunk_hash,
                    chunk_text=chunk.chunk_text or "",
                    source_type_category=source_type_category,
                    scope_category=scope.category,
                    keyword_score=keyword_score,
                    vector_score=vector_score,
                    combined_score=combined_score,
                    stable_order=(
                        source.source_type,
                        source.logical_source_fingerprint,
                        str(source.content_version),
                        f"{chunk.ordinal:08d}",
                        str(chunk.id),
                    ),
                )
            )
        candidates.sort(
            key=lambda hit: (
                -hit.combined_score,
                -hit.keyword_score,
                -(hit.vector_score if hit.vector_score is not None else -1.0),
                hit.stable_order,
            )
        )
        selected = tuple(candidates[: int(limit)])
        if not selected:
            return _result(
                authority,
                status="empty",
                degradation_code="keyword_only" if query_vector is None else "none",
                error_code="none",
            )
        used_vector = query_vector is not None and any(
            hit.vector_score is not None for hit in selected
        )
        return _result(
            authority,
            hits=selected,
            status="ready" if used_vector else "degraded",
            degradation_code="none" if used_vector else "keyword_only",
            error_code="none",
        )

    def render_private_evidence(
        self,
        uow: Stage06PlatformUnitOfWork,
        result: object,
        *,
        now: datetime,
    ) -> _Stage08PrivateEvidence | None:
        _, hits = _revalidated_result_hits(uow, result, now=now)
        if not hits:
            return None
        return _Stage08PrivateEvidence(
            _EVIDENCE_ISSUER,
            tuple(hit.chunk_text for hit in hits),
        )

    def safe_citations(
        self,
        uow: Stage06PlatformUnitOfWork,
        result: object,
        *,
        now: datetime,
    ) -> tuple[RetrievalSafeCitation, ...]:
        _, hits = _revalidated_result_hits(uow, result, now=now)
        return tuple(
            validate_retrieval_safe_citation(
                RetrievalSafeCitation(
                    display_ordinal=index,
                    label="retrieved_material",
                    source_type_category=hit.source_type_category,
                    scope_category=hit.scope_category,
                )
            )
            for index, hit in enumerate(hits, start=1)
        )

    def safe_view(
        self,
        uow: Stage06PlatformUnitOfWork,
        result: object,
        *,
        now: datetime,
    ) -> RetrievalSafeView:
        result_snapshot, hits = _revalidated_result_hits(uow, result, now=now)
        if result_snapshot is None:
            return _safe_view_model(
                status="unavailable",
                hits=(),
                degradation_code="none",
                error_code="authority_changed",
            )
        if result_snapshot.status == "failed":
            return _safe_view_model(
                status="failed",
                hits=(),
                degradation_code=result_snapshot.degradation_code,
                error_code=result_snapshot.error_code,
            )
        if _revalidate_authority(
            uow, _authority_snapshot(result_snapshot.authority)
        ) is None:
            return _safe_view_model(
                status="unavailable",
                hits=(),
                degradation_code="none",
                error_code="authority_changed",
            )
        if not hits:
            return _safe_view_model(
                status="empty",
                hits=(),
                degradation_code=result_snapshot.degradation_code,
                error_code=(
                    "source_revalidation_failed"
                    if result_snapshot.hits
                    else result_snapshot.error_code
                ),
            )
        return _safe_view_model(
            status=result_snapshot.status,
            hits=hits,
            degradation_code=result_snapshot.degradation_code,
            error_code="none",
        )


def _fresh_scalars(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    statement: object,
) -> tuple[object, ...]:
    with uow.session.no_autoflush:
        refreshed = statement.execution_options(  # type: ignore[attr-defined]
            populate_existing=True,
            autoflush=False,
        )
        return tuple(uow.session.scalars(refreshed))


def _fresh_one(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    statement: object,
) -> object | None:
    rows = _fresh_scalars(uow, statement)
    return rows[0] if len(rows) == 1 else None


def _refresh_current_authority_rows(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    customer_record_id: UUID | None,
    project_record_id: UUID | None,
) -> bool:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        return True
    try:
        workspace = _fresh_one(
            uow,
            select(Workspace).where(Workspace.id == workspace_id),
        )
        employee = _fresh_one(
            uow,
            select(DigitalEmployee).where(DigitalEmployee.id == employee_id),
        )
        if not isinstance(workspace, Workspace) or not isinstance(
            employee, DigitalEmployee
        ):
            return False
        table_ids = _strict_uuid_tuple(employee.accessible_tables)
        view_ids = _strict_uuid_tuple(employee.accessible_views)
        if not table_ids or not view_ids or not isinstance(employee.base_id, UUID):
            return False
        base = _fresh_one(
            uow,
            select(BitableBase).where(BitableBase.id == employee.base_id),
        )
        tables = _fresh_scalars(
            uow,
            select(PlatformTable).where(PlatformTable.id.in_(table_ids)),
        )
        views = _fresh_scalars(
            uow,
            select(PlatformView).where(PlatformView.id.in_(view_ids)),
        )
        if (
            not isinstance(base, BitableBase)
            or len(tables) != len(table_ids)
            or len(views) != len(view_ids)
            or not all(isinstance(row, PlatformTable) for row in tables)
            or not all(isinstance(row, PlatformView) for row in views)
        ):
            return False
        _fresh_scalars(
            uow,
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id
            ),
        )
        grants = _fresh_scalars(
            uow,
            select(DigitalEmployeeMemberGrant).where(
                DigitalEmployeeMemberGrant.employee_id == employee_id
            ),
        )
        granted_member_ids = tuple(
            grant.workspace_member_id
            for grant in grants
            if isinstance(grant, DigitalEmployeeMemberGrant)
            and isinstance(grant.workspace_member_id, UUID)
        )
        if len(granted_member_ids) != len(grants):
            return False
        if granted_member_ids:
            _fresh_scalars(
                uow,
                select(WorkspaceMember).where(
                    WorkspaceMember.id.in_(granted_member_ids)
                ),
            )
        _fresh_scalars(
            uow,
            select(PlatformField).where(PlatformField.table_id.in_(table_ids)),
        )
        _fresh_scalars(
            uow,
            select(ViewMemberGrant).where(ViewMemberGrant.view_id.in_(view_ids)),
        )
        record_ids = tuple(
            dict.fromkeys(
                record_id
                for record_id in (customer_record_id, project_record_id)
                if record_id is not None
            )
        )
        if record_ids:
            records = _fresh_scalars(
                uow,
                select(PlatformRecord).where(PlatformRecord.id.in_(record_ids)),
            )
            if len(records) != len(record_ids) or not all(
                isinstance(row, PlatformRecord) for row in records
            ):
                return False
            _fresh_scalars(
                uow,
                select(RecordLink).where(
                    or_(
                        RecordLink.source_record_id.in_(record_ids),
                        RecordLink.target_record_id.in_(record_ids),
                    )
                ),
            )
        return True
    except Exception:
        return False


def _build_authority_snapshot(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    workspace_id: UUID,
    employee_id: UUID,
    customer_record_id: UUID | None,
    project_record_id: UUID | None,
) -> _AuthoritySnapshot:
    if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        with uow.session.no_autoflush:
            return _build_authority_snapshot_impl(
                uow,
                actor=actor,
                workspace_id=workspace_id,
                employee_id=employee_id,
                customer_record_id=customer_record_id,
                project_record_id=project_record_id,
            )
    return _build_authority_snapshot_impl(
        uow,
        actor=actor,
        workspace_id=workspace_id,
        employee_id=employee_id,
        customer_record_id=customer_record_id,
        project_record_id=project_record_id,
    )


def _build_authority_snapshot_impl(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    workspace_id: UUID,
    employee_id: UUID,
    customer_record_id: UUID | None,
    project_record_id: UUID | None,
) -> _AuthoritySnapshot:
    if (
        type(actor) is not Actor
        or actor.actor_type != "user"
        or not isinstance(actor.actor_id, str)
        or not actor.actor_id.strip()
        or not isinstance(actor.role, str)
        or not actor.role.strip()
        or not isinstance(actor.customer_ids, frozenset)
        or not all(isinstance(value, str) for value in actor.customer_ids)
        or not isinstance(workspace_id, UUID)
        or not isinstance(employee_id, UUID)
        or (customer_record_id is not None and not isinstance(customer_record_id, UUID))
        or (project_record_id is not None and not isinstance(project_record_id, UUID))
    ):
        raise ValueError("retrieval_authority_unavailable")
    if not _refresh_current_authority_rows(
        uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        customer_record_id=customer_record_id,
        project_record_id=project_record_id,
    ):
        raise ValueError("retrieval_authority_unavailable")
    workspace = uow.get_workspace(workspace_id)
    employee = uow.get_digital_employee(employee_id)
    active_members = [
        member
        for member in uow.list_workspace_members(workspace_id)
        if member.user_id == actor.actor_id and member.status == "active"
    ]
    if (
        workspace is None
        or workspace.status != "active"
        or employee is None
        or employee.status != "active"
        or employee.workspace_id != workspace_id
        or len(active_members) != 1
        or active_members[0].role != actor.role
        or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
        or not _positive_int(employee.version)
        or not isinstance(employee.allowed_actions, list)
        or len(employee.allowed_actions) != len(set(employee.allowed_actions))
        or not all(isinstance(value, str) for value in employee.allowed_actions)
        or "query" not in employee.allowed_actions
    ):
        raise ValueError("retrieval_authority_unavailable")
    member = active_members[0]
    base = uow.get_base(employee.base_id)
    member_version = (
        member.version if _positive_int(getattr(member, "version", None)) else 1
    )
    if (
        base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
    ):
        raise ValueError("retrieval_authority_unavailable")
    table_ids = _strict_uuid_tuple(employee.accessible_tables)
    view_ids = _strict_uuid_tuple(employee.accessible_views)
    if not table_ids or not view_ids:
        raise ValueError("retrieval_authority_unavailable")
    for table_id in table_ids:
        table = uow.get_table(table_id)
        if table is None or table.status != "active" or table.base_id != base.id:
            raise ValueError("retrieval_authority_unavailable")
    view_versions: list[tuple[UUID, int]] = []
    for view_id in view_ids:
        view = uow.get_view(view_id)
        if (
            view is None
            or view.status != "active"
            or view.base_id != base.id
            or view.table_id not in table_ids
            or not _positive_int(view.version)
        ):
            raise ValueError("retrieval_authority_unavailable")
        get_view_presentation(uow, view.id, actor=actor)
        view_versions.append((view.id, view.version))
    access_mode = employee.access_mode
    if access_mode not in {"workspace", "assigned"}:
        raise ValueError("retrieval_authority_unavailable")
    grants = uow.list_digital_employee_member_grants(employee.id)
    grant_member_ids = tuple(
        sorted((grant.workspace_member_id for grant in grants), key=str)
    )
    if access_mode == "workspace":
        grant_member_ids = ()
    else:
        if len(grant_member_ids) != len(set(grant_member_ids)):
            raise ValueError("retrieval_authority_unavailable")
        for granted_member_id in grant_member_ids:
            granted_member = uow.get_workspace_member(granted_member_id)
            if (
                granted_member is None
                or granted_member.workspace_id != workspace_id
                or granted_member.status != "active"
            ):
                raise ValueError("retrieval_authority_unavailable")
        if member.id not in grant_member_ids:
            raise ValueError("retrieval_authority_unavailable")
    business_scope = resolve_business_scope(
        uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
        customer_record_id=customer_record_id,
        project_record_id=project_record_id,
    )
    return _AuthoritySnapshot(
        workspace_id=workspace_id,
        employee_id=employee_id,
        employee_version=employee.version,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        actor_customer_ids=actor.customer_ids,
        member_id=member.id,
        member_version=member_version,
        base_id=base.id,
        table_ids=table_ids,
        view_versions=tuple(sorted(view_versions, key=lambda item: str(item[0]))),
        access_mode=access_mode,
        grant_member_ids=grant_member_ids,
        business_scope=business_scope,
    )


def _revalidate_authority(
    uow: Stage06PlatformUnitOfWork,
    snapshot: _AuthoritySnapshot | None,
) -> _AuthoritySnapshot | None:
    if not isinstance(snapshot, _AuthoritySnapshot):
        return None
    actor = Actor(
        actor_type="user",
        actor_id=snapshot.actor_id,
        role=snapshot.actor_role,
        customer_ids=snapshot.actor_customer_ids,
    )
    try:
        current = _build_authority_snapshot(
            uow,
            actor=actor,
            workspace_id=snapshot.workspace_id,
            employee_id=snapshot.employee_id,
            customer_record_id=snapshot.business_scope.customer_record_id,
            project_record_id=snapshot.business_scope.project_record_id,
        )
    except Exception:
        return None
    return current if current == snapshot else None


def _candidate_rows(
    uow: Stage06PlatformUnitOfWork,
    authority: _AuthoritySnapshot,
    now: datetime,
    *,
    query_terms: tuple[str, ...],
    query_vector: tuple[float, ...] | None,
) -> tuple[tuple[Stage08KnowledgeSource, Stage08KnowledgeChunk], ...]:
    try:
        if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
            source_scope_workspace = Stage08KnowledgeSource.scope[
                "workspace_id"
            ].as_string()
            source_scope_base = Stage08KnowledgeSource.scope["base_id"].as_string()
            source_scope_table = Stage08KnowledgeSource.scope["table_id"].as_string()
            source_scope_view = Stage08KnowledgeSource.scope["view_id"].as_string()
            source_scope_customer = Stage08KnowledgeSource.scope[
                "customer_record_id"
            ].as_string()
            source_scope_project = Stage08KnowledgeSource.scope[
                "project_record_id"
            ].as_string()
            allowed_view_ids = [
                str(view_id) for view_id, _version in authority.view_versions
            ]
            structured_filters = (
                Stage08KnowledgeSource.workspace_id == authority.workspace_id,
                Stage08KnowledgeSource.source_type.in_(tuple(sorted(_SOURCE_TYPES))),
                Stage08KnowledgeSource.status == "active",
                Stage08KnowledgeSource.revoked_at.is_(None),
                Stage08KnowledgeSource.deleted_at.is_(None),
                or_(
                    Stage08KnowledgeSource.valid_until.is_(None),
                    Stage08KnowledgeSource.valid_until > now,
                ),
                Stage08KnowledgeChunk.workspace_id == authority.workspace_id,
                Stage08KnowledgeChunk.status == "indexed",
                Stage08KnowledgeChunk.deleted_at.is_(None),
                source_scope_workspace == str(authority.workspace_id),
                or_(
                    source_scope_base.is_(None),
                    source_scope_base == str(authority.base_id),
                ),
                or_(
                    source_scope_table.is_(None),
                    source_scope_table.in_([str(value) for value in authority.table_ids]),
                ),
                or_(
                    source_scope_view.is_(None),
                    source_scope_view.in_(allowed_view_ids),
                ),
                _scope_value_filter(
                    source_scope_customer,
                    authority.business_scope.customer_record_id,
                ),
                _scope_value_filter(
                    source_scope_project,
                    authority.business_scope.project_record_id,
                ),
            )
            base_statement = (
                select(Stage08KnowledgeSource, Stage08KnowledgeChunk)
                .join(
                    Stage08KnowledgeChunk,
                    and_(
                        Stage08KnowledgeChunk.source_id == Stage08KnowledgeSource.id,
                        Stage08KnowledgeChunk.workspace_id
                        == Stage08KnowledgeSource.workspace_id,
                        Stage08KnowledgeChunk.source_version
                        == Stage08KnowledgeSource.content_version,
                    ),
                )
                .where(*structured_filters)
                .execution_options(populate_existing=True, autoflush=False)
            )
            keyword_statement = base_statement.where(
                Stage08KnowledgeChunk.keyword_terms.op("&&")(list(query_terms))
            ).order_by(
                Stage08KnowledgeSource.source_type,
                Stage08KnowledgeSource.logical_source_fingerprint,
                Stage08KnowledgeSource.content_version,
                Stage08KnowledgeChunk.ordinal,
                Stage08KnowledgeChunk.id,
            )
            with uow.session.no_autoflush:
                rows = list(uow.session.execute(keyword_statement))
                if query_vector is not None:
                    distance = cast(
                        Stage08KnowledgeChunk.embedding,
                        Vector(TEST_EMBEDDING_DIMENSION),
                    ).cosine_distance(list(query_vector))
                    vector_statement = (
                        base_statement.where(
                            Stage08KnowledgeChunk.embedding.is_not(None),
                            Stage08KnowledgeChunk.embedding_profile
                            == TEST_EMBEDDING_PROFILE,
                            Stage08KnowledgeChunk.embedding_version
                            == TEST_EMBEDDING_VERSION,
                        )
                        .order_by(
                            distance,
                            Stage08KnowledgeSource.source_type,
                            Stage08KnowledgeSource.logical_source_fingerprint,
                            Stage08KnowledgeSource.content_version,
                            Stage08KnowledgeChunk.ordinal,
                            Stage08KnowledgeChunk.id,
                        )
                    )
                    rows.extend(uow.session.execute(vector_statement))
            unique_rows = {
                (source.id, chunk.id): (source, chunk)
                for source, chunk in rows
            }
            return tuple(
                unique_rows[key]
                for key in sorted(unique_rows, key=lambda item: (str(item[0]), str(item[1])))
            )
        rows: list[tuple[Stage08KnowledgeSource, Stage08KnowledgeChunk]] = []
        for source in uow.list_knowledge_sources(authority.workspace_id):
            if not _active_source(source, authority.workspace_id, now):
                continue
            for chunk in uow.list_knowledge_chunks(source.id, source.content_version):
                if chunk.status == "indexed" and chunk.deleted_at is None:
                    rows.append((source, chunk))
        return tuple(rows)
    except Exception:
        return ()


def _scope_value_filter(expression: object, value: UUID | None) -> object:
    if value is None:
        return expression.is_(None)  # type: ignore[attr-defined, no-any-return]
    return expression == str(value)


def _validate_current_candidate(
    uow: Stage06PlatformUnitOfWork,
    authority: _AuthoritySnapshot,
    source: Stage08KnowledgeSource,
    chunk: Stage08KnowledgeChunk,
    *,
    now: datetime,
) -> tuple[_ValidatedScope, RetrievalSourceTypeCategory] | None:
    if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        with uow.session.no_autoflush:
            return _validate_current_candidate_impl(
                uow,
                authority,
                source,
                chunk,
                now=now,
            )
    return _validate_current_candidate_impl(
        uow,
        authority,
        source,
        chunk,
        now=now,
    )


def _validate_current_candidate_impl(
    uow: Stage06PlatformUnitOfWork,
    authority: _AuthoritySnapshot,
    source: Stage08KnowledgeSource,
    chunk: Stage08KnowledgeChunk,
    *,
    now: datetime,
) -> tuple[_ValidatedScope, RetrievalSourceTypeCategory] | None:
    if not _active_source(source, authority.workspace_id, now):
        return None
    if source.source_type not in _SOURCE_TYPES:
        return None
    scope = _validate_scope(uow, authority, source.scope)
    if scope is None:
        return None
    if not _valid_source_projection(source):
        return None
    if not _valid_chunk_for_source(source, chunk):
        return None
    if source.source_type == "memory_item":
        if not _revalidate_memory_source(uow, authority, source, scope, now=now):
            return None
        category: RetrievalSourceTypeCategory = "business_memory"
    else:
        # D4 has no approved document/summary origin verifier yet. A row alone
        # is not enough authority to release either category.
        return None
    return scope, category


def _validate_scope(
    uow: Stage06PlatformUnitOfWork,
    authority: _AuthoritySnapshot,
    raw_scope: object,
) -> _ValidatedScope | None:
    if (
        not isinstance(raw_scope, dict)
        or set(raw_scope).difference(_SCOPE_KEYS)
        or "workspace_id" not in raw_scope
    ):
        return None
    try:
        values = {
            key: None if raw_scope.get(key) is None else _canonical_uuid(raw_scope.get(key))
            for key in _SCOPE_KEYS
        }
    except (TypeError, ValueError):
        return None
    if any(
        key in raw_scope and raw_scope.get(key) is not None and values[key] is None
        for key in _SCOPE_KEYS
    ):
        return None
    if values["workspace_id"] != authority.workspace_id:
        return None
    if values["base_id"] is not None and values["base_id"] != authority.base_id:
        return None
    if values["table_id"] is not None and values["table_id"] not in authority.table_ids:
        return None
    allowed_views = {view_id for view_id, _ in authority.view_versions}
    if values["view_id"] is not None and values["view_id"] not in allowed_views:
        return None
    if (
        values["customer_record_id"]
        != authority.business_scope.customer_record_id
        or values["project_record_id"]
        != authority.business_scope.project_record_id
    ):
        return None
    if values["base_id"] is not None:
        base = uow.get_base(values["base_id"])
        if base is None or base.status != "active" or base.workspace_id != authority.workspace_id:
            return None
    if values["table_id"] is not None:
        table = uow.get_table(values["table_id"])
        if table is None or table.status != "active" or table.base_id != authority.base_id:
            return None
    if values["view_id"] is not None:
        view = uow.get_view(values["view_id"])
        if (
            view is None
            or view.status != "active"
            or view.base_id != authority.base_id
            or view.table_id != values["table_id"]
        ):
            return None
    if values["field_id"] is not None:
        field = uow.get_field(values["field_id"])
        if (
            field is None
            or field.status != "active"
            or values["table_id"] is None
            or field.table_id != values["table_id"]
        ):
            return None
        actor = _actor_from_snapshot(authority)
        visible_ids = {
            _canonical_uuid(item.get("id"))
            for item in get_table_schema(uow, field.table_id, actor=actor).get("fields", [])
            if isinstance(item, dict)
        }
        if field.id not in visible_ids:
            return None
    try:
        current_business = resolve_business_scope(
            uow,
            workspace_id=authority.workspace_id,
            employee_id=authority.employee_id,
            actor=_actor_from_snapshot(authority),
            customer_record_id=values["customer_record_id"],
            project_record_id=values["project_record_id"],
        )
    except PlatformValidationError:
        return None
    if current_business != authority.business_scope:
        return None
    category: RetrievalScopeCategory
    if values["field_id"] is not None:
        category = "field"
    elif values["view_id"] is not None:
        category = "view"
    elif values["customer_record_id"] is not None or values["project_record_id"] is not None:
        category = "business"
    elif values["table_id"] is not None:
        category = "table"
    elif values["base_id"] is not None:
        category = "base"
    else:
        category = "workspace"
    return _ValidatedScope(
        category=category,
        workspace_id=values["workspace_id"],
        base_id=values["base_id"],
        table_id=values["table_id"],
        view_id=values["view_id"],
        field_id=values["field_id"],
        customer_record_id=values["customer_record_id"],
        project_record_id=values["project_record_id"],
    )


def _revalidate_memory_source(
    uow: Stage06PlatformUnitOfWork,
    authority: _AuthoritySnapshot,
    source: Stage08KnowledgeSource,
    scope: _ValidatedScope,
    *,
    now: datetime,
) -> bool:
    source_ref = source.source_ref
    if not isinstance(source_ref, dict) or set(source_ref) != _MEMORY_SOURCE_REF_KEYS:
        return False
    item_id = _canonical_uuid(source_ref.get("memory_item_id"))
    item_version = source_ref.get("memory_item_version")
    if item_id is None or not _positive_int(item_version):
        return False
    root_id = _resolve_current_memory_lineage_root(
        uow,
        item_id,
        authority.workspace_id,
    )
    if (
        root_id is None
        or source.logical_source_fingerprint
        != _sha256(f"memory_lineage:{root_id}")
    ):
        return False
    projection = read_memory_projection(
        uow,
        item_id,
        actor=_actor_from_snapshot(authority),
        now=now,
        lifecycle_mode="read_only",
    )
    if not isinstance(projection, dict) or set(projection) != {
        "id",
        "memory_type",
        "version",
        "scope",
        "payload",
        "valid_until",
    }:
        return False
    if (
        projection.get("id") != item_id
        or projection.get("version") != item_version
        or projection.get("version") != source.content_version
        or projection.get("valid_until") != source.valid_until
        or projection.get("scope") != source.scope
        or not isinstance(projection.get("memory_type"), str)
        or not isinstance(projection.get("payload"), dict)
    ):
        return False
    try:
        canonical = canonicalize_knowledge_text(
            json.dumps(
                {
                    "memory_type": projection["memory_type"],
                    "payload": projection["payload"],
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError):
        return False
    return (
        canonical == source.projection_text
        and _sha256(canonical) == source.projection_hash
        and scope.workspace_id == authority.workspace_id
    )


def _valid_source_projection(source: Stage08KnowledgeSource) -> bool:
    if (
        not isinstance(source.id, UUID)
        or not isinstance(source.workspace_id, UUID)
        or not _sha256_hex(source.logical_source_fingerprint)
        or not _sha256_hex(source.projection_hash)
        or not isinstance(source.projection_text, str)
    ):
        return False
    try:
        canonical = canonicalize_knowledge_text(source.projection_text)
    except ValueError:
        return False
    return canonical == source.projection_text and _sha256(canonical) == source.projection_hash


def _valid_chunk_for_source(
    source: Stage08KnowledgeSource,
    chunk: Stage08KnowledgeChunk,
) -> bool:
    if (
        not isinstance(chunk.id, UUID)
        or not _sha256_hex(chunk.chunk_hash)
        or chunk.workspace_id != source.workspace_id
        or chunk.source_id != source.id
        or chunk.source_version != source.content_version
        or chunk.status != "indexed"
        or chunk.deleted_at is not None
        or not isinstance(chunk.chunk_text, str)
        or not chunk.chunk_text.strip()
        or _sha256(chunk.chunk_text) != chunk.chunk_hash
        or not isinstance(chunk.keyword_terms, list)
        or not all(isinstance(term, str) for term in chunk.keyword_terms)
    ):
        return False
    try:
        projections = chunk_knowledge_projection(source.projection_text)
    except (TypeError, ValueError):
        return False
    if chunk.ordinal < 0 or chunk.ordinal >= len(projections):
        return False
    projection = projections[chunk.ordinal]
    return (
        projection.chunk_text == chunk.chunk_text
        and projection.chunk_hash == chunk.chunk_hash
        and projection.keyword_terms == tuple(chunk.keyword_terms)
    )


def _fresh_current_hit_rows(
    uow: Stage06PlatformUnitOfWork,
    hit: _HitSnapshot,
) -> tuple[Stage08KnowledgeSource, Stage08KnowledgeChunk] | None:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        source = uow.get_knowledge_source(hit.source_id)
        if source is None:
            return None
        chunks = uow.list_knowledge_chunks(source.id, source.content_version)
        chunk = next((item for item in chunks if item.id == hit.chunk_id), None)
        return None if chunk is None else (source, chunk)
    try:
        source = _fresh_one(
            uow,
            select(Stage08KnowledgeSource).where(
                Stage08KnowledgeSource.id == hit.source_id
            ),
        )
        chunk = _fresh_one(
            uow,
            select(Stage08KnowledgeChunk).where(
                Stage08KnowledgeChunk.id == hit.chunk_id,
                Stage08KnowledgeChunk.source_id == hit.source_id,
                Stage08KnowledgeChunk.source_version == hit.source_version,
            ),
        )
        if not isinstance(source, Stage08KnowledgeSource) or not isinstance(
            chunk, Stage08KnowledgeChunk
        ):
            return None
        return source, chunk
    except Exception:
        return None


def _current_memory_item(
    uow: Stage06PlatformUnitOfWork,
    item_id: UUID,
) -> Stage08MemoryItem | None:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        item = uow.get_memory_item(item_id)
        return item if isinstance(item, Stage08MemoryItem) else None
    try:
        item = _fresh_one(
            uow,
            select(Stage08MemoryItem).where(Stage08MemoryItem.id == item_id),
        )
    except Exception:
        return None
    return item if isinstance(item, Stage08MemoryItem) else None


def _resolve_current_memory_lineage_root(
    uow: Stage06PlatformUnitOfWork,
    item_id: UUID,
    workspace_id: UUID,
) -> UUID | None:
    current = _current_memory_item(uow, item_id)
    current_identity = _memory_lineage_identity(current, workspace_id)
    if (
        current is None
        or current.id != item_id
        or current.workspace_id != workspace_id
        or current.status != "active"
        or current.revoked_at is not None
        or current.deleted_at is not None
        or not _positive_int(current.version)
        or current_identity is None
        or not _valid_memory_lineage_source_refs(current)
    ):
        return None
    seen = {current.id}
    while current.supersedes_id is not None:
        predecessor_id = current.supersedes_id
        if not isinstance(predecessor_id, UUID) or predecessor_id in seen:
            return None
        predecessor = _current_memory_item(uow, predecessor_id)
        if (
            predecessor is None
            or predecessor.id != predecessor_id
            or predecessor.workspace_id != workspace_id
            or predecessor.status != "superseded"
            or predecessor.revoked_at is not None
            or predecessor.deleted_at is not None
            or not _positive_int(predecessor.version)
            or predecessor.version >= current.version
            or _memory_lineage_identity(predecessor, workspace_id)
            != current_identity
            or not _valid_memory_lineage_source_refs(predecessor)
        ):
            return None
        seen.add(predecessor_id)
        current = predecessor
    return current.id


def _memory_lineage_identity(
    item: object,
    workspace_id: UUID,
) -> tuple[str, str] | None:
    memory_type = getattr(item, "memory_type", None)
    scope = getattr(item, "scope", None)
    if not isinstance(memory_type, str) or not memory_type.strip():
        return None
    try:
        projection = MemoryScopeProjection.model_validate(scope)
        canonical_scope = json.dumps(
            projection.model_dump(mode="json", exclude_none=False),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None
    if (
        projection.workspace_id != workspace_id
        or projection.group_chat_ref is not None
    ):
        return None
    return memory_type, canonical_scope


def _valid_memory_lineage_source_refs(item: object) -> bool:
    source_refs = getattr(item, "source_refs", None)
    if not isinstance(source_refs, list) or not source_refs:
        return False
    try:
        projections = tuple(
            MemorySourceRef.model_validate(source_ref) for source_ref in source_refs
        )
    except (TypeError, ValueError):
        return False
    return all(
        projection.source_kind in {"platform_record", "record_change_draft"}
        for projection in projections
    )


def _revalidated_result_hits(
    uow: Stage06PlatformUnitOfWork,
    result: object,
    *,
    now: datetime,
) -> tuple[_ResultSnapshot | None, tuple[_HitSnapshot, ...]]:
    if not _valid_now(now):
        return None, ()
    result_snapshot = _result_snapshot(result)
    if result_snapshot is None:
        return None, ()
    authority = _authority_snapshot(result_snapshot.authority)
    current_authority = _revalidate_authority(uow, authority)
    if current_authority is None:
        return result_snapshot, ()
    current_hits: list[_HitSnapshot] = []
    for hit in result_snapshot.hits:
        try:
            current_rows = _fresh_current_hit_rows(uow, hit)
            if current_rows is None:
                continue
            source, chunk = current_rows
            if (
                source.content_version != hit.source_version
                or source.projection_hash != hit.source_hash
            ):
                continue
            if chunk.chunk_hash != hit.chunk_hash or chunk.chunk_text != hit.chunk_text:
                continue
            validated = _validate_current_candidate(
                uow,
                current_authority,
                source,
                chunk,
                now=now,
            )
            if validated is None:
                continue
            scope, source_type_category = validated
            if (
                scope.category != hit.scope_category
                or source_type_category != hit.source_type_category
            ):
                continue
            current_hits.append(hit)
        except Exception:
            continue
    return result_snapshot, tuple(current_hits)


def _query_embedding(
    provider: EmbeddingProvider | None,
    query: str,
) -> tuple[float, ...] | None:
    if provider is None or not _valid_embedding_profile(provider):
        return None
    try:
        output = provider.embed_batch(TEST_EMBEDDING_PROFILE, (query,))
    except (EmbeddingProviderUnavailable, Exception):
        return None
    if not isinstance(output, tuple) or len(output) != 1:
        return None
    return _finite_vector(output[0])


def _valid_embedding_profile(provider: object) -> bool:
    try:
        return (
            type(provider.profile) is str
            and provider.profile == TEST_EMBEDDING_PROFILE
            and type(provider.version) is int
            and provider.version == TEST_EMBEDDING_VERSION
            and type(provider.dimension) is int
            and provider.dimension == TEST_EMBEDDING_DIMENSION
        )
    except Exception:
        return False


def _vector_score(
    query_vector: tuple[float, ...] | None,
    chunk: Stage08KnowledgeChunk,
) -> float | None:
    if (
        query_vector is None
        or chunk.embedding_profile != TEST_EMBEDDING_PROFILE
        or chunk.embedding_version != TEST_EMBEDDING_VERSION
    ):
        return None
    candidate = _finite_vector(chunk.embedding)
    if candidate is None:
        return None
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    candidate_norm = math.sqrt(sum(value * value for value in candidate))
    if query_norm == 0.0 or candidate_norm == 0.0:
        return None
    cosine = sum(
        left * right for left, right in zip(query_vector, candidate, strict=True)
    ) / (query_norm * candidate_norm)
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def _finite_vector(value: object) -> tuple[float, ...] | None:
    try:
        candidate = tuple(value)
        if len(candidate) != TEST_EMBEDDING_DIMENSION:
            return None
        converted = tuple(float(item) for item in candidate)
        if any(isinstance(item, bool) for item in candidate) or not all(
            math.isfinite(item) for item in converted
        ):
            return None
        return converted
    except Exception:
        return None


def _keyword_score(query_terms: tuple[str, ...], chunk_terms: object) -> float:
    if not isinstance(chunk_terms, list) or not all(
        isinstance(term, str) for term in chunk_terms
    ):
        return 0.0
    return len(set(query_terms).intersection(chunk_terms)) / len(set(query_terms))


def _query_terms(query: str) -> tuple[str, ...]:
    try:
        return chunk_knowledge_projection(query)[0].keyword_terms
    except (TypeError, ValueError, IndexError):
        return ()


def _validated_query(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        canonical = canonicalize_knowledge_text(value)
    except ValueError:
        return None
    return canonical if len(canonical) <= 500 else None


def _active_source(
    source: object,
    workspace_id: UUID,
    now: datetime,
) -> bool:
    if (
        not isinstance(source, Stage08KnowledgeSource)
        or source.workspace_id != workspace_id
        or source.status != "active"
        or source.revoked_at is not None
        or source.deleted_at is not None
        or not _positive_int(source.content_version)
    ):
        return False
    if source.valid_until is None:
        return True
    try:
        return source.valid_until > now
    except TypeError:
        return False


def _safe_view_model(
    *,
    status: Literal["ready", "degraded", "unavailable", "empty", "failed"],
    hits: tuple[_HitSnapshot, ...],
    degradation_code: Literal["none", "keyword_only", "embedding_unavailable"],
    error_code: Literal[
        "none",
        "retrieval_unavailable",
        "source_revalidation_failed",
        "authority_changed",
        "scope_mismatch",
        "index_unavailable",
    ],
) -> RetrievalSafeView:
    grouped: dict[tuple[str, str], int] = {}
    for hit in hits:
        key = (hit.source_type_category, hit.scope_category)
        grouped[key] = grouped.get(key, 0) + 1
    sources = tuple(
        RetrievalSafeSourceView(
            source_type_category=source_type,
            scope_category=scope_category,
            count=count,
            available=True,
        )
        for (source_type, scope_category), count in sorted(grouped.items())
    )
    return validate_retrieval_safe_view(
        RetrievalSafeView(
            contract_version="stage08.retrieval-safe.v1",
            status=status,
            sources=sources,
            result_count=len(hits),
            has_results=bool(hits),
            degradation_code=degradation_code,
            error_code=error_code,
        )
    )


def _result(
    authority: object,
    *,
    hits: tuple[_HitSnapshot, ...] = (),
    status: Literal["ready", "degraded", "unavailable", "empty", "failed"],
    degradation_code: Literal["none", "keyword_only", "embedding_unavailable"],
    error_code: Literal[
        "none",
        "retrieval_unavailable",
        "source_revalidation_failed",
        "authority_changed",
        "scope_mismatch",
        "index_unavailable",
    ],
) -> _Stage08RetrievalResult:
    if not isinstance(authority, _Stage08RetrievalAuthority):
        authority = _Stage08RetrievalAuthority(_AUTHORITY_ISSUER, None)
    return _Stage08RetrievalResult(
        _RESULT_ISSUER,
        _ResultSnapshot(
            authority=authority,
            hits=hits,
            status=status,
            degradation_code=degradation_code,
            error_code=error_code,
        ),
    )


def _authority_snapshot(value: object) -> _AuthoritySnapshot | None:
    if type(value) is not _Stage08RetrievalAuthority:
        return None
    snapshot = object.__getattribute__(value, "_sealed_snapshot")
    return snapshot if isinstance(snapshot, _AuthoritySnapshot) else None


def _result_snapshot(value: object) -> _ResultSnapshot | None:
    if type(value) is not _Stage08RetrievalResult:
        return None
    snapshot = object.__getattribute__(value, "_sealed_snapshot")
    return snapshot if isinstance(snapshot, _ResultSnapshot) else None


def _actor_from_snapshot(snapshot: _AuthoritySnapshot) -> Actor:
    return Actor(
        actor_type="user",
        actor_id=snapshot.actor_id,
        role=snapshot.actor_role,
        customer_ids=snapshot.actor_customer_ids,
    )


def _strict_uuid_tuple(values: object) -> tuple[UUID, ...]:
    if not isinstance(values, list):
        raise ValueError("retrieval_authority_unavailable")
    parsed = tuple(_canonical_uuid(value) for value in values)
    if any(value is None for value in parsed) or len(set(parsed)) != len(parsed):
        raise ValueError("retrieval_authority_unavailable")
    return tuple(sorted(parsed, key=str))


def _canonical_uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return parsed if str(parsed) == value else None


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_limit(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 12


def _valid_now(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
