"""Add Stage 05 customer reply send request linkage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260707_0016"
down_revision = "20260707_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_send_requests",
        sa.Column("source_service_draft_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "telegram_send_requests",
        sa.Column(
            "send_purpose",
            sa.String(length=60),
            server_default="test_send",
            nullable=False,
        ),
    )
    op.add_column(
        "telegram_send_requests",
        sa.Column("message_text_summary", postgresql.JSONB(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tg_send_req_source_draft",
        "telegram_send_requests",
        "service_drafts",
        ["source_service_draft_id"],
        ["id"],
    )
    op.create_index(
        "ix_telegram_send_requests_source_service_draft_id",
        "telegram_send_requests",
        ["source_service_draft_id"],
    )
    op.create_index(
        "ix_telegram_send_requests_send_purpose_status_created_at",
        "telegram_send_requests",
        ["send_purpose", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_send_requests_send_purpose_status_created_at",
        table_name="telegram_send_requests",
    )
    op.drop_index(
        "ix_telegram_send_requests_source_service_draft_id",
        table_name="telegram_send_requests",
    )
    op.drop_constraint(
        "fk_tg_send_req_source_draft",
        "telegram_send_requests",
        type_="foreignkey",
    )
    op.drop_column("telegram_send_requests", "message_text_summary")
    op.drop_column("telegram_send_requests", "send_purpose")
    op.drop_column("telegram_send_requests", "source_service_draft_id")
