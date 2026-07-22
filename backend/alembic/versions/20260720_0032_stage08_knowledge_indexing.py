"""Add Stage08 safe knowledge source and pgvector indexing contracts."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv


revision = "20260720_0032"
down_revision = "20260720_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "stage08_knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "source_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "logical_source_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("projection_hash", sa.String(length=64), nullable=False),
        sa.Column("projection_text", sa.Text(), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "source_type IN "
            "('memory_item', 'document_projection', 'approved_summary')",
            name=conv("ck_stage08_knowledge_source_type"),
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending', 'active', 'replaced', 'revoked', 'expired', 'deleted')",
            name=conv("ck_stage08_knowledge_source_status"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_ref) = 'object'",
            name=conv("ck_stage08_knowledge_source_ref_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope) = 'object'",
            name=conv("ck_stage08_knowledge_source_scope_object"),
        ),
        sa.CheckConstraint(
            "logical_source_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_stage08_knowledge_source_fingerprint_sha256"),
        ),
        sa.CheckConstraint(
            "projection_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_stage08_knowledge_source_projection_hash_sha256"),
        ),
        sa.CheckConstraint(
            "content_version > 0",
            name=conv("ck_stage08_knowledge_source_version_positive"),
        ),
        sa.CheckConstraint(
            "status <> 'active' OR "
            "(projection_text IS NOT NULL "
            "AND char_length(btrim(projection_text)) > 0)",
            name=conv("ck_stage08_knowledge_source_active_projection"),
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["stage08_knowledge_sources.id"],
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "source_type",
            "logical_source_fingerprint",
            "content_version",
            name=(
                "uq_stage08_knowledge_source_workspace_type_"
                "fingerprint_version"
            ),
        ),
        sa.UniqueConstraint(
            "id",
            "workspace_id",
            "content_version",
            name="uq_stage08_knowledge_source_id_workspace_version",
        ),
    )
    op.create_index(
        "ix_stage08_knowledge_source_workspace_status_valid_until",
        "stage08_knowledge_sources",
        ["workspace_id", "status", "valid_until"],
    )
    op.create_index(
        "ix_stage08_knowledge_source_workspace_fingerprint_version",
        "stage08_knowledge_sources",
        ["workspace_id", "logical_source_fingerprint", "content_version"],
    )

    op.create_table(
        "stage08_knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=True),
        sa.Column("chunk_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "keyword_terms",
            postgresql.ARRAY(sa.String(length=64)),
            nullable=False,
        ),
        sa.Column("embedding_profile", sa.String(length=80), nullable=True),
        sa.Column("embedding_version", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'indexed', 'stale', 'deleted', 'failed')",
            name=conv("ck_stage08_knowledge_chunk_status"),
        ),
        sa.CheckConstraint(
            "source_version > 0",
            name=conv("ck_stage08_knowledge_chunk_source_version_positive"),
        ),
        sa.CheckConstraint(
            "ordinal >= 0",
            name=conv("ck_stage08_knowledge_chunk_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "chunk_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_stage08_knowledge_chunk_hash_sha256"),
        ),
        sa.CheckConstraint(
            "status <> 'indexed' OR "
            "(chunk_text IS NOT NULL AND char_length(btrim(chunk_text)) > 0)",
            name=conv("ck_stage08_knowledge_chunk_indexed_text"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "workspace_id", "source_version"],
            [
                "stage08_knowledge_sources.id",
                "stage08_knowledge_sources.workspace_id",
                "stage08_knowledge_sources.content_version",
            ],
            name="fk_stage08_knowledge_chunk_source_scope_version",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "source_version",
            "ordinal",
            name="uq_stage08_knowledge_chunk_source_version_ordinal",
        ),
    )
    op.create_index(
        "ix_stage08_knowledge_chunk_workspace_status_source_version",
        "stage08_knowledge_chunks",
        ["workspace_id", "status", "source_version"],
    )
    op.create_index(
        "ix_stage08_knowledge_chunk_source_status",
        "stage08_knowledge_chunks",
        ["source_id", "status"],
    )
    op.create_index(
        "ix_stage08_knowledge_chunk_keyword_terms_gin",
        "stage08_knowledge_chunks",
        ["keyword_terms"],
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_stage08_knowledge_chunk_hnsw_test_profile "
        "ON stage08_knowledge_chunks USING hnsw "
        "((embedding::vector(8)) vector_cosine_ops) "
        "WHERE status = 'indexed' "
        "AND embedding_profile = 'stage08.test-hash-v1' "
        "AND embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage08_knowledge_chunk_hnsw_test_profile",
        table_name="stage08_knowledge_chunks",
    )
    op.drop_index(
        "ix_stage08_knowledge_chunk_keyword_terms_gin",
        table_name="stage08_knowledge_chunks",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_stage08_knowledge_chunk_source_status",
        table_name="stage08_knowledge_chunks",
    )
    op.drop_index(
        "ix_stage08_knowledge_chunk_workspace_status_source_version",
        table_name="stage08_knowledge_chunks",
    )
    op.drop_table("stage08_knowledge_chunks")
    op.drop_index(
        "ix_stage08_knowledge_source_workspace_fingerprint_version",
        table_name="stage08_knowledge_sources",
    )
    op.drop_index(
        "ix_stage08_knowledge_source_workspace_status_valid_until",
        table_name="stage08_knowledge_sources",
    )
    op.drop_table("stage08_knowledge_sources")
