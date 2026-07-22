from datetime import UTC, datetime, timedelta
import hashlib
import os
import re
from uuid import UUID, uuid4

import pytest
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    create_engine,
    event,
    func,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import OpsAuditEvent
from app.models.outbox import OutboxEvent
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.models.stage06_platform import Workspace, WorkspaceMember
from app.models.stage06_runtime import DigitalEmployee
from app.models.stage08_knowledge import (
    Stage08KnowledgeChunk,
    Stage08KnowledgeSource,
)
from app.models.stage08_memory import Stage08MemoryItem
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.runtime.stage08_collaboration_contracts import (
    Stage08CollaborationContractFactory,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_memory import materialize_memory_from_projection
from app.services.stage08_collaboration import execute_collaboration_reads
from app.services.stage08_retrieval import (
    process_knowledge_cleanup_event,
    process_knowledge_index_event,
    register_memory_knowledge_source,
    request_knowledge_reindex,
    revoke_knowledge_source,
)
from app.services.stage08_retrieval_embeddings import TestHashEmbeddingProvider
from app.services.stage08_retrieval_provider import (
    PostgresRetrievalProvider,
    Stage08RetrievalAuthorityFactory,
)


STAGE08_RAG_DATABASE_URL_ENV = "STAGE08_RAG_DATABASE_URL"

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _stage08_rag_database_url() -> str:
    database_url = os.getenv(STAGE08_RAG_DATABASE_URL_ENV)
    if not database_url:
        pytest.skip(
            "STAGE08_RAG_DATABASE_URL is required for Stage08 pgvector integration"
        )
    return database_url


def _normalized_sql(value: str) -> str:
    return " ".join(value.lower().split())


def _status_literals(check_sql: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", check_sql))


def test_stage08_rag_database_has_vector_extension() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            extension_version = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
    finally:
        engine.dispose()

    assert extension_version is not None, "pgvector extension 'vector' is unavailable"


def test_stage08_knowledge_migration_has_exact_tables_columns_and_constraints() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    try:
        inspector = inspect(engine)
        assert {
            "stage08_knowledge_sources",
            "stage08_knowledge_chunks",
        } <= set(inspector.get_table_names())

        source_columns = {
            column["name"]: column
            for column in inspector.get_columns("stage08_knowledge_sources")
        }
        assert set(source_columns) == {
            "id",
            "workspace_id",
            "source_type",
            "status",
            "source_ref",
            "scope",
            "logical_source_fingerprint",
            "projection_hash",
            "projection_text",
            "content_version",
            "supersedes_id",
            "valid_until",
            "revoked_at",
            "deleted_at",
            "created_at",
            "updated_at",
        }
        assert isinstance(source_columns["source_ref"]["type"], postgresql.JSONB)
        assert isinstance(source_columns["scope"]["type"], postgresql.JSONB)
        assert isinstance(source_columns["content_version"]["type"], Integer)
        assert source_columns["projection_text"]["nullable"] is True
        for name in ("valid_until", "revoked_at", "deleted_at"):
            assert isinstance(source_columns[name]["type"], DateTime)
            assert source_columns[name]["type"].timezone is True

        with engine.connect() as connection:
            chunk_column_rows = connection.execute(
                text(
                    "SELECT column_name, data_type, udt_name, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'stage08_knowledge_chunks'"
                )
            ).mappings()
            chunk_columns = {
                row["column_name"]: row for row in chunk_column_rows
            }
            keyword_terms_type = connection.scalar(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) "
                    "FROM pg_attribute a "
                    "WHERE a.attrelid = 'stage08_knowledge_chunks'::regclass "
                    "AND a.attname = 'keyword_terms'"
                )
            )
        assert set(chunk_columns) == {
            "id",
            "workspace_id",
            "source_id",
            "source_version",
            "ordinal",
            "chunk_text",
            "chunk_hash",
            "keyword_terms",
            "embedding_profile",
            "embedding_version",
            "embedding",
            "status",
            "deleted_at",
            "created_at",
            "updated_at",
        }
        assert chunk_columns["source_version"]["data_type"] == "integer"
        assert chunk_columns["ordinal"]["data_type"] == "integer"
        assert chunk_columns["keyword_terms"]["data_type"] == "ARRAY"
        assert keyword_terms_type == "character varying(64)[]"
        assert chunk_columns["keyword_terms"]["is_nullable"] == "NO"
        assert chunk_columns["embedding"]["udt_name"] == "vector"
        assert chunk_columns["embedding"]["is_nullable"] == "YES"

        source_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints(
                "stage08_knowledge_sources"
            )
        }
        assert _status_literals(source_checks["ck_stage08_knowledge_source_status"]) == {
            "pending",
            "active",
            "replaced",
            "revoked",
            "expired",
            "deleted",
        }
        assert "jsonb_typeof(source_ref) = 'object'" in _normalized_sql(
            source_checks["ck_stage08_knowledge_source_ref_object"]
        )
        assert "jsonb_typeof(scope) = 'object'" in _normalized_sql(
            source_checks["ck_stage08_knowledge_source_scope_object"]
        )
        assert "content_version > 0" in _normalized_sql(
            source_checks["ck_stage08_knowledge_source_version_positive"]
        )
        assert "projection_text" in _normalized_sql(
            source_checks["ck_stage08_knowledge_source_active_projection"]
        )

        chunk_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints(
                "stage08_knowledge_chunks"
            )
        }
        assert _status_literals(chunk_checks["ck_stage08_knowledge_chunk_status"]) == {
            "pending",
            "indexed",
            "stale",
            "deleted",
            "failed",
        }
        assert "source_version > 0" in _normalized_sql(
            chunk_checks["ck_stage08_knowledge_chunk_source_version_positive"]
        )
        assert "ordinal >= 0" in _normalized_sql(
            chunk_checks["ck_stage08_knowledge_chunk_ordinal_nonnegative"]
        )
        assert "chunk_text" in _normalized_sql(
            chunk_checks["ck_stage08_knowledge_chunk_indexed_text"]
        )

        source_uniques = {
            constraint["name"]: constraint["column_names"]
            for constraint in inspector.get_unique_constraints(
                "stage08_knowledge_sources"
            )
        }
        assert source_uniques[
            "uq_stage08_knowledge_source_workspace_type_fingerprint_version"
        ] == [
            "workspace_id",
            "source_type",
            "logical_source_fingerprint",
            "content_version",
        ]
        assert source_uniques[
            "uq_stage08_knowledge_source_id_workspace_version"
        ] == ["id", "workspace_id", "content_version"]
        chunk_uniques = {
            constraint["name"]: constraint["column_names"]
            for constraint in inspector.get_unique_constraints(
                "stage08_knowledge_chunks"
            )
        }
        assert chunk_uniques[
            "uq_stage08_knowledge_chunk_source_version_ordinal"
        ] == ["source_id", "source_version", "ordinal"]
        chunk_foreign_keys = {
            constraint["name"]: (
                constraint["constrained_columns"],
                constraint["referred_table"],
                constraint["referred_columns"],
            )
            for constraint in inspector.get_foreign_keys(
                "stage08_knowledge_chunks"
            )
        }
        assert chunk_foreign_keys[
            "fk_stage08_knowledge_chunk_source_scope_version"
        ] == (
            ["source_id", "workspace_id", "source_version"],
            "stage08_knowledge_sources",
            ["id", "workspace_id", "content_version"],
        )
    finally:
        engine.dispose()


