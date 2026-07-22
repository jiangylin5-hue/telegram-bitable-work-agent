from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.naming import conv
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stage08KnowledgeSource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage08_knowledge_sources"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_type",
            "logical_source_fingerprint",
            "content_version",
            name=(
                "uq_stage08_knowledge_source_workspace_type_"
                "fingerprint_version"
            ),
        ),
        UniqueConstraint(
            "id",
            "workspace_id",
            "content_version",
            name="uq_stage08_knowledge_source_id_workspace_version",
        ),
        CheckConstraint(
            "source_type IN "
            "('memory_item', 'document_projection', 'approved_summary')",
            name=conv("ck_stage08_knowledge_source_type"),
        ),
        CheckConstraint(
            "status IN "
            "('pending', 'active', 'replaced', 'revoked', 'expired', 'deleted')",
            name=conv("ck_stage08_knowledge_source_status"),
        ),
        CheckConstraint(
            "jsonb_typeof(source_ref) = 'object'",
            name=conv("ck_stage08_knowledge_source_ref_object"),
        ),
        CheckConstraint(
            "jsonb_typeof(scope) = 'object'",
            name=conv("ck_stage08_knowledge_source_scope_object"),
        ),
        CheckConstraint(
            "logical_source_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_stage08_knowledge_source_fingerprint_sha256"),
        ),
        CheckConstraint(
            "projection_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_stage08_knowledge_source_projection_hash_sha256"),
        ),
        CheckConstraint(
            "content_version > 0",
            name=conv("ck_stage08_knowledge_source_version_positive"),
        ),
        CheckConstraint(
            "status <> 'active' OR "
            "(projection_text IS NOT NULL "
            "AND char_length(btrim(projection_text)) > 0)",
            name=conv("ck_stage08_knowledge_source_active_projection"),
        ),
        Index(
            "ix_stage08_knowledge_source_workspace_status_valid_until",
            "workspace_id",
            "status",
            "valid_until",
        ),
        Index(
            "ix_stage08_knowledge_source_workspace_fingerprint_version",
            "workspace_id",
            "logical_source_fingerprint",
            "content_version",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ref: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    logical_source_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    projection_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage08_knowledge_sources.id"),
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


class Stage08KnowledgeChunk(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage08_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "source_version",
            "ordinal",
            name="uq_stage08_knowledge_chunk_source_version_ordinal",
        ),
        ForeignKeyConstraint(
            ["source_id", "workspace_id", "source_version"],
            [
                "stage08_knowledge_sources.id",
                "stage08_knowledge_sources.workspace_id",
                "stage08_knowledge_sources.content_version",
            ],
            name="fk_stage08_knowledge_chunk_source_scope_version",
        ),
        CheckConstraint(
            "status IN ('pending', 'indexed', 'stale', 'deleted', 'failed')",
            name=conv("ck_stage08_knowledge_chunk_status"),
        ),
        CheckConstraint(
            "source_version > 0",
            name=conv("ck_stage08_knowledge_chunk_source_version_positive"),
        ),
        CheckConstraint(
            "ordinal >= 0",
            name=conv("ck_stage08_knowledge_chunk_ordinal_nonnegative"),
        ),
        CheckConstraint(
            "chunk_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_stage08_knowledge_chunk_hash_sha256"),
        ),
        CheckConstraint(
            "status <> 'indexed' OR "
            "(chunk_text IS NOT NULL AND char_length(btrim(chunk_text)) > 0)",
            name=conv("ck_stage08_knowledge_chunk_indexed_text"),
        ),
        Index(
            "ix_stage08_knowledge_chunk_workspace_status_source_version",
            "workspace_id",
            "status",
            "source_version",
        ),
        Index(
            "ix_stage08_knowledge_chunk_source_status",
            "source_id",
            "status",
        ),
        Index(
            "ix_stage08_knowledge_chunk_keyword_terms_gin",
            "keyword_terms",
            postgresql_using="gin",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    keyword_terms: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
    )
    embedding_profile: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
    embedding_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
