"""Create confirmation and recharge flow tables.

Revision ID: 20260704_0003
Revises: 20260704_0002
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0003"
down_revision: str | None = "20260704_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_records",
        sa.Column("service_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("account_asset_id", sa.Uuid(), nullable=True),
        sa.Column("source_draft_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
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
            ["customer_id"],
            ["customers.id"],
            name="fk_service_records_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["source_draft_id"],
            ["service_drafts.id"],
            name="fk_service_records_source_draft_id_service_drafts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_service_records"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_service_records_idempotency_key",
        ),
    )
    op.create_index("ix_service_records_trace_id", "service_records", ["trace_id"])

    op.create_table(
        "execution_tickets",
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("allowed_action", sa.String(length=120), nullable=False),
        sa.Column("allowed_customer_id", sa.Uuid(), nullable=True),
        sa.Column("allowed_account_id", sa.Uuid(), nullable=True),
        sa.Column("amount_limit", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("payment_profile_id", sa.Uuid(), nullable=True),
        sa.Column("risk_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("permission_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_execution_tickets"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_execution_tickets_idempotency_key",
        ),
    )
    op.create_index(
        "ix_execution_tickets_trace_id",
        "execution_tickets",
        ["trace_id"],
    )

    op.create_table(
        "execution_logs",
        sa.Column("service_record_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("provider_response_id", sa.String(length=160), nullable=True),
        sa.Column("execution_status", sa.String(length=40), nullable=False),
        sa.Column("request_summary", postgresql.JSONB(), nullable=False),
        sa.Column("response_summary", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message_redacted", sa.String(length=500), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_record_id"],
            ["service_records.id"],
            name="fk_execution_logs_service_record_id_service_records",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_logs"),
    )
    op.create_index("ix_execution_logs_trace_id", "execution_logs", ["trace_id"])

    op.create_table(
        "recharge_records",
        sa.Column("service_record_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("account_asset_id", sa.Uuid(), nullable=True),
        sa.Column("collection_record_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("collection_status", sa.String(length=40), nullable=False),
        sa.Column("execution_status", sa.String(length=40), nullable=False),
        sa.Column("readback_status", sa.String(length=40), nullable=False),
        sa.Column("readback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_ticket_id", sa.Uuid(), nullable=True),
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
            name="fk_recharge_records_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["execution_ticket_id"],
            ["execution_tickets.id"],
            name="fk_recharge_records_execution_ticket_id_execution_tickets",
        ),
        sa.ForeignKeyConstraint(
            ["service_record_id"],
            ["service_records.id"],
            name="fk_recharge_records_service_record_id_service_records",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recharge_records"),
        sa.UniqueConstraint(
            "service_record_id",
            name="uq_recharge_records_service_record_id",
        ),
    )

    op.create_table(
        "collection_records",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("recharge_record_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("collection_method", sa.String(length=40), nullable=False),
        sa.Column("evidence_attachment_ref", sa.String(length=500), nullable=True),
        sa.Column("collection_status", sa.String(length=40), nullable=False),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finance_note", sa.String(length=500), nullable=True),
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
            ["customer_id"],
            ["customers.id"],
            name="fk_collection_records_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["recharge_record_id"],
            ["recharge_records.id"],
            name="fk_collection_records_recharge_record_id_recharge_records",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_records"),
    )
    op.create_index(
        "ix_collection_records_trace_id",
        "collection_records",
        ["trace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_records_trace_id", table_name="collection_records")
    op.drop_table("collection_records")
    op.drop_table("recharge_records")
    op.drop_index("ix_execution_logs_trace_id", table_name="execution_logs")
    op.drop_table("execution_logs")
    op.drop_index("ix_execution_tickets_trace_id", table_name="execution_tickets")
    op.drop_table("execution_tickets")
    op.drop_index("ix_service_records_trace_id", table_name="service_records")
    op.drop_table("service_records")
