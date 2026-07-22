from datetime import datetime, timedelta, timezone
from inspect import getsource
from uuid import UUID, uuid4

import pytest

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
)
from app.schemas.telegram import MockTelegramUpdate
from app.services import telegram_ingestion, telegram_update_parser
from app.services.telegram_ingestion import (
    InMemoryTelegramIngestionUnitOfWork,
    IngestedMessage,
    ingest_mock_telegram_update,
)
from app.services.telegram_update_parser import (
    TelegramUpdateParseError,
    parse_telegram_update,
)


EVENT_AT = datetime(2026, 7, 19, 8, 30, tzinfo=timezone.utc)


def _update(
    *,
    update_id: str = "update-1",
    message_id: str = "message-1",
    chat_type: str = "group",
    update_kind: str = "new",
    sender_user_id: str = "user-1",
    text: str | None = "  hello   controlled context  ",
    caption: str | None = None,
    received_at: datetime = EVENT_AT,
    edited_at: datetime | None = None,
    chat_id: str = "chat-1",
) -> MockTelegramUpdate:
    return MockTelegramUpdate(
        update_id=update_id,
        chat_id=chat_id,
        message_id=message_id,
        sender_user_id=sender_user_id,
        text=text,
        caption=caption,
        message_type="text",
        received_at=received_at,
        update_kind=update_kind,
        chat_type=chat_type,
        edited_at=edited_at,
    )


def _seed_target(
    uow: InMemoryTelegramIngestionUnitOfWork,
    *,
    binding_status: str = "active",
    binding_type: str = "chat_user",
    mapping_status: str = "active",
    workspace_drift: bool = False,
    record_relation_valid: bool = True,
    duplicate_binding: bool = False,
    duplicate_mapping: bool = False,
) -> tuple[Stage06TelegramBinding, Stage08GroupBusinessContextBinding]:
    workspace_id = uuid4()
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace_id,
        workspace_member_id=uuid4(),
        telegram_chat_id="chat-1",
        telegram_user_id="user-1",
        binding_type=binding_type,
        scope_policy={},
        status=binding_status,
    )
    customer_record_id = uuid4()
    project_record_id = uuid4()
    mapping = Stage08GroupBusinessContextBinding(
        id=uuid4(),
        workspace_id=uuid4() if workspace_drift else workspace_id,
        telegram_binding_id=binding.id,
        customer_record_id=customer_record_id,
        project_record_id=project_record_id,
        mapping_version=1,
        status=mapping_status,
    )
    uow.group_context_telegram_bindings.append(binding)
    uow.group_business_context_bindings.append(mapping)
    if record_relation_valid:
        uow.group_context_record_workspaces[customer_record_id] = workspace_id
        uow.group_context_record_workspaces[project_record_id] = workspace_id
    if duplicate_binding:
        second = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace_id,
            workspace_member_id=uuid4(),
            telegram_chat_id="chat-1",
            telegram_user_id="user-1",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        second_mapping = Stage08GroupBusinessContextBinding(
            id=uuid4(),
            workspace_id=workspace_id,
            telegram_binding_id=second.id,
            customer_record_id=customer_record_id,
            project_record_id=project_record_id,
            mapping_version=1,
            status="active",
        )
        uow.group_context_telegram_bindings.append(second)
        uow.group_business_context_bindings.append(second_mapping)
    if duplicate_mapping:
        uow.group_business_context_bindings.append(
            Stage08GroupBusinessContextBinding(
                id=uuid4(),
                workspace_id=workspace_id,
                telegram_binding_id=binding.id,
                customer_record_id=customer_record_id,
                project_record_id=project_record_id,
                mapping_version=2,
                status="active",
            )
        )
    return binding, mapping


