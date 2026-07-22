from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.naming import conv
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stage08GroupBusinessContextBinding(
    UuidPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "stage08_group_business_context_bindings"
    __table_args__ = (
        UniqueConstraint(
            "telegram_binding_id",
            "mapping_version",
            name="uq_stage08_group_context_binding_version",
        ),
        CheckConstraint(
            "mapping_version >= 1",
            name=conv("ck_stage08_group_context_mapping_version_positive"),
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name=conv("ck_stage08_group_context_mapping_status"),
        ),
        CheckConstraint(
            "customer_record_id <> project_record_id",
            name=conv("ck_stage08_group_context_distinct_business_records"),
        ),
        Index(
            "uq_stage08_group_context_active_telegram_binding",
            "telegram_binding_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_stage08_group_context_workspace_status",
            "workspace_id",
            "status",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    telegram_binding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage06_telegram_bindings.id"),
        nullable=False,
    )
    customer_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=False,
    )
    project_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=False,
    )
    mapping_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class Stage08GroupMessageProjection(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage08_group_message_projections"
    __table_args__ = (
        UniqueConstraint(
            "source_message_id",
            "content_version",
            name="uq_stage08_group_projection_source_version",
        ),
        CheckConstraint(
            "content_version >= 1",
            name=conv("ck_stage08_group_projection_content_version_positive"),
        ),
        CheckConstraint(
            "char_length(content_fragment) <= 500",
            name=conv("ck_stage08_group_projection_fragment_length"),
        ),
        CheckConstraint(
            "lifecycle_status IN ('active', 'superseded', 'purged')",
            name=conv("ck_stage08_group_projection_lifecycle_status"),
        ),
        CheckConstraint(
            "source_chat_type IN ('group', 'supergroup', 'unknown')",
            name=conv("ck_stage08_group_projection_source_chat_type"),
        ),
        CheckConstraint(
            "retention_expires_at > event_at",
            name=conv("ck_stage08_group_projection_retention_after_event"),
        ),
        CheckConstraint(
            "(lifecycle_status = 'purged' AND content_fragment = '') OR "
            "(lifecycle_status IN ('active', 'superseded') "
            "AND char_length(content_fragment) >= 1)",
            name=conv("ck_stage08_group_projection_fragment_lifecycle"),
        ),
        Index(
            "ix_stage08_group_projection_mapping_lifecycle_event",
            "business_context_binding_id",
            "source_chat_type",
            "lifecycle_status",
            "event_at",
            "id",
        ),
        Index(
            "ix_stage08_group_projection_retention_lifecycle",
            "retention_expires_at",
            "lifecycle_status",
        ),
    )

    source_message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=False,
    )
    business_context_binding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage08_group_business_context_bindings.id"),
        nullable=False,
    )
    content_fragment: Mapped[str] = mapped_column(Text, nullable=False)
    content_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_chat_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
    )
