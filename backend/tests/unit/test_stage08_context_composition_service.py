from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import inspect
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.runtime.stage08_context_composition_contracts import (
    CompositeContextBudgetUsage,
    CompositeContextView,
)
from app.runtime.stage08_context_contracts import (
    ContextBudget,
    ContextPlan,
    ContextPlanningRequest,
)
from app.runtime.stage08_group_context_contracts import (
    GroupContextBudgetUsage,
    GroupContextOmissionCounts,
    GroupContextWindowView,
)
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services import stage08_context_composition as composition_service
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_context import build_context_plan
from app.services.stage08_context_composition import (
    compose_stage08_context,
    prepare_stage08_group_compression_material,
    render_stage08_composite_context,
    validate_stage08_group_compression_digest,
)
from app.runtime.stage08_collaboration_contracts import (
    Stage08CollaborationContractFactory,
)
from app.services.stage08_memory import materialize_memory_from_projection


NOW = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)


def _fixture(*, with_group: bool = True):
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-c3", role="owner")
    workspace = create_workspace(
        uow, name="C3", owner_user_id=actor.actor_id, actor=actor
    )
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    customers = create_table(
        uow, base.id, name="Customers", key="customers", actor=actor
    )
    projects = create_table(
        uow, base.id, name="Projects", key="projects", actor=actor
    )
    create_field(
        uow, customers.id, name="Name", key="name", field_type="text", actor=actor
    )
    create_field(
        uow, projects.id, name="Title", key="title", field_type="text", actor=actor
    )
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=actor,
    )
    customer = create_record(
        uow, customers.id, values={"name": "Acme C3"}, actor=actor
    )
    project = create_record(
        uow,
        projects.id,
        values={"title": "Launch C3", "customer": [str(customer.id)]},
        actor=actor,
    )
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["title", "customer"]},
        actor=actor,
    )
    view.version = 1
    employee = create_digital_employee(
        uow,
        base.id,
        name="C3 employee",
        description="private context composition",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    binding = None
    mapping = None
    if with_group:
        binding = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="-100300400",
            telegram_user_id="300400",
            binding_type="chat_user",
            scope_policy={},
            status="active",
        )
        uow.add_telegram_binding(binding)
        mapping = Stage08GroupBusinessContextBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            telegram_binding_id=binding.id,
            customer_record_id=customer.id,
            project_record_id=project.id,
            mapping_version=1,
            status="active",
        )
        uow.add_group_business_context_binding(mapping)
    return SimpleNamespace(
        uow=uow,
        actor=actor,
        workspace=workspace,
        member=member,
        base=base,
        customers=customers,
        projects=projects,
        customer=customer,
        project=project,
        view=view,
        employee=employee,
        binding=binding,
        mapping=mapping,
    )


def _plan(fixture, *, intent="business_fact", allow_general_advice=True):
    request = ContextPlanningRequest(
        workspace_id=fixture.workspace.id,
        employee_id=fixture.employee.id,
        intent=intent,
        view_ids=(fixture.view.id,) if intent in {"business_fact", "mixed"} else (),
        customer_record_id=fixture.customer.id,
        project_record_id=fixture.project.id,
        allow_general_advice=allow_general_advice,
        budget=ContextBudget(
            max_table_records=20,
            max_memory_items=12,
            max_evidence_items=24,
            max_item_chars=2000,
            max_total_chars=12000,
        ),
    )
    return build_context_plan(fixture.uow, request, actor=fixture.actor)


def _projection(fixture, text: str, *, minutes_ago: int = 0):
    projection = Stage08GroupMessageProjection(
        id=uuid4(),
        source_message_id=uuid4(),
        business_context_binding_id=fixture.mapping.id,
        content_fragment=text,
        content_version=1,
        event_at=NOW - timedelta(minutes=minutes_ago),
        edited_at=None,
        retention_expires_at=NOW + timedelta(days=30),
        lifecycle_status="active",
        source_chat_type="group",
    )
    fixture.uow.add_group_message_projection(projection)
    return projection


