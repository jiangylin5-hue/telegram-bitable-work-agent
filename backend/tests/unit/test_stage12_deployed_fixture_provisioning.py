from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.agent_field_policy_v2 import parse_stage12_field_policy_v2
from app.services.agent_stage12_fixture_resolution import (
    resolve_stage12_isolated_workspace,
)
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from scripts import stage12_deployed_fixture_provisioning as provisioning
from scripts.stage12_deployed_fixture_provisioning import (
    Stage12DeployedFixtureProvisioningError,
    Stage12DeployedFixtureProvisioningResult,
    provision_stage12_deployed_fixture,
)


def test_provisioning_creates_one_resolvable_scoped_evaluation_workspace() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()

    result = provision_stage12_deployed_fixture(
        uow,
        actor_user_id="stage12-deployed-eval-owner",
    )

    assert len(uow.workspaces) == 1
    assert uow.workspaces[0].name == "Stage12 Quality Architecture V2 Evaluation"
    assert len(uow.digital_employees) == 1
    employee = uow.digital_employees[0]
    assert employee.id == result.digital_employee_id
    assert set(employee.allowed_actions) == {
        "schema_inspect",
        "query",
        "summarize",
        "draft_create",
        "draft_update",
        "task_create",
        "notification.request",
    }

    policy = parse_stage12_field_policy_v2(employee.field_policy)
    hidden_field_ids = {
        field.id
        for field in uow.fields
        if field.key in {"customer_secret", "internal_note"}
    }
    task_table_id = result.table_ids["tasks"]
    expected_writable = {
        field.id
        for field in uow.fields
        if field.table_id == task_table_id and field.id not in hidden_field_ids
    }
    assert hidden_field_ids.isdisjoint(policy.readable_field_ids)
    assert set(policy.writable_field_ids) == expected_writable

    context = resolve_stage12_isolated_workspace(
        uow,
        workspace_id=result.workspace_id,
        actor_user_id="stage12-deployed-eval-owner",
        digital_employee_id=result.digital_employee_id,
    )
    assert context.table_ids == result.table_ids


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_main_requires_dedicated_actor_before_opening_database(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("STAGE12_DEPLOYED_USER_ID", raising=False)
    monkeypatch.setattr(
        provisioning,
        "get_session_factory",
        lambda: pytest.fail("database must not be opened"),
        raising=False,
    )

    assert provisioning.main() == 2

    assert json.loads(capsys.readouterr().out) == {
        "status": "blocked",
        "reason": "stage12_deployed_user_id_required",
    }


def test_main_commits_once_and_emits_sanitized_receipt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = _FakeSession()
    result = Stage12DeployedFixtureProvisioningResult(
        workspace_id=uuid4(),
        base_id=uuid4(),
        digital_employee_id=uuid4(),
        table_ids={"tasks": uuid4()},
    )
    monkeypatch.setenv("STAGE12_DEPLOYED_USER_ID", "stage12-deployed-eval-owner")
    monkeypatch.setattr(provisioning, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(
        provisioning,
        "SqlAlchemyStage06PlatformUnitOfWork",
        lambda value: SimpleNamespace(session=value),
    )
    monkeypatch.setattr(
        provisioning,
        "provision_stage12_deployed_fixture",
        lambda uow, actor_user_id: result,
    )

    assert provisioning.main() == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt == {
        "status": "created",
        "workspace_id": str(result.workspace_id),
        "base_id": str(result.base_id),
        "digital_employee_id": str(result.digital_employee_id),
        "table_count": 1,
    }
    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


def test_main_rolls_back_when_fixture_already_exists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = _FakeSession()
    monkeypatch.setenv("STAGE12_DEPLOYED_USER_ID", "stage12-deployed-eval-owner")
    monkeypatch.setattr(provisioning, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(
        provisioning,
        "SqlAlchemyStage06PlatformUnitOfWork",
        lambda value: SimpleNamespace(session=value),
    )

    def _raise_duplicate(*args: object, **kwargs: object) -> None:
        raise Stage12DeployedFixtureProvisioningError(
            "stage12_deployed_fixture_already_exists"
        )

    monkeypatch.setattr(
        provisioning,
        "provision_stage12_deployed_fixture",
        _raise_duplicate,
    )

    assert provisioning.main() == 2

    assert json.loads(capsys.readouterr().out) == {
        "status": "blocked",
        "reason": "stage12_deployed_fixture_already_exists",
    }
    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


def test_provisioning_refuses_a_second_evaluation_workspace() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    provision_stage12_deployed_fixture(
        uow,
        actor_user_id="stage12-deployed-eval-owner",
    )

    with pytest.raises(
        Stage12DeployedFixtureProvisioningError,
        match="^stage12_deployed_fixture_already_exists$",
    ):
        provision_stage12_deployed_fixture(
            uow,
            actor_user_id="stage12-deployed-eval-owner",
        )

    assert len(uow.workspaces) == 1
