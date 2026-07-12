from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent
from app.models.stage07_telegram import (
    Stage07TelegramDeepLink,
    Stage07TelegramDeepLinkDelivery,
)
from app.models.telegram import TelegramSendRequest
from app.services.audit import record_audit_event
from app.services.permissions import Actor, assert_action_allowed
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.services.stage07_telegram_deep_links import (
    TelegramDeepLinkDestinationInput,
    authorize_telegram_deep_link_mint_context,
    mint_telegram_deep_link,
)
from app.services.telegram_send_requests import (
    SqlAlchemyTelegramSendRequestUnitOfWork,
    STAGE07_DEEP_LINK_DELIVERY_PURPOSE,
    TelegramSendRequestNotFound,
    TelegramSendRequestUnitOfWork,
    summarize_message_text,
)


STAGE07_DEEP_LINK_DELIVERY_TEMPLATE = "stage07_open_secure_destination"
STAGE07_DEEP_LINK_DELIVERY_TEXT = "已生成一个受控工作区入口。"
STAGE07_DEEP_LINK_DELIVERY_NOT_ALLOWLISTED = (
    "stage07_telegram_deep_link_delivery_target_not_allowlisted"
)
STAGE07_DEEP_LINK_DELIVERY_CONTEXT_INVALID = (
    "stage07_telegram_deep_link_delivery_context_invalid"
)
STAGE07_DEEP_LINK_DELIVERY_REPLAYED = "stage07_telegram_deep_link_delivery_replayed"
STAGE07_DEEP_LINK_DELIVERY_MINT_FAILED = "stage07_telegram_deep_link_delivery_mint_failed"
STAGE07_DEEP_LINK_DELIVERY_BOT_REJECTED = "stage07_telegram_deep_link_delivery_bot_rejected"
STAGE07_DEEP_LINK_DELIVERY_UNKNOWN = "stage07_telegram_deep_link_delivery_unknown"


class Stage07TelegramDeepLinkDeliveryStateError(ValueError):
    pass


class Stage07TelegramDeepLinkDeliveryBlocked(ValueError):
    pass


class Stage07TelegramMainMiniAppLinkClient:
    def send_main_mini_app_link(self, *, chat_id: str, url: str):
        raise NotImplementedError


@dataclass(frozen=True)
class Stage07TelegramDeepLinkDeliveryCommand:
    workspace_id: UUID
    source_binding_id: UUID
    destination: TelegramDeepLinkDestinationInput


@dataclass(frozen=True)
class Stage07TelegramDeepLinkDeliveryReceipt:
    request_id: UUID
    delivery_id: UUID
    status: str


@dataclass(frozen=True)
class _BindingDeliveryContext:
    subject_telegram_user_id: str
    target_chat_id: str
    identity: Stage06RequestIdentity


