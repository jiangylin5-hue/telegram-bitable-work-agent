from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class TelegramIdentity(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_identities"
    __table_args__ = (
        UniqueConstraint(
            "telegram_user_id",
            name="uq_telegram_identities_telegram_user",
        ),
    )

    telegram_user_id: Mapped[str] = mapped_column(String(80), nullable=False)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    contact_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="unknown",
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class TelegramCustomerBinding(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_customer_bindings"
    __table_args__ = (
        Index(
            "uq_telegram_customer_bindings_active_chat",
            "binding_scope",
            "telegram_chat_id",
            unique=True,
            postgresql_where=text(
                "status = 'active' AND binding_scope = 'chat'"
            ),
        ),
        Index(
            "uq_telegram_customer_bindings_active_user",
            "binding_scope",
            "telegram_user_id",
            unique=True,
            postgresql_where=text(
                "status = 'active' AND binding_scope = 'user'"
            ),
        ),
        Index(
            "uq_telegram_customer_bindings_active_chat_user",
            "binding_scope",
            "telegram_chat_id",
            "telegram_user_id",
            unique=True,
            postgresql_where=text(
                "status = 'active' AND binding_scope = 'chat_user'"
            ),
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    binding_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)


class TelegramSendRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_send_requests"
    __table_args__ = (
        Index("ix_telegram_send_requests_trace_id", "trace_id"),
        Index("ix_telegram_send_requests_status_created_at", "status", "created_at"),
        Index(
            "ix_telegram_send_requests_target_chat_created_at",
            "target_chat_id",
            "created_at",
        ),
    )

    target_chat_id: Mapped[str] = mapped_column(String(80), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending_confirmation",
    )
    requested_by_actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by_actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    confirmed_by_actor_type: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )
    confirmed_by_actor_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    allowlist_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    telegram_response_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)


class Message(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("telegram_update_id", name="uq_messages_telegram_update"),
        UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_messages_chat_message",
        ),
    )

    telegram_update_id: Mapped[str] = mapped_column(String(80), nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String(80), nullable=False)
    telegram_message_id: Mapped[str] = mapped_column(String(80), nullable=False)
    telegram_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sender_identity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("telegram_identities.id"),
        nullable=True,
    )
    customer_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customer_groups.id"),
        nullable=True,
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(String(40), nullable=False)
    intent_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="unclassified",
    )
    intent_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ingestion_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="stored",
    )
    binding_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="needs_manual_binding",
    )
    processing_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="queued",
    )
    outbox_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
    )
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
