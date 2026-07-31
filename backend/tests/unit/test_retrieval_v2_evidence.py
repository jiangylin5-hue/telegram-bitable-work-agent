from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from app.schemas.authorized_query_plan import (
    StructuredAggregate,
    StructuredQueryResultV1,
    structured_query_result_sha256,
)
from app.schemas.retrieval_v2 import (
    RetrievalCandidateV2,
    RetrievalComponentScoresV2,
    RetrievalRelationEdgeProjectionV2,
    RetrievalRequestV2,
    canonical_retrieval_sha256,
)
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.authorized_query_records import (
    AuthorizedQueryContext,
    build_authorized_query_context,
)
from app.services.retrieval_v2_evidence import assemble_evidence_bundle
from app.services.retrieval_v2_hybrid import AuthorizedRetrievalResultV2
from app.services.retrieval_v2_scope import effective_retrieval_scope_hash
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    replace_field_permission_policy,
)


@dataclass(frozen=True)
class _Fixture:
    context: AuthorizedQueryContext
    request: RetrievalRequestV2
    project_table_id: UUID
    work_table_id: UUID
    project_record_id: UUID
    work_record_id: UUID
    project_code_id: UUID
    work_code_id: UUID
    status_id: UUID
    secret_id: UUID
    link_id: UUID


def _fixture(*, max_evidence_nodes: int = 24) -> _Fixture:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-evidence", role="owner")
    workspace = create_workspace(
        uow,
        name="Evidence",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="Delivery", actor=actor)
    project_table = create_table(
        uow, base.id, name="Projects", key="projects", actor=actor
    )
    work_table = create_table(uow, base.id, name="Work", key="work", actor=actor)
    project_code = create_field(
        uow,
        project_table.id,
        name="Project code",
        key="project_code",
        field_type="text",
        actor=actor,
    )
    work_code = create_field(
        uow,
        work_table.id,
        name="Work code",
        key="work_code",
        field_type="text",
        actor=actor,
    )
    status = create_field(
        uow, work_table.id, name="Status", key="status", field_type="text", actor=actor
    )
    secret = create_field(
        uow, work_table.id, name="Secret", key="secret", field_type="text", actor=actor
    )
    link = create_field(
        uow,
        work_table.id,
        name="Project",
        key="project_link",
        field_type="linked_record",
        options={"target_table_id": str(project_table.id)},
        actor=actor,
    )
    project = create_record(
        uow, project_table.id, values={"project_code": "PRJ-ATLAS"}, actor=actor
    )
    work = create_record(
        uow,
        work_table.id,
        values={
            "work_code": "MT-001",
            "status": "blocked",
            "secret": "do-not-release",
            "project_link": [str(project.id)],
        },
        actor=actor,
    )
    replace_field_permission_policy(
        uow,
        work_table.id,
        secret.id,
        policy={
            "owner": "write",
            "admin": "hidden",
            "builder": "hidden",
            "operator": "hidden",
            "viewer": "hidden",
        },
        expected_permission_version=1,
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Evidence employee",
        description="read",
        telegram_alias=None,
        accessible_tables=[str(project_table.id), str(work_table.id)],
        accessible_views=[],
        allowed_actions=["record.query"],
        actor=actor,
    )
    evidence_actor = Actor(
        actor_type="user",
        actor_id=actor.actor_id,
        role="viewer",
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=evidence_actor,
    )
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        actor=evidence_actor,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    request = RetrievalRequestV2(
        version="retrieval-request.v2",
        objective_id="obj-evidence",
        query="Atlas 阻塞项",
        workspace_id=workspace.id,
        base_id=base.id,
        table_ids=(project_table.id, work_table.id),
        exact_record_ids=(work.id,),
        query_result_ref="artifact:query-result",
        scope_hash=effective_retrieval_scope_hash(context),
        schema_hash=snapshot.schema_hash,
        max_primary_candidates=20,
        max_relation_expansions_per_primary=10,
        max_evidence_nodes=max_evidence_nodes,
    )
    return _Fixture(
        context=context,
        request=request,
        project_table_id=project_table.id,
        work_table_id=work_table.id,
        project_record_id=project.id,
        work_record_id=work.id,
        project_code_id=project_code.id,
        work_code_id=work_code.id,
        status_id=status.id,
        secret_id=secret.id,
        link_id=link.id,
    )


