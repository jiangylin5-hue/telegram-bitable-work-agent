"""Add Stage 03 Telegram customer bindings and inbox fields.

Revision ID: 20260706_0010
Revises: 20260705_0009
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260706_0010"
down_revision: str | None = "20260705_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("telegram_user_id", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column(
            "binding_status",
            sa.String(length=40),
            server_default="needs_manual_binding",
            nullable=False,
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "processing_status",
            sa.String(length=40),
            server_default="queued",
            nullable=False,
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "outbox_status",
            sa.String(length=40),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "messages",
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "telegram_customer_bindings",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=80), nullable=True),
        sa.Column("telegram_user_id", sa.String(length=80), nullable=True),
        sa.Column("binding_scope", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
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
    )
    op.create_index(
        "ix_telegram_customer_bindings_chat_id",
        "telegram_customer_bindings",
        ["telegram_chat_id"],
    )
    op.create_index(
        "ix_telegram_customer_bindings_user_id",
        "telegram_customer_bindings",
        ["telegram_user_id"],
    )
    op.create_index(
        "uq_telegram_customer_bindings_active_chat",
        "telegram_customer_bindings",
        ["binding_scope", "telegram_chat_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND binding_scope = 'chat'"),
    )
    op.create_index(
        "uq_telegram_customer_bindings_active_user",
        "telegram_customer_bindings",
        ["binding_scope", "telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND binding_scope = 'user'"),
    )
    op.create_index(
        "uq_telegram_customer_bindings_active_chat_user",
        "telegram_customer_bindings",
        ["binding_scope", "telegram_chat_id", "telegram_user_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'active' AND binding_scope = 'chat_user'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_telegram_customer_bindings_active_chat_user",
        table_name="telegram_customer_bindings",
    )
    op.drop_index(
        "uq_telegram_customer_bindings_active_user",
        table_name="telegram_customer_bindings",
    )
    op.drop_index(
        "uq_telegram_customer_bindings_active_chat",
        table_name="telegram_customer_bindings",
    )
    op.drop_index(
        "ix_telegram_customer_bindings_user_id",
        table_name="telegram_customer_bindings",
    )
    op.drop_index(
        "ix_telegram_customer_bindings_chat_id",
        table_name="telegram_customer_bindings",
    )
    op.drop_table("telegram_customer_bindings")

    op.drop_column("messages", "processed_at")
    op.drop_column("messages", "last_error_code")
    op.drop_column("messages", "outbox_status")
    op.drop_column("messages", "processing_status")
    op.drop_column("messages", "binding_status")
    op.drop_column("messages", "telegram_user_id")
