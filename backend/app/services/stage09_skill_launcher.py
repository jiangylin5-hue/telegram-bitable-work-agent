from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.agents.stage06_skills import (
    STAGE06_SKILL_MANIFEST_VERSION,
    get_stage06_skill_manifest,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    can_actor_write_record_fields,
    get_view_presentation,
    read_record_for_actor,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)
from app.services.stage08_collaboration import _employee_field_is_current
from app.services.stage08_group_context import Stage08GroupContextAuthorityFactory


SkillDisabledReason = Literal[
    "context_required",
    "read_scope_unavailable",
    "write_scope_unavailable",
    "chat_scope_unavailable",
    "runtime_unsupported",
]


@dataclass(frozen=True, slots=True)
class _SkillPresentationDefinition:
    skill_id: str
    label: str
    description: str
    supported_intents: tuple[str, ...]
    read_scope: Literal["table", "telegram"]


@dataclass(frozen=True, slots=True)
class Stage09SkillCatalogItem:
    skill_id: str
    label: str
    description: str
    enabled: bool
    disabled_reason: SkillDisabledReason | None
    supported_intents: tuple[str, ...]
    supported_actions: tuple[str, ...]
    confirmation_policy: Literal["read_only", "draft_required_for_write"]


@dataclass(frozen=True, slots=True)
class Stage09SkillCatalog:
    manifest_version: str
    default_selection: Literal["auto"]
    skills: tuple[Stage09SkillCatalogItem, ...]


_PUBLIC_SKILLS: tuple[_SkillPresentationDefinition, ...] = (
    _SkillPresentationDefinition(
        skill_id="platform-base",
        label="查表问答",
        description="基于已授权表格、视图与记录回答问题",
        supported_intents=("business_fact", "mixed"),
        read_scope="table",
    ),
    _SkillPresentationDefinition(
        skill_id="platform-tabular-analysis",
        label="汇总分析",
        description="基于已授权表格与视图整理结论",
        supported_intents=("business_fact", "mixed"),
        read_scope="table",
    ),
    _SkillPresentationDefinition(
        skill_id="platform-task",
        label="待办梳理",
        description="基于已授权记录梳理待办与后续行动",
        supported_intents=("business_fact", "mixed"),
        read_scope="table",
    ),
    _SkillPresentationDefinition(
        skill_id="platform-telegram-im",
        label="群聊上下文",
        description="基于当前受控群聊上下文整理结论",
        supported_intents=("mixed",),
        read_scope="telegram",
    ),
)


def resolve_stage09_skill_catalog(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    target_record_id: UUID | None,
    actor: Actor,
) -> Stage09SkillCatalog:
    """Return a safe, non-authoritative snapshot of public launcher capability."""
    employee = _require_current_employee_scope(
        uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
    )
    has_table_read_scope = _has_current_table_read_scope(uow, employee, actor)
    has_telegram_scope = _has_current_telegram_scope(
        uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
    )
    has_draft_scope = _has_current_draft_scope(
        uow,
        employee=employee,
        target_record_id=target_record_id,
        actor=actor,
    )
    return Stage09SkillCatalog(
        manifest_version=STAGE06_SKILL_MANIFEST_VERSION,
        default_selection="auto",
        skills=tuple(
            _catalog_item(
                definition,
                has_table_read_scope=has_table_read_scope,
                has_telegram_scope=has_telegram_scope,
                has_draft_scope=has_draft_scope,
            )
            for definition in _PUBLIC_SKILLS
        ),
    )


def _catalog_item(
    definition: _SkillPresentationDefinition,
    *,
    has_table_read_scope: bool,
    has_telegram_scope: bool,
    has_draft_scope: bool,
) -> Stage09SkillCatalogItem:
    manifest = get_stage06_skill_manifest(definition.skill_id)
    if manifest.status != "active":
        return Stage09SkillCatalogItem(
            skill_id=definition.skill_id,
            label=definition.label,
            description=definition.description,
            enabled=False,
            disabled_reason="runtime_unsupported",
            supported_intents=definition.supported_intents,
            supported_actions=(),
            confirmation_policy="read_only",
        )
    if definition.read_scope == "telegram":
        if not has_telegram_scope:
            return Stage09SkillCatalogItem(
                skill_id=definition.skill_id,
                label=definition.label,
                description=definition.description,
                enabled=False,
                disabled_reason="chat_scope_unavailable",
                supported_intents=definition.supported_intents,
                supported_actions=("read_only",),
                confirmation_policy="read_only",
            )
        return Stage09SkillCatalogItem(
            skill_id=definition.skill_id,
            label=definition.label,
            description=definition.description,
            enabled=True,
            disabled_reason=None,
            supported_intents=definition.supported_intents,
            supported_actions=("read_only",),
            confirmation_policy="read_only",
        )
    if not has_table_read_scope:
        return Stage09SkillCatalogItem(
            skill_id=definition.skill_id,
            label=definition.label,
            description=definition.description,
            enabled=False,
            disabled_reason="read_scope_unavailable",
            supported_intents=definition.supported_intents,
            supported_actions=("read_only",),
            confirmation_policy="read_only",
        )
    supports_draft = definition.skill_id in {"platform-base", "platform-task"}
    actions = (
        ("read_only", "draft_update")
        if supports_draft and has_draft_scope
        else ("read_only",)
    )
    return Stage09SkillCatalogItem(
        skill_id=definition.skill_id,
        label=definition.label,
        description=definition.description,
        enabled=True,
        disabled_reason=None,
        supported_intents=definition.supported_intents,
        supported_actions=actions,
        confirmation_policy=(
            "draft_required_for_write" if len(actions) > 1 else "read_only"
        ),
    )


