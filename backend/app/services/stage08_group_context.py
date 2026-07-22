from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import exp, log
from typing import Final
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.runtime.stage08_context_contracts import ResolvedBusinessScope
from app.runtime.stage08_group_context_contracts import (
    GROUP_CONTEXT_COMPRESSION_THRESHOLD_CHARS,
    GROUP_CONTEXT_HISTORY_HALF_LIFE_DAYS,
    GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT,
    GROUP_CONTEXT_LATEST_RAW_CHARS,
    GROUP_CONTEXT_MAX_FRAGMENT_CHARS,
    GROUP_CONTEXT_MAX_FRAGMENTS,
    GROUP_CONTEXT_MAX_RAW_CHARS,
    GROUP_CONTEXT_RETENTION_DAYS,
    GroupContextBudgetUsage,
    GroupContextOmissionCounts,
    GroupContextPurgeResult,
    GroupContextWindowView,
    validate_group_context_purge_result,
    validate_group_context_window_view,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)
from app.services.stage08_context import resolve_business_scope


_ISSUER: Final[object] = object()
_EXPIRY_PURGE_BATCH_LIMIT = 120


class _GroupContextAuthority:
    __slots__ = (
        "_actor",
        "_workspace_id",
        "_employee_id",
        "_employee_version",
        "_binding_id",
        "_mapping_id",
        "_mapping_version",
        "_customer_id",
        "_customer_version",
        "_project_id",
        "_project_version",
        "_available",
        "_nonce",
    )

    def __init__(
        self,
        issuer: object,
        *,
        actor: Actor,
        workspace_id: UUID,
        employee_id: UUID,
        employee_version: int | None = None,
        binding_id: UUID | None = None,
        mapping_id: UUID | None = None,
        mapping_version: int | None = None,
        customer_id: UUID | None = None,
        customer_version: int | None = None,
        project_id: UUID | None = None,
        project_version: int | None = None,
        available: bool = False,
    ) -> None:
        if issuer is not _ISSUER:
            raise TypeError("group_context_authority_private")
        self._actor = actor
        self._workspace_id = workspace_id
        self._employee_id = employee_id
        self._employee_version = employee_version
        self._binding_id = binding_id
        self._mapping_id = mapping_id
        self._mapping_version = mapping_version
        self._customer_id = customer_id
        self._customer_version = customer_version
        self._project_id = project_id
        self._project_version = project_version
        self._available = available
        self._nonce = uuid4()

    def __repr__(self) -> str:
        return "<_GroupContextAuthority opaque>"


class _GroupProjectionHandle:
    __slots__ = ("_authority_nonce", "_projection_id", "_mapping_id")

    def __init__(
        self,
        issuer: object,
        *,
        authority_nonce: UUID,
        projection_id: UUID,
        mapping_id: UUID,
    ) -> None:
        if issuer is not _ISSUER:
            raise TypeError("group_context_projection_handle_private")
        self._authority_nonce = authority_nonce
        self._projection_id = projection_id
        self._mapping_id = mapping_id

    def __repr__(self) -> str:
        return "<_GroupProjectionHandle opaque>"


class _SelectedGroupContextFragment:
    __slots__ = (
        "_text",
        "label",
        "source_type",
        "display_id",
        "scope_categories",
    )

    def __init__(self, *, text: str, display_id: str) -> None:
        self._text = text
        self.label = "group_context"
        self.source_type = "group_message_fragment"
        self.display_id = display_id
        self.scope_categories = (
            "workspace",
            "group",
            "customer",
            "project",
        )

    def __repr__(self) -> str:
        return (
            "<_SelectedGroupContextFragment "
            f"display_id={self.display_id!r} chars={len(self._text)}>"
        )


