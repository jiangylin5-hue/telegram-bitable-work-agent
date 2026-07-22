"""Add Stage08 business-memory persistent contracts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv


revision = "20260718_0029"
down_revision = "20260717_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage08_memory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("memory_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
            "status IN ('active', 'conflicted', 'superseded', 'revoked', "
            "'expired', 'deleted')",
            name=conv("ck_stage08_memory_item_status"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope) = 'object'",
            name=conv("ck_stage08_memory_item_scope_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name=conv("ck_stage08_memory_item_payload_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name=conv("ck_stage08_memory_item_source_refs_array"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=conv("ck_stage08_memory_item_version_positive"),
        ),
        sa.ForeignKeyConstraint(["supersedes_id"], ["stage08_memory_items.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "memory_type",
            "source_fingerprint",
            name="uq_stage08_memory_item_workspace_type_fingerprint",
        ),
    )
    op.create_index(
        "ix_stage08_memory_item_workspace_status_valid_until",
        "stage08_memory_items",
        ["workspace_id", "status", "valid_until"],
    )
    op.create_table(
        "stage08_memory_extraction_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "normalized_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
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
            "status IN ('candidate', 'accepted', 'rejected', 'expired')",
            name=conv("ck_stage08_memory_candidate_status"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=conv("ck_stage08_memory_candidate_confidence_range"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope) = 'object'",
            name=conv("ck_stage08_memory_candidate_scope_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(normalized_payload) = 'object'",
            name=conv("ck_stage08_memory_candidate_payload_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name=conv("ck_stage08_memory_candidate_source_refs_array"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=conv("ck_stage08_memory_candidate_version_positive"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "candidate_type",
            "source_fingerprint",
            name="uq_stage08_memory_candidate_workspace_type_fingerprint",
        ),
    )
    op.create_index(
        "ix_stage08_memory_candidate_workspace_status_valid_until",
        "stage08_memory_extraction_candidates",
        ["workspace_id", "status", "valid_until"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage08_memory_candidate_workspace_status_valid_until",
        table_name="stage08_memory_extraction_candidates",
    )
    op.drop_table("stage08_memory_extraction_candidates")
    op.drop_index(
        "ix_stage08_memory_item_workspace_status_valid_until",
        table_name="stage08_memory_items",
    )
    op.drop_table("stage08_memory_items")
