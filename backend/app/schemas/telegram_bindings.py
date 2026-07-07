from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TelegramBindingCreate(BaseModel):
    customer_id: UUID
    binding_scope: str = Field(pattern="^(chat|user|chat_user)$")
    telegram_chat_id: str | None = None
    telegram_user_id: str | None = None
    label: str | None = None
    created_by: str | None = None

    @model_validator(mode="after")
    def validate_scope_identifiers(self) -> "TelegramBindingCreate":
        if self.binding_scope in {"chat", "chat_user"} and not self.telegram_chat_id:
            raise ValueError("telegram_chat_id is required for chat scoped bindings")
        if self.binding_scope in {"user", "chat_user"} and not self.telegram_user_id:
            raise ValueError("telegram_user_id is required for user scoped bindings")
        return self


class TelegramBindingDisableRequest(BaseModel):
    disabled_by: str | None = None
    reason: str | None = None


class TelegramBindingRecord(BaseModel):
    binding_id: UUID
    customer_id: UUID
    telegram_chat_id: str | None
    telegram_user_id: str | None
    binding_scope: str
    status: str
    label: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class TelegramBindingListResponse(BaseModel):
    bindings: list[TelegramBindingRecord]


class TelegramBindingMutationResponse(BaseModel):
    status: str
    binding_id: UUID
    customer_id: UUID | None = None
    binding_scope: str | None = None
