from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pydantic import ValidationError

from app.runtime import stage08_context_composition_contracts as _contracts
from app.runtime import stage08_context_contracts as _context_contracts
from app.services import stage08_context as _context_service
from app.services import stage08_group_context as _group_context_service
from app.services.permissions import Actor as _Actor
from app.services.stage06_platform import (
    PlatformValidationError as _PlatformValidationError,
    Stage06PlatformUnitOfWork as _Stage06PlatformUnitOfWork,
)


_ISSUER: Final[object] = object()
_COMPRESSION_ISSUER: Final[object] = object()
_COMPRESSION_SEAL: Final[object] = object()
_GROUP_SCOPE_CATEGORIES: Final[tuple[str, ...]] = (
    "workspace",
    "group",
    "customer",
    "project",
)
_materialize_group_context_window = (
    _group_context_service._materialize_group_context_window
)


class _Stage08CompositeBlock:
    __slots__ = ("_text",)

    def __init__(self, issuer: object, *, text: str) -> None:
        if issuer is not _ISSUER:
            raise TypeError("stage08_composite_block_private")
        self._text = text

    def __repr__(self) -> str:
        return f"<_Stage08CompositeBlock chars={len(self._text)}>"


class _Stage08CompositeContext:
    __slots__ = (
        "_plan",
        "_actor",
        "_c1_pack",
        "_group_authority",
        "_group_window",
        "_group_rendered_count",
        "_blocks",
        "_view",
        "_renderable",
    )

    def __init__(
        self,
        issuer: object,
        *,
        plan: _context_contracts.ContextPlan | None,
        actor: _Actor | None,
        c1_pack: _context_contracts.ContextPack | None,
        group_authority: object | None,
        group_window: object | None,
        group_rendered_count: int,
        blocks: tuple[_Stage08CompositeBlock, ...],
        view: _contracts.CompositeContextView,
        renderable: bool,
    ) -> None:
        if issuer is not _ISSUER:
            raise TypeError("stage08_composite_context_private")
        self._plan = plan
        self._actor = actor
        self._c1_pack = c1_pack
        self._group_authority = group_authority
        self._group_window = group_window
        self._group_rendered_count = group_rendered_count
        self._blocks = blocks
        self._view = _contracts.validate_composite_context_view(view)
        self._renderable = renderable

    def view(self) -> _contracts.CompositeContextView:
        try:
            return _contracts.validate_composite_context_view(self._view)
        except (ValidationError, TypeError, ValueError, AttributeError):
            return _no_evidence_view()

    def __repr__(self) -> str:
        safe = self.view()
        return (
            "<_Stage08CompositeContext "
            f"status={safe.status!r} blocks={len(self._blocks)}>"
        )


@dataclass(frozen=True, slots=True)
class _Stage08GroupCompressionSnapshot:
    seal: object
    composite: _Stage08CompositeContext
    text: str


