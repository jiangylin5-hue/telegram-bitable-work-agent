from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stage07TelegramDeepLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage07_telegram_deep_links"
    __table_args__ = (
        UniqueConstraint(
            "token_hash",
            name="uq_stage07_telegram_deep_links_token_hash",
        ),
        CheckConstraint(
            "destination_kind IN ('base', 'view', 'record', 'record_change_draft')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="status",
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    subject_telegram_user_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    source_telegram_chat_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    destination_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    destination_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(120), nullable=False)