def _side_effect_counts(uow):
    return (
        len(uow.records),
        len(uow.memory_items),
        len(uow.audit_events),
        len(uow.outbox_events),
        len(uow.agent_runs),
        len(uow.record_change_drafts),
        len(uow.notification_requests),
        len(uow.group_message_projections),
    )


def _high_group_window(fixture, *, secret: str = "pending-group-secret"):
    projections = []
    fragments = []
    for index in range(49):
        marker = f"{secret}-{index:02d}-"
        fragment = marker + ("x" * (500 - len(marker)))
        assert len(fragment) == 500
        projections.append(
            _projection(fixture, fragment, minutes_ago=index)
        )
        fragments.append(fragment)
    assert sum(len(fragment) for fragment in fragments) == 24_500
    return projections, tuple(fragments)


def test_direct_composition_merges_c1_then_group_in_deterministic_order() -> None:
    fixture = _fixture()
    newest = _projection(fixture, "current group decision")
    older = _projection(fixture, "earlier group context", minutes_ago=1)
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )

    view = composite.view()
    rendered = render_stage08_composite_context(
        fixture.uow, composite, now=NOW
    )

    assert view.status == "internal_evidence"
    assert view.c1_status == "internal_evidence"
    assert view.group_status == "group_context_available"
    assert view.group_compression_required is False
    assert view.usage.c1_evidence_items == 1
    assert view.usage.group_window_fragments == 2
    assert view.usage.group_rendered_fragments == 2
    assert view.usage.group_rendered_chars == len(newest.content_fragment) + len(
        older.content_fragment
    )
    assert view.usage.total_content_chars == (
        view.usage.c1_content_chars + view.usage.group_rendered_chars
    )
    assert rendered is not None
    assert rendered.index("[business_data:01") < rendered.index("[group_context:01")
    assert rendered.index("current group decision") < rendered.index(
        "earlier group context"
    )
    assert (
        "[group_context:01 label=group_context type=group_message_fragment "
        "scope=workspace/group/customer/project]"
    ) in rendered
    assert (
        "[group_context:02 label=group_context type=group_message_fragment "
        "scope=workspace/group/customer/project]"
    ) in rendered
    for forbidden in (
        fixture.workspace.id,
        fixture.customer.id,
        fixture.project.id,
        fixture.binding.id,
        fixture.mapping.id,
        newest.id,
        newest.source_message_id,
    ):
        assert str(forbidden) not in rendered


@pytest.mark.parametrize(
    ("kind", "expected_status", "expected_render"),
    [
        ("internal", "internal_evidence", "Launch C3"),
        ("general", "general_advice_only", '"internal_evidence":false'),
        ("none", "no_evidence", ""),
    ],
)
def test_group_unavailable_preserves_each_c1_result(
    kind: str, expected_status: str, expected_render: str
) -> None:
    fixture = _fixture(with_group=False)
    if kind == "general":
        plan = _plan(fixture, intent="business_fact")
        fixture.view.version += 1
    else:
        plan = _plan(
            fixture,
            intent="business_fact",
            allow_general_advice=kind != "none",
        )
        if kind == "none":
            fixture.view.version += 1
    composite = compose_stage08_context(
        fixture.uow, plan, actor=fixture.actor, now=NOW
    )
    assert composite.view().status == expected_status
    assert composite.view().group_status == "group_context_unavailable"
    rendered = render_stage08_composite_context(fixture.uow, composite, now=NOW)
    assert rendered is not None
    assert expected_render in rendered