def create_stage07_telegram_deep_link_delivery(
    platform_uow: Stage06PlatformUnitOfWork,
    send_uow: TelegramSendRequestUnitOfWork,
    *,
    actor: Actor,
    command: Stage07TelegramDeepLinkDeliveryCommand,
    allowed_chat_ids: tuple[str, ...],
    now: datetime,
) -> Stage07TelegramDeepLinkDeliveryReceipt:
    trace_id = f"stage07:telegram-deep-link-delivery:{uuid4()}"
    assert_action_allowed(
        actor,
        "request_test_telegram_send",
        session=send_uow.audit_session,
        trace_id=trace_id,
        entity_type="telegram_send_request",
    )
    context = _authorize_delivery_context(
        platform_uow,
        command=command,
    )
    if not _has_exact_allowed_target(context.target_chat_id, allowed_chat_ids):
        raise Stage07TelegramDeepLinkDeliveryBlocked(
            STAGE07_DEEP_LINK_DELIVERY_NOT_ALLOWLISTED
        )

    send_request = TelegramSendRequest(
        id=uuid4(),
        target_chat_id=context.target_chat_id,
        message_text=STAGE07_DEEP_LINK_DELIVERY_TEXT,
        source_service_draft_id=None,
        send_purpose=STAGE07_DEEP_LINK_DELIVERY_PURPOSE,
        message_text_summary=summarize_message_text(
            STAGE07_DEEP_LINK_DELIVERY_TEXT
        ),
        status="pending_confirmation",
        requested_by_actor_type=actor.actor_type,
        requested_by_actor_id=actor.actor_id,
        confirmed_by_actor_type=None,
        confirmed_by_actor_id=None,
        confirmed_at=None,
        allowlist_snapshot={"target_allowed": True, "allowed_chat_count": 1},
        telegram_response_summary=None,
        last_error_code=None,
        sent_at=None,
        trace_id=trace_id,
        created_at=now,
        updated_at=now,
    )
    send_uow.add_send_request(send_request)
    send_uow.flush()
    delivery = Stage07TelegramDeepLinkDelivery(
        id=uuid4(),
        send_request_id=send_request.id,
        workspace_id=command.workspace_id,
        source_binding_id=command.source_binding_id,
        subject_telegram_user_id=context.subject_telegram_user_id,
        target_chat_id=context.target_chat_id,
        destination_kind=command.destination.kind,
        destination_id=command.destination.destination_id,
        message_template=STAGE07_DEEP_LINK_DELIVERY_TEMPLATE,
        dispatch_state="pending_confirmation",
        stage07_telegram_deep_link_id=None,
        telegram_message_id=None,
        outcome_code=None,
        created_at=now,
        updated_at=now,
    )
    platform_uow.add_stage07_telegram_deep_link_delivery(delivery)
    platform_uow.flush()
    _record_delivery_audit(
        send_uow,
        trace_id=trace_id,
        actor=actor,
        event_type="stage07.telegram_deep_link_delivery.requested",
        delivery=delivery,
        request=send_request,
    )
    return Stage07TelegramDeepLinkDeliveryReceipt(
        request_id=send_request.id,
        delivery_id=delivery.id,
        status=send_request.status,
    )


