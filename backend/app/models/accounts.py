from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class AccountInventory(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_inventory"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_account_id",
            name="uq_account_inventory_platform_external_account",
        ),
    )

    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(120), nullable=False)
    inventory_status: Mapped[str] = mapped_column(String(40), nullable=False)
    production_batch_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    produced_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    assigned_customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AccountAssignment(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_assignments"

    account_inventory_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_inventory.id"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    assignment_status: Mapped[str] = mapped_column(String(40), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)


class AccountStatusEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_status_events"

    account_inventory_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_inventory.id"),
        nullable=True,
    )
    account_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    before_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    risk_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class AccountAsset(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_assets"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_account_id",
            name="uq_account_assets_platform_external_account",
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    account_inventory_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_inventory.id"),
        nullable=True,
    )
    external_account_id: Mapped[str] = mapped_column(String(120), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    balance_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance_currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    spend_today: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    spend_yesterday: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )
    spend_7d: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    risk_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
