"""Create tokenized card binding fact tables.

Revision ID: 20260705_0009
Revises: 20260704_0008
Create Date: 2026-07-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260705_0009"
down_revision: str | None = "20260704_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_profiles",
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("tokenized_profile_id", sa.String(length=160), nullable=False),
        sa.Column("masked_label", sa.String(length=160), nullable=False),
        sa.Column("last4", sa.String(length=8), nullable=True),
        sa.Column("brand", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("limit_summary", sa.String(length=500), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "tokenized_profile_id",
            name="uq_payment_profiles_provider_tokenized_profile",
        ),
    )
    op.create_table(
        "account_card_bindings",
        sa.Column("account_asset_id", sa.Uuid(), nullable=False),
        sa.Column("payment_profile_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("binding_status", sa.String(length=40), nullable=False),
        sa.Column(
            "one_card_one_account_policy",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column("service_record_id", sa.Uuid(), nullable=True),
        sa.Column("execution_log_id", sa.Uuid(), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
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
        sa.ForeignKeyConstraint(["account_asset_id"], ["account_assets.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["execution_log_id"], ["execution_logs.id"]),
        sa.ForeignKeyConstraint(["payment_profile_id"], ["payment_profiles.id"]),
        sa.ForeignKeyConstraint(["service_record_id"], ["service_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_card_bindings_trace_id",
        "account_card_bindings",
        ["trace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_card_bindings_trace_id", table_name="account_card_bindings")
    op.drop_table("account_card_bindings")
    op.drop_table("payment_profiles")