def confirm_stage07_telegram_deep_link_delivery(
    platform_uow: Stage06PlatformUnitOfWork,
    send_uow: TelegramSendRequestUnitOfWork,
    *,
    actor: Actor,
    request_id: UUID,
    allowed_chat_ids: tuple[str, ...],
    now: datetime,
) -> TelegramSendRequest:
    send_request = send_uow.get_send_request(request_id)
    if send_request is None:
        raise TelegramSendRequestNotFound(f"Telegram send request {request_id} not found")
    trace_id = send_request.trace_id
    assert_action_allowed(
        actor,
        "confirm_test_telegram_send",
        session=send_uow.audit_session,
        trace_id=trace_id,
        entity_type="telegram_send_request",
        entity_id=request_id,
    )
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id(
        request_id
    )
    if delivery is None or send_request.send_purpose != STAGE07_DEEP_LINK_DELIVERY_PURPOSE:
        raise Stage07TelegramDeepLinkDeliveryStateError(
            "stage07_telegram_deep_link_delivery_not_found"
        )
    if (
        send_request.status != "pending_confirmation"
        or delivery.dispatch_state != "pending_confirmation"
    ):
        raise Stage07TelegramDeepLinkDeliveryStateError(
            "stage07_telegram_deep_link_delivery_invalid_state"
        )
    command = Stage07TelegramDeepLinkDeliveryCommand(
        workspace_id=delivery.workspace_id,
        source_binding_id=delivery.source_binding_id,
        destination=TelegramDeepLinkDestinationInput(
            kind=delivery.destination_kind,
            destination_id=delivery.destination_id,
        ),
    )
    try:
        context = _authorize_delivery_context(platform_uow, command=command)
    except Exception as exc:
        _block_delivery(
            platform_uow,
            send_uow,
            delivery=delivery,
            request=send_request,
            actor=actor,
            now=now,
            code=STAGE07_DEEP_LINK_DELIVERY_CONTEXT_INVALID,
        )
        raise Stage07TelegramDeepLinkDeliveryBlocked(
            STAGE07_DEEP_LINK_DELIVERY_CONTEXT_INVALID
        ) from exc
    if not _has_exact_allowed_target(context.target_chat_id, allowed_chat_ids):
        _block_delivery(
            platform_uow,
            send_uow,
            delivery=delivery,
            request=send_request,
            actor=actor,
            now=now,
            code=STAGE07_DEEP_LINK_DELIVERY_NOT_ALLOWLISTED,
        )
        raise Stage07TelegramDeepLinkDeliveryBlocked(
            STAGE07_DEEP_LINK_DELIVERY_NOT_ALLOWLISTED
        )

    send_request.status = "confirmed"
    send_request.confirmed_by_actor_type = actor.actor_type
    send_request.confirmed_by_actor_id = actor.actor_id
    send_request.confirmed_at = now
    send_request.allowlist_snapshot = {"target_allowed": True, "allowed_chat_count": 1}
    send_request.updated_at = now
    event = OutboxEvent(
        id=uuid4(),
        event_type="stage07.telegram_deep_link_delivery_requested",
        aggregate_type="telegram_send_request",
        aggregate_id=str(send_request.id),
        payload={"request_id": str(send_request.id)},
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=1,
        idempotency_key=f"stage07.telegram_deep_link_delivery:{send_request.id}",
        trace_id=trace_id,
        created_at=now,
    )
    send_uow.add_outbox_event(event)
    send_uow.flush()
    platform_uow.flush()
    _record_delivery_audit(
        send_uow,
        trace_id=trace_id,
        actor=actor,
        event_type="stage07.telegram_deep_link_delivery.confirmed",
        delivery=delivery,
        request=send_request,
        extra={"outbox_event_id": str(event.id)},
    )
    return send_request


def dispatch_stage07_telegram_deep_link_delivery(
    session: Session,
    *,
    request_id: UUID,
    bot_client: Stage07TelegramMainMiniAppLinkClient,
    allowed_chat_ids: tuple[str, ...],
    bot_username: str,
    now: datetime,
) -> None:
    reserved = _reserve_delivery_attempt(
        session,
        request_id=request_id,
        allowed_chat_ids=allowed_chat_ids,
        now=now,
    )
    if not reserved:
        return
    try:
        raw_token, target_chat_id = _mint_reserved_delivery_link(
            session,
            request_id=request_id,
            allowed_chat_ids=allowed_chat_ids,
            now=now,
        )
    except Exception:
        session.rollback()
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="failed",
            code=STAGE07_DEEP_LINK_DELIVERY_MINT_FAILED,
            now=now,
        )
        return

    url = f"https://t.me/{bot_username}?startapp={raw_token}"
    try:
        result = bot_client.send_main_mini_app_link(
            chat_id=target_chat_id,
            url=url,
        )
    except Exception:
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="delivery_unknown",
            code=STAGE07_DEEP_LINK_DELIVERY_UNKNOWN,
            now=now,
        )
        return
    if not bool(getattr(result, "ok", False)):
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="failed",
            code=STAGE07_DEEP_LINK_DELIVERY_BOT_REJECTED,
            now=now,
        )
        return
    try:
        _finish_sent_delivery(
            session,
            request_id=request_id,
            response_summary=getattr(result, "response_summary", {}),
            now=now,
        )
    except Exception:
        session.rollback()
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="delivery_unknown",
            code=STAGE07_DEEP_LINK_DELIVERY_UNKNOWN,
            now=now,
        )


