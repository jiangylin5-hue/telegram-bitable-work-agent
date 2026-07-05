from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class RechargeRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recharge_records"
    __table_args__ = (
        UniqueConstraint(
            "service_record_id",
            name="uq_recharge_records_service_record_id",
        ),
    )

    service_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("service_records.id"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    account_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    collection_record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(12), nullable=False)
    collection_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="missing",
    )
    execution_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="not_started",
    )
    readback_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="not_started",
    )
    readback_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_ticket_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("execution_tickets.id"),
        nullable=True,
    )


class CollectionRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_records"

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    recharge_record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("recharge_records.id"),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(12), nullable=False)
    collection_method: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_attachment_ref: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    collection_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
    )
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finance_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
