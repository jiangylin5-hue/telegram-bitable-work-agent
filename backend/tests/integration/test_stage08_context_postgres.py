from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import pytest

from app.models.stage08_memory import Stage08MemoryItem
from app.models.telegram import Message
from app.runtime.stage08_context_contracts import ContextBudget, ContextPlanningRequest
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_context import (
    build_context_plan,
    compose_context_pack,
    render_evidence_pack,
)
from app.services.stage08_memory import materialize_memory_from_projection
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    stage06_postgres,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=f"{DATABASE_URL_ENV} is required for disposable C1 PostgreSQL tests",
    ),
]


def _seed(stage06_postgres: Stage06Postgres):
    session = stage06_postgres.session_factory()
    uow = SqlAlchemyStage06PlatformUnitOfWork(session)
    actor = Actor(actor_type="user", actor_id="context-owner", role="owner")
    workspace = create_workspace(
        uow, name=f"Context {uuid4().hex[:8]}", owner_user_id=actor.actor_id, actor=actor
    )
    uow.flush()
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    customers = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    projects = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    create_field(uow, customers.id, name="Name", key="name", field_type="text", actor=actor)
    title = create_field(uow, projects.id, name="Title", key="title", field_type="text", actor=actor)
    relation = create_field(
        uow,
        projects.id,
        name="Customer",
        key="customer",
        field_type="linked_record",
        options={"target_table_id": str(customers.id)},
        actor=actor,
    )
    hidden = create_field(
        uow,
        projects.id,
        name="Hidden",
        key="hidden_field",
        field_type="text",
        permission_policy={"owner": "hidden"},
        actor=actor,
    )
    uow.flush()
    customer = create_record(uow, customers.id, values={"name": "Acme"}, actor=actor)
    uow.flush()
    project = create_record(
        uow,
        projects.id,
        values={
            "title": "Launch",
            "customer": [str(customer.id)],
            "hidden_field": "pg-secret-sentinel",
        },
        actor=actor,
    )
    uow.flush()
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["title", "customer", "hidden_field"]},
        actor=actor,
    )
    uow.flush()
    employee = create_digital_employee(
        uow,
        base.id,
        name="Context employee",
        description="C1 PostgreSQL fixture",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=actor,
    )
    uow.flush()
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
        actor=actor,
        now=NOW,
    )
    uow.flush()
    return session, uow, actor, workspace, base, customers, projects, title, relation, hidden, customer, project, view, employee, item


def _request(workspace, employee, view, *, intent="mixed", scoped=True):
    return ContextPlanningRequest(
        workspace_id=workspace.id,
        employee_id=employee.id,
        intent=intent,
        view_ids=(view.id,) if intent in {"business_fact", "mixed"} else (),
        customer_record_id=workspace._context_customer_id if scoped else None,
        project_record_id=workspace._context_project_id if scoped else None,
        allow_general_advice=True,
        budget=ContextBudget(
            max_table_records=5,
            max_memory_items=5,
            max_evidence_items=10,
            max_item_chars=1000,
            max_total_chars=4000,
        ),
    )


def _attach_scope(workspace, customer, project) -> None:
    # Transient fixture-only attributes; never persisted and never consumed by C1.
    workspace._context_customer_id = customer.id
    workspace._context_project_id = project.id