def test_group_evidence_replaces_general_advice_marker_but_keeps_safe_c1_status() -> None:
    fixture = _fixture()
    _projection(fixture, "group evidence only")
    plan = _plan(fixture, intent="business_fact")
    fixture.view.version += 1
    composite = compose_stage08_context(
        fixture.uow,
        plan,
        actor=fixture.actor,
        now=NOW,
    )
    view = composite.view()
    rendered = render_stage08_composite_context(fixture.uow, composite, now=NOW)
    assert view.status == "internal_evidence"
    assert view.c1_status == "general_advice_only"
    assert view.usage.c1_evidence_items == 0
    assert view.usage.c1_content_chars == 0
    assert rendered is not None
    assert "group evidence only" in rendered
    assert "general_advice" not in rendered
    assert "internal_evidence\":false" not in rendered


def test_partial_group_status_and_all_private_representations_are_count_only() -> None:
    fixture = _fixture()
    secret = "partial fragment secret"
    _projection(fixture, secret)
    _projection(fixture, "x" * 501, minutes_ago=1)
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    dumped = composite.view().model_dump_json()
    assert composite.view().group_status == "group_context_partial"
    assert secret not in dumped
    assert secret not in repr(composite)
    assert "group_context" not in repr(composite)
    for value in vars(composition_service).values():
        if type(value).__module__ == composition_service.__name__ and type(value).__name__.startswith("_"):
            assert secret not in repr(value)
    with pytest.raises(TypeError):
        json.dumps(composite)


def test_forged_inputs_nested_safe_view_and_invalid_now_fail_closed() -> None:
    fixture = _fixture()
    _projection(fixture, "must not leak")
    plan = _plan(fixture)
    forged_plan = ContextPlan.model_construct(
        **{**plan.model_dump(mode="python"), "employee_id": "not-a-uuid"}
    )
    invalid = compose_stage08_context(
        fixture.uow, forged_plan, actor=fixture.actor, now=NOW
    )
    assert invalid.view().status == "no_evidence"
    assert render_stage08_composite_context(fixture.uow, invalid, now=NOW) is None
    assert render_stage08_composite_context(fixture.uow, object(), now=NOW) is None

    composite = compose_stage08_context(
        fixture.uow, plan, actor=fixture.actor, now=NOW
    )

    class UsageCarrier(CompositeContextBudgetUsage):
        secret: str = "nested-secret"

    carrier = UsageCarrier(**composite.view().usage.model_dump(mode="python"))
    composite._view = CompositeContextView.model_construct(
        **{
            **composite.view().model_dump(mode="python"),
            "usage": carrier,
        }
    )
    safe = composite.view()
    assert type(safe) is CompositeContextView
    assert type(safe.usage) is CompositeContextBudgetUsage
    assert "nested-secret" not in safe.model_dump_json()

    invalid_now = NOW.astimezone(timezone(timedelta(hours=8)))
    invalid_time_composite = compose_stage08_context(
        fixture.uow, plan, actor=fixture.actor, now=invalid_now
    )
    assert invalid_time_composite.view().status == "no_evidence"
    assert (
        render_stage08_composite_context(
            fixture.uow, composite, now=invalid_now
        )
        is None
    )


def test_tampered_private_group_window_view_fails_closed() -> None:
    fixture = _fixture()
    _projection(fixture, "must remain private")
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )


def test_structurally_valid_zero_window_cannot_bypass_original_group_lineage() -> None:
    fixture = _fixture()
    secret = "forged-zero-lineage-secret"
    _projection(fixture, secret)
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    fixture.mapping.mapping_version += 1
    without_forgery = render_stage08_composite_context(
        fixture.uow, composite, now=NOW
    )
    assert without_forgery is not None
    assert secret not in without_forgery

    composite._group_window._view = GroupContextWindowView(
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
    )

    assert (
        render_stage08_composite_context(fixture.uow, composite, now=NOW)
        is None
    )
    composite._group_window._view = object()

    assert (
        render_stage08_composite_context(fixture.uow, composite, now=NOW)
        is None
    )


