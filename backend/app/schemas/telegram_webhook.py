from pydantic import BaseModel, ConfigDict, Field


class TelegramWebhookUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str
    is_bot: bool | None = None
    first_name: str | None = None
    username: str | None = None


class TelegramWebhookChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str
    type: str
    title: str | None = None
    username: str | None = None


class TelegramWebhookPhotoSize(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_id: str
    width: int | None = None
    height: int | None = None


class TelegramWebhookDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_id: str
    file_name: str | None = None
    mime_type: str | None = None


class TelegramWebhookMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: int | str
    date: int
    chat: TelegramWebhookChat
    from_user: TelegramWebhookUser | None = Field(default=None, alias="from")
    text: str | None = None
    caption: str | None = None
    photo: list[TelegramWebhookPhotoSize] | None = None
    document: TelegramWebhookDocument | None = None


class TelegramWebhookUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int | str
    message: TelegramWebhookMessage
