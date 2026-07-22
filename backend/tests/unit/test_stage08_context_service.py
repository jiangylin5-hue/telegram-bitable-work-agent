from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

import pytest

from app.models.stage08_memory import Stage08MemoryItem
from app.runtime.stage08_context_contracts import (
    ContextBudget,
    ContextBudgetUsage,
    ContextPack,
    ContextPlan,
    ContextPlanningRequest,
    ContextSourcePlan,
    EvidenceItem,
    EvidenceScope,
    EvidenceVersion,
    ResolvedBusinessScope,
)
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_context import (
    _normalize_json,
    build_context_plan,
    compose_context_pack,
    render_evidence_pack,
    resolve_business_scope,
)
from app.services.stage08_memory import materialize_memory_from_projection


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _budget(**overrides) -> ContextBudget:
    values = {
        "max_table_records": 20,
        "max_memory_items": 12,
        "max_evidence_items": 24,
        "max_item_chars": 2000,
        "max_total_chars": 12000,
    }
    values.update(overrides)
    return ContextBudget(**values)


def _fixture(*, memory: bool = True):
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow, name="Context", owner_user_id=owner.actor_id, actor=owner
    )
    base = create_base(uow, workspace.id, name="CRM", actor=owner)
    customers = create_table(uow, base.id, name="Customers", key="customers", actor=owner)
    projects = create_table(uow, base.id, name="Projects", key="projects", actor=owner)
    create_field(uow, customers.id, name="Name", key="name", field_type="text", actor=owner)
    create_field(uow, projects.id, name="Title", key="title", field_type="text", actor=owner)
    create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="Hidden",
        key="hidden_field",
        field_type="text",
        permission_policy={"owner": "hidden", "viewer": "hidden"},
        actor=owner,
    )
    customer = create_record(uow, customers.id, values={"name": "Acme"}, actor=owner)
    project = create_record(
        uow,
        projects.id,
        values={
            "title": "Launch",
            "customer": [str(customer.id)],
            "hidden_field": "never",
        },
        actor=owner,
    )
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["title", "customer", "hidden_field"]},
        actor=owner,
    )
    # SQLAlchemy applies this server-side default in PostgreSQL; the in-memory
    # UoW intentionally does not flush column defaults.
    view.version = 1
    employee = create_digital_employee(
        uow,
        base.id,
        name="Context employee",
        description="Bounded context",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=owner,
    )
    item = None
    if memory:
        item = materialize_memory_from_projection(
            uow,
            MemoryMaterializationProjection(
                memory_type="decision",
                scope=MemoryScopeProjection(
                    workspace_id=workspace.id,
                    base_id=base.id,
                    table_id=projects.id,
                    customer_record_id=customer.id,
                    project_record_id=project.id,
                ),
                payload={"title": "Launch"},
                source_refs=(
                    MemorySourceRef(
                        source_kind="platform_record",
                        source_id=project.id,
                        source_version=project.version,
                        field_keys=("title",),
                    ),
                ),
                valid_until=NOW + timedelta(days=1),
            ),
            actor=owner,
            now=NOW,
        )
    return uow, owner, workspace, base, customers, projects, customer, project, view, employee, item


def _request(workspace, employee, view, *, intent="mixed", **overrides):
    values = {
        "workspace_id": workspace.id,
        "employee_id": employee.id,
        "intent": intent,
        "view_ids": (view.id,) if intent in {"business_fact", "mixed"} else (),
        "customer_record_id": None,
        "project_record_id": None,
        "allow_general_advice": True,
        "budget": _budget(),
    }
    values.update(overrides)
    return ContextPlanningRequest(**values)


def test_resolver_accepts_only_visible_one_hop_customer_project_relation() -> None:
    uow, owner, workspace, _base, _customers, _projects, customer, project, _view, employee, _item = _fixture()
    scope = resolve_business_scope(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
        customer_record_id=customer.id,
        project_record_id=project.id,
    )
    assert scope.relation_kind == "visible_linked_record"
    assert scope.customer_version == customer.version
    assert scope.project_version == project.version
    assert "values" not in scope.model_dump()


