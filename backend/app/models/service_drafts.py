from decimal import Decimal
from uuid import UUID

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class ServiceDraft(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_drafts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_service_drafts_idempotency_key"),
    )

    draft_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    account_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    account_inventory_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=True,
    )
    source_agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )
    created_by_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    missing_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risk_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    intent_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
