from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    desc,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.naming import conv
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stage08ExecutionTicket(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage08_execution_tickets"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "trace_id",
            name="uq_stage08_execution_ticket_workspace_trace",
        ),
        CheckConstraint(
            "status IN ('planned', 'executing', 'succeeded', 'failed', "
            "'denied', 'cancelled', 'timed_out', 'expired')",
            name=conv("ck_stage08_execution_ticket_status"),
        ),
        CheckConstraint(
            "jsonb_typeof(budget) = 'object'",
            name=conv("ck_stage08_execution_ticket_budget_object"),
        ),
        CheckConstraint(
            "jsonb_typeof(tool_summary) = 'array'",
            name=conv("ck_stage08_execution_ticket_tool_summary_array"),
        ),
        Index(
            "ix_stage08_execution_ticket_workspace_status_created",
            "workspace_id",
            "status",
            desc("created_at"),
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("digital_employees.id"),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    budget: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tool_summary: Mapped[list] = mapped_column(JSONB, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