class _Stage08GroupCompressionMaterial:
    """Private, invocation-local group material for the Package E compressor."""

    __slots__ = ("_sealed_snapshot",)

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if issuer is not _COMPRESSION_ISSUER:
            raise TypeError("stage08_group_compression_material_private")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name == "__class__":
            return type(self)
        if name in {"__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError("stage08_group_compression_material_private")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("stage08_group_compression_material_private")

    def __repr__(self) -> str:
        return "<_Stage08GroupCompressionMaterial opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("stage08_group_compression_material_unavailable")


def compose_stage08_context(
    uow: _Stage06PlatformUnitOfWork,
    plan: _context_contracts.ContextPlan,
    *,
    actor: _Actor,
    now: datetime,
) -> _Stage08CompositeContext:
    if not _valid_utc_now(now):
        return _invalid_composite()
    validated_plan = _validated_plan(plan)
    validated_actor = _validated_actor(actor)
    if (
        validated_plan is None
        or validated_actor is None
        or validated_actor.actor_type != "user"
        or validated_actor.actor_id != validated_plan.actor_user_id
    ):
        return _invalid_composite()
    try:
        c1_pack = _context_contracts.validate_context_pack(
            _context_service.compose_context_pack(
                uow,
                validated_plan,
                actor=validated_actor,
                now=now,
            )
        )
        authority = _group_context_service.Stage08GroupContextAuthorityFactory.build(
            uow,
            actor=validated_actor,
            employee_id=validated_plan.employee_id,
            workspace_id=validated_plan.workspace_id,
        )
        window = _group_context_service.build_group_context_window(
            uow,
            authority,
            business_scope=validated_plan.business_scope,
            now=now,
        )
        window_view = window.view()
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return _invalid_composite()

    if window_view.compression_required:
        return _compose_pending_result(
            validated_plan,
            validated_actor,
            c1_pack,
            authority,
            window,
            window_view,
        )

    if window_view.status == "group_context_unavailable":
        return _compose_direct_result(
            validated_plan,
            validated_actor,
            c1_pack,
            authority,
            window,
            window_view,
            (),
        )

    try:
        materialized = _materialize_group_context_window(
            uow,
            authority,
            window,
            business_scope=validated_plan.business_scope,
            now=now,
        )
    except (
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return _invalid_composite()
    if type(materialized) is not _group_context_service._GroupContextMaterialization:
        return _invalid_composite()
    if not materialized._available:
        return _compose_direct_result(
            validated_plan,
            validated_actor,
            c1_pack,
            authority,
            window,
            window_view,
            (),
        )
    fragments = materialized._fragments
    if not _valid_materialized_fragments(fragments, window_view):
        return _invalid_composite()
    return _compose_direct_result(
        validated_plan,
        validated_actor,
        c1_pack,
        authority,
        window,
        window_view,
        fragments,
    )


def render_stage08_composite_context(
    uow: _Stage06PlatformUnitOfWork,
    composite: _Stage08CompositeContext,
    *,
    now: datetime,
) -> str | None:
    if (
        type(composite) is not _Stage08CompositeContext
        or not composite._renderable
        or composite._plan is None
        or composite._actor is None
        or not _valid_utc_now(now)
    ):
        return None
    try:
        original_view = _contracts.validate_composite_context_view(
            composite._view
        )
        original_window_view = composite._group_window.view()
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None
    if (
        original_view.status == "group_compression_pending"
        or original_window_view.compression_required
    ):
        return _render_pending_composite(
            uow,
            composite,
            original_view=original_view,
            original_window_view=original_window_view,
            now=now,
        )
    current = compose_stage08_context(
        uow,
        composite._plan,
        actor=composite._actor,
        now=now,
    )
    if not current._renderable:
        return None
    try:
        current_view = _contracts.validate_composite_context_view(
            current._view
        )
        current_window_view = current._group_window.view()
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None
    if current_view.status == "group_compression_pending":
        return _render_pending_composite(
            uow,
            current,
            original_view=current_view,
            original_window_view=current_window_view,
            now=now,
        )
    group_drift = _original_group_window_drifted(uow, composite, now=now)
    if group_drift is None:
        return None
    if group_drift:
        return _render_c1_pack(current._c1_pack)
    return "\n\n".join(block._text for block in current._blocks)


def prepare_stage08_group_compression_material(
    uow: _Stage06PlatformUnitOfWork,
    composite: object,
    *,
    now: datetime,
) -> _Stage08GroupCompressionMaterial | None:
    """Re-read a pending group window and return an opaque, non-persistent input."""

    if (
        type(composite) is not _Stage08CompositeContext
        or not _valid_utc_now(now)
        or not composite._renderable
    ):
        return None
    plan = _validated_plan(composite._plan)
    actor = _validated_actor(composite._actor)
    authority = composite._group_authority
    window = composite._group_window
    if (
        plan is None
        or actor is None
        or actor.actor_type != "user"
        or actor.actor_id != plan.actor_user_id
        or type(authority) is not _group_context_service._GroupContextAuthority
        or type(window) is not _group_context_service._GroupContextWindow
    ):
        return None
    try:
        original_view = _contracts.validate_composite_context_view(composite._view)
        original_window_view = window.view()
        original_pack = _context_contracts.validate_context_pack(composite._c1_pack)
        current_pack = _context_contracts.validate_context_pack(
            _context_service.compose_context_pack(
                uow,
                plan,
                actor=actor,
                now=now,
            )
        )
        fresh_window = _group_context_service.build_group_context_window(
            uow,
            authority,
            business_scope=plan.business_scope,
            now=now,
        )
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None
    if (
        original_view.status != "group_compression_pending"
        or not original_view.group_compression_required
        or not original_window_view.compression_required
        or original_pack.plan != plan
        or current_pack.status not in {"internal_evidence", "general_advice_only", "no_evidence"}
        or not _pending_window_lineage_is_current(
            authority,
            window,
            original_view,
            original_window_view,
            fresh_window,
        )
    ):
        return None
    try:
        fresh_view = fresh_window.view()
        materialized = _materialize_group_context_window(
            uow,
            authority,
            fresh_window,
            business_scope=plan.business_scope,
            now=now,
        )
    except (
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None
    if (
        type(materialized) is not _group_context_service._GroupContextMaterialization
        or not materialized._available
        or not _valid_materialized_fragments(materialized._fragments, fresh_view)
    ):
        return None
    blocks = tuple(
        (
            f"[{fragment.display_id} label=group_context "
            "type=group_message_fragment "
            "scope=workspace/group/customer/project]\n"
            f"{fragment._text}"
        )
        for fragment in materialized._fragments
    )
    text = "\n\n".join(blocks)
    if not text or len(text) > 64_000:
        return None
    return _Stage08GroupCompressionMaterial(
        _COMPRESSION_ISSUER,
        _Stage08GroupCompressionSnapshot(
            seal=_COMPRESSION_SEAL,
            composite=composite,
            text=text,
        ),
    )


def validate_stage08_group_compression_digest(
    uow: _Stage06PlatformUnitOfWork,
    material: object,
    *,
    digest: object,
    now: datetime,
) -> bool:
    """Accept only a bounded digest while the exact pending material is current."""

    snapshot = _group_compression_snapshot(material)
    if snapshot is None or not _valid_utc_now(now):
        return False
    try:
        from app.runtime.stage08_collaboration_contracts import (
            _compressed_digest_snapshot,
        )

        digest_snapshot = _compressed_digest_snapshot(digest)
        text = digest_snapshot.text
    except (TypeError, ValueError, AttributeError):
        return False
    if type(text) is not str or not text.strip() or len(text) > 12_000:
        return False
    current = prepare_stage08_group_compression_material(
        uow,
        snapshot.composite,
        now=now,
    )
    current_snapshot = _group_compression_snapshot(current)
    return current_snapshot is not None and current_snapshot.text == snapshot.text


def _group_compression_snapshot(
    material: object,
) -> _Stage08GroupCompressionSnapshot | None:
    if type(material) is not _Stage08GroupCompressionMaterial:
        return None
    try:
        snapshot = object.__getattribute__(material, "_sealed_snapshot")
    except (AttributeError, TypeError):
        return None
    if (
        type(snapshot) is not _Stage08GroupCompressionSnapshot
        or snapshot.seal is not _COMPRESSION_SEAL
        or type(snapshot.composite) is not _Stage08CompositeContext
        or type(snapshot.text) is not str
        or not snapshot.text
    ):
        return None
    return snapshot


def _compose_pending_result(
    plan: _context_contracts.ContextPlan,
    actor: _Actor,
    c1_pack: _context_contracts.ContextPack,
    authority: object,
    window: object,
    window_view: object,
) -> _Stage08CompositeContext:
    c1_is_internal = c1_pack.status == "internal_evidence"
    c1_items = c1_pack.usage.evidence_items if c1_is_internal else 0
    c1_chars = c1_pack.usage.content_chars if c1_is_internal else 0
    if (
        type(window) is not _group_context_service._GroupContextWindow
        or type(authority) is not _group_context_service._GroupContextAuthority
        or window_view.status == "group_context_unavailable"
        or not window_view.compression_required
        or window_view.usage.selected_fragments == 0
        or c1_items > _contracts.COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS
        or c1_chars > _contracts.COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS
    ):
        return _invalid_composite()
    view = _contracts.CompositeContextView(
        contract_version="stage08-composite-context.v1",
        status="group_compression_pending",
        c1_status=c1_pack.status,
        group_status=window_view.status,
        group_compression_required=True,
        usage=_contracts.CompositeContextBudgetUsage(
            c1_evidence_items=c1_items,
            group_window_fragments=window_view.usage.selected_fragments,
            group_rendered_fragments=0,
            c1_content_chars=c1_chars,
            group_rendered_chars=0,
            total_content_chars=c1_chars,
        ),
    )
    return _Stage08CompositeContext(
        _ISSUER,
        plan=plan,
        actor=actor,
        c1_pack=c1_pack,
        group_authority=authority,
        group_window=window,
        group_rendered_count=0,
        blocks=(),
        view=view,
        renderable=True,
    )


def _render_pending_composite(
    uow: _Stage06PlatformUnitOfWork,
    composite: _Stage08CompositeContext,
    *,
    original_view: _contracts.CompositeContextView,
    original_window_view: object,
    now: datetime,
) -> str | None:
    plan = _validated_plan(composite._plan)
    actor = _validated_actor(composite._actor)
    authority = composite._group_authority
    window = composite._group_window
    authority_actor = _validated_actor(
        getattr(authority, "_actor", None)
    )
    if (
        plan is None
        or actor is None
        or authority_actor is None
        or actor != authority_actor
        or actor.actor_type != "user"
        or actor.actor_id != plan.actor_user_id
        or type(authority) is not _group_context_service._GroupContextAuthority
        or type(window) is not _group_context_service._GroupContextWindow
        or original_view.status != "group_compression_pending"
        or not original_view.group_compression_required
        or not original_window_view.compression_required
        or type(composite._group_rendered_count) is not int
        or composite._group_rendered_count != 0
        or type(composite._blocks) is not tuple
        or composite._blocks
    ):
        return None
    try:
        original_pack = _context_contracts.validate_context_pack(
            composite._c1_pack
        )
        current_pack = _context_contracts.validate_context_pack(
            _context_service.compose_context_pack(
                uow,
                plan,
                actor=actor,
                now=now,
            )
        )
        fresh_window = _group_context_service.build_group_context_window(
            uow,
            authority,
            business_scope=plan.business_scope,
            now=now,
        )
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None
    if (
        original_pack.plan != plan
        or not _pending_window_lineage_is_current(
            authority,
            window,
            original_view,
            original_window_view,
            fresh_window,
        )
        or current_pack.status != "internal_evidence"
    ):
        return None
    return _render_c1_pack(current_pack)


def _pending_window_lineage_is_current(
    authority: object,
    window: object,
    composite_view: _contracts.CompositeContextView,
    original_window_view: object,
    fresh_window: object,
) -> bool:
    if (
        type(authority) is not _group_context_service._GroupContextAuthority
        or type(window) is not _group_context_service._GroupContextWindow
        or type(fresh_window) is not _group_context_service._GroupContextWindow
    ):
        return False
    try:
        fresh_view = fresh_window.view()
        original_handles = window._projection_handles
        fresh_handles = fresh_window._projection_handles
        selected_count = original_window_view.usage.selected_fragments
        if (
            type(original_handles) is not tuple
            or type(fresh_handles) is not tuple
            or not authority._available
            or authority._mapping_id is None
            or window._authority_nonce != authority._nonce
            or fresh_window._authority_nonce != authority._nonce
            or not original_window_view.compression_required
            or not fresh_view.compression_required
            or original_window_view != fresh_view
            or len(original_handles) != selected_count
            or len(fresh_handles) != selected_count
            or composite_view.group_status != original_window_view.status
            or composite_view.usage.group_window_fragments != selected_count
            or composite_view.usage.group_rendered_fragments != 0
            or composite_view.usage.group_rendered_chars != 0
        ):
            return False
        original_signature = []
        fresh_signature = []
        for original_handle, fresh_handle in zip(
            original_handles, fresh_handles, strict=True
        ):
            if (
                type(original_handle)
                is not _group_context_service._GroupProjectionHandle
                or type(fresh_handle)
                is not _group_context_service._GroupProjectionHandle
                or original_handle._authority_nonce != authority._nonce
                or fresh_handle._authority_nonce != authority._nonce
                or original_handle._mapping_id != authority._mapping_id
                or fresh_handle._mapping_id != authority._mapping_id
            ):
                return False
            original_signature.append(
                (original_handle._projection_id, original_handle._mapping_id)
            )
            fresh_signature.append(
                (fresh_handle._projection_id, fresh_handle._mapping_id)
            )
        return original_signature == fresh_signature
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return False


def _compose_direct_result(
    plan: _context_contracts.ContextPlan,
    actor: _Actor,
    c1_pack: _context_contracts.ContextPack,
    authority: object,
    window: object,
    window_view: object,
    fragments: tuple[object, ...],
) -> _Stage08CompositeContext:
    has_group = bool(fragments)
    c1_is_internal = c1_pack.status == "internal_evidence"
    c1_rendered = (
        _context_service.render_evidence_pack(c1_pack)
        if c1_is_internal or not has_group
        else ""
    )
    blocks: list[_Stage08CompositeBlock] = []
    if c1_rendered:
        blocks.append(_Stage08CompositeBlock(_ISSUER, text=c1_rendered))
    group_chars = 0
    for fragment in fragments:
        group_chars += len(fragment._text)
        header = (
            f"[{fragment.display_id} label=group_context "
            "type=group_message_fragment "
            "scope=workspace/group/customer/project]"
        )
        blocks.append(
            _Stage08CompositeBlock(
                _ISSUER,
                text=f"{header}\n{fragment._text}",
            )
        )

    c1_items = c1_pack.usage.evidence_items if c1_is_internal else 0
    c1_chars = c1_pack.usage.content_chars if c1_is_internal else 0
    total_chars = c1_chars + group_chars
    if (
        c1_items > _contracts.COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS
        or c1_chars > _contracts.COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS
        or len(fragments) > _contracts.COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS
        or group_chars > _contracts.COMPOSITE_CONTEXT_GROUP_MAX_DIRECT_CHARS
        or total_chars > _contracts.COMPOSITE_CONTEXT_MAX_CONTENT_CHARS
    ):
        return _invalid_composite()

    group_status = (
        window_view.status if has_group else "group_context_unavailable"
    )
    status = (
        "internal_evidence"
        if c1_is_internal or has_group
        else c1_pack.status
    )
    view = _contracts.CompositeContextView(
        contract_version="stage08-composite-context.v1",
        status=status,
        c1_status=c1_pack.status,
        group_status=group_status,
        group_compression_required=False,
        usage=_contracts.CompositeContextBudgetUsage(
            c1_evidence_items=c1_items,
            group_window_fragments=(
                window_view.usage.selected_fragments if has_group else 0
            ),
            group_rendered_fragments=len(fragments),
            c1_content_chars=c1_chars,
            group_rendered_chars=group_chars,
            total_content_chars=total_chars,
        ),
    )
    return _Stage08CompositeContext(
        _ISSUER,
        plan=plan,
        actor=actor,
        c1_pack=c1_pack,
        group_authority=authority,
        group_window=window,
        group_rendered_count=len(fragments),
        blocks=tuple(blocks),
        view=view,
        renderable=True,
    )


def _valid_materialized_fragments(
    fragments: object,
    window_view: object,
) -> bool:
    if not isinstance(fragments, tuple) or len(fragments) != (
        window_view.usage.selected_fragments
    ):
        return False
    for index, fragment in enumerate(fragments, start=1):
        if (
            type(fragment)
            is not _group_context_service._SelectedGroupContextFragment
            or type(fragment._text) is not str
            or not fragment._text
            or len(fragment._text) > 500
            or fragment.label != "group_context"
            or fragment.source_type != "group_message_fragment"
            or fragment.display_id != f"group_context:{index:02d}"
            or fragment.scope_categories != _GROUP_SCOPE_CATEGORIES
        ):
            return False
    return True


def _validated_plan(plan: object) -> _context_contracts.ContextPlan | None:
    try:
        if not isinstance(plan, _context_contracts.ContextPlan):
            return None
        return _context_contracts.ContextPlan.model_validate(
            plan.model_dump(mode="python", warnings="none")
        )
    except (ValidationError, TypeError, ValueError, AttributeError):
        return None


def _original_group_window_drifted(
    uow: _Stage06PlatformUnitOfWork,
    composite: _Stage08CompositeContext,
    *,
    now: datetime,
) -> bool | None:
    window = composite._group_window
    authority = composite._group_authority
    if (
        type(window) is not _group_context_service._GroupContextWindow
        or type(authority) is not _group_context_service._GroupContextAuthority
    ):
        return None
    try:
        window_view = window.view()
        composite_view = _contracts.validate_composite_context_view(
            composite._view
        )
        handles = window._projection_handles
        selected_count = window_view.usage.selected_fragments
        if (
            type(handles) is not tuple
            or type(composite._group_rendered_count) is not int
            or len(handles) != selected_count
            or composite._group_rendered_count != selected_count
            or composite_view.usage.group_window_fragments != selected_count
            or composite_view.usage.group_rendered_fragments != selected_count
            or composite_view.group_status != window_view.status
            or composite_view.group_compression_required
        ):
            return None
        if window_view.usage.selected_fragments == 0:
            if (
                window_view.status != "group_context_unavailable"
                or window._authority_nonce not in {None, authority._nonce}
            ):
                return None
            return False
        if (
            window_view.status == "group_context_unavailable"
            or not authority._available
            or authority._mapping_id is None
            or window._authority_nonce != authority._nonce
            or any(
                type(handle)
                is not _group_context_service._GroupProjectionHandle
                or handle._authority_nonce != authority._nonce
                or handle._mapping_id != authority._mapping_id
                for handle in handles
            )
        ):
            return None
        materialized = _materialize_group_context_window(
            uow,
            authority,
            window,
            business_scope=composite._plan.business_scope,
            now=now,
        )
    except (
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None
    if type(materialized) is not _group_context_service._GroupContextMaterialization:
        return None
    if not materialized._available:
        return True
    if not _valid_materialized_fragments(
        materialized._fragments, window_view
    ):
        return None
    return False


def _render_c1_pack(pack: object) -> str | None:
    if not isinstance(pack, _context_contracts.ContextPack):
        return None
    try:
        return _context_service.render_evidence_pack(
            _context_contracts.validate_context_pack(pack)
        )
    except (
        ValidationError,
        _PlatformValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        return None


def _validated_actor(actor: object) -> _Actor | None:
    if (
        type(actor) is not _Actor
        or type(actor.actor_type) is not str
        or type(actor.actor_id) is not str
        or type(actor.role) is not str
        or not actor.actor_type
        or not actor.actor_id
        or not actor.role
        or type(actor.customer_ids) is not frozenset
        or any(type(value) is not str for value in actor.customer_ids)
    ):
        return None
    return _Actor(
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        role=actor.role,
        customer_ids=frozenset(actor.customer_ids),
    )


def _valid_utc_now(now: object) -> bool:
    return (
        type(now) is datetime
        and now.tzinfo is not None
        and now.utcoffset() is not None
        and now.utcoffset().total_seconds() == 0
    )


def _invalid_composite() -> _Stage08CompositeContext:
    return _Stage08CompositeContext(
        _ISSUER,
        plan=None,
        actor=None,
        c1_pack=None,
        group_authority=None,
        group_window=None,
        group_rendered_count=0,
        blocks=(),
        view=_no_evidence_view(),
        renderable=False,
    )


def _no_evidence_view() -> _contracts.CompositeContextView:
    return _contracts.CompositeContextView(
        contract_version="stage08-composite-context.v1",
        status="no_evidence",
        c1_status="no_evidence",
        group_status="group_context_unavailable",
        group_compression_required=False,
        usage=_contracts.CompositeContextBudgetUsage(
            c1_evidence_items=0,
            group_window_fragments=0,
            group_rendered_fragments=0,
            c1_content_chars=0,
            group_rendered_chars=0,
            total_content_chars=0,
        ),
    )