@pytest.mark.parametrize("drift", ["foreign_workspace", "hidden_relation", "inactive_record", "employee_table_out_of_scope"])
def test_resolver_fails_closed_for_invalid_or_invisible_relation(drift: str) -> None:
    uow, owner, workspace, _base, customers, projects, customer, project, _view, employee, _item = _fixture()
    if drift == "foreign_workspace":
        foreign = create_workspace(uow, name="Foreign", owner_user_id=owner.actor_id)
        foreign_base = create_base(uow, foreign.id, name="Foreign")
        foreign_table = create_table(uow, foreign_base.id, name="Foreign", key="foreign")
        create_field(uow, foreign_table.id, name="Name", key="name", field_type="text")
        customer = create_record(uow, foreign_table.id, values={"name": "Foreign"})
        employee.accessible_tables.append(str(foreign_table.id))
    elif drift == "hidden_relation":
        relation_field = next(field for field in uow.fields if field.key == "customer")
        relation_field.permission_policy = {"owner": "hidden"}
    elif drift == "inactive_record":
        project.record_status = "inactive"
    else:
        employee.accessible_tables = [str(customers.id)]
    with pytest.raises(PlatformValidationError, match="context_business_scope_denied"):
        resolve_business_scope(
            uow,
            workspace_id=workspace.id,
            employee_id=employee.id,
            actor=owner,
            customer_record_id=customer.id,
            project_record_id=project.id,
        )


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ("business_fact", ("table_view", "general_advice")),
        ("memory_lookup", ("business_memory", "general_advice")),
        ("mixed", ("table_view", "business_memory", "general_advice")),
        ("general_advice", ("general_advice",)),
    ],
)
def test_planner_uses_fixed_source_matrix(intent: str, expected: tuple[str, ...]) -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, _item = _fixture()
    plan = build_context_plan(uow, _request(workspace, employee, view, intent=intent), actor=owner)
    assert tuple(source.source_kind for source in plan.sources) == expected


def test_planner_fails_closed_when_employee_or_view_authority_changes() -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, _item = _fixture()
    request = _request(workspace, employee, view, intent="business_fact")
    employee.allowed_actions = ["draft_update"]
    with pytest.raises(PlatformValidationError, match="context_authority_denied"):
        build_context_plan(uow, request, actor=owner)
    employee.allowed_actions = ["query"]
    view.status = "inactive"
    with pytest.raises(PlatformValidationError, match="context_view_denied"):
        build_context_plan(uow, request, actor=owner)


def test_compose_uses_only_visible_bounded_table_and_platform_memory_projection() -> None:
    uow, owner, workspace, _base, _customers, _projects, customer, project, view, employee, _item = _fixture()
    plan = build_context_plan(
        uow,
        _request(
            workspace,
            employee,
            view,
            customer_record_id=customer.id,
            project_record_id=project.id,
        ),
        actor=owner,
    )
    pack = compose_context_pack(uow, plan, actor=owner, now=NOW)
    assert [item.label for item in pack.evidence] == ["business_data", "confirmed_memory"]
    assert all("hidden_field" not in json.dumps(item.content) for item in pack.evidence)
    assert all("group_chat_ref" not in item.scope.model_dump() for item in pack.evidence)
    assert pack.usage.table_records_selected == 1
    assert pack.usage.memory_items_selected == 1
    rendered = render_evidence_pack(pack)
    assert str(customer.id) not in rendered
    assert str(project.id) not in rendered


def test_compose_rereads_and_falls_back_when_record_and_memory_versions_drift() -> None:
    uow, owner, workspace, _base, _customers, _projects, customer, project, view, employee, item = _fixture()
    plan = build_context_plan(
        uow,
        _request(
            workspace,
            employee,
            view,
            customer_record_id=customer.id,
            project_record_id=project.id,
        ),
        actor=owner,
    )
    project.version += 1
    item.status = "revoked"
    pack = compose_context_pack(uow, plan, actor=owner, now=NOW)
    assert pack.status == "general_advice_only"
    assert [evidence.label for evidence in pack.evidence] == ["general_advice"]
    assert {omission.reason_code for omission in pack.omissions} >= {
        "business_scope_changed"
    }


