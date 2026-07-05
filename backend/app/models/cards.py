from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class PaymentProfile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_profiles"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "tokenized_profile_id",
            name="uq_payment_profiles_provider_tokenized_profile",
        ),
    )

    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    tokenized_profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    masked_label: Mapped[str] = mapped_column(String(160), nullable=False)
    last4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    limit_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AccountCardBinding(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_card_bindings"

    account_asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("account_assets.id"),
        nullable=False,
    )
    payment_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payment_profiles.id"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    binding_status: Mapped[str] = mapped_column(String(40), nullable=False)
    one_card_one_account_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    service_record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("service_records.id"),
        nullable=True,
    )
    execution_log_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("execution_logs.id"),
        nullable=True,
    )
    bound_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    unbound_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