class _GroupContextWindow:
    __slots__ = ("_authority_nonce", "_projection_handles", "_view")

    def __init__(
        self,
        *,
        authority_nonce: UUID | None,
        projection_handles: tuple[_GroupProjectionHandle, ...],
        view: GroupContextWindowView,
    ) -> None:
        self._authority_nonce = authority_nonce
        self._projection_handles = projection_handles
        self._view = validate_group_context_window_view(view)

    def view(self) -> GroupContextWindowView:
        return validate_group_context_window_view(self._view)

    def __repr__(self) -> str:
        return f"<_GroupContextWindow status={self._view.status!r}>"


class _GroupContextMaterialization:
    __slots__ = ("_available", "_fragments")

    def __init__(
        self,
        *,
        available: bool,
        fragments: tuple[_SelectedGroupContextFragment, ...],
    ) -> None:
        self._available = available
        self._fragments = fragments

    def __repr__(self) -> str:
        return (
            "<_GroupContextMaterialization "
            f"available={self._available!r} count={len(self._fragments)}>"
        )


class Stage08GroupContextAuthorityFactory:
    @staticmethod
    def build(
        uow: Stage06PlatformUnitOfWork,
        *,
        actor: Actor,
        employee_id: UUID,
        workspace_id: UUID,
    ) -> _GroupContextAuthority:
        try:
            workspace = uow.get_workspace(workspace_id)
            if (
                workspace is None
                or workspace.status != "active"
                or actor.actor_type != "user"
            ):
                raise ValueError
            members = [
                member
                for member in uow.list_workspace_members(workspace_id)
                if member.user_id == actor.actor_id and member.status == "active"
            ]
            if len(members) != 1:
                raise ValueError
            member = members[0]
            employee = uow.get_digital_employee(employee_id)
            if (
                employee is None
                or employee.status != "active"
                or employee.workspace_id != workspace_id
                or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
            ):
                raise ValueError
            base = uow.get_base(employee.base_id)
            if (
                base is None
                or base.status != "active"
                or base.workspace_id != workspace_id
            ):
                raise ValueError
            table_ids = _strict_uuid_set(employee.accessible_tables)
            if any(
                (table := uow.get_table(table_id)) is None
                or table.status != "active"
                or table.base_id != employee.base_id
                for table_id in table_ids
            ):
                raise ValueError
            bindings = [
                binding
                for binding in uow.list_telegram_bindings()
                if binding.workspace_id == workspace_id
                and binding.workspace_member_id == member.id
                and binding.status == "active"
                and binding.binding_type == "chat_user"
                and isinstance(binding.telegram_chat_id, str)
                and bool(binding.telegram_chat_id)
                and isinstance(binding.telegram_user_id, str)
                and bool(binding.telegram_user_id)
            ]
            if len(bindings) != 1:
                raise ValueError
            binding = bindings[0]
            mappings = [
                mapping
                for mapping in uow.list_group_business_context_bindings(binding.id)
                if mapping.status == "active" and mapping.workspace_id == workspace_id
            ]
            if len(mappings) != 1:
                raise ValueError
            mapping = mappings[0]
            customer = _require_mapping_record(
                uow,
                mapping.customer_record_id,
                workspace_id=workspace_id,
                employee_base_id=employee.base_id,
                table_ids=table_ids,
            )
            project = _require_mapping_record(
                uow,
                mapping.project_record_id,
                workspace_id=workspace_id,
                employee_base_id=employee.base_id,
                table_ids=table_ids,
            )
            resolved = resolve_business_scope(
                uow,
                workspace_id=workspace_id,
                employee_id=employee_id,
                actor=actor,
                customer_record_id=customer.id,
                project_record_id=project.id,
            )
            if resolved.relation_kind != "visible_linked_record":
                raise ValueError
            return _GroupContextAuthority(
                _ISSUER,
                actor=actor,
                workspace_id=workspace_id,
                employee_id=employee_id,
                employee_version=employee.version,
                binding_id=binding.id,
                mapping_id=mapping.id,
                mapping_version=mapping.mapping_version,
                customer_id=customer.id,
                customer_version=customer.version,
                project_id=project.id,
                project_version=project.version,
                available=True,
            )
        except (PlatformValidationError, TypeError, ValueError, AttributeError):
            return _GroupContextAuthority(
                _ISSUER,
                actor=actor,
                workspace_id=workspace_id,
                employee_id=employee_id,
            )


