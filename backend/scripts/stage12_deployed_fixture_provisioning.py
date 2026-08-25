"""Provision the single isolated Stage12 deployed-evaluation workspace."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from app.core.database import get_session_factory
from app.models.stage06_platform import Workspace
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
)
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture


EVALUATION_WORKSPACE_NAME = "Stage12 Quality Architecture V2 Evaluation"


class Stage12DeployedFixtureProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Stage12DeployedFixtureProvisioningResult:
    workspace_id: UUID
    base_id: UUID
    digital_employee_id: UUID
    table_ids: dict[str, UUID]


def provision_stage12_deployed_fixture(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor_user_id: str,
) -> Stage12DeployedFixtureProvisioningResult:
    if _evaluation_workspace_exists(uow):
        raise Stage12DeployedFixtureProvisioningError(
            "stage12_deployed_fixture_already_exists"
        )
    actor = Actor(actor_type="user", actor_id=actor_user_id, role="owner")
    fixture = materialize_stage12_evaluation_fixture(uow, actor)
    hidden_field_keys = {"customer_secret", "internal_note"}
    readable_field_ids = tuple(
        field.id
        for table_id in fixture.table_ids.values()
        for field in uow.list_fields(table_id)
        if field.key not in hidden_field_keys
    )
    writable_field_ids = tuple(
        field.id
        for field in uow.list_fields(fixture.table_ids["tasks"])
        if field.key not in hidden_field_keys
    )
    employee = create_digital_employee(
        uow,
        fixture.base_id,
        name="Stage12 Evaluator",
        description="Read-only deployed Stage12 evaluation employee",
        telegram_alias=None,
        accessible_tables=[str(value) for value in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=[
            "schema_inspect",
            "query",
            "summarize",
            "draft_create",
            "draft_update",
            "task_create",
            "notification.request",
        ],
        field_policy=build_stage12_field_policy_v2(
            readable_field_ids=readable_field_ids,
            writable_field_ids=writable_field_ids,
        ),
        actor=actor,
    )
    return Stage12DeployedFixtureProvisioningResult(
        workspace_id=fixture.core.workspace_id,
        base_id=fixture.base_id,
        digital_employee_id=employee.id,
        table_ids=dict(fixture.table_ids),
    )


def _evaluation_workspace_exists(uow: Stage06PlatformUnitOfWork) -> bool:
    if isinstance(uow, InMemoryStage06PlatformUnitOfWork):
        return any(
            workspace.name == EVALUATION_WORKSPACE_NAME
            for workspace in uow.workspaces
        )
    if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        return (
            uow.session.scalar(
                select(Workspace.id)
                .where(Workspace.name == EVALUATION_WORKSPACE_NAME)
                .limit(1)
            )
            is not None
        )
    raise TypeError("unsupported_stage12_provisioning_unit_of_work")


def build_provisioning_receipt(
    result: Stage12DeployedFixtureProvisioningResult,
) -> dict[str, object]:
    return {
        "status": "created",
        "workspace_id": str(result.workspace_id),
        "base_id": str(result.base_id),
        "digital_employee_id": str(result.digital_employee_id),
        "table_count": len(result.table_ids),
    }


def main() -> int:
    actor_user_id = os.getenv("STAGE12_DEPLOYED_USER_ID", "").strip()
    if not actor_user_id:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "stage12_deployed_user_id_required",
                }
            )
        )
        return 2

    session = get_session_factory()()
    try:
        result = provision_stage12_deployed_fixture(
            SqlAlchemyStage06PlatformUnitOfWork(session),
            actor_user_id=actor_user_id,
        )
        session.commit()
    except Stage12DeployedFixtureProvisioningError as exc:
        session.rollback()
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    except Exception:
        session.rollback()
        print(json.dumps({"status": "failed"}))
        return 1
    finally:
        session.close()

    print(json.dumps(build_provisioning_receipt(result)))
    return 0


__all__ = [
    "build_provisioning_receipt",
    "Stage12DeployedFixtureProvisioningError",
    "Stage12DeployedFixtureProvisioningResult",
    "provision_stage12_deployed_fixture",
]


if __name__ == "__main__":
    raise SystemExit(main())
