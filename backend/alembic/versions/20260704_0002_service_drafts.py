"""Create service drafts table.

Revision ID: 20260704_0002
Revises: 20260704_0001
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0002"
down_revision: str | None = "20260704_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_drafts",
        sa.Column("draft_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("account_asset_id", sa.Uuid(), nullable=True),
        sa.Column("account_inventory_id", sa.Uuid(), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_type", sa.String(length=40), nullable=False),
        sa.Column("created_by_id", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("missing_fields", postgresql.JSONB(), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_service_drafts_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            name="fk_service_drafts_source_message_id_messages",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_service_drafts"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_service_drafts_idempotency_key",
        ),
    )
    op.create_index(
        "ix_service_drafts_trace_id",
        "service_drafts",
        ["trace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_drafts_trace_id", table_name="service_drafts")
    op.drop_table("service_drafts")