@pytest.mark.parametrize(
    "drift", ["projection", "source_type", "mapping", "member", "binding", "relation"]
)
def test_renderer_recomposes_and_drops_stale_group_or_c1_content(drift: str) -> None:
    fixture = _fixture()
    projection = _projection(fixture, "old group secret")
    plan = _plan(fixture)
    composite = compose_stage08_context(
        fixture.uow, plan, actor=fixture.actor, now=NOW
    )
    assert "old group secret" in (
        render_stage08_composite_context(fixture.uow, composite, now=NOW) or ""
    )
    if drift == "projection":
        projection.lifecycle_status = "purged"
        projection.content_fragment = ""
    elif drift == "source_type":
        projection.source_chat_type = "unknown"
    elif drift == "mapping":
        fixture.mapping.mapping_version += 1
    elif drift == "member":
        fixture.member.status = "inactive"
    elif drift == "binding":
        fixture.binding.status = "inactive"
    else:
        fixture.project.record_values["customer"] = []
    rendered = render_stage08_composite_context(fixture.uow, composite, now=NOW)
    assert rendered is not None
    assert "old group secret" not in rendered
    if drift == "relation":
        assert "Launch C3" not in rendered


def test_renderer_recomposes_c1_view_and_record_state_without_old_content() -> None:
    fixture = _fixture()
    _projection(fixture, "current group")
    plan = _plan(fixture)
    composite = compose_stage08_context(
        fixture.uow, plan, actor=fixture.actor, now=NOW
    )
    fixture.project.record_values["title"] = "Updated Launch"
    rendered = render_stage08_composite_context(fixture.uow, composite, now=NOW)
    assert rendered is not None
    assert "Updated Launch" in rendered
    assert '"title":"Launch C3"' not in rendered

    fixture.view.version += 1
    rendered_after_view_drift = render_stage08_composite_context(
        fixture.uow, composite, now=NOW
    )
    assert rendered_after_view_drift is not None
    assert "Updated Launch" not in rendered_after_view_drift
    assert "current group" in rendered_after_view_drift


def test_renderer_recomposes_and_drops_revoked_c1_memory() -> None:
    fixture = _fixture()
    _projection(fixture, "current group")
    memory = materialize_memory_from_projection(
        fixture.uow,
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(
                workspace_id=fixture.workspace.id,
                base_id=fixture.base.id,
                table_id=fixture.projects.id,
                customer_record_id=fixture.customer.id,
                project_record_id=fixture.project.id,
            ),
            payload={"title": "Launch C3"},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=fixture.project.id,
                    source_version=fixture.project.version,
                    field_keys=("title",),
                ),
            ),
            valid_until=NOW + timedelta(days=1),
        ),
        actor=fixture.actor,
        now=NOW,
    )
    composite = compose_stage08_context(
        fixture.uow,
        _plan(fixture, intent="mixed"),
        actor=fixture.actor,
        now=NOW,
    )
    assert "[confirmed_memory:" in (
        render_stage08_composite_context(fixture.uow, composite, now=NOW) or ""
    )
    memory.status = "revoked"
    rendered = render_stage08_composite_context(fixture.uow, composite, now=NOW)
    assert rendered is not None
    assert "[confirmed_memory:" not in rendered
    assert "current group" in rendered


def test_actor_mismatch_never_uses_a_different_members_group_binding() -> None:
    fixture = _fixture()
    _projection(fixture, "cross actor group secret")
    plan = _plan(fixture)
    fixture.member.user_id = "different-member"
    different_actor = Actor(
        actor_type="user", actor_id="different-member", role="owner"
    )

    composite = compose_stage08_context(
        fixture.uow, plan, actor=different_actor, now=NOW
    )

    assert composite.view().status == "no_evidence"
    assert (
        render_stage08_composite_context(fixture.uow, composite, now=NOW)
        is None
    )