def test_budget_renderer_and_composition_are_deterministic_and_id_free() -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, _item = _fixture(memory=False)
    request = _request(
        workspace,
        employee,
        view,
        intent="business_fact",
        budget=_budget(max_item_chars=128, max_total_chars=256),
    )
    plan = build_context_plan(uow, request, actor=owner)
    first = compose_context_pack(uow, plan, actor=owner, now=NOW)
    second = compose_context_pack(uow, plan, actor=owner, now=NOW)
    rendered = render_evidence_pack(first)
    assert first.model_dump_json() == second.model_dump_json()
    assert rendered == render_evidence_pack(second)
    assert first.usage.content_chars <= first.plan.budget.max_total_chars
    assert str(workspace.id) not in rendered
    assert str(view.id) not in rendered
    assert "permission" not in rendered
    assert "identity_token" not in rendered


def test_general_advice_plan_never_lists_table_or_memory_sources() -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, _item = _fixture()
    plan = build_context_plan(uow, _request(workspace, employee, view, intent="general_advice"), actor=owner)
    pack = compose_context_pack(uow, plan, actor=owner, now=NOW)
    assert pack.status == "general_advice_only"
    assert pack.evidence[0].content == {"internal_evidence": False}
    assert pack.usage.table_records_considered == 0
    assert pack.usage.memory_items_considered == 0


def test_compose_enforces_global_table_budget_across_multiple_views() -> None:
    uow, owner, workspace, base, _customers, projects, _customer, _project, view, employee, _item = _fixture(memory=False)
    second_view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Second",
        view_type="grid",
        config={"fields": ["title"]},
        actor=owner,
    )
    second_view.version = 1
    employee.accessible_views.append(str(second_view.id))
    request = _request(
        workspace,
        employee,
        view,
        intent="business_fact",
        view_ids=(view.id, second_view.id),
        budget=_budget(max_table_records=1),
    )
    pack = compose_context_pack(
        uow, build_context_plan(uow, request, actor=owner), actor=owner, now=NOW
    )
    assert pack.usage.table_records_considered == 1
    assert pack.usage.table_records_selected == 1