def test_stage08_knowledge_migration_has_gin_and_exact_partial_hnsw_indexes() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            index_rows = connection.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = current_schema() "
                    "AND tablename IN "
                    "('stage08_knowledge_sources', 'stage08_knowledge_chunks')"
                )
            ).all()
        definitions = {
            row.indexname: _normalized_sql(row.indexdef) for row in index_rows
        }
    finally:
        engine.dispose()

    assert definitions[
        "ix_stage08_knowledge_source_workspace_status_valid_until"
    ]
    assert definitions[
        "ix_stage08_knowledge_source_workspace_fingerprint_version"
    ]
    assert definitions[
        "ix_stage08_knowledge_chunk_workspace_status_source_version"
    ]
    assert definitions["ix_stage08_knowledge_chunk_source_status"]

    gin = definitions["ix_stage08_knowledge_chunk_keyword_terms_gin"]
    assert "using gin (keyword_terms)" in gin

    hnsw = definitions["ix_stage08_knowledge_chunk_hnsw_test_profile"]
    assert "using hnsw" in hnsw
    assert "(((embedding)::vector(8)) vector_cosine_ops)" in hnsw
    assert "((status)::text = 'indexed'::text)" in hnsw
    assert "((embedding_profile)::text = 'stage08.test-hash-v1'::text)" in hnsw
    assert "embedding is not null" in hnsw


def _insert_scope_fk_facts(connection) -> tuple[dict, dict, dict]:
    workspace_a_id = uuid4()
    workspace_b_id = uuid4()
    source_id = uuid4()
    for workspace_id, suffix in (
        (workspace_a_id, "a"),
        (workspace_b_id, "b"),
    ):
        connection.execute(
            Workspace.__table__.insert().values(
                id=workspace_id,
                name=f"D1 scope FK {suffix}",
                slug=f"d1-scope-fk-{suffix}-{uuid4().hex}",
                owner_user_id="d1-scope-fk-owner",
                status="active",
                settings={},
            )
        )
    connection.execute(
        Stage08KnowledgeSource.__table__.insert().values(
            id=source_id,
            workspace_id=workspace_a_id,
            source_type="memory_item",
            status="active",
            source_ref={"entity_kind": "memory_item", "version": 7},
            scope={"scope_category": "business"},
            logical_source_fingerprint=uuid4().hex + uuid4().hex,
            projection_hash=uuid4().hex + uuid4().hex,
            projection_text="approved projection",
            content_version=7,
        )
    )
    common_chunk = {
        "source_id": source_id,
        "workspace_id": workspace_a_id,
        "source_version": 7,
        "ordinal": 0,
        "chunk_text": "approved projection",
        "chunk_hash": uuid4().hex + uuid4().hex,
        "keyword_terms": ["approved", "projection"],
        "embedding_profile": "stage08.test-hash-v1",
        "embedding_version": 1,
        "embedding": [0.1] * 8,
        "status": "indexed",
    }
    return common_chunk, {"workspace_id": workspace_b_id}, {"source_version": 8}


