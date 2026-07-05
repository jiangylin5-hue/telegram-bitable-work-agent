"""Create reporting tables.

Revision ID: 20260704_0005
Revises: 20260704_0004
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0005"
down_revision: str | None = "20260704_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_daily_metrics",
        sa.Column("account_asset_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("balance_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("balance_currency", sa.String(length=12), nullable=True),
        sa.Column("spend_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("spend_currency", sa.String(length=12), nullable=True),
        sa.Column("freshness_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("read_status", sa.String(length=40), nullable=False),
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
            ["account_asset_id"],
            ["account_assets.id"],
            name="fk_account_daily_metrics_account_asset_id_account_assets",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_account_daily_metrics_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_daily_metrics"),
        sa.UniqueConstraint(
            "account_asset_id",
            "metric_date",
            "source",
            name="uq_account_daily_metrics_asset_date_source",
        ),
    )

    op.create_table(
        "risk_events",
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("account_asset_id", sa.Uuid(), nullable=True),
        sa.Column("risk_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("source_metric_id", sa.Uuid(), nullable=True),
        sa.Column("source_metric", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("freshness_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
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
            ["account_asset_id"],
            ["account_assets.id"],
            name="fk_risk_events_account_asset_id_account_assets",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_risk_events_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["source_metric_id"],
            ["account_daily_metrics.id"],
            name="fk_risk_events_source_metric_id_account_daily_metrics",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_events"),
    )

    op.create_table(
        "customer_daily_reports",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("visibility_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("delivery_status", sa.String(length=40), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_customer_daily_reports_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_daily_reports"),
    )
    op.create_index(
        "ix_customer_daily_reports_trace_id",
        "customer_daily_reports",
        ["trace_id"],
    )

    op.create_table(
        "company_daily_reports",
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("delivery_status", sa.String(length=40), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_company_daily_reports"),
    )
    op.create_index(
        "ix_company_daily_reports_trace_id",
        "company_daily_reports",
        ["trace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_daily_reports_trace_id", table_name="company_daily_reports")
    op.drop_table("company_daily_reports")
    op.drop_index("ix_customer_daily_reports_trace_id", table_name="customer_daily_reports")
    op.drop_table("customer_daily_reports")
    op.drop_table("risk_events")
    op.drop_table("account_daily_metrics")
