from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
import json
import math
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.runtime.stage08_context_contracts import (
    ContextBudgetUsage,
    ContextOmission,
    ContextPack,
    ContextPlan,
    ContextPlanningRequest,
    ContextSourceKind,
    ContextSourcePlan,
    EvidenceItem,
    EvidenceScope,
    EvidenceVersion,
    JsonValue,
    ResolvedBusinessScope,
    _UUID_FRAGMENT_RE,
    _is_internal_identifier_key,
    _is_sensitive_metadata_key,
    validate_context_pack,
    validate_context_plan,
    validate_context_request,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    get_view_presentation,
    list_view_records,
    read_record_for_actor,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)
from app.services.stage08_memory import read_memory_projection


_CONTRACT_VERSION_NUMBER = 1


def resolve_business_scope(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
    customer_record_id: UUID | None,
    project_record_id: UUID | None,
) -> ResolvedBusinessScope:
    _, employee, table_ids, _ = _require_current_authority(
        uow,
        workspace_id=workspace_id,
        employee_id=employee_id,
        actor=actor,
    )
    del employee
    customer = _read_scoped_record(
        uow,
        customer_record_id,
        workspace_id=workspace_id,
        table_ids=table_ids,
        actor=actor,
    )
    project = _read_scoped_record(
        uow,
        project_record_id,
        workspace_id=workspace_id,
        table_ids=table_ids,
        actor=actor,
    )
    if customer is not None and project is not None:
        if customer_record_id == project_record_id or not (
            _visible_link_exists(uow, customer, project_record_id, actor)
            or _visible_link_exists(uow, project, customer_record_id, actor)
        ):
            _deny("context_business_scope_denied")
        relation_kind = "visible_linked_record"
    elif customer is not None or project is not None:
        relation_kind = "single_record"
    else:
        relation_kind = "none"
    return ResolvedBusinessScope(
        workspace_id=workspace_id,
        customer_record_id=customer_record_id,
        customer_version=None if customer is None else customer["version"],
        project_record_id=project_record_id,
        project_version=None if project is None else project["version"],
        relation_kind=relation_kind,
    )


def build_context_plan(
    uow: Stage06PlatformUnitOfWork,
    request: ContextPlanningRequest,
    *,
    actor: Actor,
) -> ContextPlan:
    """Compile bounded source choices; a ContextPlan is not an authority token or ticket."""

    try:
        request = validate_context_request(request)
    except ValidationError as exc:
        raise PlatformValidationError("context_request_invalid", "context_request_invalid") from exc
    _, employee, table_ids, view_ids = _require_current_authority(
        uow,
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        actor=actor,
    )
    business_scope = resolve_business_scope(
        uow,
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        actor=actor,
        customer_record_id=request.customer_record_id,
        project_record_id=request.project_record_id,
    )
    sources: list[ContextSourcePlan] = []
    if request.intent in {"business_fact", "mixed"}:
        actions = employee.allowed_actions
        if (
            not isinstance(actions, list)
            or not all(isinstance(value, str) for value in actions)
            or not {"query", "summarize"}.intersection(actions)
        ):
            _deny("context_authority_denied")
        allocation_base, allocation_extra = divmod(
            request.budget.max_table_records, len(request.view_ids)
        )
        for index, view_id in enumerate(request.view_ids):
            view = _require_current_view(
                uow,
                view_id,
                workspace_id=request.workspace_id,
                table_ids=table_ids,
                view_ids=view_ids,
                actor=actor,
            )
            sources.append(
                ContextSourcePlan(
                    source_kind="table_view",
                    priority=1,
                    view_id=view.id,
                    source_version=view.version,
                    max_items=allocation_base + (1 if index < allocation_extra else 0),
                    reason_code="business_fact_requested",
                )
            )
    if request.intent in {"memory_lookup", "mixed"}:
        sources.append(
            ContextSourcePlan(
                source_kind="business_memory",
                priority=2,
                max_items=request.budget.max_memory_items,
                reason_code="memory_requested",
            )
        )
    if request.intent == "general_advice" or request.allow_general_advice:
        sources.append(
            ContextSourcePlan(
                source_kind="general_advice",
                priority=3 if request.intent != "general_advice" else 1,
                max_items=1,
                reason_code=(
                    "general_advice_requested"
                    if request.intent == "general_advice"
                    else "general_advice_fallback_allowed"
                ),
            )
        )
    return ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        actor_user_id=actor.actor_id,
        intent=request.intent,
        business_scope=business_scope,
        budget=request.budget,
        sources=tuple(sources),
    )


