from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Literal
from uuid import UUID

from app.models.stage07_telegram import Stage07TelegramDeepLink
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    get_view_presentation,
    read_record_for_actor,
)
from app.services.stage07_telegram_mini_app_identity import (
    ValidatedTelegramMiniAppLaunch,
)


TelegramDeepLinkKind = Literal["base", "view", "record", "record_change_draft"]


@dataclass(frozen=True)
class TelegramDeepLinkDestinationInput:
    kind: TelegramDeepLinkKind
    destination_id: UUID


@dataclass(frozen=True)
class MintedTelegramDeepLink:
    raw_token: str
    expires_at: datetime


@dataclass(frozen=True)
class ResolvedTelegramDeepLinkDestination:
    kind: TelegramDeepLinkKind
    workspace_id: UUID
    base_id: UUID | None = None
    table_id: UUID | None = None
    view_id: UUID | None = None
    record_id: UUID | None = None
    draft_id: UUID | None = None


def mint_telegram_deep_link(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    subject_telegram_user_id: str,
    source_telegram_chat_id: str,
    destination: TelegramDeepLinkDestinationInput,
    now: datetime,
) -> MintedTelegramDeepLink:
    identity = _identity_for_user_actor(actor)
    safe_destination = _resolve_destination_or_raise(uow, destination, identity)
    if not _has_current_source_binding(
        uow,
        workspace_id=safe_destination.workspace_id,
        telegram_user_id=subject_telegram_user_id,
        source_telegram_chat_id=source_telegram_chat_id,
        user_id=identity.user_id,
    ):
        raise PlatformValidationError(
            "telegram_deep_link_source_binding_invalid",
            "telegram_deep_link_source_binding_invalid",
        )
    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=10)
    link = Stage07TelegramDeepLink(
        token_hash=_hash_token(raw_token),
        workspace_id=safe_destination.workspace_id,
        subject_telegram_user_id=subject_telegram_user_id,
        source_telegram_chat_id=source_telegram_chat_id,
        destination_kind=destination.kind,
        destination_id=destination.destination_id,
        status="active",
        expires_at=expires_at,
        created_by_type=actor.actor_type,
        created_by_id=actor.actor_id,
    )
    uow.add_telegram_deep_link(link)
    _record_link_audit(
        uow,
        actor=actor,
        event_type="stage07.telegram_deep_link_minted",
        link=link,
        outcome="minted",
    )
    return MintedTelegramDeepLink(raw_token=raw_token, expires_at=expires_at)


def resolve_telegram_deep_link(
    uow: Stage06PlatformUnitOfWork,
    *,
    identity: Stage06RequestIdentity,
    launch: ValidatedTelegramMiniAppLaunch,
    start_param: str,
    now: datetime,
) -> ResolvedTelegramDeepLinkDestination | None:
    if start_param != launch.start_param:
        return None
    link = uow.get_active_telegram_deep_link_by_token_hash(
        _hash_token(start_param),
        now,
    )
    if link is None or link.subject_telegram_user_id != launch.telegram_user_id:
        return None
    if not _has_current_source_binding(
        uow,
        workspace_id=link.workspace_id,
        telegram_user_id=launch.telegram_user_id,
        source_telegram_chat_id=link.source_telegram_chat_id,
        user_id=identity.user_id,
    ):
        return None
    try:
        destination = _resolve_destination_or_raise(
            uow,
            TelegramDeepLinkDestinationInput(
                kind=link.destination_kind,
                destination_id=link.destination_id,
            ),
            identity,
            expected_workspace_id=link.workspace_id,
        )
    except (PlatformValidationError, Stage06AuthorizationError):
        return None
    _record_link_audit(
        uow,
        actor=Actor(actor_type="user", actor_id=identity.user_id, role="unknown"),
        event_type="stage07.telegram_deep_link_resolved",
        link=link,
        outcome="resolved",
    )
    return destination


