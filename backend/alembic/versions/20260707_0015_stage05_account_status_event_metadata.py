"""Add Stage 05 account status event metadata columns.

Revision ID: 20260707_0015
Revises: 20260707_0013
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260707_0015"
down_revision = "20260707_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_status_events",
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "account_status_events",
        sa.Column("risk_flags", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("account_status_events", "risk_flags")
    op.drop_column("account_status_events", "confidence")