def _reserve_delivery_attempt(
    session: Session,
    *,
    request_id: UUID,
    allowed_chat_ids: tuple[str, ...],
    now: datetime,
) -> bool:
    platform_uow = _sql_platform_uow(session)
    send_uow = SqlAlchemyTelegramSendRequestUnitOfWork(session)
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id_for_update(
        request_id
    )
    if delivery is None:
        session.rollback()
        return False
    request = _locked_send_request(session, request_id)
    event = _locked_delivery_event(session, request_id)
    if request is None or event is None:
        session.rollback()
        return False
    if delivery.dispatch_state == "sent":
        _mark_event_processed(event, now)
        session.commit()
        return False
    if delivery.dispatch_state == "dispatch_reserved":
        session.rollback()
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="delivery_unknown",
            code=STAGE07_DEEP_LINK_DELIVERY_REPLAYED,
            now=now,
        )
        return False
    if delivery.dispatch_state != "pending_confirmation" or request.status != "confirmed":
        session.rollback()
        return False
    try:
        context = _authorize_delivery_context(
            platform_uow,
            command=_command_for_delivery(delivery),
        )
    except Exception:
        session.rollback()
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="blocked",
            code=STAGE07_DEEP_LINK_DELIVERY_CONTEXT_INVALID,
            now=now,
        )
        return False
    if not _has_exact_allowed_target(context.target_chat_id, allowed_chat_ids):
        session.rollback()
        _finish_terminal_delivery(
            session,
            request_id=request_id,
            state="blocked",
            code=STAGE07_DEEP_LINK_DELIVERY_NOT_ALLOWLISTED,
            now=now,
        )
        return False
    delivery.dispatch_state = "dispatch_reserved"
    delivery.updated_at = now
    event.status = "processing"
    _record_delivery_audit(
        send_uow,
        trace_id=request.trace_id,
        actor=Actor(actor_type="worker", actor_id="stage07_telegram_delivery_worker", role="admin"),
        event_type="stage07.telegram_deep_link_delivery.dispatch_reserved",
        delivery=delivery,
        request=request,
    )
    session.commit()
    return True


def _mint_reserved_delivery_link(
    session: Session,
    *,
    request_id: UUID,
    allowed_chat_ids: tuple[str, ...],
    now: datetime,
) -> tuple[str, str]:
    platform_uow = _sql_platform_uow(session)
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id_for_update(
        request_id
    )
    request = _locked_send_request(session, request_id)
    if (
        delivery is None
        or request is None
        or delivery.dispatch_state != "dispatch_reserved"
    ):
        raise Stage07TelegramDeepLinkDeliveryStateError(
            "stage07_telegram_deep_link_delivery_invalid_state"
        )
    context = _authorize_delivery_context(
        platform_uow,
        command=_command_for_delivery(delivery),
    )
    if not _has_exact_allowed_target(context.target_chat_id, allowed_chat_ids):
        raise Stage07TelegramDeepLinkDeliveryBlocked(
            STAGE07_DEEP_LINK_DELIVERY_NOT_ALLOWLISTED
        )
    minted = mint_telegram_deep_link(
        platform_uow,
        actor=Actor(
            actor_type="user",
            actor_id=context.identity.user_id,
            role="unknown",
        ),
        subject_telegram_user_id=context.subject_telegram_user_id,
        source_telegram_chat_id=context.target_chat_id,
        destination=_command_for_delivery(delivery).destination,
        now=now,
    )
    delivery.stage07_telegram_deep_link_id = minted.link_id
    delivery.updated_at = now
    session.commit()
    return minted.raw_token, context.target_chat_id


