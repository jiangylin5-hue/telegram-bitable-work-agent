from __future__ import annotations

from hashlib import sha256
from typing import cast
from uuid import UUID

import pytest

import app.services.retrieval_v2_hybrid as retrieval_hybrid

from app.schemas.agent_task_spec_v2 import (
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    authorized_schema_sha256,
)
from app.schemas.retrieval_v2 import (
    RetrievalRelationEdgeProjectionV2,
    RetrievalRequestV2,
    canonical_retrieval_sha256,
)
from app.services.authorized_query_records import AuthorizedQueryContext
from app.services.permissions import Actor
from app.services.retrieval_v2_hybrid import (
    ObjectiveTableQuotaV2,
    RawRetrievalHitV2,
    RetrievalV2Denied,
    retrieve_authorized_candidates,
)
from app.services.stage06_platform import Stage06PlatformUnitOfWork


WORKSPACE_ID = UUID("20000000-0000-0000-0000-000000000001")
EMPLOYEE_ID = UUID("20000000-0000-0000-0000-000000000002")
BASE_ID = UUID("20000000-0000-0000-0000-000000000003")
TABLE_A = UUID("20000000-0000-0000-0000-000000000010")
TABLE_B = UUID("20000000-0000-0000-0000-000000000020")
FIELD_A = UUID("20000000-0000-0000-0000-000000000101")
FIELD_B = UUID("20000000-0000-0000-0000-000000000201")
HIDDEN_FIELD = UUID("20000000-0000-0000-0000-000000000999")
SCOPE_HASH = "a" * 64
PROFILE = "stage12.openrouter-bge-m3-v1"
VIEW_A = UUID("20000000-0000-0000-0000-000000000101")
VIEW_B = UUID("20000000-0000-0000-0000-000000000102")
VIEW_SCOPE_HASH = "f0efec4b2400e42cac2f38cf7034e711ad334ed48186db0008f5c7536fbfab92"
WHOLE_TABLE_SCOPE_HASH = (
    "f69452c776cadfa5e233dd6838a19658b8c19f8b6265ebd69e8a27a0480d50e9"
)


def _field(field_id: UUID, table_id: UUID, key: str) -> AuthorizedFieldSpec:
    return AuthorizedFieldSpec(
        field_id=field_id,
        table_id=table_id,
        key=key,
        name=key,
        field_type="text",
        aliases=(),
        choices=(),
        writable=False,
        default_value=None,
    )