def compose_context_pack(
    uow: Stage06PlatformUnitOfWork,
    plan: ContextPlan,
    *,
    actor: Actor,
    now: datetime,
) -> ContextPack:
    try:
        plan = validate_context_plan(plan)
    except ValidationError as exc:
        raise PlatformValidationError("context_plan_invalid", "context_plan_invalid") from exc
    omissions = _OmissionAccumulator()
    if actor.actor_id != plan.actor_user_id:
        omissions.add("general_advice", "authority_changed")
        return _make_pack(plan, [], omissions, 0, 0, 0, 0)
    try:
        _, employee, table_ids, view_ids = _require_current_authority(
            uow,
            workspace_id=plan.workspace_id,
            employee_id=plan.employee_id,
            actor=actor,
        )
    except PlatformValidationError:
        omissions.add("general_advice", "authority_changed")
        return _make_pack(plan, [], omissions, 0, 0, 0, 0)
    try:
        current_scope = resolve_business_scope(
            uow,
            workspace_id=plan.workspace_id,
            employee_id=plan.employee_id,
            actor=actor,
            customer_record_id=plan.business_scope.customer_record_id,
            project_record_id=plan.business_scope.project_record_id,
        )
    except PlatformValidationError:
        omissions.add("general_advice", "business_scope_changed")
        return _fallback_pack(plan, omissions)
    if current_scope != plan.business_scope:
        omissions.add("general_advice", "business_scope_changed")
        return _fallback_pack(plan, omissions)

    candidates: list[_EvidenceCandidate] = []
    table_considered = 0
    memory_considered = 0
    for source in plan.sources:
        if source.source_kind == "table_view":
            remaining_table_records = plan.budget.max_table_records - table_considered
            if source.max_items <= 0 or remaining_table_records <= 0:
                omissions.add("table_view", "source_limit_reached")
                continue
            if not {"query", "summarize"}.intersection(employee.allowed_actions):
                omissions.add("table_view", "authority_changed")
                continue
            try:
                view = _require_current_view(
                    uow,
                    source.view_id,
                    workspace_id=plan.workspace_id,
                    table_ids=table_ids,
                    view_ids=view_ids,
                    actor=actor,
                )
            except PlatformValidationError:
                omissions.add("table_view", "authority_changed")
                continue
            if view.version != source.source_version:
                omissions.add("table_view", "view_version_changed")
                continue
            try:
                listing = list_view_records(
                    uow,
                    view.id,
                    actor=actor,
                    limit=min(source.max_items, remaining_table_records),
                )
            except PlatformValidationError:
                omissions.add("table_view", "source_revalidation_failed")
                continue
            presentation = get_view_presentation(uow, view.id, actor=actor)
            visible_keys = set(presentation.get("visible_field_keys", ()))
            for listed in listing.get("records", []):
                table_considered += 1
                try:
                    record_id = UUID(str(listed["id"]))
                    record = uow.get_record(record_id)
                    if (
                        record is None
                        or record.table_id != view.table_id
                        or record.record_status != "active"
                    ):
                        raise ValueError
                    safe = read_record_for_actor(uow, record_id, actor=actor)
                    if safe["version"] != record.version or safe["record_status"] != "active":
                        raise ValueError
                    listed_fields = listed.get("fields")
                    safe_values = safe.get("values")
                    if not isinstance(listed_fields, dict) or not isinstance(safe_values, dict):
                        raise ValueError
                    content = {
                        key: safe_values[key]
                        for key in sorted(visible_keys.intersection(listed_fields, safe_values))
                        if listed_fields[key] == safe_values[key]
                    }
                    base = uow.get_base(view.base_id)
                    if base is None or base.status != "active":
                        raise ValueError
                    candidates.append(
                        _EvidenceCandidate(
                            source_kind="table_view",
                            label="business_data",
                            source_type="platform_record",
                            scope=EvidenceScope(
                                workspace_id=plan.workspace_id,
                                base_id=base.id,
                                table_id=view.table_id,
                                view_id=view.id,
                                customer_record_id=plan.business_scope.customer_record_id,
                                project_record_id=plan.business_scope.project_record_id,
                            ),
                            version=EvidenceVersion(kind="record", value=record.version),
                            source_version=source.source_version,
                            content=content,
                        )
                    )
                except (KeyError, TypeError, ValueError, PlatformValidationError):
                    omissions.add("table_view", "source_revalidation_failed")
        elif source.source_kind == "business_memory":
            selected_for_source = 0
            for item in uow.list_memory_items(plan.workspace_id):
                if item.status != "active":
                    continue
                memory_considered += 1
                if selected_for_source >= source.max_items:
                    omissions.add("business_memory", "source_limit_reached")
                    continue
                if _stored_memory_is_group(item):
                    omissions.add("business_memory", "group_source_deferred")
                    continue
                projection = read_memory_projection(
                    uow,
                    item.id,
                    actor=actor,
                    now=now,
                    lifecycle_mode="read_only",
                )
                if projection is None:
                    omissions.add("business_memory", "source_revalidation_failed")
                    continue
                scope = projection.get("scope")
                payload = projection.get("payload")
                if not isinstance(scope, dict) or not isinstance(payload, dict):
                    omissions.add("business_memory", "source_revalidation_failed")
                    continue
                evidence_scope = _validated_memory_scope(
                    uow,
                    scope,
                    workspace_id=plan.workspace_id,
                    table_ids=table_ids,
                    business_scope=plan.business_scope,
                )
                if evidence_scope is None:
                    omissions.add("business_memory", "scope_mismatch")
                    continue
                version = projection.get("version")
                if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                    omissions.add("business_memory", "source_revalidation_failed")
                    continue
                candidates.append(
                    _EvidenceCandidate(
                        source_kind="business_memory",
                        label="confirmed_memory",
                        source_type="memory_item",
                        scope=evidence_scope,
                        version=EvidenceVersion(kind="memory", value=version),
                        content=payload,
                    )
                )
                selected_for_source += 1

    evidence, selected_by_kind = _apply_budget(plan, candidates, omissions)
    if not evidence and any(
        source.source_kind == "general_advice" for source in plan.sources
    ):
        advice = _EvidenceCandidate(
            source_kind="general_advice",
            label="general_advice",
            source_type="policy_marker",
            scope=EvidenceScope(workspace_id=plan.workspace_id),
            version=EvidenceVersion(kind="contract", value=_CONTRACT_VERSION_NUMBER),
            content={"internal_evidence": False},
        )
        evidence, advice_selected = _apply_budget(plan, [advice], omissions)
        selected_by_kind.update(advice_selected)
    return _make_pack(
        plan,
        evidence,
        omissions,
        table_considered,
        selected_by_kind.get("table_view", 0),
        memory_considered,
        selected_by_kind.get("business_memory", 0),
    )


