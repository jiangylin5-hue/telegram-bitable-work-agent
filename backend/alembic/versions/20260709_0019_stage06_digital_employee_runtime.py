"""Add Stage 06 digital employee runtime tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260709_0019"
down_revision = "20260709_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digital_employees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("telegram_alias", sa.String(length=80), nullable=True),
        sa.Column("accessible_tables", postgresql.JSONB(), nullable=False),
        sa.Column("accessible_views", postgresql.JSONB(), nullable=False),
        sa.Column("field_policy", postgresql.JSONB(), nullable=False),
        sa.Column("allowed_actions", postgresql.JSONB(), nullable=False),
        sa.Column("confirmation_policy", postgresql.JSONB(), nullable=False),
        sa.Column("response_style", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_digital_employees_base_id_bases")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_digital_employees_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_digital_employees")),
    )
    op.create_table(
        "record_change_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=True),
        sa.Column("draft_type", sa.String(length=60), nullable=False),
        sa.Column("proposed_values", postgresql.JSONB(), nullable=False),
        sa.Column("before_values", postgresql.JSONB(), nullable=True),
        sa.Column("created_by_type", sa.String(length=40), nullable=False),
        sa.Column("created_by_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("confirmation_policy", postgresql.JSONB(), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_record_change_drafts_base_id_bases")),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"], name=op.f("fk_record_change_drafts_record_id_records")),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"], name=op.f("fk_record_change_drafts_table_id_tables")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_record_change_drafts_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_change_drafts")),
    )
    op.create_table(
        "notification_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=True),
        sa.Column("source_record_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("target", postgresql.JSONB(), nullable=False),
        sa.Column("message_payload", postgresql.JSONB(), nullable=False),
        sa.Column("send_policy", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_notification_requests_base_id_bases")),
        sa.ForeignKeyConstraint(["source_record_id"], ["records.id"], name=op.f("fk_notification_requests_source_record_id_records")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_notification_requests_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_requests")),
    )


def downgrade() -> None:
    op.drop_table("notification_requests")
    op.drop_table("record_change_drafts")
    op.drop_table("digital_employees")
