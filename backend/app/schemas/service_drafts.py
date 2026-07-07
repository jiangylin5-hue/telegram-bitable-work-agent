from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ConfirmationActionRequest(BaseModel):
    action: str
    actor_type: str
    actor_id: str
    role: str
    reason: str | None = None
    missing_fields: list[str] = Field(default_factory=list)


class ConfirmationActionResponse(BaseModel):
    draft_id: str
    draft_status: str
    service_record_id: str | None = None
    execution_ticket_id: str | None = None
    telegram_send_request_id: str | None = None
    side_effect: str | None = None


class ServiceDraftRecord(BaseModel):
    id: str
    draft_type: str
    status: str
    customer_id: str | None
    source_message_id: str | None
    created_by_type: str
    created_by_id: str
    trace_id: str
    payload: dict[str, object]
    missing_fields: list[str]
    risk_flags: list[str]
    confidence: Decimal | None
    created_at: datetime | None


class ServiceDraftListResponse(BaseModel):
    records: list[ServiceDraftRecord]
