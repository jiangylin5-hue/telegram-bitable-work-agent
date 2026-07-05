from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class AccountDailyMetric(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_daily_metrics"
    __table_args__ = (
        UniqueConstraint(
            "account_asset_id",
            "metric_date",
            "source",
            name="uq_account_daily_metrics_asset_date_source",
        ),
    )

    account_asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_assets.id"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance_currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    spend_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    spend_currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    freshness_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    read_status: Mapped[str] = mapped_column(String(40), nullable=False)


class RiskEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_events"

    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    account_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_assets.id"),
        nullable=True,
    )
    risk_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    source_metric_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_daily_metrics.id"),
        nullable=True,
    )
    source_metric: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    freshness_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class CustomerDailyReport(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_daily_reports"

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    visibility_scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)


class CompanyDailyReport(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_daily_reports"

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(40), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
