from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
from uuid import UUID

import app.api.routes.agent_runs as agent_run_routes
from app.core.config import Settings
from app.schemas.agent_task_spec_v2 import (
    AuthorizedEntitySpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    PlannerRequestV2,
    authorized_schema_sha256,
)
from app.services.agent_task_gateway import TaskGatewayRequest, build_task_plan
from app.services.agent_task_planner_shadow import (
    planner_shadow_enabled,
    run_task_planner_shadow,
    run_task_planner_shadow_with_artifact,
)


WORKSPACE_ID = UUID("20000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("20000000-0000-4000-8000-000000000002")
BASE_ID = UUID("20000000-0000-4000-8000-000000000003")
TABLE_ID = UUID("20000000-0000-4000-8000-000000000004")


def _snapshot() -> AuthorizedSchemaSnapshot:
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "a" * 64,
        "tables": (),
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _entity_snapshot() -> AuthorizedSchemaSnapshot:
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "b" * 64,
        "tables": (
            AuthorizedTableSpec(
                table_id=TABLE_ID,
                base_id=BASE_ID,
                key="cases",
                name="案例",
                aliases=(),
                fields=(),
            ),
        ),
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _v1_plan(query: str, *, requested_action: str = "read_only"):
    return build_task_plan(
        TaskGatewayRequest(
            workspace_id=WORKSPACE_ID,
            employee_id=EMPLOYEE_ID,
            actor_user_id="user-shadow",
            intent="business_fact",
            requested_action=requested_action,
            query=query,
            target_record_id=None,
            idempotency_key="stage12-shadow-test",
            skill_id=None,
        )
    )


def _request(query: str) -> PlannerRequestV2:
    return PlannerRequestV2(
        query=query,
        authorized_schema=_snapshot(),
        authorized_entities=(),
        clock=datetime.fromisoformat("2026-07-29T00:00:00+08:00"),
        timezone_name="Asia/Shanghai",
        allowed_action_kinds=(),
    )


def test_shadow_gate_is_default_off_and_workspace_allowlisted() -> None:
    assert planner_shadow_enabled(Settings(), WORKSPACE_ID) is False
    assert (
        planner_shadow_enabled(
            Settings(
                agent_task_planner_v2_mode="shadow",
                agent_task_planner_v2_shadow_workspace_ids=(str(WORKSPACE_ID),),
            ),
            WORKSPACE_ID,
        )
        is True
    )
    assert (
        planner_shadow_enabled(
            Settings(
                agent_task_planner_v2_mode="shadow",
                agent_task_planner_v2_shadow_workspace_ids=(
                    "20000000-0000-4000-8000-000000000099",
                ),
            ),
            WORKSPACE_ID,
        )
        is False
    )


def test_shadow_observation_contains_only_sanitized_deltas_and_hashes() -> None:
    raw_query = "读取客户密钥 private-value-987"
    observations = []

    observation = run_task_planner_shadow(
        _v1_plan(raw_query),
        _request(raw_query),
        _snapshot(),
        observer=observations.append,
    )

    serialized = json.dumps(observation.model_dump(mode="json"), ensure_ascii=False)
    assert observations == [observation]
    assert observation.status == "observed"
    assert observation.v1_dispatch_unchanged is True
    assert raw_query not in serialized
    assert "private-value-987" not in serialized
    assert "客户密钥" not in serialized
    assert set(observation.denial_codes) <= {
        "field_not_in_authorized_schema",
        "schema_binding_ambiguous",
    }


def test_route_gate_does_not_build_snapshot_for_non_allowlisted_workspace(
    monkeypatch,
) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("non-allowlisted workspaces must not build a snapshot")

    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_schema_snapshot",
        fail_if_called,
    )

    result = agent_run_routes._observe_task_planner_v2_shadow(
        settings=Settings(),
        request=SimpleNamespace(workspace_id=WORKSPACE_ID),
        actor=SimpleNamespace(actor_type="user", actor_id="user-shadow"),
        platform_uow=object(),
        v1_plan=_v1_plan("显示项目"),
    )

    assert result is None