def test_parser_distinguishes_new_and_edited_and_requires_exactly_one_message() -> None:
    base_message = {
        "message_id": 77,
        "date": 1784451600,
        "chat": {"id": "chat-1", "type": "supergroup"},
        "from": {"id": "user-1", "is_bot": False},
        "text": "hello",
    }

    new = parse_telegram_update({"update_id": 1, "message": base_message})
    edited = parse_telegram_update(
        {
            "update_id": 2,
            "edited_message": {**base_message, "edit_date": 1784451700},
        }
    )

    assert (new.update_kind, new.chat_type, new.edited_at) == (
        "new",
        "supergroup",
        None,
    )
    assert edited.update_kind == "edited"
    assert edited.chat_type == "supergroup"
    assert edited.edited_at == datetime.fromtimestamp(1784451700, timezone.utc)
    assert edited.text_preview is None
    assert "hello" not in str(edited.to_safe_view_fields())
    with pytest.raises(TelegramUpdateParseError, match="telegram_update_invalid"):
        parse_telegram_update({"update_id": 3})
    with pytest.raises(TelegramUpdateParseError, match="telegram_update_invalid"):
        parse_telegram_update(
            {
                "update_id": 4,
                "message": base_message,
                "edited_message": base_message,
            }
        )


@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
def test_new_group_message_creates_one_bounded_projection(chat_type: str) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    _, mapping = _seed_target(uow)
    body = "  " + ("x" * 520) + "   ignored-spacing "

    result = ingest_mock_telegram_update(
        _update(chat_type=chat_type, text=body),
        uow,
    )

    assert result.status == "stored"
    assert len(uow.group_message_projections) == 1
    projection = uow.group_message_projections[0]
    assert projection.business_context_binding_id == mapping.id
    assert projection.source_message_id == uow.messages[0].id
    assert projection.content_fragment == ("x" * 500)
    assert len(projection.content_fragment) == 500
    assert projection.content_version == 1
    assert projection.event_at == EVENT_AT
    assert projection.event_at.tzinfo == timezone.utc
    assert projection.retention_expires_at == EVENT_AT + timedelta(days=30)
    assert projection.lifecycle_status == "active"
    assert projection.source_chat_type == chat_type
    duplicate = ingest_mock_telegram_update(
        _update(chat_type=chat_type, text="must not create another projection"),
        uow,
    )
    assert duplicate.status == "duplicate"
    assert len(uow.group_message_projections) == 1


@pytest.mark.parametrize(
    ("case", "update_overrides", "seed_overrides"),
    [
        ("private", {"chat_type": "private"}, {}),
        ("channel", {"chat_type": "channel"}, {}),
        ("missing_sender", {"sender_user_id": ""}, {}),
        ("unmapped", {}, None),
        ("inactive_binding", {}, {"binding_status": "inactive"}),
        ("wrong_binding_type", {}, {"binding_type": "chat"}),
        ("inactive_mapping", {}, {"mapping_status": "inactive"}),
        ("workspace_drift", {}, {"workspace_drift": True}),
        ("invalid_relation", {}, {"record_relation_valid": False}),
        ("ambiguous_binding", {}, {"duplicate_binding": True}),
        ("ambiguous_mapping", {}, {"duplicate_mapping": True}),
        ("empty_body", {"text": "  \n\t "}, {}),
    ],
)
def test_ineligible_input_creates_no_projection(
    case: str,
    update_overrides: dict[str, object],
    seed_overrides: dict[str, object] | None,
) -> None:
    del case
    uow = InMemoryTelegramIngestionUnitOfWork()
    if seed_overrides is not None:
        _seed_target(uow, **seed_overrides)

    ingest_mock_telegram_update(_update(**update_overrides), uow)

    assert uow.group_message_projections == []


def test_channel_with_negative_chat_id_cannot_create_group_projection() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    binding, _mapping = _seed_target(uow)
    binding.telegram_chat_id = "-100998877"

    ingest_mock_telegram_update(
        _update(chat_type="channel", chat_id="-100998877"),
        uow,
    )

    assert uow.group_message_projections == []


