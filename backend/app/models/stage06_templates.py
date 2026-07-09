from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class PlatformTemplate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "templates"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="published")


class TemplateInstallation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "template_installations"

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
    template_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("templates.id"),
        nullable=False,
    )
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_map: Mapped[dict] = mapped_column(JSONB, nullable=False)
    installed_by_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ImportJob(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

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
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_ref: Mapped[dict] = mapped_column(JSONB, nullable=False)
    detected_schema: Mapped[list] = mapped_column(JSONB, nullable=False)
    preview_rows: Mapped[list] = mapped_column(JSONB, nullable=False)
    mapping: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
