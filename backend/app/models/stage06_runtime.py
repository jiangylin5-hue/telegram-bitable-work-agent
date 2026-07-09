from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class DigitalEmployee(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digital_employees"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    base_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bases.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    telegram_alias: Mapped[str | None] = mapped_column(String(80), nullable=True)
    accessible_tables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    accessible_views: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    field_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    allowed_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confirmation_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_style: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class RecordChangeDraft(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "record_change_drafts"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    base_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bases.id"),
        nullable=False,
    )
    table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=True,
    )
    draft_type: Mapped[str] = mapped_column(String(60), nullable=False)
    proposed_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    before_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    confirmation_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    expected_version: Mapped[int] = mapped_column(default=1, nullable=False)


class NotificationRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_requests"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    base_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bases.id"),
        nullable=True,
    )
    source_record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    target: Mapped[dict] = mapped_column(JSONB, nullable=False)
    message_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    send_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
