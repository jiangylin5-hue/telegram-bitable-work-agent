from datetime import UTC, datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.audit import OpsAuditEvent
from app.models.outbox import OutboxEvent
from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage07_telegram import (
    Stage07TelegramDeepLink,
    Stage07TelegramDeepLinkDelivery,
)
from app.models.telegram import TelegramSendRequest
from app.services.permissions import Actor
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_workspace,
)
from app.services.stage07_telegram_deep_link_delivery import (
    Stage07TelegramDeepLinkDeliveryCommand,
    Stage07TelegramDeepLinkDeliveryBlocked,
    confirm_stage07_telegram_deep_link_delivery,
    create_stage07_telegram_deep_link_delivery,
    dispatch_stage07_telegram_deep_link_delivery,
)
from app.services.stage07_telegram_deep_links import TelegramDeepLinkDestinationInput
from app.services.telegram_send_requests import SqlAlchemyTelegramSendRequestUnitOfWork
from tests.integration.test_stage07_governance_postgres import (
    Stage06Postgres,
    stage06_postgres,
)


NOW = datetime(2026, 7, 13, 15, 0, tzinfo=UTC)


class FakeTelegramBotClient:
    def __init__(self, *, raises: bool = False, ok: bool = True) -> None:
        self.raises = raises
        self.ok = ok
        self.calls: list[dict[str, str]] = []

    def send_main_mini_app_link(self, *, chat_id: str, url: str):
        self.calls.append({"chat_id": chat_id, "url": url})
        if self.raises:
            raise TimeoutError("synthetic transport timeout")
        return type(
            "Result",
            (),
            {
                "ok": self.ok,
                "response_summary": (
                    {"ok": True, "telegram_message_id": 19}
                    if self.ok
                    else {"ok": False, "error_code": 403}
                ),
            },
        )()


class BlockingFakeTelegramBotClient(FakeTelegramBotClient):
    def __init__(self) -> None:
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def send_main_mini_app_link(self, *, chat_id: str, url: str):
        self.calls.append({"chat_id": chat_id, "url": url})
        self.entered.set()
        assert self.release.wait(timeout=10)
        return type(
            "Result",
            (),
            {"ok": True, "response_summary": {"ok": True, "telegram_message_id": 19}},
        )()


def _confirmed_delivery(stage06_postgres: Stage06Postgres, *, confirm: bool = True):
    with stage06_postgres.session_factory() as session:
        platform_uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        send_uow = SqlAlchemyTelegramSendRequestUnitOfWork(session)
        workspace = create_workspace(
            platform_uow,
            name="S6.2 controlled delivery",
            owner_user_id="member-1",
        )
        session.flush()
        member = platform_uow.list_workspace_members(workspace.id)[0]
        base = create_base(platform_uow, workspace.id, name="Secure Base")
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
        session.flush()
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
        if confirm:
            confirm_stage07_telegram_deep_link_delivery(
                platform_uow,
                send_uow,
                actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
                request_id=receipt.request_id,
                allowed_chat_ids=("synthetic-chat",),
                now=NOW,
            )
        session.commit()
        return receipt.request_id


def test_worker_sends_once_after_reservation_and_replay_does_not_send_again(
    stage06_postgres: Stage06Postgres,
) -> None:
    request_id = _confirmed_delivery(stage06_postgres)
    client = FakeTelegramBotClient()

    with stage06_postgres.session_factory() as session:
        dispatch_stage07_telegram_deep_link_delivery(
            session,
            request_id=request_id,
            bot_client=client,
            allowed_chat_ids=("synthetic-chat",),
            bot_username="Stage07TestBot",
            now=NOW,
        )

        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        assert delivery is not None
        assert delivery.dispatch_state == "sent"
        assert delivery.stage07_telegram_deep_link_id is not None
        link = session.get(Stage07TelegramDeepLink, delivery.stage07_telegram_deep_link_id)
        assert link is not None
        assert link.status == "active"
        assert len(client.calls) == 1
        raw_url = client.calls[0]["url"]
        assert raw_url not in repr((delivery, link))
        audit_rows = list(
            session.scalars(
                select(OpsAuditEvent).where(
                    OpsAuditEvent.entity_id == request_id
                )
            )
        )
        assert audit_rows
        assert all(raw_url not in repr(row) for row in audit_rows)

    with stage06_postgres.session_factory() as session:
        dispatch_stage07_telegram_deep_link_delivery(
            session,
            request_id=request_id,
            bot_client=client,
            allowed_chat_ids=("synthetic-chat",),
            bot_username="Stage07TestBot",
            now=NOW,
        )
    assert len(client.calls) == 1


