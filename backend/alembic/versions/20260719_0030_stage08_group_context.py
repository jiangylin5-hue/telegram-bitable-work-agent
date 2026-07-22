"""Add Stage08 controlled group-context projections."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.naming import conv


revision = "20260719_0030"
down_revision = "20260718_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage08_group_business_context_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_binding_id", sa.Uuid(), nullable=False),
        sa.Column("customer_record_id", sa.Uuid(), nullable=False),
        sa.Column("project_record_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
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
            "mapping_version >= 1",
            name=conv("ck_stage08_group_context_mapping_version_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=conv("ck_stage08_group_context_mapping_status"),
        ),
        sa.CheckConstraint(
            "customer_record_id <> project_record_id",
            name=conv("ck_stage08_group_context_distinct_business_records"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(
            ["telegram_binding_id"],
            ["stage06_telegram_bindings.id"],
        ),
        sa.ForeignKeyConstraint(["customer_record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(["project_record_id"], ["records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_binding_id",
            "mapping_version",
            name="uq_stage08_group_context_binding_version",
        ),
    )
    op.create_index(
        "uq_stage08_group_context_active_telegram_binding",
        "stage08_group_business_context_bindings",
        ["telegram_binding_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_stage08_group_context_workspace_status",
        "stage08_group_business_context_bindings",
        ["workspace_id", "status"],
    )

    op.create_table(
        "stage08_group_message_projections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=False),
        sa.Column("business_context_binding_id", sa.Uuid(), nullable=False),
        sa.Column("content_fragment", sa.Text(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
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
            "content_version >= 1",
            name=conv("ck_stage08_group_projection_content_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(content_fragment) <= 500",
            name=conv("ck_stage08_group_projection_fragment_length"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('active', 'superseded', 'purged')",
            name=conv("ck_stage08_group_projection_lifecycle_status"),
        ),
        sa.CheckConstraint(
            "retention_expires_at > event_at",
            name=conv("ck_stage08_group_projection_retention_after_event"),
        ),
        sa.CheckConstraint(
            "(lifecycle_status = 'purged' AND content_fragment = '') OR "
            "(lifecycle_status IN ('active', 'superseded') "
            "AND char_length(content_fragment) >= 1)",
            name=conv("ck_stage08_group_projection_fragment_lifecycle"),
        ),
        sa.ForeignKeyConstraint(
            ["business_context_binding_id"],
            ["stage08_group_business_context_bindings.id"],
        ),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_message_id",
            "content_version",
            name="uq_stage08_group_projection_source_version",
        ),
    )
    op.create_index(
        "ix_stage08_group_projection_mapping_lifecycle_event",
        "stage08_group_message_projections",
        ["business_context_binding_id", "lifecycle_status", "event_at", "id"],
    )
    op.create_index(
        "ix_stage08_group_projection_retention_lifecycle",
        "stage08_group_message_projections",
        ["retention_expires_at", "lifecycle_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage08_group_projection_retention_lifecycle",
        table_name="stage08_group_message_projections",
    )
    op.drop_index(
        "ix_stage08_group_projection_mapping_lifecycle_event",
        table_name="stage08_group_message_projections",
    )
    op.drop_table("stage08_group_message_projections")
    op.drop_index(
        "ix_stage08_group_context_workspace_status",
        table_name="stage08_group_business_context_bindings",
    )
    op.drop_index(
        "uq_stage08_group_context_active_telegram_binding",
        table_name="stage08_group_business_context_bindings",
    )
    op.drop_table("stage08_group_business_context_bindings")