def _resolve_destination_or_raise(
    uow: Stage06PlatformUnitOfWork,
    destination: TelegramDeepLinkDestinationInput,
    identity: Stage06RequestIdentity,
    *,
    expected_workspace_id: UUID | None = None,
) -> ResolvedTelegramDeepLinkDestination:
    if destination.kind == "base":
        base = _require_base(uow, destination.destination_id)
        _require_workspace(expected_workspace_id, base.workspace_id)
        authorize_workspace_action(uow, identity, base.workspace_id, "base.read")
        return ResolvedTelegramDeepLinkDestination(
            kind="base",
            workspace_id=base.workspace_id,
            base_id=base.id,
        )
    if destination.kind == "view":
        view = _require_view(uow, destination.destination_id)
        if view.table_id is None:
            raise PlatformValidationError("view_not_found", "view_not_found")
        table = _require_table(uow, view.table_id)
        base = _require_base(uow, view.base_id)
        if table.base_id != base.id:
            raise PlatformValidationError("resource_scope_mismatch", "view")
        _require_workspace(expected_workspace_id, base.workspace_id)
        actor = authorize_workspace_action(uow, identity, base.workspace_id, "record.read")
        get_view_presentation(uow, view.id, actor=actor)
        return ResolvedTelegramDeepLinkDestination(
            kind="view",
            workspace_id=base.workspace_id,
            base_id=base.id,
            table_id=table.id,
            view_id=view.id,
        )
    if destination.kind == "record":
        record = _require_record(uow, destination.destination_id)
        table = _require_table(uow, record.table_id)
        base = _require_base(uow, table.base_id)
        _require_workspace(expected_workspace_id, base.workspace_id)
        actor = authorize_workspace_action(uow, identity, base.workspace_id, "record.read")
        read_record_for_actor(uow, record.id, actor=actor)
        return ResolvedTelegramDeepLinkDestination(
            kind="record",
            workspace_id=base.workspace_id,
            base_id=base.id,
            table_id=table.id,
            record_id=record.id,
        )
    if destination.kind == "record_change_draft":
        draft = uow.get_record_change_draft(destination.destination_id)
        if draft is None:
            raise PlatformValidationError(
                "record_change_draft_not_found",
                "record_change_draft_not_found",
            )
        base = _require_base(uow, draft.base_id)
        table = _require_table(uow, draft.table_id)
        if table.base_id != base.id:
            raise PlatformValidationError("resource_scope_mismatch", "draft")
        if draft.record_id is not None:
            record = _require_record(uow, draft.record_id)
            if record.table_id != table.id:
                raise PlatformValidationError("resource_scope_mismatch", "draft")
        _require_workspace(expected_workspace_id, base.workspace_id)
        authorize_workspace_action(
            uow,
            identity,
            base.workspace_id,
            "record_change_draft.read",
        )
        return ResolvedTelegramDeepLinkDestination(
            kind="record_change_draft",
            workspace_id=base.workspace_id,
            base_id=base.id,
            table_id=table.id,
            record_id=draft.record_id,
            draft_id=draft.id,
        )
    raise PlatformValidationError("telegram_deep_link_destination_invalid", "kind")


def _identity_for_user_actor(actor: Actor) -> Stage06RequestIdentity:
    if actor.actor_type != "user":
        raise PlatformValidationError(
            "telegram_deep_link_mint_forbidden",
            "telegram_deep_link_mint_forbidden",
        )
    return Stage06RequestIdentity(user_id=actor.actor_id, source="verified_adapter")


def _has_current_source_binding(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    telegram_user_id: str,
    source_telegram_chat_id: str,
    user_id: str,
) -> bool:
    for binding in uow.list_telegram_bindings():
        if (
            binding.status != "active"
            or binding.workspace_id != workspace_id
            or binding.telegram_user_id != telegram_user_id
            or binding.telegram_chat_id != source_telegram_chat_id
            or binding.workspace_member_id is None
        ):
            continue
        member = uow.get_workspace_member(binding.workspace_member_id)
        if (
            member is not None
            and member.status == "active"
            and member.workspace_id == workspace_id
            and member.user_id == user_id
        ):
            return True
    return False


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


def _require_workspace(
    expected_workspace_id: UUID | None,
    actual_workspace_id: UUID,
) -> None:
    if expected_workspace_id is not None and actual_workspace_id != expected_workspace_id:
        raise PlatformValidationError("resource_scope_mismatch", "workspace")


def _require_base(uow: Stage06PlatformUnitOfWork, base_id: UUID):
    base = uow.get_base(base_id)
    if base is None:
        raise PlatformValidationError("base_not_found", "base_not_found")
    return base


def _require_table(uow: Stage06PlatformUnitOfWork, table_id: UUID):
    table = uow.get_table(table_id)
    if table is None:
        raise PlatformValidationError("table_not_found", "table_not_found")
    return table


def _require_view(uow: Stage06PlatformUnitOfWork, view_id: UUID):
    view = uow.get_view(view_id)
    if view is None:
        raise PlatformValidationError("view_not_found", "view_not_found")
    return view


def _require_record(uow: Stage06PlatformUnitOfWork, record_id: UUID):
    record = uow.get_record(record_id)
    if record is None:
        raise PlatformValidationError("record_not_found", "record_not_found")
    return record


def _record_link_audit(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    event_type: str,
    link: Stage07TelegramDeepLink,
    outcome: str,
) -> None:
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=f"stage07:telegram-deep-link:{link.id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type="telegram_deep_link",
        entity_id=link.id,
        after_state=sanitize_stage06_audit_state(
            {
                "outcome": outcome,
                "destination_kind": link.destination_kind,
                "destination_id": str(link.destination_id),
            }
        ),
    )
