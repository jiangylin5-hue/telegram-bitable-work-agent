from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

from app.core.config import Settings
import app.api.routes.agent_runs as agent_run_routes
from app.schemas.agent_task_spec_v2 import (
    AuthorizedSchemaSnapshot,
    authorized_schema_sha256,
)
from app.services.agent_task_gateway import TaskGatewayRequest, build_task_plan
from app.services.authorized_query_shadow import (
    authorized_query_shadow_enabled,
    run_authorized_query_shadow,
)


WORKSPACE_ID = UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("30000000-0000-4000-8000-000000000002")
VIEW_ID = UUID("30000000-0000-4000-8000-000000000003")
BASE_ID = UUID("30000000-0000-4000-8000-000000000004")


def _snapshot() -> AuthorizedSchemaSnapshot:
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "b" * 64,
        "tables": (),
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def test_query_shadow_gate_defaults_off_and_requires_workspace_allowlist() -> None:
    assert authorized_query_shadow_enabled(Settings(), WORKSPACE_ID) is False
    assert (
        authorized_query_shadow_enabled(
            Settings(
                authorized_query_engine_v1_mode="shadow",
                authorized_query_engine_v1_workspace_allowlist=(str(WORKSPACE_ID),),
            ),
            WORKSPACE_ID,
        )
        is True
    )
    assert (
        authorized_query_shadow_enabled(
            Settings(
                authorized_query_engine_v1_mode="shadow",
                authorized_query_engine_v1_workspace_allowlist=(
                    "30000000-0000-4000-8000-000000000099",
                ),
            ),
            WORKSPACE_ID,
        )
        is False
    )


def test_observation_contains_only_hashes_counts_duration_code_and_scope(
    monkeypatch,
) -> None:
    import app.services.authorized_query_shadow as shadow

    sensitive_value = "hidden-record-value-987"
    sensitive_label = "Private customer label"
    sensitive_field = "secret_margin"
    hidden_identifier = "30000000-0000-4000-8000-000000000099"
    task_spec = SimpleNamespace(
        query_intents=(SimpleNamespace(query_intent_id="query-01"),),
    )
    task_artifact = SimpleNamespace(
        task_spec=task_spec,
        content_hash="a" * 64,
    )
    snapshot = SimpleNamespace(scope_hash="b" * 64)
    plan = SimpleNamespace(plan_hash="unused")
    result = SimpleNamespace(
        result_hash="d" * 64,
        records=(SimpleNamespace(value=sensitive_value),),
        groups=(SimpleNamespace(label=sensitive_label),),
        aggregates=(SimpleNamespace(field=sensitive_field),),
        relation_paths=(SimpleNamespace(record_id=hidden_identifier),),
        source_versions=(SimpleNamespace(record_id=hidden_identifier),),
        scanned_record_count=17,
        traversed_edge_count=3,
        scope_hash="b" * 64,
    )
    execution_artifact = SimpleNamespace(
        plan_hash="c" * 64,
        result=result,
    )
    monkeypatch.setattr(shadow, "build_authorized_relation_catalog", lambda *_: ())
    monkeypatch.setattr(
        shadow,
        "compile_authorized_query_plan",
        lambda **_kwargs: plan,
    )
    monkeypatch.setattr(
        shadow,
        "execute_authorized_query",
        lambda *_args, **_kwargs: execution_artifact,
    )

    observation = run_authorized_query_shadow(
        object(),
        actor=object(),
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        snapshot=snapshot,
        task_artifact=task_artifact,
        authorized_view_ids=(VIEW_ID,),
    )

    serialized = json.dumps(observation.model_dump(mode="json"), ensure_ascii=False)
    assert observation.status == "observed"
    assert observation.task_spec_hash == "a" * 64
    assert observation.plan_hashes == ("c" * 64,)
    assert observation.result_hashes == ("d" * 64,)
    assert observation.query_intent_count == 1
    assert observation.result_record_count == 1
    assert observation.group_count == 1
    assert observation.aggregate_count == 1
    assert observation.relation_path_count == 1
    assert observation.source_version_count == 1
    assert observation.scanned_record_count == 17
    assert observation.traversed_edge_count == 3
    assert observation.error_code is None
    assert observation.scope_hash == "b" * 64
    assert observation.duration_ms >= 0
    for forbidden in (
        sensitive_value,
        sensitive_label,
        sensitive_field,
        hidden_identifier,
    ):
        assert forbidden not in serialized


