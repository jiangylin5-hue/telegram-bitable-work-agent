from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_group_context import (
    Stage08GroupBusinessContextBinding,
    Stage08GroupMessageProjection,
)
from app.models.telegram import Message
from app.runtime.stage08_context_contracts import (
    ContextBudget,
    ContextPlanningRequest,
)
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
    update_record,
)
from app.services.stage08_context import build_context_plan
from app.services.stage08_context_composition import (
    compose_stage08_context,
    render_stage08_composite_context,
)
from app.services.stage08_group_context import (
    purge_expired_group_context_projections,
)
from app.services.stage08_memory import materialize_memory_from_projection
from tests.integration.test_stage07_governance_postgres import (
    DATABASE_URL_ENV,
    Stage06Postgres,
    stage06_postgres,
)


NOW = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv(DATABASE_URL_ENV),
        reason=(
            f"{DATABASE_URL_ENV} is required for disposable C3 PostgreSQL tests"
        ),
    ),
]


def _seed(stage06_postgres: Stage06Postgres) -> SimpleNamespace:
    session = stage06_postgres.session_factory()
    uow = SqlAlchemyStage06PlatformUnitOfWork(session)
    actor = Actor(actor_type="user", actor_id="stage08-c3-owner", role="owner")
    workspace = create_workspace(
        uow,
        name=f"Stage08 C3 {uuid4().hex[:8]}",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    session.flush()
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="C3 Base", actor=actor)
    customers = create_table(
        uow, base.id, name="Customers", key="customers", actor=actor
    )
    projects = create_table(
        uow, base.id, name="Projects", key="projects", actor=actor
    )
    create_field(
        uow, customers.id, name="Name", key="name", field_type="text", actor=actor
    )
    title = create_field(
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
    session.flush()
    customer = create_record(
        uow, customers.id, values={"name": "C3 PostgreSQL customer"}, actor=actor
    )
    session.flush()
    project = create_record(
        uow,
        projects.id,
        values={
            "title": "C3 PostgreSQL launch",
            "customer": [str(customer.id)],
        },
        actor=actor,
    )
    session.flush()
    view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Projects",
        view_type="grid",
        config={"fields": ["title", "customer"]},
        actor=actor,
    )
    session.flush()
    employee = create_digital_employee(
        uow,
        base.id,
        name="C3 employee",
        description="C3 PostgreSQL composition evidence",
        telegram_alias=None,
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id=f"-100{uuid4().int % 10**9:09d}",
        telegram_user_id=actor.actor_id,
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
    session.flush()
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
    session.flush()
    return SimpleNamespace(
        session=session,
        uow=uow,
        actor=actor,
        workspace=workspace,
        member=member,
        base=base,
        customer=customer,
        project=project,
        title=title,
        view=view,
        employee=employee,
        binding=binding,
        mapping=mapping,
    )


def _plan(
    data: SimpleNamespace,
    *,
    intent: str = "business_fact",
):
    request = ContextPlanningRequest(
        workspace_id=data.workspace.id,
        employee_id=data.employee.id,
        intent=intent,
        view_ids=(data.view.id,) if intent in {"business_fact", "mixed"} else (),
        customer_record_id=data.customer.id,
        project_record_id=data.project.id,
        allow_general_advice=True,
        budget=ContextBudget(
            max_table_records=20,
            max_memory_items=12,
            max_evidence_items=24,
            max_item_chars=2000,
            max_total_chars=12000,
        ),
    )
    return build_context_plan(data.uow, request, actor=data.actor)


def _add_projection(
    data: SimpleNamespace,
    content: str,
    *,
    minutes_ago: int = 0,
) -> Stage08GroupMessageProjection:
    source = Message(
        id=uuid4(),
        telegram_update_id=f"c3-update-{uuid4()}",
        telegram_chat_id=data.binding.telegram_chat_id,
        telegram_message_id=f"c3-message-{uuid4()}",
        telegram_user_id=data.actor.actor_id,
        raw_text=None,
        raw_caption=None,
        normalized_text=None,
        message_type="text",
        intent_status="unclassified",
        received_at=NOW - timedelta(minutes=minutes_ago),
        ingestion_status="stored",
        binding_status="bound",
        processing_status="queued",
        outbox_status="pending",
        trace_id=f"c3-trace-{uuid4()}",
    )
    data.session.add(source)
    data.session.flush()
    projection = Stage08GroupMessageProjection(
        id=uuid4(),
        source_message_id=source.id,
        business_context_binding_id=data.mapping.id,
        content_fragment=content,
        content_version=1,
        event_at=source.received_at,
        edited_at=None,
        retention_expires_at=NOW + timedelta(days=30),
        lifecycle_status="active",
        source_chat_type="group",
    )
    data.uow.add_group_message_projection(projection)
    data.session.flush()
    return projection


def _add_memory(data: SimpleNamespace):
    memory = materialize_memory_from_projection(
        data.uow,
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(
                workspace_id=data.workspace.id,
                base_id=data.base.id,
                table_id=data.project.table_id,
                customer_record_id=data.customer.id,
                project_record_id=data.project.id,
            ),
            payload={"title": "C3 PostgreSQL launch"},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=data.project.id,
                    source_version=data.project.version,
                    field_keys=("title",),
                ),
            ),
            valid_until=NOW + timedelta(days=1),
        ),
        actor=data.actor,
        now=NOW,
    )
    data.session.flush()
    return memory


def _close(data: SimpleNamespace) -> None:
    data.session.rollback()
    data.session.close()