def build_group_context_window(
    uow: Stage06PlatformUnitOfWork,
    authority: _GroupContextAuthority,
    *,
    business_scope: ResolvedBusinessScope,
    now: datetime,
) -> _GroupContextWindow:
    _require_utc_now(now)
    current = _revalidate_authority(uow, authority)
    scope = _validate_business_scope(business_scope)
    if current is None or scope is None or not _scope_matches(current, scope):
        return _unavailable_window()

    event_cutoff = now - timedelta(days=GROUP_CONTEXT_RETENTION_DAYS)
    age_omissions, limit_omissions = (
        uow.count_group_message_projection_window_omissions(
            current._mapping_id,
            now=now,
            event_cutoff=event_cutoff,
            eligible_limit=GROUP_CONTEXT_MAX_FRAGMENTS,
        )
    )
    eligible = uow.list_eligible_group_message_projections_for_window(
        current._mapping_id,
        now=now,
        event_cutoff=event_cutoff,
        limit=GROUP_CONTEXT_MAX_FRAGMENTS,
    )
    eligible.sort(key=lambda item: (item.event_at, item.id), reverse=True)

    selected: list[object] = []
    latest_selected_count = 0
    omissions = {
        "expired": age_omissions,
        "latest_band_limit": 0,
        "fragment_limit": limit_omissions,
        "character_limit": 0,
    }
    latest_chars = 0
    for projection in eligible[:GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT]:
        chars = len(projection.content_fragment)
        if chars > GROUP_CONTEXT_MAX_FRAGMENT_CHARS:
            omissions["character_limit"] += 1
            continue
        if latest_chars + chars > GROUP_CONTEXT_LATEST_RAW_CHARS:
            omissions["latest_band_limit"] += 1
            continue
        selected.append(projection)
        latest_chars += chars
        latest_selected_count += 1

    history = eligible[GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT:]
    history.sort(
        key=lambda item: (
            _time_decay_score(item.event_at, now),
            item.event_at,
            item.id,
        ),
        reverse=True,
    )
    total_chars = latest_chars
    history_selected_count = 0
    for projection in history:
        chars = len(projection.content_fragment)
        if chars > GROUP_CONTEXT_MAX_FRAGMENT_CHARS:
            omissions["character_limit"] += 1
        elif history_selected_count >= (
            GROUP_CONTEXT_MAX_FRAGMENTS - GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT
        ):
            omissions["fragment_limit"] += 1
        elif total_chars + chars > GROUP_CONTEXT_MAX_RAW_CHARS:
            omissions["character_limit"] += 1
        else:
            selected.append(projection)
            total_chars += chars
            history_selected_count += 1

    handles = tuple(
        _GroupProjectionHandle(
            _ISSUER,
            authority_nonce=authority._nonce,
            projection_id=projection.id,
            mapping_id=current._mapping_id,
        )
        for projection in selected
    )
    omission_counts = GroupContextOmissionCounts(**omissions)
    if not selected:
        status = "group_context_unavailable"
    else:
        status = (
            "group_context_partial"
            if omission_counts.total
            else "group_context_available"
        )
    view = GroupContextWindowView(
        contract_version="stage08-group-context-window.v1",
        status=status,
        usage=GroupContextBudgetUsage(
            considered_fragments=(
                len(eligible) + age_omissions + limit_omissions
            ),
            selected_fragments=len(selected),
            latest_selected_fragments=latest_selected_count,
            history_selected_fragments=history_selected_count,
            raw_selected_chars=total_chars,
        ),
        omissions=omission_counts,
        compression_required=(
            total_chars > GROUP_CONTEXT_COMPRESSION_THRESHOLD_CHARS
        ),
    )
    return _GroupContextWindow(
        authority_nonce=authority._nonce,
        projection_handles=handles,
        view=view,
    )