def test_query_shadow_failure_is_reduced_to_stable_code(monkeypatch) -> None:
    import app.services.authorized_query_shadow as shadow

    monkeypatch.setattr(shadow, "build_authorized_relation_catalog", lambda *_: ())

    def fail_compile(**_kwargs):
        raise ValueError("customer Alice secret field")

    monkeypatch.setattr(shadow, "compile_authorized_query_plan", fail_compile)
    observation = run_authorized_query_shadow(
        object(),
        actor=object(),
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        snapshot=SimpleNamespace(scope_hash="b" * 64),
        task_artifact=SimpleNamespace(
            task_spec=SimpleNamespace(
                query_intents=(SimpleNamespace(query_intent_id="query-01"),),
            ),
            content_hash="a" * 64,
        ),
        authorized_view_ids=(VIEW_ID,),
    )

    assert observation.status == "shadow_failed"
    assert observation.error_code == "authorized_query_shadow_failure"
    assert "Alice" not in observation.model_dump_json()
    assert observation.plan_hashes == ()
    assert observation.result_hashes == ()


def _v1_plan():
    return build_task_plan(
        TaskGatewayRequest(
            workspace_id=WORKSPACE_ID,
            employee_id=EMPLOYEE_ID,
            actor_user_id="user-shadow",
            intent="business_fact",
            requested_action="read_only",
            query="show projects",
            target_record_id=None,
            idempotency_key="query-shadow-test",
            skill_id=None,
        )
    )


def _route_request():
    return SimpleNamespace(
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        query="show projects",
        idempotency_key="query-shadow-route",
    )


def test_route_does_not_run_c_shadow_without_both_allowlists(monkeypatch) -> None:
    snapshot = _snapshot()

    class DummyUow:
        def get_digital_employee(self, _employee_id):
            return SimpleNamespace(
                base_id=BASE_ID,
                allowed_actions=["query"],
                accessible_views=[str(VIEW_ID)],
            )

    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_schema_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_entity_candidates",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "run_task_planner_shadow_with_artifact",
        lambda *_args, **_kwargs: SimpleNamespace(
            observation=SimpleNamespace(status="observed"),
            task_artifact=object(),
        ),
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("C shadow must require both B and C allowlists")

    monkeypatch.setattr(
        agent_run_routes,
        "run_authorized_query_shadow",
        fail_if_called,
    )
    settings = Settings(
        agent_task_planner_v2_mode="shadow",
        agent_task_planner_v2_shadow_workspace_ids=(str(WORKSPACE_ID),),
    )

    result = agent_run_routes._observe_task_planner_v2_shadow(
        settings=settings,
        request=_route_request(),
        actor=SimpleNamespace(actor_type="user", actor_id="user-shadow"),
        platform_uow=DummyUow(),
        v1_plan=_v1_plan(),
    )

    assert result.status == "observed"


def test_route_runs_c_only_after_successful_b_shadow_and_audits_safely(
    monkeypatch,
) -> None:
    snapshot = _snapshot()
    task_artifact = object()
    added_events = []
    captured = {}

    class DummyUow:
        def get_digital_employee(self, _employee_id):
            return SimpleNamespace(
                base_id=BASE_ID,
                allowed_actions=["query"],
                accessible_views=[str(VIEW_ID)],
            )

        def add(self, event):
            added_events.append(event)

    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_schema_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_authorized_entity_candidates",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "run_task_planner_shadow_with_artifact",
        lambda *_args, **_kwargs: SimpleNamespace(
            observation=SimpleNamespace(status="observed"),
            task_artifact=task_artifact,
        ),
    )
    sanitized = {
        "version": "authorized-query-shadow-observation.v1",
        "status": "observed",
        "plan_hashes": ["c" * 64],
        "result_hashes": ["d" * 64],
        "result_record_count": 2,
        "scope_hash": "b" * 64,
    }

    def observe_query(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_dump=lambda mode: sanitized)

    monkeypatch.setattr(
        agent_run_routes,
        "run_authorized_query_shadow",
        observe_query,
    )
    settings = Settings(
        agent_task_planner_v2_mode="shadow",
        agent_task_planner_v2_shadow_workspace_ids=(str(WORKSPACE_ID),),
        authorized_query_engine_v1_mode="shadow",
        authorized_query_engine_v1_workspace_allowlist=(str(WORKSPACE_ID),),
    )
    v1_plan = _v1_plan()
    original_nodes = v1_plan.nodes

    result = agent_run_routes._observe_task_planner_v2_shadow(
        settings=settings,
        request=_route_request(),
        actor=SimpleNamespace(actor_type="user", actor_id="user-shadow"),
        platform_uow=DummyUow(),
        v1_plan=v1_plan,
    )

    assert result.status == "observed"
    assert captured["task_artifact"] is task_artifact
    assert captured["authorized_view_ids"] == (VIEW_ID,)
    assert v1_plan.nodes == original_nodes
    assert len(added_events) == 1
    assert added_events[0].event_type == "stage12.authorized_query_shadow_observed"
    assert added_events[0].after_state == sanitized
