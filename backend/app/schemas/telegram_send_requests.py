from uuid import UUID

from pydantic import BaseModel, Field


class TelegramSendRequestCreate(BaseModel):
    target_chat_id: str = Field(min_length=1, max_length=80)
    message_text: str = Field(min_length=1, max_length=1000)


class TelegramSendRequestConfirm(BaseModel):
    confirm: bool


class TelegramSendRequestMutationResponse(BaseModel):
    status: str
    request_id: UUID
    trace_id: str | None = None
    queued: bool | None = None
    error_code: str | None = None