def render_evidence_pack(pack: ContextPack) -> str:
    try:
        pack = validate_context_pack(pack)
    except ValidationError as exc:
        raise PlatformValidationError("context_pack_invalid", "context_pack_invalid") from exc
    blocks: list[str] = []
    for item in pack.evidence:
        scope_labels = {
            "workspace_id": "workspace",
            "base_id": "base",
            "table_id": "table",
            "view_id": "view",
            "customer_record_id": "customer",
            "project_record_id": "project",
        }
        scope_names = [
            scope_labels[name]
            for name, value in item.scope.model_dump(mode="python").items()
            if value is not None
        ]
        header = (
            f"[{item.evidence_id} label={item.label} type={item.source_type} "
            f"version={item.version.value} scope={'/'.join(scope_names)}]"
        )
        blocks.append(f"{header}\n{_canonical_json(item.content)}")
    return "\n\n".join(blocks)


def _require_current_authority(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
):
    workspace = uow.get_workspace(workspace_id)
    employee = uow.get_digital_employee(employee_id)
    if (
        workspace is None
        or workspace.status != "active"
        or employee is None
        or employee.status != "active"
        or employee.workspace_id != workspace_id
        or actor.actor_type != "user"
        or not any(
            member.user_id == actor.actor_id and member.status == "active"
            for member in uow.list_workspace_members(workspace_id)
        )
        or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
    ):
        _deny("context_authority_denied")
    table_ids = _strict_uuid_set(employee.accessible_tables, "context_authority_denied")
    view_ids = _strict_uuid_set(employee.accessible_views, "context_authority_denied")
    return workspace, employee, table_ids, view_ids


