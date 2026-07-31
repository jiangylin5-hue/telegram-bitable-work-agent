from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models.stage06_platform import (
    BitableBase,
    PlatformField,
    PlatformRecord,
    PlatformTable,
    Workspace,
)
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalSource,
)
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.authorized_query_records import build_authorized_query_context
from app.services.retrieval_v2_registration import (
    build_registered_source_projections,
    process_registered_scope_bootstrap,
    register_authorized_retrieval_scope,
)
from app.services.stage06_digital_employees import create_digital_employee
from app.models.outbox import OutboxEvent
from app.schemas.retrieval_v2 import EmbeddingProfileV1, RetrievalProjectionV2
from app.services.retrieval_v2_embeddings import EmbeddingProviderError
from app.services.retrieval_v2_indexing import (
    SqlAlchemyRetrievalIndexUnitOfWork,
    expand_retrieval_source_change_event,
    process_retrieval_projection_event,
    request_retrieval_projection,
    revoke_retrieval_source,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    replace_field_permission_policy,
    update_record,
)
from app.workers.retrieval_v2_outbox_runtime import RetrievalV2SqlOutboxRepository
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


class _CharacterCounter:
    def encode(self, value: str) -> tuple[int, ...]:
        return tuple(ord(character) for character in value)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "".join(chr(token_id) for token_id in token_ids)


class _SyntheticProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.profile = EmbeddingProfileV1(
            version="embedding-profile.v1",
            profile_name="stage12.openrouter-bge-m3-v1",
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
        )
        self.fail = fail
        self.document_calls = 0

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        self.document_calls += 1
        if self.fail:
            raise EmbeddingProviderError("embedding_provider_unavailable")
        return tuple((1.0,) + (0.0,) * 1023 for _ in texts)


