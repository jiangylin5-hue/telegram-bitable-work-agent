from datetime import UTC, datetime
from uuid import UUID

import pytest

import app.api.routes.agent_runs as agent_run_routes
from app.core.config import Settings
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalSource,
)
from app.schemas.agent_event_runtime import AgentRunCreateRequest
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_records import (
    build_authorized_query_context,
    scan_authorized_records,
)
from app.services.permissions import Actor
from app.services.retrieval_v2_projection import (
    build_record_projection,
    build_relation_projections,
    chunk_projection,
)
from app.services.retrieval_v2_runtime import load_authorized_retrieval_v2
from app.services.retrieval_v2_scope import effective_retrieval_scope_hash
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    update_record,
)


NOW = datetime(2026, 7, 30, 14, 0, tzinfo=UTC)
PROFILE = "stage12.openrouter-bge-m3-v1"


class _Counter:
    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(ord(item) for item in text)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "".join(chr(item) for item in token_ids)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="runtime-owner", role="owner")
    workspace = create_workspace(
        uow,
        name="Runtime retrieval",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="Delivery", actor=actor)
    table = create_table(
        uow,
        base.id,
        name="工作项",
        key="work_items",
        actor=actor,
    )
    code = create_field(
        uow,
        table.id,
        name="编号",
        key="ticket_code",
        field_type="text",
        actor=actor,
    )
    title = create_field(
        uow,
        table.id,
        name="标题",
        key="title",
        field_type="text",
        actor=actor,
    )
    secret = create_field(
        uow,
        table.id,
        name="内部备注",
        key="internal_note",
        field_type="text",
        actor=actor,
    )
    table.settings = {
        **table.settings,
        "identity_field_key": "ticket_code",
        "stage12_schema_version": 1,
    }
    record = create_record(
        uow,
        table.id,
        values={
            "ticket_code": "CASE-42",
            "title": "Atlas 回滚检查",
            "internal_note": "never-release-secret",
        },
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Retrieval employee",
        description="Stage12 runtime loader",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        field_policy=build_stage12_field_policy_v2(
            readable_field_ids=(code.id, title.id),
            writable_field_ids=(),
        ),
        allowed_actions=["query"],
        actor=actor,
    )
    return uow, actor, workspace, base, table, code, title, secret, record, employee


