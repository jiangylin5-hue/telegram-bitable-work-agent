from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.naming import conv
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stage08MemoryItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage08_memory_items"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "memory_type",
            "source_fingerprint",
            name="uq_stage08_memory_item_workspace_type_fingerprint",
        ),
        CheckConstraint(
            "status IN ('active', 'conflicted', 'superseded', 'revoked', "
            "'expired', 'deleted')",
            name=conv("ck_stage08_memory_item_status"),
        ),
        CheckConstraint(
            "jsonb_typeof(scope) = 'object'",
            name=conv("ck_stage08_memory_item_scope_object"),
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name=conv("ck_stage08_memory_item_payload_object"),
        ),
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name=conv("ck_stage08_memory_item_source_refs_array"),
        ),
        CheckConstraint(
            "version > 0",
            name=conv("ck_stage08_memory_item_version_positive"),
        ),
        Index(
            "ix_stage08_memory_item_workspace_status_valid_until",
            "workspace_id",
            "status",
            "valid_until",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    memory_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage08_memory_items.id"),
        nullable=True,
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Stage08MemoryExtractionCandidate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage08_memory_extraction_candidates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "candidate_type",
            "source_fingerprint",
            name="uq_stage08_memory_candidate_workspace_type_fingerprint",
        ),
        CheckConstraint(
            "status IN ('candidate', 'accepted', 'rejected', 'expired')",
            name=conv("ck_stage08_memory_candidate_status"),
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=conv("ck_stage08_memory_candidate_confidence_range"),
        ),
        CheckConstraint(
            "jsonb_typeof(scope) = 'object'",
            name=conv("ck_stage08_memory_candidate_scope_object"),
        ),
        CheckConstraint(
            "jsonb_typeof(normalized_payload) = 'object'",
            name=conv("ck_stage08_memory_candidate_payload_object"),
        ),
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name=conv("ck_stage08_memory_candidate_source_refs_array"),
        ),
        CheckConstraint(
            "version > 0",
            name=conv("ck_stage08_memory_candidate_version_positive"),
        ),
        Index(
            "ix_stage08_memory_candidate_workspace_status_valid_until",
            "workspace_id",
            "status",
            "valid_until",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    candidate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