def test_pending_group_compression_handoff_is_opaque_and_rereads_current_lineage() -> None:
    fixture = _fixture()
    _high_group_window(fixture, secret="e2-group-private-sentinel")
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )

    material = prepare_stage08_group_compression_material(
        fixture.uow, composite, now=NOW
    )

    assert composite.view().status == "group_compression_pending"
    assert material is not None
    assert "e2-group-private-sentinel" not in repr(material)
    with pytest.raises(TypeError):
        json.dumps(material)
    with pytest.raises(TypeError):
        composition_service._Stage08GroupCompressionMaterial()
    forged = object.__new__(composition_service._Stage08GroupCompressionMaterial)
    assert validate_stage08_group_compression_digest(
        fixture.uow, forged, digest=object(), now=NOW
    ) is False
    digest = Stage08CollaborationContractFactory.compressed_digest(
        text="已压缩的群聊摘要"
    )
    assert validate_stage08_group_compression_digest(
        fixture.uow, material, digest=digest, now=NOW
    ) is True

    fixture.mapping.mapping_version += 1
    assert validate_stage08_group_compression_digest(
        fixture.uow, material, digest=digest, now=NOW
    ) is False


def test_composition_has_no_side_effects_or_prohibited_dependencies() -> None:
    fixture = _fixture()
    _projection(fixture, "read only")
    before = _side_effect_counts(fixture.uow)
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    assert render_stage08_composite_context(fixture.uow, composite, now=NOW)
    assert _side_effect_counts(fixture.uow) == before
    source = inspect.getsource(composition_service)
    for forbidden in (
        "app.models.telegram",
        "raw_text",
        "raw_caption",
        "normalized_text",
        "httpx",
        "requests",
        "OpenRouter",
        "TelegramBot",
        "Redis",
        "pgvector",
        "LangGraph",
    ):
        assert forbidden not in source


def test_inconsistent_over_budget_materialization_returns_no_consumer_content(
    monkeypatch,
) -> None:
    fixture = _fixture()
    for index in range(49):
        _projection(
            fixture,
            "s" * 489,
            minutes_ago=index,
        )
    observed_group_chars = []
    original_compose_direct_result = composition_service._compose_direct_result

    def observe_budget_branch(*args, **kwargs):
        fragments = args[-1]
        observed_group_chars.append(
            sum(len(fragment._text) for fragment in fragments)
        )
        return original_compose_direct_result(*args, **kwargs)

    def inconsistent_materialization(*_args, **_kwargs):
        fragments = tuple(
            composition_service._group_context_service._SelectedGroupContextFragment(
                text="z" * 500,
                display_id=f"group_context:{index:02d}",
            )
            for index in range(1, 50)
        )
        return composition_service._group_context_service._GroupContextMaterialization(
            available=True,
            fragments=fragments,
        )

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        inconsistent_materialization,
    )
    monkeypatch.setattr(
        composition_service,
        "_compose_direct_result",
        observe_budget_branch,
    )
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    assert composite.view().status == "no_evidence"
    assert composite.view().usage.total_content_chars == 0
    assert observed_group_chars == [24_500]
    assert render_stage08_composite_context(fixture.uow, composite, now=NOW) is None


def test_high_window_returns_opaque_pending_view_without_materializing_body(
    monkeypatch,
) -> None:
    fixture = _fixture()
    _, secrets = _high_group_window(fixture)
    before = _side_effect_counts(fixture.uow)
    materializer_calls = []

    def forbidden_materializer(*_args, **_kwargs):
        materializer_calls.append(True)
        raise AssertionError("pending path must not materialize group body")

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        forbidden_materializer,
    )

    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    view = composite.view()

    assert view.status == "group_compression_pending"
    assert view.c1_status == "internal_evidence"
    assert view.group_status == "group_context_available"
    assert view.group_compression_required is True
    assert view.usage.c1_evidence_items == 1
    assert view.usage.group_window_fragments == 49
    assert view.usage.group_rendered_fragments == 0
    assert view.usage.group_rendered_chars == 0
    assert view.usage.total_content_chars == view.usage.c1_content_chars
    assert view.usage.total_content_chars > 0

    rendered = render_stage08_composite_context(
        fixture.uow, composite, now=NOW
    )
    assert rendered is not None
    assert "[business_data:01" in rendered
    assert all(secret not in rendered for secret in secrets)
    assert materializer_calls == []
    assert _side_effect_counts(fixture.uow) == before

    safe_json = view.model_dump_json()
    private_repr = repr(composite)
    with pytest.raises(TypeError) as serialization_error:
        json.dumps(composite)
    error_text = str(serialization_error.value)
    for forbidden in (
        *secrets,
        str(fixture.workspace.id),
        str(fixture.customer.id),
        str(fixture.project.id),
        str(fixture.binding.id),
        str(fixture.mapping.id),
        fixture.actor.actor_id,
    ):
        assert forbidden not in safe_json
        assert forbidden not in private_repr
        assert forbidden not in error_text