def _candidate(
    source_id: str,
    *,
    scope_hash: str,
    table_id: UUID,
    record_id: UUID | None,
    field_ids: tuple[UUID, ...],
    source_version: int,
    source_type: str = "record",
    priority_band: str = "fuzzy",
    reason: str = "semantic",
) -> RetrievalCandidateV2:
    return RetrievalCandidateV2(
        version="retrieval-candidate.v2",
        candidate_id=f"candidate:{source_id}",
        source_type=source_type,
        source_id=source_id,
        source_version=source_version,
        table_id=table_id,
        record_id=record_id,
        field_ids=field_ids,
        priority_band=priority_band,
        retrieval_reason=reason,
        scores=RetrievalComponentScoresV2(
            keyword=0.0,
            semantic=1.0,
            entity_schema=0.0,
            freshness=0.0,
            total=0.35,
        ),
        scope_hash=scope_hash,
        content_hash=sha256(source_id.encode()).hexdigest(),
        embedding_profile=(
            "stage12.openrouter-bge-m3-v1" if priority_band == "fuzzy" else None
        ),
    )


def _result(
    candidates: tuple[RetrievalCandidateV2, ...],
    *,
    scope_hash: str,
    relation_edges: tuple[RetrievalRelationEdgeProjectionV2, ...] = (),
    truncated: bool = False,
) -> AuthorizedRetrievalResultV2:
    return AuthorizedRetrievalResultV2(
        candidates=candidates,
        primary_candidates=candidates,
        relation_edges=relation_edges,
        truncated=truncated,
    )


def _query_result(
    *,
    scope_hash: str,
    schema_hash: str,
    aggregate: int | None = None,
    truncated: bool = False,
) -> StructuredQueryResultV1:
    aggregates = (
        ()
        if aggregate is None
        else (
            StructuredAggregate(
                aggregate_id="agg-count", group_key=None, value=aggregate
            ),
        )
    )
    values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": "a" * 64,
        "records": (),
        "groups": (),
        "aggregates": aggregates,
        "relation_paths": (),
        "source_versions": (),
        "scope_hash": scope_hash,
        "schema_hash": schema_hash,
        "scanned_record_count": 0,
        "traversed_edge_count": 0,
        "truncated": truncated,
    }
    return StructuredQueryResultV1(
        **values,
        result_hash=structured_query_result_sha256(
            StructuredQueryResultV1.model_construct(
                **values,
                result_hash="0" * 64,
            ).model_dump(mode="json", exclude={"result_hash"})
        ),
    )


def _edge(
    fixture: _Fixture, *, work_version: int, project_version: int
) -> RetrievalRelationEdgeProjectionV2:
    values = {
        "version": "retrieval-relation-edge.v2",
        "relation_id": f"relation:{fixture.link_id}",
        "source_table_id": fixture.work_table_id,
        "source_record_id": fixture.work_record_id,
        "link_field_id": fixture.link_id,
        "target_table_id": fixture.project_table_id,
        "target_record_id": fixture.project_record_id,
        "direction": "forward",
        "source_version": work_version,
        "target_version": project_version,
        "visibility_profile_hash": "c" * 64,
        "scope_hash": fixture.request.scope_hash,
    }
    return RetrievalRelationEdgeProjectionV2(
        **values,
        edge_hash=canonical_retrieval_sha256(values),
    )


