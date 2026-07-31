from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import UniqueConstraint

from app.models.stage08_knowledge import Stage08KnowledgeChunk
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalSource,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    BACKEND_ROOT / "alembic" / "versions" / "20260729_0035_stage12_retrieval_v2.py"
)
RELATION_CORRECTION_MIGRATION = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "20260730_0037_stage12_same_table_relations.py"
)


def test_stage12_retrieval_models_are_additive_and_fixed_dimension() -> None:
    assert Stage12RetrievalProfile.__tablename__ == "stage12_retrieval_profiles"
    assert Stage12RetrievalSource.__tablename__ == "stage12_retrieval_sources"
    assert Stage12RetrievalChunk.__tablename__ == "stage12_retrieval_chunks"
    assert Stage12RelationEdge.__tablename__ == "stage12_relation_edges"

    assert Stage12RetrievalChunk.__table__.c.embedding.type.dim == 1024
    assert Stage08KnowledgeChunk.__table__.c.embedding.type.dim is None

    indexes = {index.name: index for index in Stage12RetrievalChunk.__table__.indexes}
    hnsw = indexes["ix_stage12_retrieval_chunk_hnsw_active_bge_m3"]
    assert hnsw.dialect_options["postgresql"]["using"] == "hnsw"
    assert hnsw.dialect_options["postgresql"]["ops"] == {
        "embedding": "vector_cosine_ops"
    }
    predicate = str(hnsw.dialect_options["postgresql"]["where"])
    assert "status = 'indexed'" in predicate
    assert "revoked_at IS NULL" in predicate
    assert "embedding_profile = 'stage12.openrouter-bge-m3-v1'" in predicate


def test_relation_identity_distinguishes_endpoints_and_authority_scope() -> None:
    unique_constraints = {
        item.name: tuple(column.name for column in item.columns)
        for item in Stage12RelationEdge.__table__.constraints
        if isinstance(item, UniqueConstraint)
    }

    assert unique_constraints["uq_s12_relation_version_visibility"] == (
        "workspace_id",
        "relation_id",
        "source_record_id",
        "target_record_id",
        "direction",
        "source_version",
        "target_version",
        "visibility_profile_hash",
        "scope_hash",
    )


def test_stage12_retrieval_migration_is_single_head_and_does_not_mutate_stage08() -> (
    None
):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    assert ScriptDirectory.from_config(config).get_heads() == ["20260730_0039"]

    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260729_0035"' in text
    assert 'down_revision = "20260728_0034"' in text
    assert "Vector(1024)" in text
    assert "vector_cosine_ops" in text
    assert "stage12.openrouter-bge-m3-v1" in text
    assert "ALTER TABLE stage08_knowledge" not in text


def test_same_table_relation_correction_is_the_single_head_and_keeps_record_guard() -> (
    None
):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    assert ScriptDirectory.from_config(config).get_heads() == ["20260730_0039"]

    text = RELATION_CORRECTION_MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "20260730_0036"' in text
    upgrade = text.split("def downgrade", maxsplit=1)[0]
    assert "source_table_id <> target_table_id" not in upgrade
    assert "source_record_id <> target_record_id" in upgrade

    endpoint_constraints = {
        str(item.sqltext)
        for item in Stage12RelationEdge.__table__.constraints
        if getattr(item, "name", "").endswith("ck_s12_relation_endpoints")
    }
    assert endpoint_constraints == {"source_record_id <> target_record_id"}
