"""Create Stage 02 core tables.

Revision ID: 20260704_0001
Revises:
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )

    op.create_table(
        "customers",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("telegram_primary_group_id", sa.Uuid(), nullable=True),
        sa.Column("report_delivery_policy", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            ["owner_user_id"],
            ["users.id"],
            name="fk_customers_owner_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("normalized_name", name="uq_customers_normalized_name"),
    )

    op.create_table(
        "customer_groups",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=80), nullable=False),
        sa.Column("group_title", sa.String(length=255), nullable=False),
        sa.Column("group_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_customer_groups_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_groups"),
        sa.UniqueConstraint(
            "telegram_chat_id",
            name="uq_customer_groups_telegram_chat",
        ),
    )

    op.create_table(
        "telegram_identities",
        sa.Column("telegram_user_id", sa.String(length=80), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("contact_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
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
            name="fk_telegram_identities_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_telegram_identities_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_identities"),
        sa.UniqueConstraint(
            "telegram_user_id",
            name="uq_telegram_identities_telegram_user",
        ),
    )

    op.create_table(
        "messages",
        sa.Column("telegram_update_id", sa.String(length=80), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=80), nullable=False),
        sa.Column("telegram_message_id", sa.String(length=80), nullable=False),
        sa.Column("sender_identity_id", sa.Uuid(), nullable=True),
        sa.Column("customer_group_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_caption", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("intent_status", sa.String(length=40), nullable=False),
        sa.Column("intent_type", sa.String(length=60), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_status", sa.String(length=40), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["customer_group_id"],
            ["customer_groups.id"],
            name="fk_messages_customer_group_id_customer_groups",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_messages_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["sender_identity_id"],
            ["telegram_identities.id"],
            name="fk_messages_sender_identity_id_telegram_identities",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_messages_chat_message",
        ),
        sa.UniqueConstraint(
            "telegram_update_id",
            name="uq_messages_telegram_update",
        ),
    )

    op.create_table(
        "ops_audit_events",
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("permission_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_audit_events"),
    )
    op.create_index(
        "ix_ops_audit_events_trace_id",
        "ops_audit_events",
        ["trace_id"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_redacted", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_outbox_events_idempotency_key",
        ),
    )
    op.create_index("ix_outbox_events_trace_id", "outbox_events", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_trace_id", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_ops_audit_events_trace_id", table_name="ops_audit_events")
    op.drop_table("ops_audit_events")
    op.drop_table("messages")
    op.drop_table("telegram_identities")
    op.drop_table("customer_groups")
    op.drop_table("customers")
    op.drop_table("users")
