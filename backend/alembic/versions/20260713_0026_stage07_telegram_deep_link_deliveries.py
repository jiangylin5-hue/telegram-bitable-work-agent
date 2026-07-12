"""Add closed controlled-delivery extension for Stage07 S6.2."""

import sqlalchemy as sa
from alembic import op


revision = "20260713_0026"
down_revision = "20260712_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage07_telegram_deep_link_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("send_request_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_binding_id", sa.Uuid(), nullable=False),
        sa.Column("subject_telegram_user_id", sa.String(length=120), nullable=False),
        sa.Column("target_chat_id", sa.String(length=120), nullable=False),
        sa.Column("destination_kind", sa.String(length=40), nullable=False),
        sa.Column("destination_id", sa.Uuid(), nullable=False),
        sa.Column("message_template", sa.String(length=80), nullable=False),
        sa.Column("dispatch_state", sa.String(length=40), nullable=False),
        sa.Column("stage07_telegram_deep_link_id", sa.Uuid(), nullable=True),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("outcome_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "destination_kind IN ('base', 'view', 'record', 'record_change_draft')",
            name="ck_stage07_telegram_deep_link_deliveries_destination_kind",
        ),
        sa.CheckConstraint(
            "dispatch_state IN ('pending_confirmation', 'dispatch_reserved', "
            "'sent', 'failed', 'delivery_unknown', 'blocked', 'cancelled')",
            name="ck_stage07_telegram_deep_link_deliveries_dispatch_state",
        ),
        sa.CheckConstraint(
            "message_template = 'stage07_open_secure_destination'",
            name="ck_stage07_telegram_deep_link_deliveries_message_template",
        ),
        sa.ForeignKeyConstraint(
            ["send_request_id"],
            ["telegram_send_requests.id"],
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(
            ["source_binding_id"],
            ["stage06_telegram_bindings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["stage07_telegram_deep_link_id"],
            ["stage07_telegram_deep_links.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "send_request_id",
            name="uq_stage07_telegram_deep_link_deliveries_send_request_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("stage07_telegram_deep_link_deliveries")
