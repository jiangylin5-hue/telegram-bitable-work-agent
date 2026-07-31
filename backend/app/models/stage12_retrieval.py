"""Stage12-D fixed-profile retrieval persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


_SHA256 = "~ '^[0-9a-f]{64}$'"


class Stage12RetrievalProfile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage12_retrieval_profiles"
    __table_args__ = (
        UniqueConstraint("profile_name", name="uq_s12_profile_name"),
        CheckConstraint(
            "dimension = 1024",
            name=conv("ck_s12_profile_dimension"),
        ),
        CheckConstraint(
            "normalization = 'l2'",
            name=conv("ck_s12_profile_normalization"),
        ),
        CheckConstraint(
            "distance_metric = 'cosine'",
            name=conv("ck_s12_profile_distance"),
        ),
        CheckConstraint(
            "max_input_tokens > 0 AND batch_size > 0",
            name=conv("ck_s12_profile_limits"),
        ),
        CheckConstraint(
            "provider_location IN ('local', 'remote')",
            name=conv("ck_s12_profile_location"),
        ),
        CheckConstraint(
            "status IN ('candidate', 'active', 'retired')",
            name=conv("ck_s12_profile_status"),
        ),
        CheckConstraint(
            f"profile_hash {_SHA256}",
            name=conv("ck_s12_profile_hash"),
        ),
        CheckConstraint(
            "(status = 'active' AND activated_at IS NOT NULL "
            "AND retired_at IS NULL) OR "
            "(status = 'candidate' AND activated_at IS NULL "
            "AND retired_at IS NULL) OR "
            "(status = 'retired' AND retired_at IS NOT NULL)",
            name=conv("ck_s12_profile_lifecycle"),
        ),
        Index(
            "uq_stage12_retrieval_profile_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    profile_name: Mapped[str] = mapped_column(String(96), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(200), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    normalization: Mapped[str] = mapped_column(String(16), nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(16), nullable=False)
    max_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_location: Mapped[str] = mapped_column(String(16), nullable=False)
    data_residency: Mapped[str] = mapped_column(String(240), nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Stage12RetrievalSource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage12_retrieval_sources"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_type",
            "source_identity",
            "source_version",
            "embedding_profile",
            "visibility_profile_hash",
            name="uq_s12_source_identity_version",
        ),
        UniqueConstraint(
            "id",
            "workspace_id",
            "source_version",
            "embedding_profile",
            name="uq_s12_source_scope_version",
        ),
        CheckConstraint(
            "source_type IN "
            "('schema_table', 'schema_field', 'record', 'record_field')",
            name=conv("ck_s12_source_type"),
        ),
        CheckConstraint(
            "source_version > 0",
            name=conv("ck_s12_source_version"),
        ),
        CheckConstraint(
            "status IN ('pending', 'indexed', 'stale', 'revoked', 'failed')",
            name=conv("ck_s12_source_status"),
        ),
        CheckConstraint(
            "((source_type IN ('record', 'record_field')) = "
            "(record_id IS NOT NULL))",
            name=conv("ck_s12_source_record_identity"),
        ),
        CheckConstraint(
            f"visibility_profile_hash {_SHA256} AND "
            f"scope_hash {_SHA256} AND content_hash {_SHA256}",
            name=conv("ck_s12_source_hashes"),
        ),
        CheckConstraint(
            "NOT is_active OR "
            "(status = 'indexed' AND activated_at IS NOT NULL "
            "AND revoked_at IS NULL)",
            name=conv("ck_s12_source_active_state"),
        ),
        CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=conv("ck_s12_source_revoked_state"),
        ),
        Index(
            "uq_stage12_retrieval_source_one_active_version",
            "workspace_id",
            "source_type",
            "source_identity",
            "visibility_profile_hash",
            unique=True,
            postgresql_where=text("is_active IS TRUE AND revoked_at IS NULL"),
        ),
        Index(
            "ix_stage12_retrieval_source_workspace_status",
            "workspace_id",
            "status",
        ),
    )

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
    field_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)),
        nullable=False,
        default=list,
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(240), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_profile: Mapped[str] = mapped_column(
        String(96),
        ForeignKey("stage12_retrieval_profiles.profile_name"),
        nullable=False,
    )
    visibility_profile_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Stage12RetrievalChunk(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage12_retrieval_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "source_version",
            "ordinal",
            name="uq_s12_chunk_source_version_ordinal",
        ),
        ForeignKeyConstraint(
            [
                "source_id",
                "workspace_id",
                "source_version",
                "embedding_profile",
            ],
            [
                "stage12_retrieval_sources.id",
                "stage12_retrieval_sources.workspace_id",
                "stage12_retrieval_sources.source_version",
                "stage12_retrieval_sources.embedding_profile",
            ],
            name="fk_s12_chunk_source_scope_version",
        ),
        CheckConstraint(
            "source_type IN "
            "('schema_table', 'schema_field', 'record', 'record_field')",
            name=conv("ck_s12_chunk_source_type"),
        ),
        CheckConstraint(
            "chunk_kind IN ('canonical', 'long_field')",
            name=conv("ck_s12_chunk_kind"),
        ),
        CheckConstraint(
            "source_version > 0 AND ordinal >= 0 "
            "AND start_token >= 0 AND end_token > start_token",
            name=conv("ck_s12_chunk_positions"),
        ),
        CheckConstraint(
            "((source_type IN ('record', 'record_field')) = "
            "(record_id IS NOT NULL))",
            name=conv("ck_s12_chunk_record_identity"),
        ),
        CheckConstraint(
            "status IN ('pending', 'indexed', 'stale', 'revoked', 'failed')",
            name=conv("ck_s12_chunk_status"),
        ),
        CheckConstraint(
            f"content_hash {_SHA256} AND "
            f"visibility_profile_hash {_SHA256} AND scope_hash {_SHA256}",
            name=conv("ck_s12_chunk_hashes"),
        ),
        CheckConstraint(
            "status <> 'indexed' OR "
            "(embedding IS NOT NULL AND revoked_at IS NULL "
            "AND char_length(btrim(chunk_text)) > 0)",
            name=conv("ck_s12_chunk_indexed_state"),
        ),
        CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=conv("ck_s12_chunk_revoked_state"),
        ),
        Index(
            "ix_stage12_retrieval_chunk_source_status",
            "source_id",
            "status",
        ),
        Index(
            "ix_stage12_retrieval_chunk_keyword_gin",
            "keyword_terms",
            postgresql_using="gin",
        ),
        Index(
            "ix_stage12_retrieval_chunk_hnsw_active_bge_m3",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text(
                "status = 'indexed' AND revoked_at IS NULL "
                "AND embedding IS NOT NULL AND "
                "embedding_profile = 'stage12.openrouter-bge-m3-v1'"
            ),
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
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
    field_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)),
        nullable=False,
        default=list,
    )
    start_token: Mapped[int] = mapped_column(Integer, nullable=False)
    end_token: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    keyword_terms: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility_profile_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_profile: Mapped[str] = mapped_column(
        String(96),
        ForeignKey("stage12_retrieval_profiles.profile_name"),
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Stage12RetrievalScopeRegistration(
    UuidPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "stage12_retrieval_scope_registrations"
    __table_args__ = (
        CheckConstraint(
            "actor_type = 'user' AND char_length(btrim(actor_id)) > 0",
            name=conv("ck_s12_registration_actor"),
        ),
        CheckConstraint(
            "employee_version > 0 AND member_version > 0",
            name=conv("ck_s12_registration_versions"),
        ),
        CheckConstraint(
            "field_policy_version = 'stage12-field-policy.v2'",
            name=conv("ck_s12_registration_policy_version"),
        ),
        CheckConstraint(
            "(allow_whole_table AND cardinality(scope_view_ids) = 0) OR "
            "(NOT allow_whole_table AND cardinality(scope_view_ids) > 0)",
            name=conv("ck_s12_registration_scope_boundary"),
        ),
        CheckConstraint(
            "cardinality(scope_view_ids) <= 128",
            name=conv("ck_s12_registration_view_budget"),
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name=conv("ck_s12_registration_status"),
        ),
        CheckConstraint(
            "(status = 'active' AND revoked_at IS NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL)",
            name=conv("ck_s12_registration_lifecycle"),
        ),
        CheckConstraint(
            "expires_at > last_seen_at",
            name=conv("ck_s12_registration_expiry"),
        ),
        CheckConstraint(
            f"schema_scope_hash {_SHA256} AND "
            f"retrieval_scope_hash {_SHA256} AND "
            f"schema_hash {_SHA256} AND "
            f"field_policy_hash {_SHA256} AND "
            f"actor_role_hash {_SHA256} AND "
            f"registration_hash {_SHA256}",
            name=conv("ck_s12_registration_hashes"),
        ),
        Index(
            "uq_s12_registration_active_identity",
            "workspace_id",
            "employee_id",
            "actor_type",
            "actor_id",
            "retrieval_scope_hash",
            unique=True,
            postgresql_where=text("status = 'active' AND revoked_at IS NULL"),
        ),
        Index(
            "ix_s12_registration_workspace_lifecycle",
            "workspace_id",
            "status",
            "expires_at",
        ),
    )

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
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("digital_employees.id"),
        nullable=False,
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_role_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    member_version: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_version: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_view_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)),
        nullable=False,
        default=list,
    )
    allow_whole_table: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schema_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    field_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    field_policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    registration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Stage12RelationEdge(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage12_relation_edges"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "relation_id",
            "source_record_id",
            "target_record_id",
            "direction",
            "source_version",
            "target_version",
            "visibility_profile_hash",
            "scope_hash",
            name="uq_s12_relation_version_visibility",
        ),
        CheckConstraint(
            "direction IN ('forward', 'reverse')",
            name=conv("ck_s12_relation_direction"),
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name=conv("ck_s12_relation_status"),
        ),
        CheckConstraint(
            "source_version > 0 AND target_version > 0",
            name=conv("ck_s12_relation_versions"),
        ),
        CheckConstraint(
            "source_record_id <> target_record_id",
            name=conv("ck_s12_relation_endpoints"),
        ),
        CheckConstraint(
            f"visibility_profile_hash {_SHA256} AND "
            f"scope_hash {_SHA256} AND edge_hash {_SHA256}",
            name=conv("ck_s12_relation_hashes"),
        ),
        CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=conv("ck_s12_relation_revoked_state"),
        ),
        Index(
            "ix_stage12_relation_source_active",
            "workspace_id",
            "source_record_id",
            "status",
        ),
        Index(
            "ix_stage12_relation_target_active",
            "workspace_id",
            "target_record_id",
            "status",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    relation_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    source_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=False,
    )
    link_field_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fields.id"),
        nullable=False,
    )
    target_table_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tables.id"),
        nullable=False,
    )
    target_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("records.id"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility_profile_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    edge_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
