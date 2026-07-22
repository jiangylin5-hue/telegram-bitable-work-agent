from __future__ import annotations

from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.runtime.stage08_memory_contracts import MemoryScopeProjection, MemorySourceRef
from app.services.stage06_platform import Stage06PlatformUnitOfWork


GroupChatKind: TypeAlias = Literal["group", "supergroup"]
GroupMemorySourceState: TypeAlias = Literal["active", "revoked", "missing"]


class TrustedGroupMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message_id: UUID
    chat_id: StrictStr = Field(min_length=1, max_length=120)
    chat_type: GroupChatKind
    binding_id: UUID


class GroupMemorySourceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref: MemorySourceRef
    scope: MemoryScopeProjection
    binding_id: UUID


def resolve_authorized_group_message_source(
    uow: Stage06PlatformUnitOfWork,
    source: TrustedGroupMessageInput,
) -> GroupMemorySourceProjection | None:
    binding = next(
        (item for item in uow.list_telegram_bindings() if item.id == source.binding_id),
        None,
    )
    if (
        binding is None
        or binding.status != "active"
        or binding.binding_type != "chat_user"
        or binding.workspace_member_id is None
        or binding.telegram_chat_id != source.chat_id
    ):
        return None
    workspace = uow.get_workspace(binding.workspace_id)
    member = uow.get_workspace_member(binding.workspace_member_id)
    if (
        workspace is None
        or workspace.status != "active"
        or member is None
        or member.workspace_id != binding.workspace_id
        or member.status != "active"
    ):
        return None
    return GroupMemorySourceProjection(
        source_ref=MemorySourceRef(
            source_kind="telegram_message",
            source_id=source.message_id,
            source_version=None,
            field_keys=("group_candidate_projection",),
        ),
        scope=MemoryScopeProjection(
            workspace_id=binding.workspace_id,
            group_chat_ref=f"stage06-binding:{binding.id}",
        ),
        binding_id=binding.id,
    )


def validate_group_memory_source_projection(
    uow: Stage06PlatformUnitOfWork,
    *,
    scope: MemoryScopeProjection,
    source_ref: MemorySourceRef,
) -> GroupMemorySourceState:
    group_chat_ref = scope.group_chat_ref
    if group_chat_ref is None or not group_chat_ref.startswith("stage06-binding:"):
        return "missing"
    try:
        binding_id = UUID(group_chat_ref.removeprefix("stage06-binding:"))
    except ValueError:
        return "missing"
    if (
        group_chat_ref != f"stage06-binding:{binding_id}"
        or source_ref.source_kind != "telegram_message"
        or source_ref.source_version is not None
        or source_ref.field_keys != ("group_candidate_projection",)
    ):
        return "missing"
    binding = next(
        (item for item in uow.list_telegram_bindings() if item.id == binding_id),
        None,
    )
    if binding is None or binding.workspace_id != scope.workspace_id:
        return "missing"
    if (
        binding.status != "active"
        or binding.binding_type != "chat_user"
        or binding.workspace_member_id is None
    ):
        return "revoked"
    workspace = uow.get_workspace(binding.workspace_id)
    member = uow.get_workspace_member(binding.workspace_member_id)
    if (
        workspace is None
        or workspace.status != "active"
        or member is None
        or member.workspace_id != binding.workspace_id
        or member.status != "active"
    ):
        return "revoked"
    return "active"
