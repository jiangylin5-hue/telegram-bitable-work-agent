from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class DraftCandidate:
    draft_type: str
    status: str
    intent_type: str
    payload: dict[str, str]
    missing_fields: list[str]
    confidence: Decimal
    customer_id: str | None = None
    amount: str | None = None
    currency: str | None = None
    account_hint: str | None = None


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class StructuredLLMRequest:
    messages: list[LLMMessage]
    response_schema: dict[str, object]
    prompt_version: str
    model_name: str | None = None


@dataclass(frozen=True)
class StructuredLLMResult:
    content: dict[str, object]
    model_provider: str
    model_name: str
    prompt_version: str
    request_id: str | None = None
    usage: dict[str, object] | None = None
    raw_text: str | None = None


class StructuredLLMClient(Protocol):
    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        pass