@pytest.mark.parametrize("mismatch_key", ["workspace_id", "source_version"])
def test_chunk_scope_tuple_mismatch_is_rejected_by_postgresql(
    mismatch_key: str,
) -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    try:
        common_chunk, workspace_mismatch, version_mismatch = (
            _insert_scope_fk_facts(connection)
        )
        mismatch = (
            workspace_mismatch
            if mismatch_key == "workspace_id"
            else version_mismatch
        )
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    Stage08KnowledgeChunk.__table__.insert().values(
                        id=uuid4(),
                        **(common_chunk | mismatch),
                    )
                )
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_chunk_matching_source_workspace_version_tuple_is_insertable() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    try:
        common_chunk, _, _ = _insert_scope_fk_facts(connection)
        chunk_id = uuid4()
        connection.execute(
            Stage08KnowledgeChunk.__table__.insert().values(
                id=chunk_id,
                **common_chunk,
            )
        )
        assert connection.scalar(
            text(
                "SELECT count(*) FROM stage08_knowledge_chunks "
                "WHERE id = :chunk_id"
            ),
            {"chunk_id": chunk_id},
        ) == 1
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_d3_worker_persists_vector_replays_and_scrubs_on_cleanup() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        workspace_id = uuid4()
        source_id = uuid4()
        projection_text = "客户 Acme 已批准预算，下一步安排会议。"
        projection_hash = hashlib.sha256(projection_text.encode("utf-8")).hexdigest()
        session.add(
            Workspace(
                id=workspace_id,
                name="D3 pgvector lifecycle",
                slug=f"d3-pgvector-{uuid4().hex}",
                owner_user_id="d3-owner",
                status="active",
                settings={},
            )
        )
        source = Stage08KnowledgeSource(
            id=source_id,
            workspace_id=workspace_id,
            source_type="memory_item",
            status="active",
            source_ref={"memory_item_id": str(uuid4()), "memory_item_version": 1},
            scope={"workspace_id": str(workspace_id)},
            logical_source_fingerprint=hashlib.sha256(
                f"d3-source:{source_id}".encode("utf-8")
            ).hexdigest(),
            projection_hash=projection_hash,
            projection_text=projection_text,
            content_version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        index_event = _d3_reference_event(
            source,
            event_type="stage08.knowledge.index_requested",
            trace_id="a" * 64,
        )
        session.add_all([source, index_event])
        session.flush()
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)

        first = process_knowledge_index_event(
            uow,
            index_event,
            provider=TestHashEmbeddingProvider(),
            now=NOW + timedelta(seconds=1),
        )
        session.flush()
        replay = process_knowledge_index_event(
            uow,
            index_event,
            provider=TestHashEmbeddingProvider(),
            now=NOW + timedelta(seconds=2),
        )
        session.flush()

        assert first.status == replay.status == "indexed"
        assert first.indexed_chunk_count == replay.indexed_chunk_count == 1
        assert connection.scalar(
            text(
                "SELECT count(*) FROM stage08_knowledge_chunks "
                "WHERE source_id = :source_id AND status = 'indexed'"
            ),
            {"source_id": source_id},
        ) == 1
        vector_text = connection.scalar(
            text(
                "SELECT embedding::vector(8)::text "
                "FROM stage08_knowledge_chunks WHERE source_id = :source_id"
            ),
            {"source_id": source_id},
        )
        assert isinstance(vector_text, str)
        assert len(vector_text.strip("[]").split(",")) == 8

        indexed_chunk = uow.list_knowledge_chunks(source.id, source.content_version)[0]
        indexed_chunk.embedding = [0.0] * 8
        index_event.status = "pending"
        index_event.processed_at = None
        vector_conflict = process_knowledge_index_event(
            uow,
            index_event,
            provider=TestHashEmbeddingProvider(),
            now=NOW + timedelta(seconds=3),
        )
        session.flush()

        assert vector_conflict.status == "failed"
        assert vector_conflict.error_code == "knowledge_index_failed"
        assert index_event.status == "pending"
        assert source.status == "active"
        assert source.projection_text == projection_text
        scrubbed_conflict = connection.execute(
            text(
                "SELECT status, chunk_text, keyword_terms, embedding, "
                "embedding_profile, embedding_version "
                "FROM stage08_knowledge_chunks WHERE source_id = :source_id"
            ),
            {"source_id": source_id},
        ).mappings().one()
        assert scrubbed_conflict == {
            "status": "stale",
            "chunk_text": None,
            "keyword_terms": [],
            "embedding": None,
            "embedding_profile": None,
            "embedding_version": None,
        }

        source.status = "replaced"
        for chunk in uow.list_knowledge_chunks(source.id, source.content_version):
            chunk.status = "stale"
        cleanup_event = _d3_reference_event(
            source,
            event_type="stage08.knowledge.cleanup_requested",
            trace_id="b" * 64,
        )
        session.add(cleanup_event)
        session.flush()
        cleaned = process_knowledge_cleanup_event(
            uow,
            cleanup_event,
            now=NOW + timedelta(seconds=4),
        )
        replay_cleaned = process_knowledge_cleanup_event(
            uow,
            cleanup_event,
            now=NOW + timedelta(seconds=5),
        )
        session.flush()

        assert cleaned.status == replay_cleaned.status == "cleaned"
        assert cleaned.cleaned_chunk_count == replay_cleaned.cleaned_chunk_count == 1
        scrubbed = connection.execute(
            text(
                "SELECT status, chunk_text, keyword_terms, embedding, "
                "embedding_profile, embedding_version, deleted_at "
                "FROM stage08_knowledge_chunks WHERE source_id = :source_id"
            ),
            {"source_id": source_id},
        ).mappings().one()
        assert scrubbed["status"] == "deleted"
        assert scrubbed["chunk_text"] is None
        assert scrubbed["keyword_terms"] == []
        assert scrubbed["embedding"] is None
        assert scrubbed["embedding_profile"] is None
        assert scrubbed["embedding_version"] is None
        assert scrubbed["deleted_at"] == NOW + timedelta(seconds=4)
        assert source.projection_text is None
        assert connection.scalar(
            text(
                "SELECT count(*) FROM stage08_knowledge_chunks "
                "WHERE source_id = :source_id AND status = 'indexed'"
            ),
            {"source_id": source_id},
        ) == 0
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_e2_postgres_reads_reread_member_scope_without_persistent_side_effects() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        owner = Actor(actor_type="user", actor_id="e2-pg-owner", role="owner")
        workspace = create_workspace(
            uow,
            name=f"E2 pgvector {uuid4().hex}",
            owner_user_id=owner.actor_id,
            actor=owner,
        )
        base = create_base(uow, workspace.id, name="CRM", actor=owner)
        table = create_table(
            uow,
            base.id,
            name="Projects",
            key=f"projects_{uuid4().hex[:8]}",
            actor=owner,
        )
        create_field(
            uow,
            table.id,
            name="Summary",
            key="summary",
            field_type="text",
            actor=owner,
        )
        project = create_record(
            uow, table.id, values={"summary": "E2 current project"}, actor=owner
        )
        view = create_form_view(
            uow,
            base.id,
            table.id,
            name="Projects",
            view_type="grid",
            config={"fields": ["summary"]},
            actor=owner,
        )
        view.version = 1
        employee = create_digital_employee(
            uow,
            base.id,
            name="E2 PG employee",
            description="controlled reads",
            telegram_alias=None,
            accessible_tables=[str(table.id)],
            accessible_views=[str(view.id)],
            allowed_actions=["query", "summarize"],
            actor=owner,
        )
        session.flush()
        command = Stage08CollaborationContractFactory.command(
            workspace_id=workspace.id,
            employee_id=employee.id,
            actor_user_id=owner.actor_id,
            intent="business_fact",
            query="当前项目进展",
            requested_action="read_only",
            target_record_id=None,
            idempotency_key="e2-pg-read",
        )
        before = (
            session.scalar(select(func.count()).select_from(OpsAuditEvent)),
            session.scalar(select(func.count()).select_from(OutboxEvent)),
            session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)),
        )
        allowed = execute_collaboration_reads(uow, command, owner, now=NOW)
        assert allowed.safe_view().status == "internal_evidence"
        assert allowed.safe_view().read_child_count == 2
        assert (
            session.scalar(select(func.count()).select_from(OpsAuditEvent)),
            session.scalar(select(func.count()).select_from(OutboxEvent)),
            session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)),
        ) == before

        target_without_group_mapping = Stage08CollaborationContractFactory.command(
            workspace_id=workspace.id,
            employee_id=employee.id,
            actor_user_id=owner.actor_id,
            intent="business_fact",
            query="当前项目进展",
            requested_action="read_only",
            target_record_id=project.id,
            idempotency_key="e2-pg-target-without-group",
        )
        target_denied = execute_collaboration_reads(
            uow, target_without_group_mapping, owner, now=NOW
        )
        assert target_denied.safe_view().status == "degraded"
        assert target_denied.safe_view().read_child_count == 0
        assert (
            session.scalar(select(func.count()).select_from(OpsAuditEvent)),
            session.scalar(select(func.count()).select_from(OutboxEvent)),
            session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)),
        ) == before

        member = uow.list_workspace_members(workspace.id)[0]
        member.status = "inactive"
        session.flush()
        revoked = execute_collaboration_reads(uow, command, owner, now=NOW)
        assert revoked.safe_view().status == "degraded"
        assert revoked.safe_view().read_child_count == 0
        assert (
            session.scalar(select(func.count()).select_from(OpsAuditEvent)),
            session.scalar(select(func.count()).select_from(OutboxEvent)),
            session.scalar(select(func.count()).select_from(Stage06IdempotencyRecord)),
        ) == before
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_d4_postgres_provider_hybrid_narrows_and_rereads_before_citation() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    retrieval_statements: list[str] = []

    def capture_retrieval_sql(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        retrieval_statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture_retrieval_sql)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        owner = Actor(actor_type="user", actor_id="d4-owner", role="owner")
        workspace = create_workspace(
            uow,
            name=f"D4 pgvector {uuid4().hex}",
            owner_user_id=owner.actor_id,
            actor=owner,
        )
        base = create_base(uow, workspace.id, name="CRM", actor=owner)
        customers = create_table(
            uow,
            base.id,
            name="Customers",
            key=f"customers_{uuid4().hex[:8]}",
            actor=owner,
        )
        projects = create_table(
            uow,
            base.id,
            name="Projects",
            key=f"projects_{uuid4().hex[:8]}",
            actor=owner,
        )
        create_field(
            uow,
            customers.id,
            name="Name",
            key="name",
            field_type="text",
            actor=owner,
        )
        create_field(
            uow,
            projects.id,
            name="Summary",
            key="summary",
            field_type="text",
            actor=owner,
        )
        create_field(
            uow,
            projects.id,
            name="Customer",
            key="customer",
            field_type="linked_record",
            options={"target_table_id": str(customers.id)},
            actor=owner,
        )
        customer = create_record(
            uow,
            customers.id,
            values={"name": "Acme"},
            actor=owner,
        )
        projection_text = "客户 Acme 已确认报价，下一步安排预算会议。"
        project = create_record(
            uow,
            projects.id,
            values={"summary": projection_text, "customer": [str(customer.id)]},
            actor=owner,
        )
        view = create_form_view(
            uow,
            base.id,
            projects.id,
            name="Projects",
            view_type="grid",
            config={"fields": ["summary", "customer"]},
            actor=owner,
        )
        employee = create_digital_employee(
            uow,
            base.id,
            name="D4 retriever",
            description="D4 PostgreSQL provider",
            telegram_alias=None,
            accessible_tables=[str(customers.id), str(projects.id)],
            accessible_views=[str(view.id)],
            allowed_actions=["query"],
            actor=owner,
        )
        session.flush()
        item = materialize_memory_from_projection(
            uow,
            MemoryMaterializationProjection(
                memory_type="decision",
                scope=MemoryScopeProjection(
                    workspace_id=workspace.id,
                    base_id=base.id,
                    table_id=projects.id,
                    customer_record_id=customer.id,
                    project_record_id=project.id,
                ),
                payload={"summary": projection_text},
                source_refs=(
                    MemorySourceRef(
                        source_kind="platform_record",
                        source_id=project.id,
                        source_version=project.version,
                        field_keys=("summary",),
                    ),
                ),
                valid_until=NOW + timedelta(days=2),
            ),
            actor=owner,
            now=NOW,
        )
        registration = register_memory_knowledge_source(
            uow,
            item.id,
            actor=owner,
            now=NOW,
            trace_id="d4-pgvector-register",
        )
        assert registration is not None
        indexed = process_knowledge_index_event(
            uow,
            registration.event,
            provider=TestHashEmbeddingProvider(),
            now=NOW + timedelta(seconds=1),
        )
        session.flush()
        assert indexed.status == "indexed"

        authority = Stage08RetrievalAuthorityFactory.build(
            uow,
            actor=owner,
            workspace_id=workspace.id,
            employee_id=employee.id,
            customer_record_id=customer.id,
            project_record_id=project.id,
        )
        hybrid = PostgresRetrievalProvider(
            embedding_provider=TestHashEmbeddingProvider()
        )
        result = hybrid.search(
            uow,
            authority,
            query="报价",
            limit=12,
            now=NOW + timedelta(seconds=2),
        )
        assert any(
            "keyword_terms &&" in statement for statement in retrieval_statements
        ), "\n---\n".join(retrieval_statements)
        assert any("<=>" in statement for statement in retrieval_statements), (
            "\n---\n".join(retrieval_statements)
        )
        safe = hybrid.safe_view(
            uow,
            result,
            now=NOW + timedelta(seconds=3),
        )
        citations = hybrid.safe_citations(
            uow,
            result,
            now=NOW + timedelta(seconds=3),
        )
        assert safe.status == "ready"
        assert safe.degradation_code == "none"
        assert safe.result_count == 1
        assert len(citations) == 1
        assert citations[0].label == "retrieved_material"
        assert citations[0].source_type_category == "business_memory"
        assert connection.scalar(
            text(
                "SELECT count(*) FROM stage08_knowledge_chunks "
                "WHERE workspace_id = :workspace_id AND status = 'indexed' "
                "AND embedding IS NOT NULL AND keyword_terms @> ARRAY['报价']::varchar[]"
            ),
            {"workspace_id": workspace.id},
        ) == 1

        keyword_only = PostgresRetrievalProvider()
        degraded = keyword_only.search(
            uow,
            authority,
            query="报价",
            limit=12,
            now=NOW + timedelta(seconds=3),
        )
        degraded_view = keyword_only.safe_view(
            uow,
            degraded,
            now=NOW + timedelta(seconds=3),
        )
        assert degraded_view.status == "degraded"
        assert degraded_view.degradation_code == "keyword_only"
        assert degraded_view.result_count == 1

        registration.source.status = "revoked"
        session.flush()
        assert hybrid.safe_citations(
            uow,
            result,
            now=NOW + timedelta(seconds=4),
        ) == ()
        assert hybrid.render_private_evidence(
            uow,
            result,
            now=NOW + timedelta(seconds=4),
        ) is None
    finally:
        event.remove(engine, "before_cursor_execute", capture_retrieval_sql)
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _build_d4_fresh_state_case(session: Session) -> dict:
    uow = SqlAlchemyStage06PlatformUnitOfWork(session)
    owner = Actor(actor_type="user", actor_id=f"d4-fresh-{uuid4().hex}", role="owner")
    workspace = create_workspace(
        uow,
        name=f"D4 fresh {uuid4().hex}",
        owner_user_id=owner.actor_id,
        actor=owner,
    )
    base = create_base(uow, workspace.id, name="CRM", actor=owner)
    customers = create_table(
        uow,
        base.id,
        name="Customers",
        key=f"customers_{uuid4().hex[:8]}",
        actor=owner,
    )
    projects = create_table(
        uow,
        base.id,
        name="Projects",
        key=f"projects_{uuid4().hex[:8]}",
        actor=owner,
    )
    create_field(
        uow,
        customers.id,
        name="Name",
        key="name",
        field_type="text",
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="Summary",
        key="summary",
        field_type="text",
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=owner,
    )
    customer = create_record(
        uow,
        customers.id,
        values={"name": "Acme"},
        actor=owner,
    )
    projection_text = "客户 Acme 已确认报价，下一步安排预算会议。"
    project = create_record(
        uow,
        projects.id,
        values={"summary": projection_text, "customer": [str(customer.id)]},
        actor=owner,
    )
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["summary", "customer"]},
        actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="D4 fresh retriever",
        description="D4 fresh-current-state regression",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query"],
        actor=owner,
    )
    session.flush()
    item = materialize_memory_from_projection(
        uow,
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(
                workspace_id=workspace.id,
                base_id=base.id,
                table_id=projects.id,
                customer_record_id=customer.id,
                project_record_id=project.id,
            ),
            payload={"summary": projection_text},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=project.id,
                    source_version=project.version,
                    field_keys=("summary",),
                ),
            ),
            valid_until=NOW + timedelta(days=2),
        ),
        actor=owner,
        now=NOW,
    )
    registration = register_memory_knowledge_source(
        uow,
        item.id,
        actor=owner,
        now=NOW,
        trace_id="d4-fresh-register",
    )
    assert registration is not None
    indexed = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=1),
    )
    session.flush()
    assert indexed.status == "indexed"
    chunk = session.scalar(
        select(Stage08KnowledgeChunk).where(
            Stage08KnowledgeChunk.source_id == registration.source.id,
            Stage08KnowledgeChunk.source_version == registration.source.content_version,
        )
    )
    assert chunk is not None
    authority = Stage08RetrievalAuthorityFactory.build(
        uow,
        actor=owner,
        workspace_id=workspace.id,
        employee_id=employee.id,
        customer_record_id=customer.id,
        project_record_id=project.id,
    )
    provider = PostgresRetrievalProvider(
        embedding_provider=TestHashEmbeddingProvider()
    )
    result = provider.search(
        uow,
        authority,
        query="报价",
        limit=12,
        now=NOW + timedelta(seconds=2),
    )
    assert provider.safe_view(
        uow, result, now=NOW + timedelta(seconds=2)
    ).result_count == 1
    return {
        "uow": uow,
        "workspace": workspace,
        "employee": employee,
        "source": registration.source,
        "chunk": chunk,
        "provider": provider,
        "authority": authority,
        "result": result,
    }