@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
def test_edit_creates_version_two_and_supersedes_without_second_message(
    chat_type: str,
) -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    _seed_target(uow)
    first = ingest_mock_telegram_update(
        _update(text="first body", chat_type=chat_type), uow
    )
    source_id = UUID(first.message_id)
    uow.messages[0].raw_text = "historical raw must never be consulted"
    uow.messages[0].raw_caption = "historical caption must never be consulted"
    uow.messages[0].normalized_text = "historical normalized must never be consulted"
    edited_at = EVENT_AT + timedelta(hours=2)

    second = ingest_mock_telegram_update(
        _update(
            update_id="update-edit-1",
            update_kind="edited",
            chat_type=chat_type,
            text="  edited   body  ",
            edited_at=edited_at,
        ),
        uow,
    )

    assert second.status == "stored"
    assert second.message_id == str(source_id)
    assert len(uow.messages) == 1
    assert len(uow.group_message_projections) == 2
    first_projection, edited_projection = uow.group_message_projections
    assert first_projection.lifecycle_status == "superseded"
    assert edited_projection.content_fragment == "edited body"
    assert edited_projection.content_version == 2
    assert edited_projection.event_at == EVENT_AT
    assert edited_projection.edited_at == edited_at
    assert edited_projection.source_message_id == source_id
    assert first_projection.source_chat_type == chat_type
    assert edited_projection.source_chat_type == chat_type

    replay = ingest_mock_telegram_update(
        _update(
            update_id="update-edit-1",
            update_kind="edited",
            chat_type=chat_type,
            text="  edited   body  ",
            edited_at=edited_at,
        ),
        uow,
    )
    assert replay.status == "stored"
    assert len(uow.group_message_projections) == 2


def test_legacy_message_source_cannot_be_backfilled_by_a_new_update() -> None:
    uow = InMemoryTelegramIngestionUnitOfWork()
    _seed_target(uow)
    legacy = IngestedMessage(
        id=uuid4(),
        telegram_update_id="legacy-update",
        telegram_chat_id="chat-1",
        telegram_message_id="message-1",
        telegram_user_id="user-1",
        customer_group_id=None,
        customer_id=None,
        raw_text="legacy raw body",
        raw_caption=None,
        normalized_text="legacy raw body",
        message_type="text",
        intent_status="unclassified",
        intent_type=None,
        ingestion_status="stored",
        trace_id="tg:legacy-update",
    )
    legacy.received_at = EVENT_AT - timedelta(days=2)
    uow.add_message(legacy)

    result = ingest_mock_telegram_update(
        _update(update_id="new-delivery-for-old-source"),
        uow,
    )

    assert result.status == "duplicate"
    assert len(uow.messages) == 1
    assert uow.group_message_projections == []


def test_c2_internal_metadata_and_projection_body_are_not_public_carriers() -> None:
    parsed = parse_telegram_update(
        {
            "update_id": 10,
            "message": {
                "message_id": 77,
                "date": 1784451600,
                "chat": {"id": "chat-1", "type": "group"},
                "from": {"id": "user-1", "is_bot": False},
                "text": "private fragment",
            },
        }
    )
    carrier = _update(text="private fragment")

    assert "update_kind" not in carrier.model_dump()
    assert "chat_type" not in carrier.model_dump()
    assert "edited_at" not in carrier.model_dump()
    assert "content_fragment" not in parsed.to_safe_view_fields()
    assert "business_context_binding_id" not in parsed.to_safe_view_fields()
    assert "source_message_id" not in parsed.to_safe_view_fields()
    assert "source_chat_type" not in parsed.to_safe_view_fields()


def test_ingress_implementation_introduces_no_network_or_api_route() -> None:
    source = getsource(telegram_ingestion) + getsource(telegram_update_parser)
    forbidden = (
        "getUpdates",
        "sendMessage",
        "httpx",
        "requests",
        "OpenRouter",
        "APIRouter",
        "add_api_route",
    )

    assert all(value not in source for value in forbidden)
