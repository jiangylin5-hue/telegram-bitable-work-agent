"""Add one-time browser handoffs and browser sessions for Stage09."""

import sqlalchemy as sa
from alembic import op


revision = "20260723_0033"
down_revision = "20260720_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mini_app_browser_handoffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=120), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticket_hash",
            name="uq_mini_app_browser_handoffs_ticket_hash",
        ),
    )
    op.create_index(
        "ix_mini_app_browser_handoffs_ticket_lifecycle",
        "mini_app_browser_handoffs",
        ["ticket_hash", "expires_at", "consumed_at", "revoked_at"],
    )
    op.create_table(
        "mini_app_browser_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=120), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_mini_app_browser_sessions_token_hash",
        ),
    )
    op.create_index(
        "ix_mini_app_browser_sessions_token_lifecycle",
        "mini_app_browser_sessions",
        ["token_hash", "expires_at", "revoked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mini_app_browser_sessions_token_lifecycle",
        table_name="mini_app_browser_sessions",
    )
    op.drop_table("mini_app_browser_sessions")
    op.drop_index(
        "ix_mini_app_browser_handoffs_ticket_lifecycle",
        table_name="mini_app_browser_handoffs",
    )
    op.drop_table("mini_app_browser_handoffs")
