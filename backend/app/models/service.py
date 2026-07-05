from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class ServiceRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_records"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_service_records_idempotency_key"),
    )

    service_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    account_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    source_draft_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("service_drafts.id"),
        nullable=True,
    )
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)


class ExecutionTicket(UuidPrimaryKeyMixin, Base):
    __tablename__ = "execution_tickets"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_execution_tickets_idempotency_key",
        ),
    )

    approved_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=1),
        nullable=False,
    )
    allowed_action: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    allowed_account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    amount_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    payment_profile_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    risk_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    permission_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="issued")
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)


class ExecutionLog(UuidPrimaryKeyMixin, Base):
    __tablename__ = "execution_logs"

    service_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("service_records.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_response_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    execution_status: Mapped[str] = mapped_column(String(40), nullable=False)
    request_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message_redacted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