class _DiagnosticSqlAlchemyUnitOfWork(SqlAlchemyRetrievalIndexUnitOfWork):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.last_error: Exception | None = None

    @contextmanager
    def atomic(self):
        try:
            with super().atomic():
                yield
        except Exception as error:
            self.last_error = error
            raise


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12-D PostgreSQL evidence",
)
def test_retrieval_registration_and_relation_materialization_persist_postgres() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    config = _alembic_config(database_url)
    with patch.dict(os.environ, {"DATABASE_URL": database_url}):
        command.upgrade(config, "head")

    connection = engine.connect()
    transaction = connection.begin()
    try:
        with Session(
            bind=connection,
            autoflush=True,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            platform_uow = SqlAlchemyStage06PlatformUnitOfWork(session)
            index_uow = SqlAlchemyRetrievalIndexUnitOfWork(session)
            actor = Actor(
                actor_type="user",
                actor_id=f"pg-registration-{uuid4().hex}",
                role="owner",
            )
            workspace = create_workspace(
                platform_uow,
                name="PG retrieval registration",
                owner_user_id=actor.actor_id,
                actor=actor,
            )
            base = create_base(
                platform_uow,
                workspace.id,
                name="PG Registration Base",
                actor=actor,
            )
            table = create_table(
                platform_uow,
                base.id,
                name="PG Work",
                key=f"pg_registration_{uuid4().hex}",
                actor=actor,
            )
            title = create_field(
                platform_uow,
                table.id,
                name="Title",
                key="title",
                field_type="text",
                actor=actor,
            )
            link = create_field(
                platform_uow,
                table.id,
                name="Related",
                key="related",
                field_type="linked_record",
                options={"target_table_id": str(table.id)},
                actor=actor,
            )
            target = create_record(
                platform_uow,
                table.id,
                values={"title": "PG target"},
                actor=actor,
            )
            source = create_record(
                platform_uow,
                table.id,
                values={"title": "PG source", "related": [str(target.id)]},
                actor=actor,
            )
            employee = create_digital_employee(
                platform_uow,
                base.id,
                name="PG retrieval employee",
                description="registration persistence",
                telegram_alias=None,
                accessible_tables=[str(table.id)],
                accessible_views=[],
                field_policy=build_stage12_field_policy_v2(
                    readable_field_ids=(title.id, link.id),
                    writable_field_ids=(),
                ),
                allowed_actions=["query"],
                actor=actor,
            )
            snapshot = build_authorized_schema_snapshot(
                platform_uow,
                workspace_id=workspace.id,
                employee_id=employee.id,
                actor=actor,
                require_field_policy_v2=True,
            )
            context = build_authorized_query_context(
                platform_uow,
                workspace_id=workspace.id,
                base_id=base.id,
                employee_id=employee.id,
                actor=actor,
                snapshot=snapshot,
                chat_authorized_view_ids=None,
                allow_whole_table=True,
            )
            now = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)
            registration = register_authorized_retrieval_scope(
                index_uow,
                context=context,
                now=now,
            )
            refreshed = register_authorized_retrieval_scope(
                index_uow,
                context=context,
                now=now.replace(minute=1),
            )
            assert refreshed.id == registration.id
            assert len(index_uow.list_registrations(workspace_id=workspace.id)) == 1
            bootstrap = list(
                session.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.event_type
                        == "stage12.retrieval_scope.bootstrap_requested",
                        OutboxEvent.aggregate_id == str(registration.id),
                    )
                )
            )
            assert len(bootstrap) == 1
            unrelated = OutboxEvent(
                id=uuid4(),
                event_type="stage06.unrelated.business_event",
                aggregate_type="unrelated",
                aggregate_id="unrelated",
                payload={"workspace_id": str(workspace.id)},
                status="pending",
                attempts=0,
                attempt_count=0,
                max_attempts=3,
                idempotency_key=f"unrelated:{uuid4()}",
                trace_id="1" * 64,
                created_at=now,
            )
            disallowed = OutboxEvent(
                id=uuid4(),
                event_type="stage12.retrieval_scope.bootstrap_requested",
                aggregate_type="stage12_retrieval_scope_registration",
                aggregate_id=str(uuid4()),
                payload={
                    "workspace_id": str(uuid4()),
                    "registration_id": str(uuid4()),
                    "cursor": None,
                    "page_size": 200,
                    "trace_id": "2" * 64,
                },
                status="pending",
                attempts=0,
                attempt_count=0,
                max_attempts=3,
                idempotency_key=f"disallowed:{uuid4()}",
                trace_id="2" * 64,
                created_at=now,
            )
            session.add_all((unrelated, disallowed))
            session.flush()
            ready = RetrievalV2SqlOutboxRepository(
                session,
                workspace_ids=frozenset({workspace.id}),
            ).list_ready(limit=20)
            assert [event.id for event in ready] == [bootstrap[0].id]

            bootstrap[0].status = "processing"
            bootstrap_result = process_registered_scope_bootstrap(
                platform_uow,
                index_uow,
                event=bootstrap[0],
                now=now.replace(minute=2),
            )
            assert bootstrap_result.status == "expanded"
            assert bootstrap_result.requested_projection_count == 5
            assert bootstrap_result.continuation_enqueued is False
            assert bootstrap[0].status == "processed"
            requested_source_ids = set(
                session.scalars(
                    select(OutboxEvent.aggregate_id).where(
                        OutboxEvent.event_type
                        == "stage12.retrieval_projection.requested"
                    )
                )
            )
            assert requested_source_ids == {
                f"schema-table:{table.id}",
                f"schema-field:{title.id}",
                f"schema-field:{link.id}",
                f"record:{source.id}",
                f"record:{target.id}",
            }

            projections = build_registered_source_projections(
                platform_uow,
                index_uow,
                reference={
                    "workspace_id": str(workspace.id),
                    "base_id": str(base.id),
                    "table_id": str(table.id),
                    "record_id": str(source.id),
                    "source_type": "record",
                    "source_id": f"record:{source.id}",
                    "source_version": source.version,
                    "mutation_kind": "link_changed",
                    "trace_id": "9" * 64,
                },
                now=now.replace(minute=2),
            )
            assert len(projections) == 1
            edges = index_uow.list_relation_edges(
                workspace_id=workspace.id,
                scope_hash=registration.retrieval_scope_hash,
            )
            assert len(edges) == 1
            assert edges[0].source_record_id == source.id
            assert edges[0].target_record_id == target.id
            assert edges[0].status == "active"

            stored_columns = set(
                session.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = "
                        "'stage12_retrieval_scope_registrations'"
                    )
                )
            )
            assert (
                not {
                    "canonical_text",
                    "record_values",
                    "provider_payload",
                    "credentials",
                }
                & stored_columns
            )
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12-D PostgreSQL evidence",
)
def test_relation_index_persists_distinct_edges_and_rejects_exact_duplicate() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    config = _alembic_config(database_url)
    with patch.dict(os.environ, {"DATABASE_URL": database_url}):
        command.upgrade(config, "head")

    connection = engine.connect()
    transaction = connection.begin()
    try:
        with Session(
            bind=connection,
            autoflush=True,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            workspace = Workspace(
                id=uuid4(),
                name="Stage12 relation identity",
                slug=f"stage12-relation-{uuid4().hex}",
                owner_user_id="stage12-relation-owner",
                status="active",
                settings={},
            )
            session.add(workspace)
            session.flush()
            base = BitableBase(
                id=uuid4(),
                workspace_id=workspace.id,
                name="Relation Base",
                description=None,
                source_type="native",
                template_id=None,
                status="active",
                settings={},
            )
            session.add(base)
            session.flush()
            table = PlatformTable(
                id=uuid4(),
                base_id=base.id,
                name="Relation records",
                key=f"relation_records_{uuid4().hex}",
                description=None,
                primary_field_id=None,
                status="active",
                settings={},
            )
            session.add(table)
            session.flush()
            link_field = PlatformField(
                id=uuid4(),
                table_id=table.id,
                name="Related",
                key=f"related_{uuid4().hex}",
                field_type="linked_record",
                required=False,
                unique=False,
                options={"target_table_id": str(table.id)},
                default_value=None,
                permission_policy={},
                permission_version=1,
                order_index=0,
                status="active",
            )
            session.add(link_field)
            records = [
                PlatformRecord(
                    id=uuid4(),
                    table_id=table.id,
                    record_values={},
                    record_status="active",
                    created_by_user_id="stage12-relation-owner",
                    updated_by_user_id="stage12-relation-owner",
                    version=1,
                )
                for _ in range(3)
            ]
            session.add_all(records)
            session.flush()

            common = {
                "workspace_id": workspace.id,
                "relation_id": f"relation:{link_field.id}",
                "source_table_id": table.id,
                "source_record_id": records[0].id,
                "link_field_id": link_field.id,
                "target_table_id": table.id,
                "direction": "forward",
                "source_version": 1,
                "target_version": 1,
                "visibility_profile_hash": "a" * 64,
                "scope_hash": "b" * 64,
                "status": "active",
                "revoked_at": None,
            }
            session.add_all(
                [
                    Stage12RelationEdge(
                        id=uuid4(),
                        target_record_id=records[1].id,
                        edge_hash="c" * 64,
                        **common,
                    ),
                    Stage12RelationEdge(
                        id=uuid4(),
                        target_record_id=records[2].id,
                        edge_hash="d" * 64,
                        **common,
                    ),
                ]
            )
            session.flush()

            duplicate_savepoint = session.begin_nested()
            with pytest.raises(IntegrityError):
                session.add(
                    Stage12RelationEdge(
                        id=uuid4(),
                        target_record_id=records[1].id,
                        edge_hash="e" * 64,
                        **common,
                    )
                )
                session.flush()
            duplicate_savepoint.rollback()

            persisted = session.scalars(
                select(Stage12RelationEdge).where(
                    Stage12RelationEdge.workspace_id == workspace.id
                )
            ).all()
            assert {edge.target_record_id for edge in persisted} == {
                records[1].id,
                records[2].id,
            }
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12-D PostgreSQL evidence",
)
def test_stage12_retrieval_fixed_vector_constraints_and_downgrade_isolation() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    config = _alembic_config(database_url)
    with engine.connect() as connection:
        assert connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_extension " "WHERE extname = 'vector')"
            )
        )
    with patch.dict(os.environ, {"DATABASE_URL": database_url}):
        command.upgrade(config, "head")

    with engine.connect() as connection:
        vector_type = connection.scalar(
            text(
                "SELECT format_type(a.atttypid, a.atttypmod) "
                "FROM pg_attribute a "
                "WHERE a.attrelid = 'stage12_retrieval_chunks'::regclass "
                "AND a.attname = 'embedding'"
            )
        )
        assert vector_type == "vector(1024)"
        definition = connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = "
                "'ix_stage12_retrieval_chunk_hnsw_active_bge_m3'"
            )
        )
        assert "USING hnsw" in definition
        assert "vector_cosine_ops" in definition
        assert "stage12.openrouter-bge-m3-v1" in definition
        index_names = set(
            connection.scalars(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname IN ("
                    "'uq_stage12_retrieval_profile_one_active', "
                    "'uq_stage12_retrieval_source_one_active_version')"
                )
            )
        )
        assert index_names == {
            "uq_stage12_retrieval_profile_one_active",
            "uq_stage12_retrieval_source_one_active_version",
        }
        constraint_names = set(
            connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname IN ("
                    "'fk_s12_chunk_source_scope_version', "
                    "'ck_s12_relation_endpoints', "
                    "'ck_s12_relation_versions', "
                    "'ck_s12_relation_hashes')"
                )
            )
        )
        assert constraint_names == {
            "fk_s12_chunk_source_scope_version",
            "ck_s12_relation_endpoints",
            "ck_s12_relation_versions",
            "ck_s12_relation_hashes",
        }
        endpoint_definition = connection.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_s12_relation_endpoints'"
            )
        )
        assert endpoint_definition == "CHECK ((source_record_id <> target_record_id))"

    now = datetime(2026, 7, 29, 15, 0, tzinfo=UTC)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        with Session(
            bind=connection,
            autoflush=True,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            workspace = Workspace(
                id=uuid4(),
                name="Stage12 D",
                slug=f"stage12-d-{uuid4().hex}",
                owner_user_id="stage12-d-owner",
                status="active",
                settings={},
            )
            session.add(workspace)
            session.flush()
            base = BitableBase(
                id=uuid4(),
                workspace_id=workspace.id,
                name="Stage12 D Base",
                description=None,
                source_type="native",
                template_id=None,
                status="active",
                settings={},
            )
            session.add(base)
            session.flush()
            table = PlatformTable(
                id=uuid4(),
                base_id=base.id,
                name="Items",
                key=f"items_{uuid4().hex}",
                description=None,
                primary_field_id=None,
                status="active",
                settings={},
            )
            session.add(table)
            session.flush()
            target_table = PlatformTable(
                id=uuid4(),
                base_id=base.id,
                name="Targets",
                key=f"targets_{uuid4().hex}",
                description=None,
                primary_field_id=None,
                status="active",
                settings={},
            )
            session.add(target_table)
            session.flush()
            field = PlatformField(
                id=uuid4(),
                table_id=table.id,
                name="Title",
                key=f"title_{uuid4().hex}",
                field_type="text",
                required=False,
                unique=False,
                options={},
                default_value=None,
                permission_policy={},
                permission_version=1,
                order_index=0,
                status="active",
            )
            session.add(field)
            source_record = PlatformRecord(
                id=uuid4(),
                table_id=table.id,
                record_values={str(field.id): "alpha"},
                record_status="active",
                created_by_user_id="stage12-d-owner",
                updated_by_user_id="stage12-d-owner",
                version=1,
            )
            target_record = PlatformRecord(
                id=uuid4(),
                table_id=table.id,
                record_values={str(field.id): "beta"},
                record_status="active",
                created_by_user_id="stage12-d-owner",
                updated_by_user_id="stage12-d-owner",
                version=1,
            )
            session.add_all([source_record, target_record])
            session.flush()

            profile = Stage12RetrievalProfile(
                id=uuid4(),
                profile_name="stage12.openrouter-bge-m3-v1",
                model_revision="baai/bge-m3-20251117",
                dimension=1024,
                normalization="l2",
                distance_metric="cosine",
                max_input_tokens=8192,
                batch_size=64,
                provider_location="remote",
                data_residency="openrouter-deny-zdr",
                profile_hash="a" * 64,
                status="active",
                activated_at=now,
                retired_at=None,
            )
            session.add(profile)
            session.flush()
            source = Stage12RetrievalSource(
                id=uuid4(),
                workspace_id=workspace.id,
                base_id=base.id,
                table_id=table.id,
                record_id=source_record.id,
                field_ids=[field.id],
                source_type="record",
                source_identity=f"record:{source_record.id}",
                source_version=1,
                embedding_profile=profile.profile_name,
                visibility_profile_hash="b" * 64,
                scope_hash="c" * 64,
                content_hash="d" * 64,
                status="indexed",
                is_active=True,
                activated_at=now,
                revoked_at=None,
            )
            session.add(source)
            session.flush()
            session.add(
                Stage12RetrievalChunk(
                    id=uuid4(),
                    workspace_id=workspace.id,
                    source_id=source.id,
                    source_version=1,
                    ordinal=0,
                    chunk_kind="canonical",
                    source_type="record",
                    table_id=table.id,
                    record_id=source_record.id,
                    field_ids=[field.id],
                    start_token=0,
                    end_token=3,
                    chunk_text="synthetic alpha",
                    keyword_terms=["synthetic", "alpha"],
                    content_hash="e" * 64,
                    visibility_profile_hash="b" * 64,
                    scope_hash="c" * 64,
                    embedding_profile=profile.profile_name,
                    embedding=[1.0] + [0.0] * 1023,
                    status="indexed",
                    revoked_at=None,
                )
            )
            session.add(
                Stage12RelationEdge(
                    id=uuid4(),
                    workspace_id=workspace.id,
                    relation_id=f"relation:{uuid4()}",
                    source_table_id=table.id,
                    source_record_id=source_record.id,
                    link_field_id=field.id,
                    target_table_id=table.id,
                    target_record_id=target_record.id,
                    direction="forward",
                    source_version=1,
                    target_version=1,
                    visibility_profile_hash="b" * 64,
                    scope_hash="c" * 64,
                    edge_hash="f" * 64,
                    status="active",
                    revoked_at=None,
                )
            )
            session.flush()

            duplicate = Stage12RetrievalSource(
                id=uuid4(),
                workspace_id=workspace.id,
                base_id=base.id,
                table_id=table.id,
                record_id=source_record.id,
                field_ids=[field.id],
                source_type="record",
                source_identity=source.source_identity,
                source_version=2,
                embedding_profile=profile.profile_name,
                visibility_profile_hash=source.visibility_profile_hash,
                scope_hash="1" * 64,
                content_hash="2" * 64,
                status="indexed",
                is_active=True,
                activated_at=now,
                revoked_at=None,
            )
            duplicate_savepoint = session.begin_nested()
            with pytest.raises(IntegrityError):
                session.add(duplicate)
                session.flush()
            duplicate_savepoint.rollback()

            for ordinal, dimension in enumerate((8, 1536), start=1):
                dimension_savepoint = session.begin_nested()
                with pytest.raises(DBAPIError):
                    session.execute(
                        text(
                            "INSERT INTO stage12_retrieval_chunks "
                            "(id, workspace_id, source_id, source_version, ordinal, "
                            "chunk_kind, source_type, table_id, record_id, field_ids, "
                            "start_token, end_token, chunk_text, keyword_terms, "
                            "content_hash, visibility_profile_hash, scope_hash, "
                            "embedding_profile, embedding, status, created_at, updated_at) "
                            "VALUES (:id, :workspace_id, :source_id, 1, :ordinal, "
                            "'canonical', 'record', :table_id, :record_id, :field_ids, "
                            "0, 1, 'bad dimension', ARRAY['bad'], :hash, :visibility, "
                            ":scope, :profile, :embedding, 'indexed', now(), now())"
                        ),
                        {
                            "id": uuid4(),
                            "workspace_id": workspace.id,
                            "source_id": source.id,
                            "ordinal": ordinal,
                            "table_id": table.id,
                            "record_id": source_record.id,
                            "field_ids": [field.id],
                            "hash": "3" * 64,
                            "visibility": "b" * 64,
                            "scope": "c" * 64,
                            "profile": profile.profile_name,
                            "embedding": "["
                            + ",".join("1" for _ in range(dimension))
                            + "]",
                        },
                    )
                dimension_savepoint.rollback()

            indexing_uow = _DiagnosticSqlAlchemyUnitOfWork(session)
            service_source_id = f"record:service:{source_record.id}"
            canonical_v1 = "[table] Items\n[record] service alpha"
            projection_v1 = RetrievalProjectionV2(
                version="retrieval-projection.v2",
                source_type="record",
                source_id=service_source_id,
                source_version=1,
                workspace_id=workspace.id,
                base_id=base.id,
                table_id=table.id,
                record_id=source_record.id,
                field_ids=(field.id,),
                visibility_profile_hash="4" * 64,
                scope_hash="5" * 64,
                content_hash=sha256(canonical_v1.encode("utf-8")).hexdigest(),
                canonical_text=canonical_v1,
            )
            event_v1 = request_retrieval_projection(
                indexing_uow,
                projection_v1,
                trace_id="stage12-pg-index-v1",
                now=now,
            )
            provider = _SyntheticProvider()
            result_v1 = process_retrieval_projection_event(
                indexing_uow,
                event_v1,
                projection_reader=lambda reference: projection_v1,
                token_counter=_CharacterCounter(),
                provider=provider,
                now=now,
            )
            assert (result_v1.status, result_v1.error_code) == (
                "indexed",
                "none",
            ), repr(indexing_uow.last_error)
            assert result_v1.indexed_chunk_count == 1
            assert event_v1.status == "processed"

            canonical_v2 = "[table] Items\n[record] service beta"
            projection_v2 = projection_v1.model_copy(
                update={
                    "source_version": 2,
                    "canonical_text": canonical_v2,
                    "content_hash": sha256(canonical_v2.encode("utf-8")).hexdigest(),
                }
            )
            event_v2 = request_retrieval_projection(
                indexing_uow,
                projection_v2,
                trace_id="stage12-pg-index-v2",
                now=now,
            )
            result_v2 = process_retrieval_projection_event(
                indexing_uow,
                event_v2,
                projection_reader=lambda reference: projection_v2,
                token_counter=_CharacterCounter(),
                provider=provider,
                now=now,
            )
            assert result_v2.status == "indexed"
            persisted_sources = indexing_uow.list_sources(
                workspace_id=workspace.id,
                source_type="record",
                source_identity=service_source_id,
                visibility_profile_hash="4" * 64,
            )
            assert [
                item.source_version for item in persisted_sources if item.is_active
            ] == [2]
            assert [item.status for item in persisted_sources] == ["stale", "indexed"]

            canonical_v3 = "[table] Items\n[record] service gamma"
            projection_v3 = projection_v1.model_copy(
                update={
                    "source_version": 3,
                    "canonical_text": canonical_v3,
                    "content_hash": sha256(canonical_v3.encode("utf-8")).hexdigest(),
                }
            )
            event_v3 = request_retrieval_projection(
                indexing_uow,
                projection_v3,
                trace_id="stage12-pg-index-v3",
                now=now,
            )
            failure = process_retrieval_projection_event(
                indexing_uow,
                event_v3,
                projection_reader=lambda reference: projection_v3,
                token_counter=_CharacterCounter(),
                provider=_SyntheticProvider(fail=True),
                now=now,
            )
            assert failure.status == "failed"
            assert failure.error_code == "embedding_provider_unavailable"
            assert event_v3.status == "pending"
            assert [
                item.source_version
                for item in indexing_uow.list_sources(
                    workspace_id=workspace.id,
                    source_type="record",
                    source_identity=service_source_id,
                    visibility_profile_hash="4" * 64,
                )
                if item.is_active
            ] == [2]

            revocation = revoke_retrieval_source(
                indexing_uow,
                workspace_id=workspace.id,
                source_type="record",
                source_identity=service_source_id,
                visibility_profile_hash="4" * 64,
                reason_code="permission_contracted",
                now=now,
            )
            session.flush()
            assert revocation.revoked_source_count == 2
            assert revocation.revoked_chunk_count == 2
            revoked_sources = indexing_uow.list_sources(
                workspace_id=workspace.id,
                source_type="record",
                source_identity=service_source_id,
                visibility_profile_hash="4" * 64,
            )
            assert all(item.status == "revoked" for item in revoked_sources)
            assert all(not item.is_active for item in revoked_sources)
            assert revocation.event.status == "pending"

            platform_uow = SqlAlchemyStage06PlatformUnitOfWork(session)
            owner = Actor(
                actor_type="user",
                actor_id="stage12-owner",
                role="owner",
            )
            mutation_workspace = create_workspace(
                platform_uow,
                name=f"Stage12 mutations {uuid4().hex}",
                owner_user_id=owner.actor_id,
                actor=owner,
            )
            platform_uow.stage12_retrieval_workspace_ids = frozenset(
                {mutation_workspace.id}
            )
            mutation_base = create_base(
                platform_uow,
                mutation_workspace.id,
                name="Mutation Base",
                actor=owner,
            )
            mutation_table = create_table(
                platform_uow,
                mutation_base.id,
                name="Mutation Tasks",
                key=f"mutation_tasks_{uuid4().hex}",
                actor=owner,
            )
            private_field = create_field(
                platform_uow,
                mutation_table.id,
                name="Private",
                key="private",
                field_type="text",
                actor=owner,
            )
            mutation_record = create_record(
                platform_uow,
                mutation_table.id,
                values={"private": "postgres-secret-one"},
                actor=owner,
            )
            update_record(
                platform_uow,
                mutation_record.id,
                values={"private": "postgres-secret-two"},
                expected_version=1,
                actor=owner,
            )
            session.flush()
            mutation_events = [
                event
                for event in session.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.event_type == "stage12.retrieval_source.changed"
                    )
                )
                if event.payload["workspace_id"] == str(mutation_workspace.id)
            ]
            assert {
                (
                    event.payload["source_type"],
                    event.payload["source_version"],
                    event.payload["mutation_kind"],
                )
                for event in mutation_events
            } == {
                ("schema_table", 1, "schema_changed"),
                ("schema_table", 2, "schema_changed"),
                ("schema_field", 2, "schema_changed"),
                ("record", 1, "record_changed"),
                ("record", 2, "record_changed"),
            }
            assert len(mutation_events) == 5
            rendered_mutation_events = str([event.payload for event in mutation_events])
            assert "postgres-secret-one" not in rendered_mutation_events
            assert "postgres-secret-two" not in rendered_mutation_events
            assert "field_ids" not in rendered_mutation_events

            current_record_event = next(
                event
                for event in mutation_events
                if event.payload["source_type"] == "record"
                and event.payload["source_version"] == 2
            )
            current_text = (
                "[table] Mutation Tasks\n"
                "[record] current\n"
                "[Private] synthetic authorized"
            )
            current_projection = RetrievalProjectionV2(
                version="retrieval-projection.v2",
                source_type="record",
                source_id=f"record:{mutation_record.id}",
                source_version=mutation_record.version,
                workspace_id=mutation_workspace.id,
                base_id=mutation_base.id,
                table_id=mutation_table.id,
                record_id=mutation_record.id,
                field_ids=(private_field.id,),
                visibility_profile_hash="6" * 64,
                scope_hash="7" * 64,
                content_hash=sha256(current_text.encode("utf-8")).hexdigest(),
                canonical_text=current_text,
            )
            expansion = expand_retrieval_source_change_event(
                indexing_uow,
                current_record_event,
                projection_reader=lambda reference: (current_projection,),
                registered_scope_profiles=frozenset(
                    {
                        (
                            current_projection.visibility_profile_hash,
                            current_projection.scope_hash,
                        )
                    }
                ),
                now=now,
            )
            assert expansion.status == "expanded"
            assert expansion.requested_projection_count == 1
            assert current_record_event.status == "processed"
            current_projection_event = session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "stage12.retrieval_projection.requested",
                    OutboxEvent.aggregate_id == f"record:{mutation_record.id}",
                )
            )
            assert current_projection_event is not None
            assert current_projection.canonical_text not in str(
                current_projection_event.payload
            )
            assert "field_ids" not in current_projection_event.payload

            indexed_source = Stage12RetrievalSource(
                id=uuid4(),
                workspace_id=mutation_workspace.id,
                base_id=mutation_base.id,
                table_id=mutation_table.id,
                record_id=mutation_record.id,
                field_ids=[private_field.id],
                source_type="record",
                source_identity=f"record:{mutation_record.id}",
                source_version=mutation_record.version,
                embedding_profile=profile.profile_name,
                visibility_profile_hash="6" * 64,
                scope_hash="7" * 64,
                content_hash="8" * 64,
                status="indexed",
                is_active=True,
                activated_at=now,
                revoked_at=None,
            )
            session.add(indexed_source)
            session.flush()
            indexed_chunk = Stage12RetrievalChunk(
                id=uuid4(),
                workspace_id=mutation_workspace.id,
                source_id=indexed_source.id,
                source_version=mutation_record.version,
                ordinal=0,
                chunk_kind="canonical",
                source_type="record",
                table_id=mutation_table.id,
                record_id=mutation_record.id,
                field_ids=[private_field.id],
                start_token=0,
                end_token=2,
                chunk_text="synthetic private",
                keyword_terms=["synthetic", "private"],
                content_hash="9" * 64,
                visibility_profile_hash="6" * 64,
                scope_hash="7" * 64,
                embedding_profile=profile.profile_name,
                embedding=[1.0] + [0.0] * 1023,
                status="indexed",
                revoked_at=None,
            )
            session.add(indexed_chunk)
            session.flush()

            replace_field_permission_policy(
                platform_uow,
                mutation_table.id,
                private_field.id,
                policy={
                    "owner": "write",
                    "admin": "write",
                    "builder": "write",
                    "operator": "read",
                    "viewer": "hidden",
                },
                expected_permission_version=1,
                actor=owner,
            )
            session.flush()
            assert indexed_source.status == "revoked"
            assert indexed_source.is_active is False
            assert indexed_chunk.status == "revoked"
            assert mutation_table.settings["stage12_schema_version"] == 3
            permission_events = [
                event
                for event in session.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.event_type.in_(
                            (
                                "stage12.retrieval_source.changed",
                                "stage12.retrieval_projection.revoked",
                            )
                        )
                    )
                )
                if event.payload["workspace_id"] == str(mutation_workspace.id)
                and (
                    event.event_type == "stage12.retrieval_projection.revoked"
                    or event.payload["mutation_kind"] == "permission_changed"
                )
            ]
            assert any(
                event.event_type == "stage12.retrieval_projection.revoked"
                for event in permission_events
            )
            assert {
                event.payload["source_id"]
                for event in permission_events
                if event.event_type == "stage12.retrieval_source.changed"
            } == {
                f"schema_table:{mutation_table.id}",
                f"schema_field:{private_field.id}",
                f"record:{mutation_record.id}",
            }
            assert "postgres-secret" not in str(
                [event.payload for event in permission_events]
            )
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()

    with patch.dict(os.environ, {"DATABASE_URL": database_url}):
        command.downgrade(config, "20260728_0034")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT to_regclass('stage08_knowledge_chunks')"))
        assert (
            connection.scalar(text("SELECT to_regclass('stage12_retrieval_chunks')"))
            is None
        )
    with patch.dict(os.environ, {"DATABASE_URL": database_url}):
        command.upgrade(config, "head")
    engine.dispose()
