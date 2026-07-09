"""Harden Stage 06 identity, constraints, indexes and idempotency."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260710_0020"
down_revision = "20260709_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stage06_telegram_bindings",
        sa.Column("workspace_member_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_stage06_binding_member",
        "stage06_telegram_bindings",
        "workspace_members",
        ["workspace_member_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_stage06_binding_employee",
        "stage06_telegram_bindings",
        "digital_employees",
        ["default_digital_employee_id"],
        ["id"],
    )

    op.create_table(
        "stage06_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("response_ref", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_stage06_idempotency_status",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_stage06_idempotency_workspace_id_workspaces",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stage06_idempotency_records"),
        sa.UniqueConstraint(
            "workspace_id",
            "operation",
            "idempotency_key",
            name="uq_stage06_idempotency_scope_key",
        ),
        sa.UniqueConstraint("trace_id", name="uq_stage06_idempotency_trace_id"),
    )

    op.create_check_constraint(
        "ck_stage06_records_positive_version",
        "records",
        "version > 0",
    )
    op.create_check_constraint(
        "ck_stage06_drafts_positive_expected_version",
        "record_change_drafts",
        "expected_version > 0",
    )

    op.create_index(
        "uq_stage06_digital_employee_alias",
        "digital_employees",
        ["base_id", "telegram_alias"],
        unique=True,
        postgresql_where=sa.text("telegram_alias IS NOT NULL AND status = 'active'"),
    )
    op.create_index(
        "uq_stage06_active_telegram_binding",
        "stage06_telegram_bindings",
        ["workspace_id", "telegram_chat_id", "telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_stage06_bindings_workspace_member_id",
        "stage06_telegram_bindings",
        ["workspace_member_id"],
    )
    op.create_index("ix_stage06_bases_workspace_id", "bases", ["workspace_id"])
    op.create_index("ix_stage06_tables_base_id", "tables", ["base_id"])
    op.create_index("ix_stage06_fields_table_id", "fields", ["table_id"])
    op.create_index("ix_stage06_records_table_id", "records", ["table_id"])
    op.create_index("ix_stage06_views_base_id", "views", ["base_id"])
    op.create_index("ix_stage06_views_table_id", "views", ["table_id"])
    op.create_index(
        "ix_stage06_import_jobs_workspace_status",
        "import_jobs",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_stage06_drafts_base_status",
        "record_change_drafts",
        ["base_id", "status"],
    )
    op.create_index(
        "ix_stage06_notifications_base_status",
        "notification_requests",
        ["base_id", "status"],
    )
    op.create_index(
        "ix_stage06_idempotency_workspace_operation",
        "stage06_idempotency_records",
        ["workspace_id", "operation"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage06_idempotency_workspace_operation",
        table_name="stage06_idempotency_records",
    )
    op.drop_index("ix_stage06_notifications_base_status", table_name="notification_requests")
    op.drop_index("ix_stage06_drafts_base_status", table_name="record_change_drafts")
    op.drop_index("ix_stage06_import_jobs_workspace_status", table_name="import_jobs")
    op.drop_index("ix_stage06_views_table_id", table_name="views")
    op.drop_index("ix_stage06_views_base_id", table_name="views")
    op.drop_index("ix_stage06_records_table_id", table_name="records")
    op.drop_index("ix_stage06_fields_table_id", table_name="fields")
    op.drop_index("ix_stage06_tables_base_id", table_name="tables")
    op.drop_index("ix_stage06_bases_workspace_id", table_name="bases")
    op.drop_index(
        "ix_stage06_bindings_workspace_member_id",
        table_name="stage06_telegram_bindings",
    )
    op.drop_index(
        "uq_stage06_active_telegram_binding",
        table_name="stage06_telegram_bindings",
    )
    op.drop_index(
        "uq_stage06_digital_employee_alias",
        table_name="digital_employees",
    )
    op.drop_constraint(
        "ck_stage06_drafts_positive_expected_version",
        "record_change_drafts",
        type_="check",
    )
    op.drop_constraint(
        "ck_stage06_records_positive_version",
        "records",
        type_="check",
    )
    op.drop_table("stage06_idempotency_records")
    op.drop_constraint(
        "fk_stage06_binding_employee",
        "stage06_telegram_bindings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stage06_binding_member",
        "stage06_telegram_bindings",
        type_="foreignkey",
    )
    op.drop_column("stage06_telegram_bindings", "workspace_member_id")
