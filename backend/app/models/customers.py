from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Customer(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(
        String(200),
        unique=True,
        nullable=True,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    risk_level: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="unknown",
    )
    telegram_primary_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    report_delivery_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerGroup(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_groups"
    __table_args__ = (
        UniqueConstraint("telegram_chat_id", name="uq_customer_groups_telegram_chat"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    telegram_chat_id: Mapped[str] = mapped_column(String(80), nullable=False)
    group_title: Mapped[str] = mapped_column(String(255), nullable=False)
    group_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="customer_group",
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