def test_worker_marks_transport_uncertainty_unknown_and_revokes_pointer(
    stage06_postgres: Stage06Postgres,
) -> None:
    request_id = _confirmed_delivery(stage06_postgres)
    client = FakeTelegramBotClient(raises=True)

    with stage06_postgres.session_factory() as session:
        dispatch_stage07_telegram_deep_link_delivery(
            session,
            request_id=request_id,
            bot_client=client,
            allowed_chat_ids=("synthetic-chat",),
            bot_username="Stage07TestBot",
            now=NOW,
        )
        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        assert delivery is not None
        assert delivery.dispatch_state == "delivery_unknown"
        assert delivery.stage07_telegram_deep_link_id is not None
        link = session.get(Stage07TelegramDeepLink, delivery.stage07_telegram_deep_link_id)
        assert link is not None
        assert link.status == "revoked"
        assert len(client.calls) == 1


def test_worker_marks_definite_bot_rejection_failed_and_revokes_pointer(
    stage06_postgres: Stage06Postgres,
) -> None:
    request_id = _confirmed_delivery(stage06_postgres)
    client = FakeTelegramBotClient(ok=False)

    with stage06_postgres.session_factory() as session:
        dispatch_stage07_telegram_deep_link_delivery(
            session,
            request_id=request_id,
            bot_client=client,
            allowed_chat_ids=("synthetic-chat",),
            bot_username="Stage07TestBot",
            now=NOW,
        )
        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        assert delivery is not None
        assert delivery.dispatch_state == "failed"
        assert delivery.stage07_telegram_deep_link_id is not None
        link = session.get(Stage07TelegramDeepLink, delivery.stage07_telegram_deep_link_id)
        assert link is not None
        assert link.status == "revoked"
        assert len(client.calls) == 1


def test_worker_replay_of_a_reserved_delivery_never_calls_bot(
    stage06_postgres: Stage06Postgres,
) -> None:
    request_id = _confirmed_delivery(stage06_postgres)
    client = FakeTelegramBotClient()

    with stage06_postgres.session_factory() as session:
        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        assert delivery is not None
        delivery.dispatch_state = "dispatch_reserved"
        session.commit()

        dispatch_stage07_telegram_deep_link_delivery(
            session,
            request_id=request_id,
            bot_client=client,
            allowed_chat_ids=("synthetic-chat",),
            bot_username="Stage07TestBot",
            now=NOW,
        )
        session.refresh(delivery)
        assert delivery.dispatch_state == "delivery_unknown"
        assert client.calls == []


def test_simultaneous_workers_make_at_most_one_external_call_and_revoke_after_claim_collision(
    stage06_postgres: Stage06Postgres,
) -> None:
    request_id = _confirmed_delivery(stage06_postgres)
    reserved_client = BlockingFakeTelegramBotClient()
    replay_client = FakeTelegramBotClient()

    def dispatch_with(client: FakeTelegramBotClient) -> None:
        with stage06_postgres.session_factory() as session:
            dispatch_stage07_telegram_deep_link_delivery(
                session,
                request_id=request_id,
                bot_client=client,
                allowed_chat_ids=("synthetic-chat",),
                bot_username="Stage07TestBot",
                now=NOW,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(dispatch_with, reserved_client)
        assert reserved_client.entered.wait(timeout=10)
        replay = executor.submit(dispatch_with, replay_client)
        replay.result(timeout=10)
        reserved_client.release.set()
        first.result(timeout=10)

    assert len(reserved_client.calls) == 1
    assert replay_client.calls == []
    with stage06_postgres.session_factory() as session:
        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        assert delivery is not None
        assert delivery.dispatch_state == "delivery_unknown"
        assert delivery.stage07_telegram_deep_link_id is not None
        link = session.get(Stage07TelegramDeepLink, delivery.stage07_telegram_deep_link_id)
        assert link is not None
        assert link.status == "revoked"


def test_confirmation_denial_persists_blocked_without_an_outbox_event(
    stage06_postgres: Stage06Postgres,
) -> None:
    request_id = _confirmed_delivery(stage06_postgres, confirm=False)

    with stage06_postgres.session_factory() as session:
        platform_uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        send_uow = SqlAlchemyTelegramSendRequestUnitOfWork(session)
        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        assert delivery is not None
        binding = session.get(Stage06TelegramBinding, delivery.source_binding_id)
        assert binding is not None
        binding.status = "revoked"

        with pytest.raises(Stage07TelegramDeepLinkDeliveryBlocked):
            confirm_stage07_telegram_deep_link_delivery(
                platform_uow,
                send_uow,
                actor=Actor(actor_type="user", actor_id="manager-1", role="manager"),
                request_id=request_id,
                allowed_chat_ids=("synthetic-chat",),
                now=NOW,
            )
        session.commit()

    with stage06_postgres.session_factory() as session:
        delivery = session.scalar(
            select(Stage07TelegramDeepLinkDelivery).where(
                Stage07TelegramDeepLinkDelivery.send_request_id == request_id
            )
        )
        request = session.get(TelegramSendRequest, request_id)
        event = session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.idempotency_key
                == f"stage07.telegram_deep_link_delivery:{request_id}"
            )
        )
        assert delivery is not None
        assert request is not None
        assert delivery.dispatch_state == "blocked"
        assert request.status == "blocked"
        assert event is None