def _materialize_group_context_window(
    uow: Stage06PlatformUnitOfWork,
    authority: _GroupContextAuthority,
    window: _GroupContextWindow,
    *,
    business_scope: ResolvedBusinessScope,
    now: datetime,
) -> _GroupContextMaterialization:
    _require_utc_now(now)
    if not isinstance(window, _GroupContextWindow):
        return _unavailable_materialization()
    current = _revalidate_authority(uow, authority)
    scope = _validate_business_scope(business_scope)
    if (
        current is None
        or scope is None
        or not _scope_matches(current, scope)
        or window._authority_nonce != authority._nonce
    ):
        return _unavailable_materialization()
    fragments: list[_SelectedGroupContextFragment] = []
    event_cutoff = now - timedelta(days=GROUP_CONTEXT_RETENTION_DAYS)
    for index, handle in enumerate(window._projection_handles, start=1):
        if (
            not isinstance(handle, _GroupProjectionHandle)
            or handle._authority_nonce != authority._nonce
            or handle._mapping_id != current._mapping_id
        ):
            return _unavailable_materialization()
        projection = (
            uow.get_eligible_group_message_projection_for_materialization(
                handle._projection_id,
                current._mapping_id,
                now=now,
                event_cutoff=event_cutoff,
            )
        )
        if (
            projection is None
            or len(projection.content_fragment) > GROUP_CONTEXT_MAX_FRAGMENT_CHARS
        ):
            return _unavailable_materialization()
        fragments.append(
            _SelectedGroupContextFragment(
                text=projection.content_fragment,
                display_id=f"group_context:{index:02d}",
            )
        )
    return _GroupContextMaterialization(
        available=bool(fragments),
        fragments=tuple(fragments),
    )


def purge_group_context_projection(
    uow: Stage06PlatformUnitOfWork,
    authority: _GroupContextAuthority,
    *,
    projection_handle: _GroupProjectionHandle,
    now: datetime,
) -> GroupContextPurgeResult:
    _require_utc_now(now)
    if not isinstance(projection_handle, _GroupProjectionHandle):
        return _purge_result(0)
    current = _revalidate_authority(uow, authority)
    if (
        current is None
        or projection_handle._authority_nonce != authority._nonce
        or projection_handle._mapping_id != current._mapping_id
    ):
        return _purge_result(0)
    projection = uow.lock_group_message_projection_for_lifecycle(
        projection_handle._projection_id
    )
    if (
        projection is None
        or projection.business_context_binding_id != current._mapping_id
        or projection.lifecycle_status == "purged"
    ):
        return _purge_result(0)
    if projection.lifecycle_status not in {"active", "superseded"}:
        return _purge_result(0)
    projection.content_fragment = ""
    projection.lifecycle_status = "purged"
    return _purge_result(1)


def purge_expired_group_context_projections(
    uow: Stage06PlatformUnitOfWork,
    *,
    now: datetime,
) -> GroupContextPurgeResult:
    _require_utc_now(now)
    projections = uow.lock_expired_active_group_message_projections(
        now=now,
        event_cutoff=now - timedelta(days=GROUP_CONTEXT_RETENTION_DAYS),
        limit=_EXPIRY_PURGE_BATCH_LIMIT,
    )
    purged = 0
    for projection in projections:
        if (
            projection.lifecycle_status == "active"
            and projection.content_fragment
            and (
                projection.retention_expires_at <= now
                or projection.event_at
                <= now - timedelta(days=GROUP_CONTEXT_RETENTION_DAYS)
            )
        ):
            projection.content_fragment = ""
            projection.lifecycle_status = "purged"
            purged += 1
    return _purge_result(purged)