def test_compose_defers_group_memory_without_reading_its_payload() -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, item = _fixture()
    item.status = "revoked"
    sentinel = "group-payload-must-not-enter-c1"
    uow.add_memory_item(
        Stage08MemoryItem(
            id=uuid4(),
            workspace_id=workspace.id,
            memory_type="decision",
            status="active",
            scope={
                "workspace_id": str(workspace.id),
                "group_chat_ref": f"stage06-binding:{uuid4()}",
            },
            payload={"summary": sentinel},
            source_refs=[
                {
                    "source_kind": "telegram_message",
                    "source_id": str(uuid4()),
                    "source_version": 1,
                    "field_keys": ["group_candidate_projection"],
                }
            ],
            source_fingerprint=uuid4().hex + uuid4().hex,
            version=1,
            valid_until=NOW + timedelta(minutes=5),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    plan = build_context_plan(
        uow, _request(workspace, employee, view, intent="memory_lookup"), actor=owner
    )
    pack = compose_context_pack(uow, plan, actor=owner, now=NOW)
    assert pack.status == "general_advice_only"
    assert sentinel not in render_evidence_pack(pack)
    assert any(item.reason_code == "group_source_deferred" for item in pack.omissions)


def test_compose_fails_closed_when_view_version_changes_after_plan() -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, _item = _fixture(memory=False)
    plan = build_context_plan(
        uow, _request(workspace, employee, view, intent="business_fact"), actor=owner
    )
    view.version += 1
    pack = compose_context_pack(uow, plan, actor=owner, now=NOW)
    assert pack.status == "general_advice_only"
    assert any(item.reason_code == "view_version_changed" for item in pack.omissions)


def test_compose_revalidates_constructed_plan_and_rejects_source_expansion() -> None:
    uow, owner, workspace, _base, _customers, _projects, _customer, _project, view, employee, _item = _fixture()
    valid = build_context_plan(
        uow, _request(workspace, employee, view, intent="memory_lookup"), actor=owner
    )
    table_source = ContextSourcePlan(
        source_kind="table_view",
        priority=1,
        view_id=view.id,
        source_version=view.version,
        max_items=1,
        reason_code="business_fact_requested",
    )
    expanded = ContextPlan.model_construct(
        contract_version=valid.contract_version,
        workspace_id=valid.workspace_id,
        employee_id=valid.employee_id,
        actor_user_id=valid.actor_user_id,
        intent=valid.intent,
        business_scope=valid.business_scope,
        budget=valid.budget,
        sources=(table_source,) + valid.sources,
    )
    with pytest.raises(PlatformValidationError, match="context_plan_invalid"):
        compose_context_pack(uow, expanded, actor=owner, now=NOW)


def test_composer_redacts_embedded_uuid_and_rejects_sensitive_metadata_key() -> None:
    uow, owner, workspace, _base, _customers, projects, _customer, project, view, employee, _item = _fixture(memory=False)
    project.record_values["title"] = f"record:{project.id}:current"
    plan = build_context_plan(
        uow, _request(workspace, employee, view, intent="business_fact"), actor=owner
    )
    pack = compose_context_pack(uow, plan, actor=owner, now=NOW)
    rendered = render_evidence_pack(pack)
    assert str(project.id) not in rendered
    assert "record:[internal-reference]:current" in rendered

    create_field(
        uow,
        projects.id,
        name="Permissions",
        key="permissions",
        field_type="json",
        actor=owner,
    )
    project.record_values["permissions"] = {"viewer": "read"}
    view.config["fields"].append("permissions")
    denied = compose_context_pack(uow, plan, actor=owner, now=NOW)
    assert all("permissions" not in item.content for item in denied.evidence)
    assert any(
        item.reason_code == "source_revalidation_failed" for item in denied.omissions
    )


@pytest.mark.parametrize(
    ("request_scope", "memory_scope", "selected"),
    [
        ((), (), True),
        (("customer",), ("customer",), True),
        (("project",), ("project",), True),
        (("customer", "project"), ("customer", "project"), True),
        (("customer",), (), False),
        (("customer",), ("project",), False),
        (("customer",), ("customer", "project"), False),
        ((), ("customer",), False),
    ],
)
def test_memory_scope_matches_customer_and_project_dimensions_exactly(
    request_scope: tuple[str, ...],
    memory_scope: tuple[str, ...],
    selected: bool,
) -> None:
    uow, owner, workspace, _base, _customers, _projects, customer, project, view, employee, item = _fixture()
    item.scope.pop("customer_record_id", None)
    item.scope.pop("project_record_id", None)
    if "customer" in memory_scope:
        item.scope["customer_record_id"] = str(customer.id)
    if "project" in memory_scope:
        item.scope["project_record_id"] = str(project.id)
    request = _request(
        workspace,
        employee,
        view,
        intent="memory_lookup",
        customer_record_id=customer.id if "customer" in request_scope else None,
        project_record_id=project.id if "project" in request_scope else None,
    )
    pack = compose_context_pack(
        uow, build_context_plan(uow, request, actor=owner), actor=owner, now=NOW
    )
    assert (pack.usage.memory_items_selected == 1) is selected
    assert (pack.evidence[0].label == "confirmed_memory") is selected


@pytest.mark.parametrize(
    "content",
    (
        {"record_id": "opaque-internal-id"},
        {"Memory-ID": "opaque-internal-id"},
        {"ID": "opaque-internal-id"},
    ),
)
def test_renderer_rejects_constructed_internal_identifier_carriers(
    content: dict[str, str],
) -> None:
    workspace_id = uuid4()
    view_id = uuid4()
    plan = ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=workspace_id,
        employee_id=uuid4(),
        actor_user_id="viewer",
        intent="business_fact",
        business_scope=ResolvedBusinessScope(
            workspace_id=workspace_id, relation_kind="none"
        ),
        budget=_budget(),
        sources=(
            ContextSourcePlan(
                source_kind="table_view",
                priority=1,
                view_id=view_id,
                source_version=4,
                max_items=1,
                reason_code="business_fact_requested",
            ),
        ),
    )
    evidence = EvidenceItem.model_construct(
        evidence_id="business_data:01",
        label="business_data",
        source_type="platform_record",
        scope=EvidenceScope(
            workspace_id=workspace_id,
            base_id=uuid4(),
            table_id=uuid4(),
            view_id=view_id,
        ),
        version=EvidenceVersion(kind="record", value=1),
        source_version=4,
        content=content,
        truncated=False,
        truncated_paths=(),
    )
    pack = ContextPack.model_construct(
        plan=plan,
        status="internal_evidence",
        evidence=(evidence,),
        omissions=(),
        usage=ContextBudgetUsage(
            table_records_considered=1,
            table_records_selected=1,
            memory_items_considered=0,
            memory_items_selected=0,
            evidence_items=1,
            content_chars=len(json.dumps(content, sort_keys=True, separators=(",", ":"))),
            truncated_items=0,
            omitted_items=0,
        ),
    )
    with pytest.raises(PlatformValidationError, match="context_pack_invalid"):
        render_evidence_pack(pack)


def test_json_normalization_has_fixed_string_list_depth_paths_and_rejects_nonfinite() -> None:
    embedded_id = uuid4()
    normalized, paths = _normalize_json(
        {
            "long": "x" * 300,
            "items": list(range(25)),
            "deep": {"a": {"b": {"c": {"d": "cut"}}}},
            f"record:{embedded_id}": "safe-key-value",
        }
    )
    assert normalized["long"] == "x" * 255 + "…"
    assert normalized["items"] == list(range(20))
    assert normalized["deep"]["a"]["b"]["c"] is None
    assert normalized["record:[internal-reference]"] == "safe-key-value"
    assert str(embedded_id) not in json.dumps(normalized)
    assert paths == [
        "$.deep.a.b.c",
        "$.items",
        "$.long",
        "$.[redacted-key]",
    ]
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="context_json_value_invalid"):
            _normalize_json({"unsafe": value})