def _read_scoped_record(
    uow: Stage06PlatformUnitOfWork,
    record_id: UUID | None,
    *,
    workspace_id: UUID,
    table_ids: set[UUID],
    actor: Actor,
) -> dict[str, Any] | None:
    if record_id is None:
        return None
    record = uow.get_record(record_id)
    if record is None or record.record_status != "active" or record.table_id not in table_ids:
        _deny("context_business_scope_denied")
    table = uow.get_table(record.table_id)
    base = None if table is None else uow.get_base(table.base_id)
    if (
        table is None
        or table.status != "active"
        or base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
    ):
        _deny("context_business_scope_denied")
    try:
        safe = read_record_for_actor(uow, record_id, actor=actor)
    except PlatformValidationError as exc:
        raise PlatformValidationError(
            "context_business_scope_denied", "context_business_scope_denied"
        ) from exc
    if safe.get("record_status") != "active" or safe.get("version") != record.version:
        _deny("context_business_scope_denied")
    return safe


def _visible_link_exists(
    uow: Stage06PlatformUnitOfWork,
    source: dict[str, Any],
    target_id: UUID | None,
    actor: Actor,
) -> bool:
    if target_id is None:
        return False
    table_id = UUID(str(source["table_id"]))
    linked_keys = {
        field.key
        for field in uow.list_fields(table_id)
        if field.status == "active" and field.field_type == "linked_record"
    }
    values = source.get("values")
    if not isinstance(values, dict):
        return False
    target = str(target_id)
    for key in linked_keys.intersection(values):
        value = values[key]
        if isinstance(value, list) and any(
            isinstance(item, dict) and item.get("id") == target for item in value
        ):
            return True
    return False


def _require_current_view(
    uow: Stage06PlatformUnitOfWork,
    view_id: UUID | None,
    *,
    workspace_id: UUID,
    table_ids: set[UUID],
    view_ids: set[UUID],
    actor: Actor,
):
    if view_id is None or view_id not in view_ids:
        _deny("context_view_denied")
    view = uow.get_view(view_id)
    table = None if view is None or view.table_id is None else uow.get_table(view.table_id)
    base = None if view is None else uow.get_base(view.base_id)
    if (
        view is None
        or view.status != "active"
        or view.table_id is None
        or view.table_id not in table_ids
        or table is None
        or table.status != "active"
        or table.base_id != view.base_id
        or base is None
        or base.status != "active"
        or base.workspace_id != workspace_id
    ):
        _deny("context_view_denied")
    try:
        get_view_presentation(uow, view.id, actor=actor)
    except PlatformValidationError as exc:
        raise PlatformValidationError("context_view_denied", "context_view_denied") from exc
    return view


