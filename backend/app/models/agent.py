from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, UuidPrimaryKeyMixin


class AgentRun(UuidPrimaryKeyMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_message_id_started_at", "message_id", "started_at"),
        Index("ix_agent_runs_status_started_at", "status", "started_at"),
    )

    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    graph_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tool_calls: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=True,
    )
    usage_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message_redacted: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    created_entity_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    redaction_policy: Mapped[str | None] = mapped_column(String(80), nullable=True)
