from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
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
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