def _strict_uuid_set(values: object, code: str) -> set[UUID]:
    if not isinstance(values, list):
        _deny(code)
    parsed: list[UUID] = []
    try:
        for value in values:
            if not isinstance(value, str):
                raise ValueError
            parsed.append(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PlatformValidationError(code, code) from exc
    if len(set(parsed)) != len(parsed):
        _deny(code)
    return set(parsed)


def _stored_memory_is_group(item: object) -> bool:
    scope = getattr(item, "scope", None)
    refs = getattr(item, "source_refs", None)
    return (
        isinstance(scope, dict)
        and scope.get("group_chat_ref") is not None
    ) or (
        isinstance(refs, list)
        and any(
            isinstance(ref, dict) and ref.get("source_kind") != "platform_record"
            for ref in refs
        )
    )


def _validated_memory_scope(
    uow: Stage06PlatformUnitOfWork,
    scope: dict[str, object],
    *,
    workspace_id: UUID,
    table_ids: set[UUID],
    business_scope: ResolvedBusinessScope,
) -> EvidenceScope | None:
    if "group_chat_ref" in scope or "identity_token" in scope:
        return None
    try:
        allowed = {
            "workspace_id",
            "base_id",
            "table_id",
            "view_id",
            "customer_record_id",
            "project_record_id",
        }
        if not set(scope).issubset(allowed):
            return None
        typed_scope = {
            key: None if value is None else UUID(str(value))
            for key, value in scope.items()
        }
        parsed = EvidenceScope.model_validate(typed_scope)
    except (ValidationError, TypeError, ValueError):
        return None
    if parsed.workspace_id != workspace_id:
        return None
    if (
        parsed.customer_record_id != business_scope.customer_record_id
        or parsed.project_record_id != business_scope.project_record_id
    ):
        return None
    if parsed.table_id is not None:
        table = uow.get_table(parsed.table_id)
        if table is None or table.status != "active" or parsed.table_id not in table_ids:
            return None
        if parsed.base_id is not None and table.base_id != parsed.base_id:
            return None
    if parsed.base_id is not None:
        base = uow.get_base(parsed.base_id)
        if base is None or base.status != "active" or base.workspace_id != workspace_id:
            return None
    return parsed


class _EvidenceCandidate:
    def __init__(
        self,
        *,
        source_kind: ContextSourceKind,
        label: str,
        source_type: str,
        scope: EvidenceScope,
        version: EvidenceVersion,
        content: dict[str, Any],
        source_version: int | None = None,
    ) -> None:
        self.source_kind = source_kind
        self.label = label
        self.source_type = source_type
        self.scope = scope
        self.version = version
        self.source_version = source_version
        self.content = content


class _OmissionAccumulator:
    def __init__(self) -> None:
        self.counts: OrderedDict[tuple[ContextSourceKind, str], int] = OrderedDict()

    def add(self, source_kind: ContextSourceKind, reason_code: str, count: int = 1) -> None:
        key = (source_kind, reason_code)
        self.counts[key] = self.counts.get(key, 0) + count

    def models(self) -> tuple[ContextOmission, ...]:
        return tuple(
            ContextOmission(source_kind=kind, reason_code=reason, count=count)
            for (kind, reason), count in self.counts.items()
        )


def _apply_budget(
    plan: ContextPlan,
    candidates: list[_EvidenceCandidate],
    omissions: _OmissionAccumulator,
) -> tuple[list[EvidenceItem], dict[ContextSourceKind, int]]:
    evidence: list[EvidenceItem] = []
    selected: dict[ContextSourceKind, int] = {}
    total_chars = 0
    for candidate in candidates:
        if len(evidence) >= plan.budget.max_evidence_items:
            omissions.add(candidate.source_kind, "source_limit_reached")
            continue
        try:
            normalized, paths = _normalize_json(candidate.content)
            encoded = _canonical_json(normalized)
        except (TypeError, ValueError):
            omissions.add(candidate.source_kind, "source_revalidation_failed")
            continue
        if len(encoded) > plan.budget.max_item_chars:
            omissions.add(candidate.source_kind, "item_budget_exceeded")
            continue
        if total_chars + len(encoded) > plan.budget.max_total_chars:
            omissions.add(candidate.source_kind, "total_budget_exceeded")
            continue
        ordinal = len(evidence) + 1
        item = EvidenceItem(
            evidence_id=f"{candidate.label}:{ordinal:02d}",
            label=candidate.label,
            source_type=candidate.source_type,
            scope=candidate.scope,
            version=candidate.version,
            source_version=candidate.source_version,
            content=normalized,
            truncated=bool(paths),
            truncated_paths=tuple(paths),
        )
        evidence.append(item)
        selected[candidate.source_kind] = selected.get(candidate.source_kind, 0) + 1
        total_chars += len(encoded)
    return evidence, selected


def _normalize_json(value: Any, *, path: str = "$", depth: int = 0):
    changed: list[str] = []
    if depth >= 4 and isinstance(value, (dict, list)):
        return None, [path]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise TypeError("context_json_key_invalid")
            if _is_internal_identifier_key(key):
                changed.append(f"{path}.{key}")
                continue
            if _is_sensitive_metadata_key(key):
                raise ValueError("context_evidence_content_forbidden")
            normalized_key, key_replacements = _UUID_FRAGMENT_RE.subn(
                "[internal-reference]", key
            )
            if normalized_key in result:
                raise ValueError("context_json_key_collision")
            if key_replacements:
                changed.append(f"{path}.[redacted-key]")
            nested, paths = _normalize_json(
                value[key], path=f"{path}.{normalized_key}", depth=depth + 1
            )
            result[normalized_key] = nested
            changed.extend(paths)
        return result, changed
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value[:20]):
            nested, paths = _normalize_json(item, path=f"{path}[{index}]", depth=depth + 1)
            result.append(nested)
            changed.extend(paths)
        if len(value) > 20:
            changed.append(path)
        return result, changed
    if isinstance(value, str):
        normalized, replacements = _UUID_FRAGMENT_RE.subn(
            "[internal-reference]", value
        )
        if replacements:
            changed.append(path)
        if len(normalized) > 255:
            normalized = normalized[:255] + "…"
            if path not in changed:
                changed.append(path)
        return normalized, changed
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("context_json_value_invalid")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value, changed
    raise TypeError("context_json_value_invalid")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _fallback_pack(plan: ContextPlan, omissions: _OmissionAccumulator) -> ContextPack:
    if any(source.source_kind == "general_advice" for source in plan.sources):
        evidence, selected = _apply_budget(
            plan,
            [
                _EvidenceCandidate(
                    source_kind="general_advice",
                    label="general_advice",
                    source_type="policy_marker",
                    scope=EvidenceScope(workspace_id=plan.workspace_id),
                    version=EvidenceVersion(kind="contract", value=1),
                    content={"internal_evidence": False},
                )
            ],
            omissions,
        )
        del selected
        return _make_pack(plan, evidence, omissions, 0, 0, 0, 0)
    return _make_pack(plan, [], omissions, 0, 0, 0, 0)


def _make_pack(
    plan: ContextPlan,
    evidence: list[EvidenceItem],
    omissions: _OmissionAccumulator,
    table_considered: int,
    table_selected: int,
    memory_considered: int,
    memory_selected: int,
) -> ContextPack:
    labels = [item.label for item in evidence]
    status = (
        "internal_evidence"
        if any(label != "general_advice" for label in labels)
        else "general_advice_only"
        if labels
        else "no_evidence"
    )
    omission_models = omissions.models()
    pack = ContextPack(
        plan=plan,
        status=status,
        evidence=tuple(evidence),
        omissions=omission_models,
        usage=ContextBudgetUsage(
            table_records_considered=table_considered,
            table_records_selected=table_selected,
            memory_items_considered=memory_considered,
            memory_items_selected=memory_selected,
            evidence_items=len(evidence),
            content_chars=sum(len(_canonical_json(item.content)) for item in evidence),
            truncated_items=sum(item.truncated for item in evidence),
            omitted_items=sum(item.count for item in omission_models),
        ),
    )
    return validate_context_pack(pack)


def _deny(code: str) -> None:
    raise PlatformValidationError(code, code)
