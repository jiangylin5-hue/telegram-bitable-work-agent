from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


IntentType = Literal[
    "recharge",
    "card_binding",
    "bm_invite",
    "customer_reply",
    "account_assignment",
    "account_status_exception",
    "spend_query",
    "spend_table",
    "report_request",
    "irrelevant",
    "unknown",
]


class RouterIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_type: IntentType
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    entities: dict[str, object] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    intent_index: int | None = Field(default=None, ge=0)


class RouterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intents: list[RouterIntent] = Field(min_length=1)
    overall_confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    requires_manual_review: bool
    manual_review_reasons: list[str] = Field(default_factory=list)
    redacted_summary: str = Field(min_length=1, max_length=1200)


class AccountStatusAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_hint: str = Field(min_length=1, max_length=120)
    target_status: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    risk_flags: list[str] = Field(default_factory=list)


DraftStatus = Literal[
    "pending_confirmation",
    "needs_more_info",
    "manual_review",
]


class DraftAgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_message_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    source_text_summary: str = Field(min_length=1, max_length=1200)
    source_agent_run_id: str | None = None


class Stage05DraftCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_type: str = Field(min_length=1, max_length=60)
    status: DraftStatus
    intent_type: IntentType
    intent_index: int = Field(ge=0)
    payload: dict[str, object] = Field(default_factory=dict)
    payload_summary: dict[str, object] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    source_message_id: str = Field(min_length=1)
    source_agent_run_id: str | None = None
    customer_id: str | None = None
    created_by_type: str = "agent"
    created_by_id: str = Field(min_length=1, max_length=120)
    agent_name: str = Field(min_length=1, max_length=120)
    trace_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=180)
    review_reason: str | None = Field(default=None, max_length=500)


__all__ = [
    "AccountStatusAction",
    "DraftAgentContext",
    "DraftStatus",
    "IntentType",
    "RouterIntent",
    "RouterResult",
    "Stage05DraftCandidate",
]
