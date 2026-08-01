from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.permissions import Actor
from app.services.agent_stage12_fixture_resolution import (
    resolve_stage12_isolated_workspace,
)
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
)
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture


ACTOR = Actor(actor_type="user", actor_id="stage12-eval-owner", role="owner")


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    fixture = materialize_stage12_evaluation_fixture(uow, ACTOR)
    employee = create_digital_employee(
        uow,
        fixture.base_id,
        name="Stage12 Evaluator",
        description="Read-only isolated Stage12 evaluation employee",
        telegram_alias=None,
        accessible_tables=[str(value) for value in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=["schema_inspect", "query", "summarize"],
        actor=ACTOR,
    )
    return uow, fixture, employee


def _business_counts(uow: InMemoryStage06PlatformUnitOfWork) -> tuple[int, ...]:
    return (
        len(uow.workspaces),
        len(uow.bases),
        len(uow.tables),
        len(uow.fields),
        len(uow.records),
        len(uow.record_links),
        len(uow.digital_employees),
    )


def test_resolver_returns_exact_read_only_workspace_context_without_creating_data() -> (
    None
):
    uow, fixture, employee = _fixture()
    before = _business_counts(uow)

    context = resolve_stage12_isolated_workspace(
        uow,
        workspace_id=fixture.core.workspace_id,
        actor_user_id=ACTOR.actor_id,
        digital_employee_id=employee.id,
    )

    assert context.workspace_id == fixture.core.workspace_id
    assert context.base_id == fixture.base_id
    assert context.table_ids == fixture.table_ids
    assert context.actor_user_id == ACTOR.actor_id
    assert context.digital_employee_id == employee.id
    assert _business_counts(uow) == before


def test_resolver_rejects_missing_workspace_or_unauthorized_actor() -> None:
    uow, fixture, employee = _fixture()

    with pytest.raises(ValueError, match="stage12_isolated_workspace_not_found"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=uuid4(),
            actor_user_id=ACTOR.actor_id,
            digital_employee_id=employee.id,
        )
    with pytest.raises(ValueError, match="stage12_isolated_actor_unauthorized"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=fixture.core.workspace_id,
            actor_user_id="outside-user",
            digital_employee_id=employee.id,
        )


def test_resolver_rejects_ambiguous_base_or_fixture_marker_drift() -> None:
    uow, fixture, employee = _fixture()
    create_base(
        uow,
        fixture.core.workspace_id,
        name="Second Base",
        actor=ACTOR,
    )

    with pytest.raises(ValueError, match="stage12_isolated_base_ambiguous"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=fixture.core.workspace_id,
            actor_user_id=ACTOR.actor_id,
            digital_employee_id=employee.id,
        )

    uow.bases.pop()
    uow.workspaces[0].name = "Renamed"
    with pytest.raises(ValueError, match="stage12_isolated_workspace_marker_mismatch"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=fixture.core.workspace_id,
            actor_user_id=ACTOR.actor_id,
            digital_employee_id=employee.id,
        )


def test_resolver_rejects_employee_scope_or_schema_drift() -> None:
    uow, fixture, employee = _fixture()
    employee.accessible_tables = employee.accessible_tables[:-1]

    with pytest.raises(ValueError, match="stage12_isolated_employee_scope_mismatch"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=fixture.core.workspace_id,
            actor_user_id=ACTOR.actor_id,
            digital_employee_id=employee.id,
        )

    employee.accessible_tables = [str(value) for value in fixture.table_ids.values()]
    uow.tables[0].key = "renamed_projects"
    with pytest.raises(ValueError, match="stage12_isolated_table_marker_mismatch"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=fixture.core.workspace_id,
            actor_user_id=ACTOR.actor_id,
            digital_employee_id=employee.id,
        )


def test_resolver_rejects_assigned_employee_without_exact_member_grant() -> None:
    uow, fixture, employee = _fixture()
    employee.access_mode = "assigned"

    with pytest.raises(ValueError, match="stage12_isolated_actor_unauthorized"):
        resolve_stage12_isolated_workspace(
            uow,
            workspace_id=fixture.core.workspace_id,
            actor_user_id=ACTOR.actor_id,
            digital_employee_id=employee.id,
        )