def test_route_shadow_preserves_the_exact_v1_plan_and_writes_sanitized_audit(
    monkeypatch,
) -> None:
    v1_plan = _v1_plan("显示项目")
    added_events = []

    class DummyUow:
        def get_digital_employee(self, employee_id):
            assert employee_id == EMPLOYEE_ID
            return SimpleNamespace(
                base_id=BASE_ID,
                allowed_actions=["query", "summarize"],
                accessible_views=[],
            )

        def add(self, event):
            added_events.append(event)

    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_schema_snapshot",
        lambda *_args, **_kwargs: _snapshot(),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_entity_candidates",
        lambda *_args, **_kwargs: (),
    )
    captured = {}
    real_shadow = run_task_planner_shadow_with_artifact

    def capture_shadow(plan, planner_request, snapshot, *, observer):
        captured["plan"] = plan
        return real_shadow(plan, planner_request, snapshot, observer=observer)

    monkeypatch.setattr(
        agent_run_routes,
        "run_task_planner_shadow_with_artifact",
        capture_shadow,
    )
    settings = Settings(
        agent_task_planner_v2_mode="shadow",
        agent_task_planner_v2_shadow_workspace_ids=(str(WORKSPACE_ID),),
    )
    request = SimpleNamespace(
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        query="显示项目",
        idempotency_key="shadow-route-case",
    )

    observation = agent_run_routes._observe_task_planner_v2_shadow(
        settings=settings,
        request=request,
        actor=SimpleNamespace(actor_type="user", actor_id="user-shadow"),
        platform_uow=DummyUow(),
        v1_plan=v1_plan,
    )

    assert captured["plan"] is v1_plan
    assert observation is not None
    assert observation.v1_dispatch_unchanged is True
    assert len(added_events) == 1
    assert added_events[0].event_type == "stage12.planner_shadow_observed"
    assert added_events[0].after_state == observation.model_dump(mode="json")


def test_route_shadow_supplies_authorized_entity_linker_candidates_to_planner(
    monkeypatch,
) -> None:
    entity = AuthorizedEntitySpec(
        entity_id=UUID("20000000-0000-4000-8000-000000000042"),
        table_id=TABLE_ID,
        code="CASE-42",
        label="Apollo",
        aliases=("阿波罗",),
    )
    captured = {}

    class DummyUow:
        def get_digital_employee(self, employee_id):
            assert employee_id == EMPLOYEE_ID
            return SimpleNamespace(
                base_id=BASE_ID,
                allowed_actions=["query", "summarize"],
                accessible_views=[],
            )

        def add(self, _event):
            return None

    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_schema_snapshot",
        lambda *_args, **_kwargs: _entity_snapshot(),
    )

    def link_entities(*_args, **kwargs):
        captured["linker_query"] = kwargs["query"]
        return (entity,)

    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_entity_candidates",
        link_entities,
        raising=False,
    )
    real_shadow = run_task_planner_shadow_with_artifact

    def capture_shadow(plan, planner_request, snapshot, *, observer):
        captured["entities"] = planner_request.authorized_entities
        return real_shadow(plan, planner_request, snapshot, observer=observer)

    monkeypatch.setattr(
        agent_run_routes,
        "run_task_planner_shadow_with_artifact",
        capture_shadow,
    )
    settings = Settings(
        agent_task_planner_v2_mode="shadow",
        agent_task_planner_v2_shadow_workspace_ids=(str(WORKSPACE_ID),),
    )
    query = "显示 CASE-42"
    request = SimpleNamespace(
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        query=query,
        idempotency_key="shadow-route-entity-case",
    )

    observation = agent_run_routes._observe_task_planner_v2_shadow(
        settings=settings,
        request=request,
        actor=SimpleNamespace(
            actor_type="user",
            actor_id="user-shadow",
            role="owner",
        ),
        platform_uow=DummyUow(),
        v1_plan=_v1_plan(query),
    )

    assert observation is not None
    assert captured["linker_query"] == query
    assert captured["entities"] == (entity,)


def test_v2_failure_is_observed_without_changing_v1_dispatch_nodes() -> None:
    query = "创建任务"
    v1_plan = _v1_plan(query, requested_action="task_create")
    original_nodes = v1_plan.nodes
    observations = []

    observation = run_task_planner_shadow(
        v1_plan,
        _request(query),
        _snapshot(),
        observer=observations.append,
    )

    assert observation.status == "shadow_failed"
    assert observation.failure_code == "task_planner_action_table_unavailable"
    assert observation.v1_dispatch_unchanged is True
    assert v1_plan.nodes == original_nodes
    assert observations == [observation]
