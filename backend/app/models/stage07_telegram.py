from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
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


class Stage07TelegramDeepLinkDelivery(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage07_telegram_deep_link_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "send_request_id",
            name="uq_stage07_telegram_deep_link_deliveries_send_request_id",
        ),
        CheckConstraint(
            "destination_kind IN ('base', 'view', 'record', 'record_change_draft')",
            name="destination_kind",
        ),
        CheckConstraint(
            "dispatch_state IN ("
            "'pending_confirmation', 'dispatch_reserved', 'sent', 'failed', "
            "'delivery_unknown', 'blocked', 'cancelled'"
            ")",
            name="dispatch_state",
        ),
        CheckConstraint(
            "message_template = 'stage07_open_secure_destination'",
            name="message_template",
        ),
    )

    send_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("telegram_send_requests.id"),
        nullable=False,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    source_binding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage06_telegram_bindings.id"),
        nullable=False,
    )
    subject_telegram_user_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    target_chat_id: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    destination_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    message_template: Mapped[str] = mapped_column(String(80), nullable=False)
    dispatch_state: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending_confirmation",
    )
    stage07_telegram_deep_link_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage07_telegram_deep_links.id"),
        nullable=True,
    )
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MiniAppBrowserHandoff(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mini_app_browser_handoffs"
    __table_args__ = (
        UniqueConstraint(
            "ticket_hash",
            name="uq_mini_app_browser_handoffs_ticket_hash",
        ),
    )

    ticket_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    telegram_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MiniAppBrowserSession(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mini_app_browser_sessions"
    __table_args__ = (
        UniqueConstraint(
            "token_hash",
            name="uq_mini_app_browser_sessions_token_hash",
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    telegram_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