def _revalidate_authority(
    uow: Stage06PlatformUnitOfWork,
    authority: object,
) -> _GroupContextAuthority | None:
    if not isinstance(authority, _GroupContextAuthority) or not authority._available:
        return None
    current = Stage08GroupContextAuthorityFactory.build(
        uow,
        actor=authority._actor,
        employee_id=authority._employee_id,
        workspace_id=authority._workspace_id,
    )
    signature = (
        "_employee_version",
        "_binding_id",
        "_mapping_id",
        "_mapping_version",
        "_customer_id",
        "_customer_version",
        "_project_id",
        "_project_version",
    )
    if not current._available or any(
        getattr(current, field) != getattr(authority, field) for field in signature
    ):
        return None
    return current


def _validate_business_scope(
    business_scope: object,
) -> ResolvedBusinessScope | None:
    if not isinstance(business_scope, ResolvedBusinessScope):
        return None
    try:
        return ResolvedBusinessScope.model_validate(
            business_scope.model_dump(mode="python")
        )
    except ValidationError:
        return None


def _scope_matches(
    authority: _GroupContextAuthority,
    scope: ResolvedBusinessScope,
) -> bool:
    return (
        scope.workspace_id == authority._workspace_id
        and scope.customer_record_id == authority._customer_id
        and scope.customer_version == authority._customer_version
        and scope.project_record_id == authority._project_id
        and scope.project_version == authority._project_version
        and scope.relation_kind == "visible_linked_record"
    )


def _strict_uuid_set(values: object) -> set[UUID]:
    if not isinstance(values, list):
        raise ValueError
    parsed: list[UUID] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError
        parsed.append(UUID(value))
    if len(parsed) != len(set(parsed)):
        raise ValueError
    return set(parsed)


def _require_mapping_record(
    uow: Stage06PlatformUnitOfWork,
    record_id: UUID,
    *,
    workspace_id: UUID,
    employee_base_id: UUID,
    table_ids: set[UUID],
):
    record = uow.get_record(record_id)
    if (
        record is None
        or record.record_status != "active"
        or record.table_id not in table_ids
    ):
        raise ValueError
    table = uow.get_table(record.table_id)
    base = None if table is None else uow.get_base(table.base_id)
    if (
        table is None
        or table.status != "active"
        or table.base_id != employee_base_id
        or base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
    ):
        raise ValueError
    return record


def _require_utc_now(now: datetime) -> None:
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
        or now.utcoffset().total_seconds() != 0
    ):
        raise PlatformValidationError(
            "group_context_now_invalid", "group_context_now_invalid"
        )


def _time_decay_score(event_at: datetime, now: datetime) -> float:
    age_seconds = max(0.0, (now - event_at.astimezone(UTC)).total_seconds())
    half_life_seconds = GROUP_CONTEXT_HISTORY_HALF_LIFE_DAYS * 86_400
    return exp(-log(2.0) * age_seconds / half_life_seconds)


def _unavailable_window() -> _GroupContextWindow:
    return _GroupContextWindow(
        authority_nonce=None,
        projection_handles=(),
        view=GroupContextWindowView(
            contract_version="stage08-group-context-window.v1",
            status="group_context_unavailable",
            usage=GroupContextBudgetUsage(
                considered_fragments=0,
                selected_fragments=0,
                latest_selected_fragments=0,
                history_selected_fragments=0,
                raw_selected_chars=0,
            ),
            omissions=GroupContextOmissionCounts(
                expired=0,
                latest_band_limit=0,
                fragment_limit=0,
                character_limit=0,
            ),
            compression_required=False,
        ),
    )


def _unavailable_materialization() -> _GroupContextMaterialization:
    return _GroupContextMaterialization(available=False, fragments=())


def _purge_result(count: int) -> GroupContextPurgeResult:
    return validate_group_context_purge_result(
        GroupContextPurgeResult(
            contract_version="stage08-group-context-purge.v1",
            purged_count=count,
        )
    )
