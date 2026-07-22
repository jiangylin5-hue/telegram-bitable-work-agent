"""Add Stage08 execution ticket runtime foundation."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv


revision = "20260717_0028"
down_revision = "20260713_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage08_execution_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("budget", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "tool_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('planned', 'executing', 'succeeded', 'failed', "
            "'denied', 'cancelled', 'timed_out', 'expired')",
            name=conv("ck_stage08_execution_ticket_status"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(budget) = 'object'",
            name=conv("ck_stage08_execution_ticket_budget_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(tool_summary) = 'array'",
            name=conv("ck_stage08_execution_ticket_tool_summary_array"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["digital_employees.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "trace_id",
            name="uq_stage08_execution_ticket_workspace_trace",
        ),
    )
    op.create_index(
        "ix_stage08_execution_ticket_workspace_status_created",
        "stage08_execution_tickets",
        ["workspace_id", "status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage08_execution_ticket_workspace_status_created",
        table_name="stage08_execution_tickets",
    )
    op.drop_table("stage08_execution_tickets")
