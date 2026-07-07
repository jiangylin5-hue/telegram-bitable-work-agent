"""Add Stage 05 AgentRun evidence columns.

Revision ID: 20260707_0012
Revises: 20260706_0011
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260707_0012"
down_revision: str | None = "20260706_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("message_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "usage_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "cost_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column("error_code", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column("error_message_redacted", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "created_entity_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("redaction_policy", sa.String(length=80), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_runs_message_id_messages",
        "agent_runs",
        "messages",
        ["message_id"],
        ["id"],
    )
    op.create_index(
        "ix_agent_runs_message_id_started_at",
        "agent_runs",
        ["message_id", "started_at"],
    )
    op.create_index(
        "ix_agent_runs_status_started_at",
        "agent_runs",
        ["status", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_runs_status_started_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_message_id_started_at", table_name="agent_runs")
    op.drop_constraint(
        "fk_agent_runs_message_id_messages",
        "agent_runs",
        type_="foreignkey",
    )
    op.drop_column("agent_runs", "redaction_policy")
    op.drop_column("agent_runs", "created_entity_refs")
    op.drop_column("agent_runs", "error_message_redacted")
    op.drop_column("agent_runs", "error_code")
    op.drop_column("agent_runs", "latency_ms")
    op.drop_column("agent_runs", "cost_summary")
    op.drop_column("agent_runs", "usage_summary")
    op.drop_column("agent_runs", "message_id")