@pytest.mark.parametrize(
    ("c1_kind", "expected_c1_status"),
    [
        ("general", "general_advice_only"),
        ("none", "no_evidence"),
    ],
)
def test_pending_without_internal_c1_evidence_is_not_renderable(
    c1_kind: str,
    expected_c1_status: str,
    monkeypatch,
) -> None:
    fixture = _fixture()
    _, secrets = _high_group_window(fixture, secret=f"{c1_kind}-secret")
    plan = _plan(
        fixture,
        allow_general_advice=c1_kind == "general",
    )
    fixture.view.version += 1

    def forbidden_materializer(*_args, **_kwargs):
        raise AssertionError("pending path must not materialize group body")

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        forbidden_materializer,
    )
    composite = compose_stage08_context(
        fixture.uow, plan, actor=fixture.actor, now=NOW
    )

    assert composite.view().status == "group_compression_pending"
    assert composite.view().c1_status == expected_c1_status
    assert composite.view().usage.c1_evidence_items == 0
    assert composite.view().usage.c1_content_chars == 0
    assert composite.view().usage.total_content_chars == 0
    rendered = render_stage08_composite_context(
        fixture.uow, composite, now=NOW
    )
    assert rendered is None
    assert all(secret not in repr(composite) for secret in secrets)


@pytest.mark.parametrize(
    "drift",
    [
        "projection",
        "source_type",
        "mapping",
        "member",
        "binding",
        "relation",
        "retention",
        "view",
        "actor",
    ],
)
def test_pending_renderer_fails_closed_on_original_lineage_drift(
    drift: str,
    monkeypatch,
) -> None:
    fixture = _fixture()
    projections, secrets = _high_group_window(fixture, secret=f"{drift}-secret")
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    assert composite.view().status == "group_compression_pending"

    if drift == "projection":
        projections[0].lifecycle_status = "purged"
        projections[0].content_fragment = ""
    elif drift == "source_type":
        projections[0].source_chat_type = "unknown"
    elif drift == "mapping":
        fixture.mapping.mapping_version += 1
    elif drift == "member":
        fixture.member.status = "inactive"
    elif drift == "binding":
        fixture.binding.status = "inactive"
    elif drift == "relation":
        fixture.project.record_values["customer"] = []
    elif drift == "retention":
        projections[0].retention_expires_at = NOW
    elif drift == "view":
        fixture.view.version += 1
    else:
        composite._actor = Actor(
            actor_type="user",
            actor_id=fixture.actor.actor_id,
            role="viewer",
        )

    def forbidden_materializer(*_args, **_kwargs):
        raise AssertionError("stale pending lineage must not materialize group body")

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        forbidden_materializer,
    )
    rendered = render_stage08_composite_context(
        fixture.uow, composite, now=NOW
    )

    assert rendered is None
    assert all(secret not in repr(composite) for secret in secrets)


