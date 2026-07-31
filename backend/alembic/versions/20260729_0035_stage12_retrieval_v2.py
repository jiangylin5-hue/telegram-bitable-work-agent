"""Add Stage12-D fixed-dimension retrieval persistence.

Revision ID: 20260729_0035
Revises: 20260728_0034
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv


revision = "20260729_0035"
down_revision = "20260728_0034"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "stage12_retrieval_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_name", sa.String(length=96), nullable=False),
        sa.Column("model_revision", sa.String(length=200), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("normalization", sa.String(length=16), nullable=False),
        sa.Column("distance_metric", sa.String(length=16), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("provider_location", sa.String(length=16), nullable=False),
        sa.Column("data_residency", sa.String(length=240), nullable=False),
        sa.Column("profile_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "dimension = 1024",
            name=conv("ck_s12_profile_dimension"),
        ),
        sa.CheckConstraint(
            "normalization = 'l2'",
            name=conv("ck_s12_profile_normalization"),
        ),
        sa.CheckConstraint(
            "distance_metric = 'cosine'",
            name=conv("ck_s12_profile_distance"),
        ),
        sa.CheckConstraint(
            "max_input_tokens > 0 AND batch_size > 0",
            name=conv("ck_s12_profile_limits"),
        ),
        sa.CheckConstraint(
            "provider_location IN ('local', 'remote')",
            name=conv("ck_s12_profile_location"),
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'active', 'retired')",
            name=conv("ck_s12_profile_status"),
        ),
        sa.CheckConstraint(
            "profile_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_s12_profile_hash"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND activated_at IS NOT NULL "
            "AND retired_at IS NULL) OR "
            "(status = 'candidate' AND activated_at IS NULL "
            "AND retired_at IS NULL) OR "
            "(status = 'retired' AND retired_at IS NOT NULL)",
            name=conv("ck_s12_profile_lifecycle"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_name", name="uq_s12_profile_name"),
    )
    op.create_index(
        "uq_stage12_retrieval_profile_one_active",
        "stage12_retrieval_profiles",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "stage12_retrieval_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=True),
        sa.Column(
            "field_ids",
            postgresql.ARRAY(sa.Uuid()),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_identity", sa.String(length=240), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("embedding_profile", sa.String(length=96), nullable=False),
        sa.Column(
            "visibility_profile_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "source_type IN "
            "('schema_table', 'schema_field', 'record', 'record_field')",
            name=conv("ck_s12_source_type"),
        ),
        sa.CheckConstraint(
            "source_version > 0",
            name=conv("ck_s12_source_version"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'indexed', 'stale', 'revoked', 'failed')",
            name=conv("ck_s12_source_status"),
        ),
        sa.CheckConstraint(
            "((source_type IN ('record', 'record_field')) = "
            "(record_id IS NOT NULL))",
            name=conv("ck_s12_source_record_identity"),
        ),
        sa.CheckConstraint(
            "visibility_profile_hash ~ '^[0-9a-f]{64}$' AND "
            "scope_hash ~ '^[0-9a-f]{64}$' AND "
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_s12_source_hashes"),
        ),
        sa.CheckConstraint(
            "NOT is_active OR "
            "(status = 'indexed' AND activated_at IS NOT NULL "
            "AND revoked_at IS NULL)",
            name=conv("ck_s12_source_active_state"),
        ),
        sa.CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=conv("ck_s12_source_revoked_state"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(
            ["embedding_profile"],
            ["stage12_retrieval_profiles.profile_name"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "source_type",
            "source_identity",
            "source_version",
            "embedding_profile",
            "visibility_profile_hash",
            name="uq_s12_source_identity_version",
        ),
        sa.UniqueConstraint(
            "id",
            "workspace_id",
            "source_version",
            "embedding_profile",
            name="uq_s12_source_scope_version",
        ),
    )
    op.create_index(
        "uq_stage12_retrieval_source_one_active_version",
        "stage12_retrieval_sources",
        [
            "workspace_id",
            "source_type",
            "source_identity",
            "visibility_profile_hash",
        ],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE AND revoked_at IS NULL"),
    )
    op.create_index(
        "ix_stage12_retrieval_source_workspace_status",
        "stage12_retrieval_sources",
        ["workspace_id", "status"],
    )

    op.create_table(
        "stage12_retrieval_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("chunk_kind", sa.String(length=16), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=True),
        sa.Column(
            "field_ids",
            postgresql.ARRAY(sa.Uuid()),
            nullable=False,
        ),
        sa.Column("start_token", sa.Integer(), nullable=False),
        sa.Column("end_token", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "keyword_terms",
            postgresql.ARRAY(sa.String(length=64)),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "visibility_profile_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_profile", sa.String(length=96), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "source_type IN "
            "('schema_table', 'schema_field', 'record', 'record_field')",
            name=conv("ck_s12_chunk_source_type"),
        ),
        sa.CheckConstraint(
            "chunk_kind IN ('canonical', 'long_field')",
            name=conv("ck_s12_chunk_kind"),
        ),
        sa.CheckConstraint(
            "source_version > 0 AND ordinal >= 0 "
            "AND start_token >= 0 AND end_token > start_token",
            name=conv("ck_s12_chunk_positions"),
        ),
        sa.CheckConstraint(
            "((source_type IN ('record', 'record_field')) = "
            "(record_id IS NOT NULL))",
            name=conv("ck_s12_chunk_record_identity"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'indexed', 'stale', 'revoked', 'failed')",
            name=conv("ck_s12_chunk_status"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$' AND "
            "visibility_profile_hash ~ '^[0-9a-f]{64}$' AND "
            "scope_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_s12_chunk_hashes"),
        ),
        sa.CheckConstraint(
            "status <> 'indexed' OR "
            "(embedding IS NOT NULL AND revoked_at IS NULL "
            "AND char_length(btrim(chunk_text)) > 0)",
            name=conv("ck_s12_chunk_indexed_state"),
        ),
        sa.CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=conv("ck_s12_chunk_revoked_state"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(
            ["embedding_profile"],
            ["stage12_retrieval_profiles.profile_name"],
        ),
        sa.ForeignKeyConstraint(
            [
                "source_id",
                "workspace_id",
                "source_version",
                "embedding_profile",
            ],
            [
                "stage12_retrieval_sources.id",
                "stage12_retrieval_sources.workspace_id",
                "stage12_retrieval_sources.source_version",
                "stage12_retrieval_sources.embedding_profile",
            ],
            name="fk_s12_chunk_source_scope_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "source_version",
            "ordinal",
            name="uq_s12_chunk_source_version_ordinal",
        ),
    )
    op.create_index(
        "ix_stage12_retrieval_chunk_source_status",
        "stage12_retrieval_chunks",
        ["source_id", "status"],
    )
    op.create_index(
        "ix_stage12_retrieval_chunk_keyword_gin",
        "stage12_retrieval_chunks",
        ["keyword_terms"],
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_stage12_retrieval_chunk_hnsw_active_bge_m3 "
        "ON stage12_retrieval_chunks USING hnsw "
        "(embedding vector_cosine_ops) "
        "WHERE status = 'indexed' "
        "AND revoked_at IS NULL "
        "AND embedding IS NOT NULL "
        "AND embedding_profile = 'stage12.openrouter-bge-m3-v1'"
    )

    op.create_table(
        "stage12_relation_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("relation_id", sa.String(length=240), nullable=False),
        sa.Column("source_table_id", sa.Uuid(), nullable=False),
        sa.Column("source_record_id", sa.Uuid(), nullable=False),
        sa.Column("link_field_id", sa.Uuid(), nullable=False),
        sa.Column("target_table_id", sa.Uuid(), nullable=False),
        sa.Column("target_record_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column(
            "visibility_profile_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("edge_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "direction IN ('forward', 'reverse')",
            name=conv("ck_s12_relation_direction"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name=conv("ck_s12_relation_status"),
        ),
        sa.CheckConstraint(
            "source_version > 0 AND target_version > 0",
            name=conv("ck_s12_relation_versions"),
        ),
        sa.CheckConstraint(
            "source_table_id <> target_table_id "
            "AND source_record_id <> target_record_id",
            name=conv("ck_s12_relation_endpoints"),
        ),
        sa.CheckConstraint(
            "visibility_profile_hash ~ '^[0-9a-f]{64}$' AND "
            "scope_hash ~ '^[0-9a-f]{64}$' AND "
            "edge_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_s12_relation_hashes"),
        ),
        sa.CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=conv("ck_s12_relation_revoked_state"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["source_table_id"], ["tables.id"]),
        sa.ForeignKeyConstraint(["source_record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(["link_field_id"], ["fields.id"]),
        sa.ForeignKeyConstraint(["target_table_id"], ["tables.id"]),
        sa.ForeignKeyConstraint(["target_record_id"], ["records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "relation_id",
            "direction",
            "source_version",
            "target_version",
            "visibility_profile_hash",
            name="uq_s12_relation_version_visibility",
        ),
    )
    op.create_index(
        "ix_stage12_relation_source_active",
        "stage12_relation_edges",
        ["workspace_id", "source_record_id", "status"],
    )
    op.create_index(
        "ix_stage12_relation_target_active",
        "stage12_relation_edges",
        ["workspace_id", "target_record_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage12_relation_target_active",
        table_name="stage12_relation_edges",
    )
    op.drop_index(
        "ix_stage12_relation_source_active",
        table_name="stage12_relation_edges",
    )
    op.drop_table("stage12_relation_edges")

    op.drop_index(
        "ix_stage12_retrieval_chunk_hnsw_active_bge_m3",
        table_name="stage12_retrieval_chunks",
    )
    op.drop_index(
        "ix_stage12_retrieval_chunk_keyword_gin",
        table_name="stage12_retrieval_chunks",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_stage12_retrieval_chunk_source_status",
        table_name="stage12_retrieval_chunks",
    )
    op.drop_table("stage12_retrieval_chunks")

    op.drop_index(
        "ix_stage12_retrieval_source_workspace_status",
        table_name="stage12_retrieval_sources",
    )
    op.drop_index(
        "uq_stage12_retrieval_source_one_active_version",
        table_name="stage12_retrieval_sources",
    )
    op.drop_table("stage12_retrieval_sources")

    op.drop_index(
        "uq_stage12_retrieval_profile_one_active",
        table_name="stage12_retrieval_profiles",
    )
    op.drop_table("stage12_retrieval_profiles")
