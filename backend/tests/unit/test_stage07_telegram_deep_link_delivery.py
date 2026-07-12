from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import (
    Settings,
    validate_stage07_telegram_controlled_delivery_settings,
)
from app.main import create_app
from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage07_telegram import Stage07TelegramDeepLinkDelivery
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_workspace,
)
from app.services.stage07_telegram_deep_link_delivery import (
    Stage07TelegramDeepLinkDeliveryBlocked,
    Stage07TelegramDeepLinkDeliveryCommand,
    confirm_stage07_telegram_deep_link_delivery,
    create_stage07_telegram_deep_link_delivery,
)
from app.services.stage07_telegram_deep_links import TelegramDeepLinkDestinationInput
from app.services.stage07_telegram_deep_links import mint_telegram_deep_link
from app.services.telegram_send_requests import (
    InMemoryTelegramSendRequestUnitOfWork,
    TelegramSendRequestStateError,
    confirm_test_send_request,
)


NOW = datetime(2026, 7, 13, 14, 0, tzinfo=UTC)
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260713_0026_stage07_telegram_deep_link_deliveries.py"
)


def _delivery(*, workspace_id, send_request_id=None, state: str = "pending_confirmation"):
    return Stage07TelegramDeepLinkDelivery(
        id=uuid4(),
        send_request_id=send_request_id or uuid4(),
        workspace_id=workspace_id,
        source_binding_id=uuid4(),
        subject_telegram_user_id="synthetic-user",
        target_chat_id="synthetic-chat",
        destination_kind="base",
        destination_id=uuid4(),
        message_template="stage07_open_secure_destination",
        dispatch_state=state,
        stage07_telegram_deep_link_id=None,
        telegram_message_id=None,
        outcome_code=None,
    )


def test_delivery_extension_has_only_closed_state_and_reference_columns() -> None:
    names = {
        constraint.name
        for constraint in Stage07TelegramDeepLinkDelivery.__table__.constraints
    }
    assert {
        "uq_stage07_telegram_deep_link_deliveries_send_request_id",
        "ck_stage07_telegram_deep_link_deliveries_destination_kind",
        "ck_stage07_telegram_deep_link_deliveries_dispatch_state",
        "ck_stage07_telegram_deep_link_deliveries_message_template",
    } <= names
    columns = set(Stage07TelegramDeepLinkDelivery.__table__.columns.keys())
    for forbidden in ("token", "url", "message_body", "bot_username", "payload"):
        assert forbidden not in columns


def test_delivery_uow_resolves_the_request_extension_and_reserves_by_row_lock() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="S6 Delivery", owner_user_id="owner-1")
    delivery = _delivery(workspace_id=workspace.id)
    uow.add_stage07_telegram_deep_link_delivery(delivery)

    assert uow.get_stage07_telegram_deep_link_delivery_by_send_request_id(
        delivery.send_request_id
    ) == delivery
    assert uow.get_stage07_telegram_deep_link_delivery_for_update(
        delivery.id
    ) == delivery
    assert uow.get_stage07_telegram_deep_link_delivery_by_send_request_id(
        uuid4()
    ) is None


def test_delivery_migration_is_additive_and_never_mentions_raw_link_material() -> None:
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260713_0026"' in content
    assert 'down_revision = "20260712_0025"' in content
    assert "stage07_telegram_deep_link_deliveries" in content
    assert "send_request_id" in content
    assert "uq_stage07_telegram_deep_link_deliveries_send_request_id" in content
    assert "raw_token" not in content
    assert "raw_url" not in content


def _delivery_service_fixture():
    platform_uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(
        platform_uow,
        name="S6 controlled delivery",
        owner_user_id="member-1",
    )
    member = platform_uow.list_workspace_members(workspace.id)[0]
    base = create_base(platform_uow, workspace.id, name="Secure destination")
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="synthetic-chat",
        telegram_user_id="synthetic-user",
        binding_type="member",
        default_base_id=base.id,
        default_digital_employee_id=None,
        scope_policy={},
        status="active",
    )
    platform_uow.add_telegram_binding(binding)
    return platform_uow, InMemoryTelegramSendRequestUnitOfWork(), workspace, base, binding