@pytest.mark.parametrize("forgery", ["window_view", "handles"])
def test_pending_renderer_rejects_forged_window_state(
    forgery: str,
    monkeypatch,
) -> None:
    fixture = _fixture()
    _high_group_window(fixture, secret=f"forged-{forgery}-secret")
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    assert composite.view().status == "group_compression_pending"
    if forgery == "window_view":
        composite._group_window._view = object()
    else:
        composite._group_window._projection_handles = (
            *composite._group_window._projection_handles[:-1],
            object(),
        )

    def forbidden_materializer(*_args, **_kwargs):
        raise AssertionError("forged pending state must not materialize group body")

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        forbidden_materializer,
    )
    assert (
        render_stage08_composite_context(fixture.uow, composite, now=NOW)
        is None
    )


def test_original_pending_composite_cannot_consume_a_new_direct_window(
    monkeypatch,
) -> None:
    fixture = _fixture()
    projections, _ = _high_group_window(fixture, secret="direct-transition-secret")
    composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    assert composite.view().status == "group_compression_pending"

    projections[0].lifecycle_status = "purged"
    projections[0].content_fragment = ""

    def forbidden_materializer(*_args, **_kwargs):
        raise AssertionError("pending-to-direct transition requires explicit rebuild")

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        forbidden_materializer,
    )
    assert (
        render_stage08_composite_context(fixture.uow, composite, now=NOW)
        is None
    )


def test_pending_composition_has_no_provider_or_persistence_dependency() -> None:
    source = inspect.getsource(composition_service)
    for forbidden in (
        "Provider",
        "LLM",
        "app.models.telegram",
        "MemoryItem",
        "httpx",
        "requests",
        "OpenRouter",
        "TelegramBot",
        "Redis",
        "pgvector",
        "LangGraph",
        "AgentRun",
        "audit",
        "outbox",
    ):
        assert forbidden not in source


def test_direct_composite_transitioning_to_pending_renders_current_c1_only() -> None:
    fixture = _fixture()
    direct_group_secret = "old-direct-group-secret-" + ("d" * 476)
    assert len(direct_group_secret) == 500
    _projection(fixture, direct_group_secret, minutes_ago=100)
    direct_composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    assert direct_composite.view().status == "internal_evidence"
    assert direct_composite.view().group_compression_required is False

    pending_group_secrets = []
    for index in range(48):
        marker = f"new-pending-group-secret-{index:02d}-"
        fragment = marker + ("p" * (500 - len(marker)))
        assert len(fragment) == 500
        _projection(fixture, fragment, minutes_ago=index)
        pending_group_secrets.append(fragment)
    assert len(direct_group_secret) + sum(
        len(fragment) for fragment in pending_group_secrets
    ) == 24_500

    rendered = render_stage08_composite_context(
        fixture.uow, direct_composite, now=NOW
    )

    assert rendered is not None
    assert "[business_data:01" in rendered
    assert "Launch C3" in rendered
    assert direct_group_secret not in rendered
    assert all(fragment not in rendered for fragment in pending_group_secrets)


def test_direct_to_pending_renderer_never_materializes_group_body(
    monkeypatch,
) -> None:
    fixture = _fixture()
    direct_group_secret = "old-direct-materialization-secret-" + ("d" * 466)
    assert len(direct_group_secret) == 500
    _projection(fixture, direct_group_secret, minutes_ago=100)
    direct_composite = compose_stage08_context(
        fixture.uow, _plan(fixture), actor=fixture.actor, now=NOW
    )
    for index in range(48):
        marker = f"new-pending-materialization-secret-{index:02d}-"
        _projection(
            fixture,
            marker + ("p" * (500 - len(marker))),
            minutes_ago=index,
        )

    materializer_calls = []

    def forbidden_materializer(*_args, **_kwargs):
        materializer_calls.append(True)
        raise AssertionError("direct-to-pending renderer must not materialize group body")

    monkeypatch.setattr(
        composition_service,
        "_materialize_group_context_window",
        forbidden_materializer,
    )
    rendered = render_stage08_composite_context(
        fixture.uow, direct_composite, now=NOW
    )

    assert rendered is not None
    assert "Launch C3" in rendered
    assert direct_group_secret not in rendered
    assert materializer_calls == []