def test_context_postgres_visible_relation_and_bounded_pack(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    session, uow, actor, workspace, _base, _customers, _projects, _title, _relation, _hidden, customer, project, view, employee, _item = data
    try:
        _attach_scope(workspace, customer, project)
        plan = build_context_plan(uow, _request(workspace, employee, view), actor=actor)
        pack = compose_context_pack(uow, plan, actor=actor, now=NOW)
        assert [item.label for item in pack.evidence] == ["business_data", "confirmed_memory"]
        assert pack.usage.table_records_selected == 1
        assert pack.usage.memory_items_selected == 1
        assert "pg-secret-sentinel" not in render_evidence_pack(pack)
    finally:
        session.rollback()
        session.close()


def test_context_postgres_workspace_wide_memory_scope_is_selected(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    session, uow, actor, workspace, _base, _customers, _projects, _title, _relation, _hidden, customer, project, view, employee, item = data
    try:
        _attach_scope(workspace, customer, project)
        item.scope = {
            key: value
            for key, value in item.scope.items()
            if key not in {"customer_record_id", "project_record_id"}
        }
        uow.flush()
        plan = build_context_plan(
            uow,
            _request(
                workspace,
                employee,
                view,
                intent="memory_lookup",
                scoped=False,
            ),
            actor=actor,
        )
        pack = compose_context_pack(uow, plan, actor=actor, now=NOW)
        assert pack.usage.memory_items_selected == 1
        assert [evidence.label for evidence in pack.evidence] == ["confirmed_memory"]
    finally:
        session.rollback()
        session.close()


def test_context_postgres_field_revocation_after_plan_fails_closed(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    session, uow, actor, workspace, _base, _customers, _projects, title, _relation, _hidden, customer, project, view, employee, _item = data
    try:
        _attach_scope(workspace, customer, project)
        request = _request(workspace, employee, view, intent="business_fact", scoped=False)
        plan = build_context_plan(uow, request, actor=actor)
        title.permission_policy = {"owner": "hidden"}
        title.permission_version += 1
        uow.flush()
        pack = compose_context_pack(uow, plan, actor=actor, now=NOW)
        assert all("Launch" not in str(item.content) for item in pack.evidence)
        assert all("hidden_field" not in str(item.content) for item in pack.evidence)
    finally:
        session.rollback()
        session.close()


def test_context_postgres_record_version_and_relation_drift_after_plan_fails_closed(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    session, uow, actor, workspace, _base, _customers, _projects, _title, _relation, _hidden, customer, project, view, employee, _item = data
    try:
        _attach_scope(workspace, customer, project)
        plan = build_context_plan(uow, _request(workspace, employee, view), actor=actor)
        project.version += 1
        uow.flush()
        pack = compose_context_pack(uow, plan, actor=actor, now=NOW)
        assert pack.status == "general_advice_only"
        assert {item.reason_code for item in pack.omissions} == {"business_scope_changed"}
    finally:
        session.rollback()
        session.close()


def test_context_postgres_memory_ttl_and_source_version_reread_fails_closed(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    session, uow, actor, workspace, _base, _customers, _projects, _title, _relation, _hidden, customer, project, view, employee, item = data
    try:
        _attach_scope(workspace, customer, project)
        plan = build_context_plan(
            uow, _request(workspace, employee, view, intent="memory_lookup", scoped=False), actor=actor
        )
        item.valid_until = NOW
        project.version += 1
        uow.flush()
        audit_count = len(uow.list_audit_events())
        pack = compose_context_pack(uow, plan, actor=actor, now=NOW)
        assert pack.status == "general_advice_only"
        assert "Launch" not in render_evidence_pack(pack)
        assert any(item.reason_code == "source_revalidation_failed" for item in pack.omissions)
        assert item.status == "active"
        assert len(uow.list_audit_events()) == audit_count
    finally:
        session.rollback()
        session.close()


def test_context_postgres_group_memory_and_message_rows_are_never_selected_by_c1(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    session, uow, actor, workspace, _base, _customers, _projects, _title, _relation, _hidden, customer, project, view, employee, item = data
    try:
        _attach_scope(workspace, customer, project)
        item.status = "revoked"
        sentinel = "c1-must-never-read-message-sentinel"
        session.add(
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
            )
        )
        session.add(
            Message(
                id=uuid4(),
                telegram_update_id=f"update-{uuid4()}",
                telegram_chat_id=f"chat-{uuid4()}",
                telegram_message_id=f"message-{uuid4()}",
                raw_text=sentinel,
                raw_caption=None,
                normalized_text=sentinel,
                message_type="text",
                intent_status="unclassified",
                received_at=NOW,
                ingestion_status="stored",
                binding_status="needs_manual_binding",
                processing_status="queued",
                outbox_status="pending",
                trace_id=f"trace-{uuid4()}",
            )
        )
        uow.flush()
        plan = build_context_plan(
            uow, _request(workspace, employee, view, intent="memory_lookup", scoped=False), actor=actor
        )
        pack = compose_context_pack(uow, plan, actor=actor, now=NOW)
        rendered = render_evidence_pack(pack)
        assert pack.status == "general_advice_only"
        assert sentinel not in rendered
        assert any(item.reason_code == "group_source_deferred" for item in pack.omissions)
    finally:
        session.rollback()
        session.close()
