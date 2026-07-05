from datetime import datetime, timezone

from pydantic import BaseModel, Field


class MockTelegramUpdate(BaseModel):
    update_id: str
    chat_id: str
    message_id: str
    sender_user_id: str
    username: str | None = None
    text: str | None = None
    caption: str | None = None
    message_type: str = "text"
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MockTelegramIngestionResponse(BaseModel):
    status: str
    message_id: str
    trace_id: str