def _finish_sent_delivery(
    session: Session,
    *,
    request_id: UUID,
    response_summary: object,
    now: datetime,
) -> None:
    platform_uow = _sql_platform_uow(session)
    send_uow = SqlAlchemyTelegramSendRequestUnitOfWork(session)
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id_for_update(
        request_id
    )
    request = _locked_send_request(session, request_id)
    event = _locked_delivery_event(session, request_id)
    if delivery is None or request is None or event is None:
        raise Stage07TelegramDeepLinkDeliveryStateError(
            "stage07_telegram_deep_link_delivery_not_found"
        )
    if delivery.dispatch_state != "dispatch_reserved":
        raise Stage07TelegramDeepLinkDeliveryStateError(
            "stage07_telegram_deep_link_delivery_invalid_state"
        )
    safe_summary = _safe_bot_response_summary(response_summary)
    delivery.dispatch_state = "sent"
    delivery.telegram_message_id = safe_summary.get("telegram_message_id")
    delivery.outcome_code = None
    delivery.updated_at = now
    request.status = "sent"
    request.sent_at = now
    request.last_error_code = None
    request.telegram_response_summary = safe_summary
    request.updated_at = now
    _mark_event_processed(event, now)
    _record_delivery_audit(
        send_uow,
        trace_id=request.trace_id,
        actor=Actor(actor_type="worker", actor_id="stage07_telegram_delivery_worker", role="admin"),
        event_type="stage07.telegram_deep_link_delivery.sent",
        delivery=delivery,
        request=request,
    )
    session.commit()


def _finish_terminal_delivery(
    session: Session,
    *,
    request_id: UUID,
    state: str,
    code: str,
    now: datetime,
) -> None:
    session.rollback()
    platform_uow = _sql_platform_uow(session)
    send_uow = SqlAlchemyTelegramSendRequestUnitOfWork(session)
    delivery = platform_uow.get_stage07_telegram_deep_link_delivery_by_send_request_id_for_update(
        request_id
    )
    request = _locked_send_request(session, request_id)
    event = _locked_delivery_event(session, request_id)
    if delivery is None or request is None or event is None:
        session.rollback()
        return
    delivery.dispatch_state = state
    delivery.outcome_code = code
    delivery.updated_at = now
    if delivery.stage07_telegram_deep_link_id is not None:
        link = session.scalar(
            select(Stage07TelegramDeepLink)
            .where(Stage07TelegramDeepLink.id == delivery.stage07_telegram_deep_link_id)
            .with_for_update()
        )
        if link is not None and link.status == "active":
            link.status = "revoked"
    request.status = "blocked" if state == "blocked" else "failed"
    request.last_error_code = code
    request.updated_at = now
    event.status = "dead_letter"
    event.processed_at = now
    event.last_error = code
    event.last_error_redacted = code
    _record_delivery_audit(
        send_uow,
        trace_id=request.trace_id,
        actor=Actor(actor_type="worker", actor_id="stage07_telegram_delivery_worker", role="admin"),
        event_type=f"stage07.telegram_deep_link_delivery.{state}",
        delivery=delivery,
        request=request,
    )
    session.commit()


def _sql_platform_uow(session: Session):
    from app.services.stage06_platform import SqlAlchemyStage06PlatformUnitOfWork

    return SqlAlchemyStage06PlatformUnitOfWork(session)


def _locked_send_request(session: Session, request_id: UUID) -> TelegramSendRequest | None:
    return session.scalar(
        select(TelegramSendRequest)
        .where(TelegramSendRequest.id == request_id)
        .with_for_update()
    )


def _locked_delivery_event(session: Session, request_id: UUID) -> OutboxEvent | None:
    return session.scalar(
        select(OutboxEvent)
        .where(
            OutboxEvent.idempotency_key
            == f"stage07.telegram_deep_link_delivery:{request_id}"
        )
        .with_for_update()
    )


def _command_for_delivery(
    delivery: Stage07TelegramDeepLinkDelivery,
) -> Stage07TelegramDeepLinkDeliveryCommand:
    return Stage07TelegramDeepLinkDeliveryCommand(
        workspace_id=delivery.workspace_id,
        source_binding_id=delivery.source_binding_id,
        destination=TelegramDeepLinkDestinationInput(
            kind=delivery.destination_kind,
            destination_id=delivery.destination_id,
        ),
    )