def test_server_only_delivery_request_derives_closed_target_and_queues_one_typed_event() -> None:
    platform_uow, send_uow, workspace, base, binding = _delivery_service_fixture()
    command = Stage07TelegramDeepLinkDeliveryCommand(
        workspace_id=workspace.id,
        source_binding_id=binding.id,
        destination=TelegramDeepLinkDestinationInput(kind="base", destination_id=base.id),
    )

    receipt = create_stage07_telegram_deep_link_delivery(
        platform_uow,
        send_uow,
        actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
        command=command,
        allowed_chat_ids=("synthetic-chat",),
        now=NOW,
    )

    request = send_uow.send_requests[0]
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id(
        request.id
    )
    assert receipt.request_id == request.id
    assert request.target_chat_id == "synthetic-chat"
    assert request.message_text == "已生成一个受控工作区入口。"
    assert request.send_purpose == "stage07_deep_link_delivery"
    assert delivery is not None
    assert delivery.dispatch_state == "pending_confirmation"
    assert delivery.destination_id == base.id
    assert delivery.stage07_telegram_deep_link_id is None
    assert send_uow.outbox_events == []
    serialized = repr((request, delivery, send_uow.audit_events))
    for forbidden in ("startapp", "https://t.me", "Secure destination"):
        assert forbidden not in serialized

    confirmed = confirm_stage07_telegram_deep_link_delivery(
        platform_uow,
        send_uow,
        actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
        request_id=request.id,
        allowed_chat_ids=("synthetic-chat",),
        now=NOW,
    )
    assert confirmed.status == "confirmed"
    assert send_uow.outbox_events[0].event_type == (
        "stage07.telegram_deep_link_delivery_requested"
    )
    assert send_uow.outbox_events[0].payload == {"request_id": str(request.id)}
    assert send_uow.outbox_events[0].max_attempts == 1


def test_server_only_mint_returns_a_durable_link_id_for_in_memory_and_sql_uows() -> None:
    platform_uow, _send_uow, workspace, base, binding = _delivery_service_fixture()

    minted = mint_telegram_deep_link(
        platform_uow,
        actor=Actor(actor_type="user", actor_id="member-1", role="owner"),
        subject_telegram_user_id=binding.telegram_user_id,
        source_telegram_chat_id=binding.telegram_chat_id,
        destination=TelegramDeepLinkDestinationInput(
            kind="base",
            destination_id=base.id,
        ),
        now=NOW,
    )

    assert minted.link_id is not None
    assert platform_uow.telegram_deep_links[-1].id == minted.link_id


def test_confirmation_rechecks_exact_single_target_without_enqueuing() -> None:
    platform_uow, send_uow, workspace, base, binding = _delivery_service_fixture()
    receipt = create_stage07_telegram_deep_link_delivery(
        platform_uow,
        send_uow,
        actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
        command=Stage07TelegramDeepLinkDeliveryCommand(
            workspace_id=workspace.id,
            source_binding_id=binding.id,
            destination=TelegramDeepLinkDestinationInput(
                kind="base",
                destination_id=base.id,
            ),
        ),
        allowed_chat_ids=("synthetic-chat",),
        now=NOW,
    )

    with pytest.raises(Stage07TelegramDeepLinkDeliveryBlocked):
        confirm_stage07_telegram_deep_link_delivery(
            platform_uow,
            send_uow,
            actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
            request_id=receipt.request_id,
            allowed_chat_ids=("synthetic-chat", "second-chat"),
            now=NOW,
        )

    assert send_uow.send_requests[0].status == "blocked"
    assert send_uow.outbox_events == []
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id(
        receipt.request_id
    )
    assert delivery is not None
    assert delivery.dispatch_state == "blocked"