def _require_current_employee_scope(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
) -> object:
    workspace = uow.get_workspace(workspace_id)
    if workspace is None:
        raise PlatformValidationError(
            "stage08_collaboration_workspace_not_found",
            "stage08_collaboration_workspace_not_found",
        )
    employee = uow.get_digital_employee(employee_id)
    if employee is None or employee.workspace_id != workspace_id:
        raise PlatformValidationError(
            "stage08_collaboration_employee_not_found",
            "stage08_collaboration_employee_not_found",
        )
    base = uow.get_base(employee.base_id)
    active_members = [
        member
        for member in uow.list_workspace_members(workspace_id)
        if member.user_id == actor.actor_id and member.status == "active"
    ]
    if (
        workspace.status != "active"
        or employee.status != "active"
        or base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
        or len(active_members) != 1
        or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
        or not _is_valid_employee_scope(uow, employee)
    ):
        raise PlatformValidationError(
            "stage09_skill_catalog_scope_denied",
            "stage09_skill_catalog_scope_denied",
        )
    return employee


def _is_valid_employee_scope(
    uow: Stage06PlatformUnitOfWork,
    employee: object,
) -> bool:
    for attribute in ("allowed_actions", "accessible_tables", "accessible_views"):
        values = getattr(employee, attribute, None)
        if (
            not isinstance(values, list)
            or not all(isinstance(value, str) for value in values)
            or len(values) != len(set(values))
        ):
            return False
    try:
        table_ids = {UUID(value) for value in employee.accessible_tables}
        view_ids = tuple(UUID(value) for value in employee.accessible_views)
    except (TypeError, ValueError, AttributeError):
        return False
    for table_id in table_ids:
        table = uow.get_table(table_id)
        if (
            table is None
            or table.status != "active"
            or table.base_id != employee.base_id
        ):
            return False
    for view_id in view_ids:
        view = uow.get_view(view_id)
        if (
            view is None
            or view.status != "active"
            or view.base_id != employee.base_id
            or view.table_id is None
            or view.table_id not in table_ids
        ):
            return False
    return True


def _has_current_table_read_scope(
    uow: Stage06PlatformUnitOfWork,
    employee: object,
    actor: Actor,
) -> bool:
    if not {"query", "summarize"}.intersection(employee.allowed_actions):
        return False
    table_ids = {UUID(value) for value in employee.accessible_tables}
    for value in employee.accessible_views:
        view = uow.get_view(UUID(value))
        if (
            view is None
            or view.status != "active"
            or view.table_id is None
            or view.table_id not in table_ids
            or view.base_id != employee.base_id
        ):
            continue
        table = uow.get_table(view.table_id)
        if table is None or table.status != "active" or table.base_id != employee.base_id:
            continue
        try:
            presentation = get_view_presentation(uow, view.id, actor=actor)
        except PlatformValidationError:
            continue
        if presentation.get("visible_field_keys"):
            return True
    return False


def _has_current_telegram_scope(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
) -> bool:
    authority = Stage08GroupContextAuthorityFactory.build(
        uow,
        actor=actor,
        employee_id=employee_id,
        workspace_id=workspace_id,
    )
    return bool(getattr(authority, "_available", False))


def _has_current_draft_scope(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee: object,
    target_record_id: UUID | None,
    actor: Actor,
) -> bool:
    if target_record_id is None or "draft_update" not in employee.allowed_actions:
        return False
    record = uow.get_record(target_record_id)
    if record is None or record.record_status != "active":
        return False
    table = uow.get_table(record.table_id)
    if (
        table is None
        or table.status != "active"
        or table.base_id != employee.base_id
        or str(table.id) not in set(employee.accessible_tables)
    ):
        return False
    try:
        if read_record_for_actor(uow, target_record_id, actor=actor).get("record_status") != "active":
            return False
    except PlatformValidationError:
        return False
    writable_fields = _employee_writable_field_keys(employee)
    if not writable_fields:
        return False
    return any(
        _employee_field_is_current(
            uow,
            employee,
            table_id=table.id,
            field_key=field_key,
        )
        and can_actor_write_record_fields(uow, table.id, [field_key], actor=actor)
        for field_key in writable_fields
    )


def _employee_writable_field_keys(employee: object) -> tuple[str, ...]:
    policy = getattr(employee, "field_policy", None)
    keys = policy.get("writable_fields") if isinstance(policy, dict) else None
    if (
        not isinstance(keys, list)
        or not keys
        or not all(isinstance(value, str) and value for value in keys)
        or len(keys) != len(set(keys))
    ):
        return ()
    return tuple(keys)


__all__ = [
    "SkillDisabledReason",
    "Stage09SkillCatalog",
    "Stage09SkillCatalogItem",
    "resolve_stage09_skill_catalog",
]