def _mark_event_processed(event: OutboxEvent, now: datetime) -> None:
    event.status = "processed"
    event.processed_at = now
    event.dispatched_at = now
    event.last_error = None
    event.last_error_redacted = None


def _safe_bot_response_summary(response_summary: object) -> dict[str, object]:
    if not isinstance(response_summary, dict):
        return {"ok": True}
    message_id = response_summary.get("telegram_message_id")
    if isinstance(message_id, int):
        return {"ok": True, "telegram_message_id": message_id}
    return {"ok": True}


def _authorize_delivery_context(
    platform_uow: Stage06PlatformUnitOfWork,
    *,
    command: Stage07TelegramDeepLinkDeliveryCommand,
) -> _BindingDeliveryContext:
    binding = next(
        (
            item
            for item in platform_uow.list_telegram_bindings()
            if item.id == command.source_binding_id
        ),
        None,
    )
    if (
        binding is None
        or binding.status != "active"
        or binding.workspace_id != command.workspace_id
        or binding.workspace_member_id is None
        or binding.telegram_user_id is None
        or binding.telegram_chat_id is None
    ):
        raise Stage07TelegramDeepLinkDeliveryBlocked(
            STAGE07_DEEP_LINK_DELIVERY_CONTEXT_INVALID
        )
    member = platform_uow.get_workspace_member(binding.workspace_member_id)
    if (
        member is None
        or member.status != "active"
        or member.workspace_id != command.workspace_id
    ):
        raise Stage07TelegramDeepLinkDeliveryBlocked(
            STAGE07_DEEP_LINK_DELIVERY_CONTEXT_INVALID
        )
    identity = Stage06RequestIdentity(
        user_id=member.user_id,
        source="telegram_binding",
        telegram_user_id=binding.telegram_user_id,
    )
    authorize_telegram_deep_link_mint_context(
        platform_uow,
        identity=identity,
        subject_telegram_user_id=binding.telegram_user_id,
        source_telegram_chat_id=binding.telegram_chat_id,
        destination=command.destination,
    )
    return _BindingDeliveryContext(
        subject_telegram_user_id=binding.telegram_user_id,
        target_chat_id=binding.telegram_chat_id,
        identity=identity,
    )


def _block_delivery(
    platform_uow: Stage06PlatformUnitOfWork,
    send_uow: TelegramSendRequestUnitOfWork,
    *,
    delivery: Stage07TelegramDeepLinkDelivery,
    request: TelegramSendRequest,
    actor: Actor,
    now: datetime,
    code: str,
) -> None:
    request.status = "blocked"
    request.last_error_code = code
    request.updated_at = now
    delivery.dispatch_state = "blocked"
    delivery.outcome_code = code
    delivery.updated_at = now
    send_uow.flush()
    platform_uow.flush()
    _record_delivery_audit(
        send_uow,
        trace_id=request.trace_id,
        actor=actor,
        event_type="stage07.telegram_deep_link_delivery.blocked",
        delivery=delivery,
        request=request,
    )


def _has_exact_allowed_target(
    target_chat_id: str,
    allowed_chat_ids: tuple[str, ...],
) -> bool:
    return len(allowed_chat_ids) == 1 and allowed_chat_ids[0] == target_chat_id


def _record_delivery_audit(
    send_uow: TelegramSendRequestUnitOfWork,
    *,
    trace_id: str,
    actor: Actor,
    event_type: str,
    delivery: Stage07TelegramDeepLinkDelivery,
    request: TelegramSendRequest,
    extra: dict[str, object] | None = None,
) -> None:
    record_audit_event(
        send_uow.audit_session,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type="telegram_send_request",
        entity_id=request.id,
        after_state={
            "request_id": str(request.id),
            "delivery_id": str(delivery.id),
            "status": request.status,
            "dispatch_state": delivery.dispatch_state,
            "destination_kind": delivery.destination_kind,
            "destination_id": str(delivery.destination_id),
            **(extra or {}),
        },
    )
