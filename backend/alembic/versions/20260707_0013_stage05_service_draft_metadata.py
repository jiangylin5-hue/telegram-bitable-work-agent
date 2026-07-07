"""Add Stage 05 service draft metadata columns.

Revision ID: 20260707_0013
Revises: 20260707_0012
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260707_0013"
down_revision = "20260707_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_drafts",
        sa.Column("source_agent_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "service_drafts",
        sa.Column("intent_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "service_drafts",
        sa.Column("payload_summary", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "service_drafts",
        sa.Column("review_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "service_drafts",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_service_drafts_source_agent_run_id_agent_runs",
        "service_drafts",
        "agent_runs",
        ["source_agent_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_service_drafts_source_agent_run_id_agent_runs",
        "service_drafts",
        type_="foreignkey",
    )
    op.drop_column("service_drafts", "confirmed_at")
    op.drop_column("service_drafts", "review_reason")
    op.drop_column("service_drafts", "payload_summary")
    op.drop_column("service_drafts", "intent_index")
    op.drop_column("service_drafts", "source_agent_run_id")
