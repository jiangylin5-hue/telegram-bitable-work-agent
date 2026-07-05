"""Create account inventory tables.

Revision ID: 20260704_0004
Revises: 20260704_0003
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260704_0004"
down_revision: str | None = "20260704_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_inventory",
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("external_account_id", sa.String(length=120), nullable=False),
        sa.Column("inventory_status", sa.String(length=40), nullable=False),
        sa.Column("production_batch_id", sa.String(length=120), nullable=True),
        sa.Column("produced_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_customer_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_reason", sa.String(length=500), nullable=True),
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
            ["assigned_customer_id"],
            ["customers.id"],
            name="fk_account_inventory_assigned_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_inventory"),
        sa.UniqueConstraint(
            "platform",
            "external_account_id",
            name="uq_account_inventory_platform_external_account",
        ),
    )

    op.create_table(
        "account_assets",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("account_inventory_id", sa.Uuid(), nullable=True),
        sa.Column("external_account_id", sa.String(length=120), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("balance_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("balance_currency", sa.String(length=12), nullable=True),
        sa.Column("spend_today", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("spend_yesterday", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("spend_7d", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_status", sa.String(length=40), nullable=False),
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
            ["account_inventory_id"],
            ["account_inventory.id"],
            name="fk_account_assets_account_inventory_id_account_inventory",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_account_assets_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_assets"),
        sa.UniqueConstraint(
            "platform",
            "external_account_id",
            name="uq_account_assets_platform_external_account",
        ),
    )

    op.create_table(
        "account_assignments",
        sa.Column("account_inventory_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("assignment_status", sa.String(length=40), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_inventory_id"],
            ["account_inventory.id"],
            name="fk_account_assignments_account_inventory_id_account_inventory",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_account_assignments_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_assignments"),
    )
    op.create_index(
        "ix_account_assignments_trace_id",
        "account_assignments",
        ["trace_id"],
    )

    op.create_table(
        "account_status_events",
        sa.Column("account_inventory_id", sa.Uuid(), nullable=True),
        sa.Column("account_asset_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("before_status", sa.String(length=40), nullable=True),
        sa.Column("after_status", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("source_entity_type", sa.String(length=80), nullable=True),
        sa.Column("source_entity_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_inventory_id"],
            ["account_inventory.id"],
            name="fk_account_status_events_account_inventory_id_account_inventory",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_account_status_events_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_status_events"),
    )


def downgrade() -> None:
    op.drop_table("account_status_events")
    op.drop_index("ix_account_assignments_trace_id", table_name="account_assignments")
    op.drop_table("account_assignments")
    op.drop_table("account_assets")
    op.drop_table("account_inventory")
