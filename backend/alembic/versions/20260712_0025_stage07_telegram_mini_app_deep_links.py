"""Add opaque Telegram Mini App deep links for Stage07 S6.1."""

import sqlalchemy as sa
from alembic import op


revision = "20260712_0025"
down_revision = "20260712_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage07_telegram_deep_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("subject_telegram_user_id", sa.String(length=120), nullable=False),
        sa.Column("source_telegram_chat_id", sa.String(length=120), nullable=False),
        sa.Column("destination_kind", sa.String(length=40), nullable=False),
        sa.Column("destination_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_type", sa.String(length=40), nullable=False),
        sa.Column("created_by_id", sa.String(length=120), nullable=False),
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
            name="ck_stage07_telegram_deep_links_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_stage07_telegram_deep_links_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_stage07_telegram_deep_links_token_hash",
        ),
    )


def downgrade() -> None:
    op.drop_table("stage07_telegram_deep_links")