def test_generic_confirmation_route_cannot_queue_a_controlled_delivery_as_text_send() -> None:
    platform_uow, send_uow, workspace, base, binding = _delivery_service_fixture()
    receipt = create_stage07_telegram_deep_link_delivery(
        platform_uow,
        send_uow,
        actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
        command=Stage07TelegramDeepLinkDeliveryCommand(
            workspace_id=workspace.id,
            source_binding_id=binding.id,
            destination=TelegramDeepLinkDestinationInput(
                kind="base",
                destination_id=base.id,
            ),
        ),
        allowed_chat_ids=("synthetic-chat",),
        now=NOW,
    )

    with pytest.raises(TelegramSendRequestStateError):
        confirm_test_send_request(
            send_uow,
            actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
            request_id=receipt.request_id,
            allowed_chat_ids=("synthetic-chat",),
        )

    assert send_uow.send_requests[0].status == "pending_confirmation"
    assert send_uow.outbox_events == []


@pytest.mark.parametrize("invalidates", ["binding", "member", "destination"])
def test_confirmation_rechecks_current_binding_member_and_destination(
    invalidates: str,
) -> None:
    platform_uow, send_uow, workspace, base, binding = _delivery_service_fixture()
    receipt = create_stage07_telegram_deep_link_delivery(
        platform_uow,
        send_uow,
        actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
        command=Stage07TelegramDeepLinkDeliveryCommand(
            workspace_id=workspace.id,
            source_binding_id=binding.id,
            destination=TelegramDeepLinkDestinationInput(
                kind="base",
                destination_id=base.id,
            ),
        ),
        allowed_chat_ids=("synthetic-chat",),
        now=NOW,
    )
    if invalidates == "binding":
        binding.status = "revoked"
    elif invalidates == "member":
        platform_uow.get_workspace_member(binding.workspace_member_id).status = "inactive"
    else:
        platform_uow.bases.remove(base)

    with pytest.raises(Stage07TelegramDeepLinkDeliveryBlocked):
        confirm_stage07_telegram_deep_link_delivery(
            platform_uow,
            send_uow,
            actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
            request_id=receipt.request_id,
            allowed_chat_ids=("synthetic-chat",),
            now=NOW,
        )

    assert send_uow.send_requests[0].status == "blocked"
    assert send_uow.outbox_events == []


def test_openapi_has_no_stage07_delivery_or_browser_mint_route() -> None:
    paths = create_app().openapi()["paths"]

    assert not any("deep-link-deliver" in path for path in paths)
    assert not any("telegram/deep-links/mint" in path for path in paths)


@pytest.mark.parametrize(
    ("settings", "code"),
    [
        (
            Settings(
                telegram_send_mode="dry_run",
                telegram_test_send_allowed_chat_ids=("synthetic-chat",),
                stage07_telegram_bot_username="Stage07TestBot",
            ),
            "telegram_send_mode",
        ),
        (
            Settings(
                telegram_send_mode="restricted_test",
                telegram_test_send_allowed_chat_ids=("synthetic-chat", "second-chat"),
                stage07_telegram_bot_username="Stage07TestBot",
            ),
            "telegram_test_send_allowed_chat_ids",
        ),
        (
            Settings(
                telegram_send_mode="restricted_test",
                telegram_test_send_allowed_chat_ids=("synthetic-chat",),
                stage07_telegram_bot_username="not a bot username",
            ),
            "stage07_telegram_bot_username",
        ),
    ],
)
def test_controlled_delivery_settings_fail_closed(
    settings: Settings,
    code: str,
) -> None:
    with pytest.raises(RuntimeError, match=code):
        validate_stage07_telegram_controlled_delivery_settings(settings)


def test_controlled_delivery_settings_accept_one_restricted_test_target() -> None:
    settings = Settings(
        telegram_send_mode="restricted_test",
        telegram_test_send_allowed_chat_ids=("synthetic-chat",),
        stage07_telegram_bot_username="Stage07TestBot",
        telegram_bot_token="test-token",
    )

    assert validate_stage07_telegram_controlled_delivery_settings(settings) == (
        "Stage07TestBot"
    )