def _seed_current_projection(uow, actor, workspace, base, table, record, employee):
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        require_field_policy_v2=True,
    )
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    fields = tuple(item.field_id for item in snapshot.tables[0].fields)
    authorized = next(
        item
        for item in scan_authorized_records(
            context=context,
            table_id=table.id,
            required_field_ids=fields,
        ).records
        if item.record_id == record.id
    )
    projection = build_record_projection(
        snapshot,
        authorized,
        retrieval_scope_hash=effective_retrieval_scope_hash(context),
        retrievable_field_ids=frozenset(fields),
        long_text_field_ids=frozenset(),
        field_positions={
            field.id: field.order_index for field in uow.list_fields(table.id)
        },
    )
    chunks = chunk_projection(
        projection,
        token_counter=_Counter(),
        max_tokens=8192,
        overlap_tokens=32,
    )
    index = uow.stage12_retrieval_uow
    index.profiles.append(
        Stage12RetrievalProfile(
            id=UUID("90000000-0000-4000-8000-000000000001"),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    source = Stage12RetrievalSource(
        id=UUID("90000000-0000-4000-8000-000000000002"),
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=record.id,
        field_ids=list(projection.field_ids),
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        embedding_profile=PROFILE,
        visibility_profile_hash=projection.visibility_profile_hash,
        scope_hash=projection.scope_hash,
        content_hash=projection.content_hash,
        status="indexed",
        is_active=True,
        activated_at=NOW,
        revoked_at=None,
    )
    index.sources.append(source)
    index.chunks.extend(
        Stage12RetrievalChunk(
            id=UUID(int=100 + item.ordinal),
            workspace_id=workspace.id,
            source_id=source.id,
            source_version=source.source_version,
            ordinal=item.ordinal,
            chunk_kind=item.chunk_kind,
            source_type=item.source_type,
            table_id=item.table_id,
            record_id=item.record_id,
            field_ids=list(item.field_ids),
            start_token=item.start_token,
            end_token=item.end_token,
            chunk_text=item.chunk_text,
            keyword_terms=list(item.keyword_terms),
            content_hash=item.content_hash,
            visibility_profile_hash=item.visibility_profile_hash,
            scope_hash=item.scope_hash,
            embedding_profile=PROFILE,
            embedding=[1.0] + [0.0] * 1023,
            status="indexed",
            revoked_at=None,
            created_at=NOW,
            updated_at=NOW,
        )
        for item in chunks
    )
    return source


def test_runtime_loader_returns_only_current_authorized_projection() -> None:
    fixture = _fixture()
    uow, actor, workspace, base, table, _code, _title, _secret, record, employee = (
        fixture
    )
    _seed_current_projection(uow, actor, workspace, base, table, record, employee)

    result = load_authorized_retrieval_v2(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        query="查看 CASE-42 的 Atlas 回滚检查",
        actor=actor,
        active_embedding_profile=PROFILE,
        query_embedding=(1.0,) + (0.0,) * 1023,
    )

    assert [item.source_id for item in result.primary_candidates] == [
        f"record:{record.id}"
    ]
    assert "never-release-secret" not in str(result)
    registrations = uow.stage12_retrieval_uow.registrations
    assert len(registrations) == 1
    assert registrations[0].status == "active"
    assert registrations[0].retrieval_scope_hash == result.candidates[0].scope_hash


def test_runtime_loader_expands_only_current_authorized_relation_target() -> None:
    fixture = _fixture()
    uow, actor, workspace, base, table, code, title, _secret, source, employee = (
        fixture
    )
    link = create_field(
        uow,
        table.id,
        name="Related work",
        key="related_work",
        field_type="linked_record",
        options={"target_table_id": str(table.id)},
        actor=actor,
    )
    target = create_record(
        uow,
        table.id,
        values={"ticket_code": "CASE-99", "title": "Downstream evidence"},
        actor=actor,
    )
    update_record(
        uow,
        source.id,
        values={"related_work": [str(target.id)]},
        expected_version=source.version,
        actor=actor,
    )
    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(code.id, title.id, link.id),
        writable_field_ids=(),
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        require_field_policy_v2=True,
    )
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    visible_fields = tuple(item.field_id for item in snapshot.tables[0].fields)
    records = scan_authorized_records(
        context=context,
        table_id=table.id,
        required_field_ids=visible_fields,
    ).records
    index = uow.stage12_retrieval_uow
    index.profiles.append(
        Stage12RetrievalProfile(
            id=UUID("91000000-0000-4000-8000-000000000001"),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    positions = {
        field.id: field.order_index for field in uow.list_fields(table.id)
    }
    for ordinal, authorized_record in enumerate(records, start=1):
        projection = build_record_projection(
            snapshot,
            authorized_record,
            retrieval_scope_hash=effective_retrieval_scope_hash(context),
            retrievable_field_ids=frozenset(visible_fields),
            long_text_field_ids=frozenset(),
            field_positions=positions,
        )
        chunks = chunk_projection(
            projection,
            token_counter=_Counter(),
            max_tokens=8192,
            overlap_tokens=32,
        )
        persisted_source = Stage12RetrievalSource(
            id=UUID(int=1000 + ordinal),
            workspace_id=workspace.id,
            base_id=base.id,
            table_id=table.id,
            record_id=authorized_record.record_id,
            field_ids=list(projection.field_ids),
            source_type=projection.source_type,
            source_identity=projection.source_id,
            source_version=projection.source_version,
            embedding_profile=PROFILE,
            visibility_profile_hash=projection.visibility_profile_hash,
            scope_hash=projection.scope_hash,
            content_hash=projection.content_hash,
            status="indexed",
            is_active=True,
            activated_at=NOW,
            revoked_at=None,
        )
        index.sources.append(persisted_source)
        embedding = (
            [1.0] + [0.0] * 1023
            if authorized_record.record_id == source.id
            else [0.0, 1.0] + [0.0] * 1022
        )
        index.chunks.extend(
            Stage12RetrievalChunk(
                id=UUID(int=2000 + ordinal * 10 + chunk.ordinal),
                workspace_id=workspace.id,
                source_id=persisted_source.id,
                source_version=persisted_source.source_version,
                ordinal=chunk.ordinal,
                chunk_kind=chunk.chunk_kind,
                source_type=chunk.source_type,
                table_id=chunk.table_id,
                record_id=chunk.record_id,
                field_ids=list(chunk.field_ids),
                start_token=chunk.start_token,
                end_token=chunk.end_token,
                chunk_text=chunk.chunk_text,
                keyword_terms=list(chunk.keyword_terms),
                content_hash=chunk.content_hash,
                visibility_profile_hash=chunk.visibility_profile_hash,
                scope_hash=chunk.scope_hash,
                embedding_profile=PROFILE,
                embedding=embedding,
                status="indexed",
                revoked_at=None,
                created_at=NOW,
                updated_at=NOW,
            )
            for chunk in chunks
        )
    catalog = build_authorized_relation_catalog(uow, snapshot)
    assert len(catalog) == 1
    source_record = next(item for item in records if item.record_id == source.id)
    source_values = {item.field_id: item.value for item in source_record.values}
    assert source_values[link.id] == [
        {"id": str(target.id), "label": "CASE-99"}
    ]
    projected_edges = build_relation_projections(
        snapshot,
        retrieval_scope_hash=effective_retrieval_scope_hash(context),
        records=records,
        catalog=catalog,
    )
    assert len(projected_edges) == 1
    edge = projected_edges[0]
    index.relation_edges = [
        Stage12RelationEdge(
            id=UUID("91000000-0000-4000-8000-000000000002"),
            workspace_id=workspace.id,
            relation_id=edge.relation_id,
            source_table_id=edge.source_table_id,
            source_record_id=edge.source_record_id,
            link_field_id=edge.link_field_id,
            target_table_id=edge.target_table_id,
            target_record_id=edge.target_record_id,
            direction=edge.direction,
            source_version=edge.source_version,
            target_version=edge.target_version,
            visibility_profile_hash=edge.visibility_profile_hash,
            scope_hash=edge.scope_hash,
            edge_hash=edge.edge_hash,
            status="active",
            revoked_at=None,
        )
    ]

    result = load_authorized_retrieval_v2(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        query="CASE-42",
        actor=actor,
        active_embedding_profile=PROFILE,
        query_embedding=(1.0,) + (0.0,) * 1023,
    )

    assert [item.record_id for item in result.primary_candidates] == [source.id]
    linked = tuple(
        item for item in result.candidates if item.priority_band == "linked"
    )
    assert [item.record_id for item in linked] == [target.id]
    assert result.relation_edges == projected_edges


def test_runtime_loader_rejects_stale_record_and_policy_contraction() -> None:
    fixture = _fixture()
    uow, actor, workspace, base, table, code, _title, _secret, record, employee = (
        fixture
    )
    _seed_current_projection(uow, actor, workspace, base, table, record, employee)
    update_record(
        uow,
        record.id,
        values={"title": "new current value"},
        expected_version=record.version,
        actor=actor,
    )

    stale = load_authorized_retrieval_v2(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        query="CASE-42",
        actor=actor,
        active_embedding_profile=PROFILE,
        query_embedding=(1.0,) + (0.0,) * 1023,
    )
    assert stale.candidates == ()

    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(code.id,),
        writable_field_ids=(),
    )
    contracted = load_authorized_retrieval_v2(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        query="CASE-42",
        actor=actor,
        active_embedding_profile=PROFILE,
        query_embedding=(1.0,) + (0.0,) * 1023,
    )
    assert contracted.candidates == ()


def test_runtime_loader_requires_stage12_field_policy_v2() -> None:
    fixture = _fixture()
    uow, actor, workspace, _base, _table, _code, _title, _secret, _record, employee = (
        fixture
    )
    employee.field_policy = {}

    with pytest.raises(
        PlatformValidationError,
        match="digital_employee_field_policy_v2_required",
    ):
        load_authorized_retrieval_v2(
            uow,
            workspace_id=workspace.id,
            employee_id=employee.id,
            query="CASE-42",
            actor=actor,
            active_embedding_profile=PROFILE,
            query_embedding=None,
        )


def test_route_shadow_loader_returns_materialized_authorized_candidates(
    monkeypatch,
) -> None:
    fixture = _fixture()
    uow, actor, workspace, base, table, _code, _title, _secret, record, employee = (
        fixture
    )
    _seed_current_projection(uow, actor, workspace, base, table, record, employee)

    class QueryProvider:
        closed = False

        def embed_queries(self, texts):
            assert texts == ("查看 CASE-42",)
            return ((1.0,) + (0.0,) * 1023,)

        def close(self):
            self.closed = True

    provider = QueryProvider()
    monkeypatch.setattr(
        agent_run_routes,
        "build_stage12_query_embedding_provider",
        lambda _settings: provider,
    )
    settings = Settings(
        openrouter_api_key="synthetic-key",
        retrieval_v2_mode="shadow",
        retrieval_v2_workspace_allowlist=(str(workspace.id),),
        retrieval_v2_active_profile=PROFILE,
    )

    loaded = agent_run_routes._load_retrieval_v2_shadow_candidates(
        settings=settings,
        request=AgentRunCreateRequest(
            workspace_id=workspace.id,
            employee_id=employee.id,
            intent="business_fact",
            query="查看 CASE-42",
            requested_action="read_only",
            target_record_id=None,
            idempotency_key="runtime-shadow-loader-1",
            skill_id=None,
        ),
        actor=actor,
        platform_uow=uow,
    )

    assert [item.source_id for item in loaded.v2_result.primary_candidates] == [
        f"record:{record.id}"
    ]
    assert provider.closed is True