def test_bundle_issues_stable_evidence_ids_safe_fields_relations_and_citations() -> (
    None
):
    fixture = _fixture()
    work = fixture.context.uow.get_record(fixture.work_record_id)
    project = fixture.context.uow.get_record(fixture.project_record_id)
    assert work is not None and project is not None
    work_candidate = _candidate(
        f"record:{work.id}",
        scope_hash=fixture.request.scope_hash,
        table_id=fixture.work_table_id,
        record_id=work.id,
        field_ids=(fixture.work_code_id, fixture.status_id),
        source_version=work.version,
    )
    project_candidate = _candidate(
        f"record:{project.id}",
        scope_hash=fixture.request.scope_hash,
        table_id=fixture.project_table_id,
        record_id=project.id,
        field_ids=(fixture.project_code_id,),
        source_version=project.version,
    )
    edge = _edge(fixture, work_version=work.version, project_version=project.version)
    retrieval = _result(
        (work_candidate, project_candidate),
        scope_hash=fixture.request.scope_hash,
        relation_edges=(edge,),
    )
    versions = {
        work_candidate.source_id: work.version,
        project_candidate.source_id: project.version,
    }

    first = assemble_evidence_bundle(
        request=fixture.request,
        context=fixture.context,
        retrieval=retrieval,
        structured_query_result=None,
        active_source_versions=versions,
    )
    second = assemble_evidence_bundle(
        request=fixture.request,
        context=fixture.context,
        retrieval=retrieval,
        structured_query_result=None,
        active_source_versions=versions,
    )

    assert first.bundle.bundle_hash == second.bundle.bundle_hash
    assert all(node.evidence_id.startswith("ev-") for node in first.bundle.nodes)
    assert {citation.evidence_id for citation in first.citations} == {
        node.evidence_id for node in first.bundle.nodes
    }
    work_node = next(node for node in first.bundle.nodes if node.record_id == work.id)
    assert {field.field_key for field in work_node.fields} == {"work_code", "status"}
    assert "do-not-release" not in repr(first)
    assert fixture.secret_id not in {field.field_id for field in work_node.fields}
    assert len(first.bundle.relations) == 1
    assert first.bundle.relations[0].source_version == work.version
    assert first.bundle.relations[0].target_version == project.version
    assert first.bundle.query_result_ref == "artifact:query-result"
    assert first.bundle.complete is True
    assert first.bundle.truncated is False


def test_any_evidence_budget_cut_sets_truncated_and_incomplete() -> None:
    fixture = _fixture(max_evidence_nodes=1)
    schema_candidates = tuple(
        _candidate(
            f"schema-field:{index}",
            scope_hash=fixture.request.scope_hash,
            table_id=fixture.work_table_id,
            record_id=None,
            field_ids=(fixture.work_code_id,),
            source_version=1,
            source_type="schema_field",
        )
        for index in range(2)
    )

    assembly = assemble_evidence_bundle(
        request=fixture.request,
        context=fixture.context,
        retrieval=_result(schema_candidates, scope_hash=fixture.request.scope_hash),
        structured_query_result=None,
        active_source_versions={
            candidate.source_id: 1 for candidate in schema_candidates
        },
    )

    assert len(assembly.bundle.nodes) == 1
    assert assembly.bundle.truncated is True
    assert assembly.bundle.complete is False


def test_complete_structured_aggregate_remains_exact_without_contributing_record_text() -> (
    None
):
    fixture = _fixture()
    query_result = _query_result(
        scope_hash=fixture.context.snapshot.scope_hash,
        schema_hash=fixture.request.schema_hash,
        aggregate=37,
    )

    assembly = assemble_evidence_bundle(
        request=fixture.request,
        context=fixture.context,
        retrieval=_result((), scope_hash=fixture.request.scope_hash),
        structured_query_result=query_result,
        active_source_versions={},
        aggregate_output_keys={"agg-count": "blocked_count"},
    )

    assert assembly.bundle.nodes == ()
    assert assembly.bundle.aggregates[0].value == 37
    assert assembly.bundle.aggregates[0].output_key == "blocked_count"
    assert assembly.bundle.aggregates[0].query_result_ref == "artifact:query-result"
    assert assembly.bundle.complete is True
    assert assembly.bundle.truncated is False