def _snapshot() -> AuthorizedSchemaSnapshot:
    tables = (
        AuthorizedTableSpec(
            table_id=TABLE_A,
            base_id=BASE_ID,
            key="a",
            name="A",
            aliases=(),
            fields=(_field(FIELD_A, TABLE_A, "code_a"),),
            identity_field_id=FIELD_A,
        ),
        AuthorizedTableSpec(
            table_id=TABLE_B,
            base_id=BASE_ID,
            key="b",
            name="B",
            aliases=(),
            fields=(_field(FIELD_B, TABLE_B, "code_b"),),
            identity_field_id=FIELD_B,
        ),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": SCOPE_HASH,
        "tables": tables,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _context() -> AuthorizedQueryContext:
    snapshot = _snapshot()
    return AuthorizedQueryContext(
        uow=cast(Stage06PlatformUnitOfWork, None),
        actor=Actor(actor_type="user", actor_id="owner", role="owner"),
        workspace_id=WORKSPACE_ID,
        base_id=BASE_ID,
        employee_id=EMPLOYEE_ID,
        snapshot=snapshot,
        employee_table_ids=frozenset({TABLE_A, TABLE_B}),
        employee_view_ids=frozenset(),
        scope_view_ids=(),
        allow_whole_table=True,
    )


def _request(
    *,
    exact_record_ids: tuple[UUID, ...] = (),
    max_primary_candidates: int = 20,
    max_relation_expansions_per_primary: int = 10,
) -> RetrievalRequestV2:
    snapshot = _snapshot()
    return RetrievalRequestV2(
        version="retrieval-request.v2",
        objective_id="obj-hybrid",
        query="查找 Atlas 相关记录",
        workspace_id=WORKSPACE_ID,
        base_id=BASE_ID,
        table_ids=(TABLE_A, TABLE_B),
        exact_record_ids=exact_record_ids,
        query_result_ref=None,
        scope_hash=WHOLE_TABLE_SCOPE_HASH,
        schema_hash=snapshot.schema_hash,
        max_primary_candidates=max_primary_candidates,
        max_relation_expansions_per_primary=max_relation_expansions_per_primary,
        max_evidence_nodes=24,
    )


def _hit(
    source_id: str,
    *,
    table_id: UUID = TABLE_A,
    record_id: UUID | None = None,
    source_type: str = "record",
    field_ids: tuple[UUID, ...] | None = None,
    workspace_id: UUID = WORKSPACE_ID,
    scope_hash: str = WHOLE_TABLE_SCOPE_HASH,
    keyword: float = 0.0,
    semantic: float = 0.0,
    entity_schema: float = 0.0,
    freshness: float = 0.0,
    embedding_profile: str | None = PROFILE,
) -> RawRetrievalHitV2:
    if field_ids is None:
        field_ids = (FIELD_A,) if table_id == TABLE_A else (FIELD_B,)
    if record_id is None and source_type in {"record", "record_field"}:
        record_id = UUID(int=int(sha256(source_id.encode()).hexdigest()[:32], 16))
    return RawRetrievalHitV2(
        workspace_id=workspace_id,
        base_id=BASE_ID,
        source_type=source_type,
        source_id=source_id,
        source_version=3,
        table_id=table_id,
        record_id=record_id,
        field_ids=field_ids,
        scope_hash=scope_hash,
        content_hash=sha256(source_id.encode()).hexdigest(),
        embedding_profile=embedding_profile,
        keyword_score=keyword,
        semantic_score=semantic,
        entity_schema_score=entity_schema,
        freshness_score=freshness,
    )


def _quotas(
    *, a_schema: int = 20, a_record: int = 20, b_schema: int = 20, b_record: int = 20
) -> tuple[ObjectiveTableQuotaV2, ...]:
    return (
        ObjectiveTableQuotaV2(
            table_id=TABLE_A, schema_candidates=a_schema, record_candidates=a_record
        ),
        ObjectiveTableQuotaV2(
            table_id=TABLE_B, schema_candidates=b_schema, record_candidates=b_record
        ),
    )


def _edge(
    source: RawRetrievalHitV2, target: RawRetrievalHitV2, ordinal: int = 0
) -> RetrievalRelationEdgeProjectionV2:
    values = {
        "version": "retrieval-relation-edge.v2",
        "relation_id": f"relation:{ordinal}",
        "source_table_id": source.table_id,
        "source_record_id": source.record_id,
        "link_field_id": FIELD_A,
        "target_table_id": target.table_id,
        "target_record_id": target.record_id,
        "direction": "forward",
        "source_version": source.source_version,
        "target_version": target.source_version,
        "visibility_profile_hash": "b" * 64,
        "scope_hash": WHOLE_TABLE_SCOPE_HASH,
    }
    return RetrievalRelationEdgeProjectionV2(
        **values,
        edge_hash=canonical_retrieval_sha256(values),
    )


def test_effective_retrieval_scope_hash_binds_views_and_whole_table() -> None:
    builder = getattr(
        retrieval_hybrid,
        "build_effective_retrieval_scope_hash",
        lambda **_: "missing-effective-retrieval-scope",
    )

    assert builder(
        schema_scope_hash=SCOPE_HASH,
        scope_view_ids=(VIEW_B, VIEW_A),
        allow_whole_table=False,
    ) == VIEW_SCOPE_HASH
    assert builder(
        schema_scope_hash=SCOPE_HASH,
        scope_view_ids=(VIEW_A, VIEW_B),
        allow_whole_table=False,
    ) == VIEW_SCOPE_HASH
    assert builder(
        schema_scope_hash=SCOPE_HASH,
        scope_view_ids=(),
        allow_whole_table=True,
    ) == WHOLE_TABLE_SCOPE_HASH


def test_schema_scope_hash_alone_cannot_authorize_retrieval_release() -> None:
    request = _request().model_copy(update={"scope_hash": SCOPE_HASH})
    with pytest.raises(RetrievalV2Denied, match="retrieval_request_scope_denied"):
        retrieve_authorized_candidates(
            request=request,
            context=_context(),
            exact_entity_hits=(),
            fuzzy_hits=(),
            relation_edges=(),
            relation_target_hits=(),
            active_embedding_profile=PROFILE,
            table_quotas=_quotas(),
        )


def test_exact_identifier_survives_zero_semantic_similarity() -> None:
    exact = _hit("record:exact", semantic=0.0, embedding_profile=None)

    result = retrieve_authorized_candidates(
        request=_request(exact_record_ids=(exact.record_id,)),
        context=_context(),
        exact_entity_hits=(exact,),
        fuzzy_hits=(_hit("record:fuzzy", semantic=1.0),),
        relation_edges=(),
        relation_target_hits=(),
        active_embedding_profile=PROFILE,
        table_quotas=_quotas(),
    )

    assert result.candidates[0].source_id == "record:exact"
    assert result.candidates[0].priority_band == "exact"
    assert result.candidates[0].retrieval_reason == "exact_identifier"


def test_hard_authority_filters_run_before_score_normalization() -> None:
    authorized = _hit("record:authorized", semantic=0.5)
    wrong_workspace = _hit(
        "record:wrong-workspace",
        workspace_id=UUID("30000000-0000-0000-0000-000000000001"),
        semantic=100.0,
    )
    hidden_field = _hit(
        "record:hidden-field",
        field_ids=(FIELD_A, HIDDEN_FIELD),
        semantic=100.0,
    )

    result = retrieve_authorized_candidates(
        request=_request(),
        context=_context(),
        exact_entity_hits=(),
        fuzzy_hits=(wrong_workspace, hidden_field, authorized),
        relation_edges=(),
        relation_target_hits=(),
        active_embedding_profile=PROFILE,
        table_quotas=_quotas(),
    )

    assert [item.source_id for item in result.candidates] == ["record:authorized"]
    assert result.candidates[0].scores.semantic == 1.0
    assert result.candidates[0].scores.total == 0.35


def test_objective_specific_schema_and_record_quotas_are_independent() -> None:
    hits = (
        _hit("schema:a1", source_type="schema_field", record_id=None, semantic=1.0),
        _hit("schema:a2", source_type="schema_field", record_id=None, semantic=0.9),
        _hit("record:a1", semantic=0.8),
        _hit("record:a2", semantic=0.7),
        _hit("record:b1", table_id=TABLE_B, semantic=0.6),
        _hit("record:b2", table_id=TABLE_B, semantic=0.5),
        _hit("record:b3", table_id=TABLE_B, semantic=0.4),
    )

    result = retrieve_authorized_candidates(
        request=_request(),
        context=_context(),
        exact_entity_hits=(),
        fuzzy_hits=hits,
        relation_edges=(),
        relation_target_hits=(),
        active_embedding_profile=PROFILE,
        table_quotas=_quotas(a_schema=1, a_record=1, b_schema=0, b_record=2),
    )

    assert {item.source_id for item in result.primary_candidates} == {
        "schema:a1",
        "record:a1",
        "record:b1",
        "record:b2",
    }


def test_relation_candidates_require_verified_edge_and_obey_per_primary_budget() -> (
    None
):
    primary = _hit("record:primary", entity_schema=1.0)
    targets = tuple(
        _hit(f"record:target-{index}", table_id=TABLE_B) for index in range(12)
    )
    unrelated = _hit("record:unrelated", table_id=TABLE_B)
    edges = tuple(_edge(primary, target, index) for index, target in enumerate(targets))

    result = retrieve_authorized_candidates(
        request=_request(max_relation_expansions_per_primary=10),
        context=_context(),
        exact_entity_hits=(),
        fuzzy_hits=(primary,),
        relation_edges=edges,
        relation_target_hits=(*targets, unrelated),
        active_embedding_profile=PROFILE,
        table_quotas=_quotas(),
    )

    linked = [item for item in result.candidates if item.priority_band == "linked"]
    assert len(linked) == 10
    assert unrelated.source_id not in {item.source_id for item in linked}
    assert all(item.retrieval_reason == "linked_expansion" for item in linked)
    assert len(result.relation_edges) == 10
    assert result.truncated is True


def test_primary_budget_scores_reasons_and_stable_ties_are_deterministic() -> None:
    hits = tuple(
        _hit(f"record:{index:02d}", keyword=1.0, semantic=1.0) for index in range(25)
    )

    first = retrieve_authorized_candidates(
        request=_request(max_primary_candidates=20),
        context=_context(),
        exact_entity_hits=(),
        fuzzy_hits=tuple(reversed(hits)),
        relation_edges=(),
        relation_target_hits=(),
        active_embedding_profile=PROFILE,
        table_quotas=_quotas(),
    )
    second = retrieve_authorized_candidates(
        request=_request(max_primary_candidates=20),
        context=_context(),
        exact_entity_hits=(),
        fuzzy_hits=hits,
        relation_edges=(),
        relation_target_hits=(),
        active_embedding_profile=PROFILE,
        table_quotas=_quotas(),
    )

    assert len(first.primary_candidates) == 20
    assert first.truncated is True
    assert [item.source_id for item in first.candidates] == [
        item.source_id for item in second.candidates
    ]
    assert first.candidates[0].scores.model_dump() == {
        "keyword": 1.0,
        "semantic": 1.0,
        "entity_schema": 0.0,
        "freshness": 0.0,
        "total": 0.7,
    }
    assert first.candidates[0].retrieval_reason == "hybrid"
    assert [item.source_id for item in first.primary_candidates] == sorted(
        item.source_id for item in first.primary_candidates
    )


def test_reranker_may_only_reorder_existing_fuzzy_candidate_ids() -> None:
    hits = (_hit("record:a", semantic=1.0), _hit("record:b", semantic=0.5))

    with pytest.raises(RetrievalV2Denied, match="retrieval_reranker_candidate_invalid"):
        retrieve_authorized_candidates(
            request=_request(),
            context=_context(),
            exact_entity_hits=(),
            fuzzy_hits=hits,
            relation_edges=(),
            relation_target_hits=(),
            active_embedding_profile=PROFILE,
            table_quotas=_quotas(),
            reranker=lambda candidate_ids: (*candidate_ids, "invented"),
        )
