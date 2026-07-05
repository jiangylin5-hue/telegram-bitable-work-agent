"""Align outbox fields with Stage 02 plan.

Revision ID: 20260704_0008
Revises: 20260704_0007
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260704_0008"
down_revision: str | None = "20260704_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("aggregate_type", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("aggregate_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "outbox_events",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("last_error", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "processed_at")
    op.drop_column("outbox_events", "available_at")
    op.drop_column("outbox_events", "attempt_count")
    op.drop_column("outbox_events", "aggregate_id")
    op.drop_column("outbox_events", "aggregate_type")
