"""Add Stage 04 Telegram test send requests.

Revision ID: 20260706_0011
Revises: 20260706_0010
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260706_0011"
down_revision: str | None = "20260706_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_send_requests",
        sa.Column("target_chat_id", sa.String(length=80), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default="pending_confirmation",
            nullable=False,
        ),
        sa.Column("requested_by_actor_type", sa.String(length=40), nullable=False),
        sa.Column("requested_by_actor_id", sa.String(length=120), nullable=False),
        sa.Column("confirmed_by_actor_type", sa.String(length=40), nullable=True),
        sa.Column("confirmed_by_actor_id", sa.String(length=120), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "allowlist_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "telegram_response_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_send_requests_trace_id",
        "telegram_send_requests",
        ["trace_id"],
    )
    op.create_index(
        "ix_telegram_send_requests_status_created_at",
        "telegram_send_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_telegram_send_requests_target_chat_created_at",
        "telegram_send_requests",
        ["target_chat_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_send_requests_target_chat_created_at",
        table_name="telegram_send_requests",
    )
    op.drop_index(
        "ix_telegram_send_requests_status_created_at",
        table_name="telegram_send_requests",
    )
    op.drop_index(
        "ix_telegram_send_requests_trace_id",
        table_name="telegram_send_requests",
    )
    op.drop_table("telegram_send_requests")
