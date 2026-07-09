from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stage06IdempotencyRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage06_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "operation",
            "idempotency_key",
            name="uq_stage06_idempotency_scope_key",
        ),
        UniqueConstraint("trace_id", name="uq_stage06_idempotency_trace_id"),
        CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_stage06_idempotency_status",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    response_ref: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