@pytest.mark.parametrize(
    "database_drift",
    ["source_revoked", "employee_paused", "source_fingerprint"],
)
def test_d4_held_result_uses_fresh_database_authority_and_source_facts(
    database_drift: str,
) -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        case = _build_d4_fresh_state_case(session)
        if database_drift == "source_revoked":
            connection.execute(
                update(Stage08KnowledgeSource)
                .where(Stage08KnowledgeSource.id == case["source"].id)
                .values(status="revoked", revoked_at=NOW + timedelta(seconds=3))
            )
            assert connection.scalar(
                select(Stage08KnowledgeSource.status).where(
                    Stage08KnowledgeSource.id == case["source"].id
                )
            ) == "revoked"
        elif database_drift == "employee_paused":
            connection.execute(
                update(DigitalEmployee)
                .where(DigitalEmployee.id == case["employee"].id)
                .values(status="paused")
            )
            assert connection.scalar(
                select(DigitalEmployee.status).where(
                    DigitalEmployee.id == case["employee"].id
                )
            ) == "paused"
        else:
            wrong_root = hashlib.sha256(
                f"memory_lineage:{uuid4()}".encode("utf-8")
            ).hexdigest()
            connection.execute(
                update(Stage08KnowledgeSource)
                .where(Stage08KnowledgeSource.id == case["source"].id)
                .values(logical_source_fingerprint=wrong_root)
            )
            assert connection.scalar(
                select(Stage08KnowledgeSource.logical_source_fingerprint).where(
                    Stage08KnowledgeSource.id == case["source"].id
                )
            ) == wrong_root

        provider = case["provider"]
        assert provider.render_private_evidence(
            case["uow"], case["result"], now=NOW + timedelta(seconds=4)
        ) is None
        assert provider.safe_citations(
            case["uow"], case["result"], now=NOW + timedelta(seconds=4)
        ) == ()
        safe = provider.safe_view(
            case["uow"], case["result"], now=NOW + timedelta(seconds=4)
        )
        assert safe.result_count == 0
        assert safe.has_results is False
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.mark.parametrize(
    "terminal_fact",
    ["source_revoked_at", "source_deleted_at", "chunk_deleted_at"],
)
def test_d4_postgres_terminal_timestamps_exclude_candidate_and_held_result(
    terminal_fact: str,
) -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        case = _build_d4_fresh_state_case(session)
        terminal_at = NOW + timedelta(seconds=3)
        if terminal_fact == "source_revoked_at":
            connection.execute(
                update(Stage08KnowledgeSource)
                .where(Stage08KnowledgeSource.id == case["source"].id)
                .values(revoked_at=terminal_at)
            )
            persisted = connection.scalar(
                select(Stage08KnowledgeSource.revoked_at).where(
                    Stage08KnowledgeSource.id == case["source"].id
                )
            )
        elif terminal_fact == "source_deleted_at":
            connection.execute(
                update(Stage08KnowledgeSource)
                .where(Stage08KnowledgeSource.id == case["source"].id)
                .values(deleted_at=terminal_at)
            )
            persisted = connection.scalar(
                select(Stage08KnowledgeSource.deleted_at).where(
                    Stage08KnowledgeSource.id == case["source"].id
                )
            )
        else:
            connection.execute(
                update(Stage08KnowledgeChunk)
                .where(Stage08KnowledgeChunk.id == case["chunk"].id)
                .values(deleted_at=terminal_at)
            )
            persisted = connection.scalar(
                select(Stage08KnowledgeChunk.deleted_at).where(
                    Stage08KnowledgeChunk.id == case["chunk"].id
                )
            )
        assert persisted == terminal_at

        provider = case["provider"]
        assert provider.render_private_evidence(
            case["uow"], case["result"], now=NOW + timedelta(seconds=4)
        ) is None
        assert provider.safe_citations(
            case["uow"], case["result"], now=NOW + timedelta(seconds=4)
        ) == ()

        fresh_result = provider.search(
            case["uow"],
            case["authority"],
            query="报价",
            limit=12,
            now=NOW + timedelta(seconds=4),
        )
        fresh_view = provider.safe_view(
            case["uow"], fresh_result, now=NOW + timedelta(seconds=4)
        )
        assert fresh_view.result_count == 0
        assert fresh_view.has_results is False
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_d4_fresh_revalidation_does_not_flush_unrelated_pending_state() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        case = _build_d4_fresh_state_case(session)
        pending_id = uuid4()
        pending = Workspace(
            id=pending_id,
            name="D4 unrelated pending",
            slug=f"d4-unrelated-{uuid4().hex}",
            owner_user_id="unrelated-owner",
            status="active",
            settings={},
        )
        session.add(pending)
        assert pending in session.new

        safe = case["provider"].safe_view(
            case["uow"], case["result"], now=NOW + timedelta(seconds=3)
        )
        assert safe.result_count == 1
        assert pending in session.new
        assert connection.scalar(
            select(Workspace.id).where(Workspace.id == pending_id)
        ) is None
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_d5_postgres_reindex_is_transactional_idempotent_and_cleanup_aware() -> None:
    engine = create_engine(
        _stage08_rag_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    try:
        case = _build_d4_fresh_state_case(session)
        uow = case["uow"]
        workspace = case["workspace"]
        source = case["source"]
        actor = Actor(
            actor_type="user",
            actor_id=workspace.owner_user_id,
            role="owner",
        )
        original_event_count = session.scalar(
            select(func.count()).select_from(OutboxEvent).where(
                OutboxEvent.event_type == "stage08.knowledge.index_requested",
                OutboxEvent.aggregate_id == str(source.id),
            )
        )
        original_audit_count = session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage08.knowledge.reindex_requested"
            )
        )

        first = request_knowledge_reindex(
            uow,
            workspace.id,
            source.id,
            actor=actor,
            idempotency_key="d5-postgres-reindex",
            trace_id="d5-postgres-trace",
            now=NOW + timedelta(seconds=3),
        )
        session.flush()
        replay = request_knowledge_reindex(
            uow,
            workspace.id,
            source.id,
            actor=actor,
            idempotency_key="d5-postgres-reindex",
            trace_id="d5-postgres-trace",
            now=NOW + timedelta(seconds=4),
        )
        session.flush()

        assert first == replay
        assert first.status == "accepted"
        assert session.scalar(
            select(func.count()).select_from(OutboxEvent).where(
                OutboxEvent.event_type == "stage08.knowledge.index_requested",
                OutboxEvent.aggregate_id == str(source.id),
            )
        ) == original_event_count
        idempotency = session.scalars(
            select(Stage06IdempotencyRecord).where(
                Stage06IdempotencyRecord.workspace_id == workspace.id,
                Stage06IdempotencyRecord.operation == "stage08.knowledge_reindex",
            )
        ).one()
        assert idempotency.status == "completed"
        assert idempotency.response_ref == {
            "ticket_id": str(first.ticket_id),
            "status": "accepted",
        }
        assert session.scalar(
            select(func.count()).select_from(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "stage08.knowledge.reindex_requested"
            )
        ) == original_audit_count + 1

        with pytest.raises(PlatformValidationError) as conflict:
            request_knowledge_reindex(
                uow,
                workspace.id,
                source.id,
                actor=actor,
                idempotency_key="d5-postgres-reindex",
                trace_id="d5-postgres-changed-trace",
                now=NOW + timedelta(seconds=5),
            )
        assert conflict.value.code == "idempotency_conflict"

        effect_counts_before_drift = (
            connection.scalar(select(func.count()).select_from(OutboxEvent)),
            connection.scalar(
                select(func.count()).select_from(Stage06IdempotencyRecord)
            ),
            connection.scalar(select(func.count()).select_from(OpsAuditEvent)),
        )
        owner_member = session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == actor.actor_id,
            )
        )
        assert owner_member is not None and owner_member.status == "active"
        memory_item_id = UUID(source.source_ref["memory_item_id"])
        memory_item = session.scalar(
            select(Stage08MemoryItem).where(
                Stage08MemoryItem.id == memory_item_id
            )
        )
        assert memory_item is not None and memory_item.status == "active"
        connection.execute(
            update(WorkspaceMember)
            .where(WorkspaceMember.id == owner_member.id)
            .values(status="inactive")
        )
        assert connection.scalar(
            select(WorkspaceMember.status).where(
                WorkspaceMember.id == owner_member.id
            )
        ) == "inactive"
        unrelated_id = uuid4()
        unrelated = Workspace(
            id=unrelated_id,
            name="D5 unrelated pending",
            slug=f"d5-unrelated-{uuid4().hex}",
            owner_user_id="unrelated-owner",
            status="active",
            settings={},
        )
        session.add(unrelated)
        assert unrelated in session.new
        with pytest.raises(PlatformValidationError) as revoked_member:
            request_knowledge_reindex(
                uow,
                workspace.id,
                source.id,
                actor=actor,
                idempotency_key="d5-postgres-revoked-member",
                trace_id="d5-postgres-revoked-member",
                now=NOW + timedelta(seconds=5),
            )
        assert revoked_member.value.code == "knowledge_reindex_forbidden"
        assert unrelated in session.new
        assert connection.scalar(
            select(Workspace.id).where(Workspace.id == unrelated_id)
        ) is None
        connection.execute(
            update(WorkspaceMember)
            .where(WorkspaceMember.id == owner_member.id)
            .values(status="active")
        )

        connection.execute(
            update(Stage08KnowledgeSource)
            .where(Stage08KnowledgeSource.id == source.id)
            .values(status="revoked", revoked_at=NOW + timedelta(seconds=5))
        )
        assert connection.scalar(
            select(Stage08KnowledgeSource.status).where(
                Stage08KnowledgeSource.id == source.id
            )
        ) == "revoked"
        with pytest.raises(PlatformValidationError) as revoked_source:
            request_knowledge_reindex(
                uow,
                workspace.id,
                source.id,
                actor=actor,
                idempotency_key="d5-postgres-revoked-source",
                trace_id="d5-postgres-revoked-source",
                now=NOW + timedelta(seconds=5),
            )
        assert revoked_source.value.code == "knowledge_reindex_source_invalid"
        assert unrelated in session.new
        connection.execute(
            update(Stage08KnowledgeSource)
            .where(Stage08KnowledgeSource.id == source.id)
            .values(status="active", revoked_at=None)
        )

        connection.execute(
            update(Stage08MemoryItem)
            .where(Stage08MemoryItem.id == memory_item.id)
            .values(status="revoked", revoked_at=NOW + timedelta(seconds=5))
        )
        assert connection.scalar(
            select(Stage08MemoryItem.status).where(
                Stage08MemoryItem.id == memory_item.id
            )
        ) == "revoked"
        with pytest.raises(PlatformValidationError) as revoked_memory:
            request_knowledge_reindex(
                uow,
                workspace.id,
                source.id,
                actor=actor,
                idempotency_key="d5-postgres-revoked-memory",
                trace_id="d5-postgres-revoked-memory",
                now=NOW + timedelta(seconds=5),
            )
        assert revoked_memory.value.code == "knowledge_reindex_source_invalid"
        assert unrelated in session.new
        assert connection.scalar(
            select(Workspace.id).where(Workspace.id == unrelated_id)
        ) is None
        assert (
            connection.scalar(select(func.count()).select_from(OutboxEvent)),
            connection.scalar(
                select(func.count()).select_from(Stage06IdempotencyRecord)
            ),
            connection.scalar(select(func.count()).select_from(OpsAuditEvent)),
        ) == effect_counts_before_drift
        connection.execute(
            update(Stage08MemoryItem)
            .where(Stage08MemoryItem.id == memory_item.id)
            .values(status="active", revoked_at=None)
        )
        session.expunge(unrelated)

        lifecycle = revoke_knowledge_source(
            uow,
            source.id,
            now=NOW + timedelta(seconds=6),
            reason_code="d5_cleanup",
        )
        assert lifecycle is not None
        cleaned = process_knowledge_cleanup_event(
            uow,
            lifecycle.event,
            now=NOW + timedelta(seconds=7),
        )
        session.flush()
        assert cleaned.status == "cleaned"
        assert source.status == "revoked"
        assert source.projection_text is None
        assert all(
            chunk.status == "deleted" and chunk.chunk_text is None
            for chunk in uow.list_knowledge_chunks(source.id, source.content_version)
        )

        with pytest.raises(PlatformValidationError) as invalid_lifecycle:
            request_knowledge_reindex(
                uow,
                workspace.id,
                source.id,
                actor=actor,
                idempotency_key="d5-postgres-after-cleanup",
                trace_id="d5-postgres-after-cleanup",
                now=NOW + timedelta(seconds=8),
            )
        assert invalid_lifecycle.value.code == "knowledge_reindex_source_invalid"
        assert session.scalar(
            select(func.count()).select_from(Stage06IdempotencyRecord).where(
                Stage06IdempotencyRecord.idempotency_key
                == "d5-postgres-after-cleanup"
            )
        ) == 0
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _d3_reference_event(
    source: Stage08KnowledgeSource,
    *,
    event_type: str,
    trace_id: str,
) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type=event_type,
        aggregate_type="stage08_knowledge_source",
        aggregate_id=str(source.id),
        payload={
            "workspace_id": str(source.workspace_id),
            "knowledge_source_id": str(source.id),
            "content_version": source.content_version,
            "projection_hash": source.projection_hash,
            "trace_id": trace_id,
        },
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=f"stage08:d3:{event_type}:{source.id}",
        trace_id=trace_id,
        created_at=NOW,
    )