def test_composition_postgres_direct_render_is_current_and_c1_first(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    try:
        newest = _add_projection(data, "c3-pg-direct-newest")
        older = _add_projection(data, "c3-pg-direct-older", minutes_ago=1)
        composite = compose_stage08_context(
            data.uow, _plan(data), actor=data.actor, now=NOW
        )

        rendered = render_stage08_composite_context(
            data.uow, composite, now=NOW
        )

        assert composite.view().status == "internal_evidence"
        assert rendered is not None
        assert rendered.index("[business_data:01") < rendered.index(
            "[group_context:01"
        )
        assert rendered.index(newest.content_fragment) < rendered.index(
            older.content_fragment
        )
        assert (
            "[group_context:01 label=group_context "
            "type=group_message_fragment "
            "scope=workspace/group/customer/project]"
        ) in rendered
    finally:
        _close(data)


@pytest.mark.parametrize("drift", ("record_relation", "field_visibility"))
def test_composition_postgres_rereads_c1_business_state_before_render(
    stage06_postgres: Stage06Postgres,
    drift: str,
) -> None:
    data = _seed(stage06_postgres)
    try:
        group_secret = f"c3-pg-c1-{drift}-group"
        _add_projection(data, group_secret)
        composite = compose_stage08_context(
            data.uow, _plan(data), actor=data.actor, now=NOW
        )
        assert "C3 PostgreSQL launch" in (
            render_stage08_composite_context(data.uow, composite, now=NOW) or ""
        )

        if drift == "record_relation":
            update_record(
                data.uow,
                data.project.id,
                values={"customer": []},
                expected_version=data.project.version,
                actor=data.actor,
            )
        else:
            data.title.permission_policy = {"owner": "hidden"}
            data.title.permission_version += 1
        data.session.flush()

        rendered = render_stage08_composite_context(
            data.uow, composite, now=NOW
        )

        assert rendered is not None
        assert "C3 PostgreSQL launch" not in rendered
        if drift == "record_relation":
            assert group_secret not in rendered
        else:
            assert group_secret in rendered
    finally:
        _close(data)


@pytest.mark.parametrize("drift", ("lifecycle", "source", "scope"))
def test_composition_postgres_rereads_memory_state_before_render(
    stage06_postgres: Stage06Postgres,
    drift: str,
) -> None:
    data = _seed(stage06_postgres)
    try:
        group_secret = "c3-pg-memory-lifecycle-group"
        _add_projection(data, group_secret)
        memory = _add_memory(data)
        composite = compose_stage08_context(
            data.uow, _plan(data, intent="mixed"), actor=data.actor, now=NOW
        )
        assert "[confirmed_memory:" in (
            render_stage08_composite_context(data.uow, composite, now=NOW) or ""
        )

        if drift == "lifecycle":
            memory.status = "revoked"
        elif drift == "source":
            memory.source_refs = [
                {
                    **memory.source_refs[0],
                    "source_version": data.project.version + 1,
                }
            ]
        else:
            memory.scope = {
                **memory.scope,
                "customer_record_id": str(uuid4()),
            }
        data.session.flush()
        rendered = render_stage08_composite_context(
            data.uow, composite, now=NOW
        )

        assert rendered is not None
        assert "[confirmed_memory:" not in rendered
        assert group_secret in rendered
    finally:
        _close(data)


@pytest.mark.parametrize(
    "drift",
    ("mapping", "relation", "provenance", "retention", "purge"),
)
def test_composition_postgres_never_renders_group_after_c2_drift(
    stage06_postgres: Stage06Postgres,
    drift: str,
) -> None:
    data = _seed(stage06_postgres)
    try:
        group_secret = f"c3-pg-c2-{drift}-group"
        projection = _add_projection(data, group_secret, minutes_ago=1)
        composite = compose_stage08_context(
            data.uow, _plan(data), actor=data.actor, now=NOW
        )
        assert group_secret in (
            render_stage08_composite_context(data.uow, composite, now=NOW) or ""
        )

        if drift == "mapping":
            data.mapping.status = "inactive"
        elif drift == "relation":
            update_record(
                data.uow,
                data.project.id,
                values={"customer": []},
                expected_version=data.project.version,
                actor=data.actor,
            )
        elif drift == "provenance":
            projection.source_chat_type = "unknown"
        else:
            projection.retention_expires_at = NOW
            data.session.flush()
            if drift == "purge":
                assert (
                    purge_expired_group_context_projections(data.uow, now=NOW)
                    .purged_count
                    == 1
                )
        data.session.flush()

        rendered = render_stage08_composite_context(
            data.uow, composite, now=NOW
        )

        assert rendered is not None
        assert group_secret not in rendered
    finally:
        _close(data)


def test_composition_postgres_pending_group_drift_fails_closed(
    stage06_postgres: Stage06Postgres,
) -> None:
    data = _seed(stage06_postgres)
    try:
        projections = []
        secrets = []
        for index in range(49):
            marker = f"c3-pg-pending-{index:02d}-"
            content = marker + ("x" * (500 - len(marker)))
            projections.append(_add_projection(data, content, minutes_ago=index))
            secrets.append(content)
        assert sum(len(value) for value in secrets) == 24_500
        composite = compose_stage08_context(
            data.uow, _plan(data), actor=data.actor, now=NOW
        )
        assert composite.view().status == "group_compression_pending"
        assert composite.view().usage.group_rendered_chars == 0

        projections[0].source_chat_type = "unknown"
        data.session.flush()
        rendered = render_stage08_composite_context(
            data.uow, composite, now=NOW
        )

        assert rendered is None
        assert all(secret not in repr(composite) for secret in secrets)
        assert all(secret not in composite.view().model_dump_json() for secret in secrets)
    finally:
        _close(data)
