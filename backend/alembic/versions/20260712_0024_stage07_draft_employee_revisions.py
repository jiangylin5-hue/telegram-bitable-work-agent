"""Add terminal draft revision and audit reference for Stage07 S5."""

import sqlalchemy as sa
from alembic import op


revision = "20260712_0024"
down_revision = "20260712_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "record_change_drafts",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "record_change_drafts",
        sa.Column(
            "terminal_audit_event_id",
            sa.Uuid(),
            sa.ForeignKey("ops_audit_events.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("record_change_drafts", "terminal_audit_event_id")
    op.drop_column("record_change_drafts", "version")
