from datetime import datetime, timezone

import pytest

from app.services.telegram_update_parser import (
    TelegramUpdateParseError,
    parse_telegram_update,
)


def test_parse_text_message_update_extracts_safe_normalized_fields() -> None:
    parsed = parse_telegram_update(
        {
            "update_id": 123456789,
            "message": {
                "message_id": 77,
                "date": 1783276800,
                "chat": {
                    "id": -1001234567890,
                    "type": "group",
                    "title": "Customer Group",
                },
                "from": {
                    "id": 998877,
                    "is_bot": False,
                    "first_name": "Alice",
                    "username": "alice",
                },
                "text": "  recharge   account  ",
                "ignored_extra_field": "ignored",
            },
            "another_extra_field": {"ignored": True},
        }
    )

    assert parsed.update_id == "123456789"
    assert parsed.message_id == "77"
    assert parsed.chat_id == "-1001234567890"
    assert parsed.sender_user_id == "998877"
    assert parsed.username == "alice"
    assert parsed.message_type == "text"
    assert parsed.text == "  recharge   account  "
    assert parsed.caption is None
    assert parsed.received_at == datetime.fromtimestamp(1783276800, timezone.utc)
    assert parsed.text_preview == "recharge account"


def test_parse_photo_message_registers_metadata_without_downloading_file() -> None:
    parsed = parse_telegram_update(
        {
            "update_id": 200,
            "message": {
                "message_id": 88,
                "date": 1783276810,
                "chat": {"id": "chat-1", "type": "group"},
                "from": {"id": "user-1", "is_bot": False},
                "caption": " card image received ",
                "photo": [
                    {"file_id": "small", "width": 90, "height": 90},
                    {"file_id": "large", "width": 1280, "height": 720},
                ],
            },
        }
    )

    assert parsed.message_type == "photo"
    assert parsed.caption == " card image received "
    assert parsed.text_preview == "card image received"
    assert parsed.file_metadata == {
        "file_id": "large",
        "width": "1280",
        "height": "720",
    }


def test_parse_document_message_registers_document_metadata() -> None:
    parsed = parse_telegram_update(
        {
            "update_id": 201,
            "message": {
                "message_id": 89,
                "date": 1783276820,
                "chat": {"id": "chat-2", "type": "group"},
                "from": {"id": "user-2", "is_bot": False},
                "document": {
                    "file_id": "doc-file",
                    "file_name": "report.pdf",
                    "mime_type": "application/pdf",
                },
            },
        }
    )

    assert parsed.message_type == "document"
    assert parsed.file_metadata == {
        "file_id": "doc-file",
        "file_name": "report.pdf",
        "mime_type": "application/pdf",
    }


def test_parse_malformed_update_raises_stable_error_without_raw_payload() -> None:
    with pytest.raises(TelegramUpdateParseError) as exc_info:
        parse_telegram_update(
            {
                "update_id": 202,
                "secret_like": "do-not-echo",
                "message": {"message_id": 90},
            }
        )

    message = str(exc_info.value)
    assert "telegram_update_invalid" in message
    assert "do-not-echo" not in message
    assert "secret_like" not in message


def test_safe_view_fields_do_not_expose_raw_update_or_secret_values() -> None:
    parsed = parse_telegram_update(
        {
            "update_id": 203,
            "message": {
                "message_id": 91,
                "date": 1783276830,
                "chat": {"id": "chat-3", "type": "group"},
                "from": {"id": "user-3", "is_bot": False},
                "text": "x" * 220,
                "secret_like": "do-not-expose",
            },
        }
    )

    fields = parsed.to_safe_view_fields()

    assert "raw_update" not in fields
    assert "secret_like" not in fields
    assert "do-not-expose" not in str(fields)
    assert fields["telegram_update_id"] == "203"
    assert fields["telegram_chat_id"] == "chat-3"
    assert fields["telegram_user_id"] == "user-3"
    assert len(fields["text_preview"]) == 160
