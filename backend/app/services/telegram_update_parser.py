from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import ValidationError

from app.schemas.telegram_webhook import (
    TelegramWebhookDocument,
    TelegramWebhookPhotoSize,
    TelegramWebhookUpdate,
)


TEXT_PREVIEW_LIMIT = 160


class TelegramUpdateParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedTelegramUpdate:
    update_id: str
    message_id: str
    chat_id: str
    sender_user_id: str | None
    username: str | None
    message_type: str
    received_at: datetime
    text: str | None = None
    caption: str | None = None
    text_preview: str | None = None
    file_metadata: dict[str, str] | None = None

    def to_safe_view_fields(self) -> dict[str, str | None]:
        return {
            "telegram_update_id": self.update_id,
            "telegram_chat_id": self.chat_id,
            "telegram_user_id": self.sender_user_id,
            "telegram_message_id": self.message_id,
            "message_type": self.message_type,
            "text_preview": self.text_preview,
        }


def parse_telegram_update(payload: Mapping[str, Any]) -> ParsedTelegramUpdate:
    try:
        update = TelegramWebhookUpdate.model_validate(payload)
    except ValidationError as exc:
        raise TelegramUpdateParseError("telegram_update_invalid") from exc

    message = update.message
    message_type = _message_type(message)
    file_metadata = _file_metadata(message_type, message.photo, message.document)
    preview_source = message.text if message.text is not None else message.caption
    from_user = message.from_user

    return ParsedTelegramUpdate(
        update_id=str(update.update_id),
        message_id=str(message.message_id),
        chat_id=str(message.chat.id),
        sender_user_id=None if from_user is None else str(from_user.id),
        username=None if from_user is None else from_user.username,
        message_type=message_type,
        received_at=datetime.fromtimestamp(message.date, timezone.utc),
        text=message.text,
        caption=message.caption,
        text_preview=_text_preview(preview_source),
        file_metadata=file_metadata,
    )


def _message_type(message: Any) -> str:
    if message.text is not None:
        return "text"
    if message.photo:
        return "photo"
    if message.document is not None:
        return "document"
    return "other"


def _file_metadata(
    message_type: str,
    photo: list[TelegramWebhookPhotoSize] | None,
    document: TelegramWebhookDocument | None,
) -> dict[str, str] | None:
    if message_type == "photo" and photo:
        largest = photo[-1]
        return _drop_none_values(
            {
                "file_id": largest.file_id,
                "width": None if largest.width is None else str(largest.width),
                "height": None if largest.height is None else str(largest.height),
            }
        )
    if message_type == "document" and document is not None:
        return _drop_none_values(
            {
                "file_id": document.file_id,
                "file_name": document.file_name,
                "mime_type": document.mime_type,
            }
        )
    return None


def _text_preview(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.strip().split())[:TEXT_PREVIEW_LIMIT]


def _drop_none_values(values: dict[str, str | None]) -> dict[str, str]:
    return {key: value for key, value in values.items() if value is not None}
