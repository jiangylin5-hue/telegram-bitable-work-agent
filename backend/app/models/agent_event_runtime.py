from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


_HASH_CONSTRAINT = "~ '^[0-9a-f]{64}$'"


class AgentWorkflowRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('accepted','queued','running','waiting_approval',"
            "'completed','degraded','failed','cancelled','timed_out')",
            name="agent_workflow_run_status",
        ),
        CheckConstraint(
            f"scope_hash {_HASH_CONSTRAINT}",
            name="agent_workflow_run_scope_hash",
        ),
        Index("ix_agent_workflow_run_workspace_status", "workspace_id", "status"),
        Index("ix_agent_workflow_run_lease", "lease_expires_at", "status"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    root_employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("digital_employees.id"), nullable=False
    )
    target_record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("records.id"), nullable=True
    )
    parent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_workflow_runs.id"), nullable=True
    )
    workflow_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    safe_result_ref: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AgentRunCheckpoint(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_run_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "checkpoint_no", name="uq_agent_run_checkpoint_run_no"
        ),
        CheckConstraint("checkpoint_no > 0", name="agent_run_checkpoint_no_positive"),
        CheckConstraint(
            f"authorization_hash {_HASH_CONSTRAINT}",
            name="agent_run_checkpoint_authorization_hash",
        ),
        Index("ix_agent_run_checkpoint_run_created", "run_id", "created_at"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_workflow_runs.id"), nullable=False
    )
    checkpoint_no: Mapped[int] = mapped_column(Integer, nullable=False)
    node_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    control_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    authorization_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AgentCommand(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_commands"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_command_run_sequence"),
        Index("ix_agent_command_run_status", "run_id", "status"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_workflow_runs.id"), nullable=False
    )
    parent_command_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_commands.id"), nullable=True
    )
    target_capability: Mapped[str] = mapped_column(String(120), nullable=False)
    command_type: Mapped[str] = mapped_column(String(80), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class AgentArtifact(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_artifacts"
    __table_args__ = (
        CheckConstraint(
            f"content_hash {_HASH_CONSTRAINT}", name="agent_artifact_content_hash"
        ),
        CheckConstraint(
            f"visibility_scope_hash {_HASH_CONSTRAINT}",
            name="agent_artifact_visibility_hash",
        ),
        Index("ix_agent_artifact_run_kind", "run_id", "kind"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_workflow_runs.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_event_run_sequence"),
        Index("ix_agent_event_run_created", "run_id", "created_at"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_workflow_runs.id"), nullable=False
    )
    command_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_commands.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    causation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_role: Mapped[str] = mapped_column(String(24), nullable=False)
    source_capability: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_summary: Mapped[str | None] = mapped_column(String(240), nullable=True)
    artifact_ref: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_artifacts.id"), nullable=True
    )
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class AgentOutboxEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_outbox_events"
    __table_args__ = (
        Index("ix_agent_outbox_unpublished", "published_at", "next_attempt_at"),
    )

    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True
    )
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)


class AgentPrivateInput(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_private_inputs"
    __table_args__ = (
        UniqueConstraint("command_id", name="uq_agent_private_input_command"),
        CheckConstraint(
            f"scope_hash {_HASH_CONSTRAINT}", name="agent_private_input_scope_hash"
        ),
        CheckConstraint(
            f"aad_hash {_HASH_CONSTRAINT}", name="agent_private_input_aad_hash"
        ),
        Index("ix_agent_private_input_expiry", "expires_at", "consumed_at"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_workflow_runs.id"), nullable=False
    )
    command_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_commands.id"), nullable=False
    )
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[str] = mapped_column(String(80), nullable=False)
    aad_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "AgentArtifact",
    "AgentCommand",
    "AgentEvent",
    "AgentOutboxEvent",
    "AgentPrivateInput",
    "AgentRunCheckpoint",
    "AgentWorkflowRun",
]