def test_item_and_total_budget_produce_fixed_omissions_without_invalid_json() -> None:
    uow, owner, workspace, _base, _customers, projects, customer, project, view, employee, _item = _fixture(memory=False)
    project.record_values["title"] = "x" * 500
    item_limited = compose_context_pack(
        uow,
        build_context_plan(
            uow,
            _request(
                workspace,
                employee,
                view,
                intent="business_fact",
                budget=_budget(max_table_records=1, max_item_chars=128),
            ),
            actor=owner,
        ),
        actor=owner,
        now=NOW,
    )
    assert any(item.reason_code == "item_budget_exceeded" for item in item_limited.omissions)
    assert item_limited.status == "general_advice_only"

    project.record_values["title"] = "a" * 120
    create_record(
        uow,
        projects.id,
        values={
            "title": "b" * 120,
            "customer": [str(customer.id)],
            "hidden_field": "never",
        },
        actor=owner,
    )
    total_limited = compose_context_pack(
        uow,
        build_context_plan(
            uow,
            _request(
                workspace,
                employee,
                view,
                intent="business_fact",
                budget=_budget(max_table_records=2, max_total_chars=256),
            ),
            actor=owner,
        ),
        actor=owner,
        now=NOW,
    )
    assert total_limited.usage.table_records_selected == 1
    assert any(item.reason_code == "total_budget_exceeded" for item in total_limited.omissions)
    json.loads(json.dumps(total_limited.evidence[0].content, allow_nan=False))
