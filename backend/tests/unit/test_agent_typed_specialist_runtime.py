from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from uuid import UUID, uuid4

from app.models.agent_event_runtime import AgentArtifact
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.schemas.agent_specialist_results import (
    ComposerResultV1,
    ObjectiveSpecialistInputV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    StructuredQueryArtifactV1,
    StructuredQueryResultV1,
    authorized_query_plan_sha256,
    structured_query_result_sha256,
)
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    dispatch_specialist_commands,
)
from app.services.agent_specialists_v2.tabular import TabularSpecialistV2
from app.services.agent_specialists_v2.risk import RiskSpecialistV2
from app.services.agent_risk_policy import (
    AuthorizedRiskPolicyV1,
    risk_policy_sha256,
)
from app.services.agent_typed_artifacts import (
    persist_typed_artifact,
    read_typed_artifact,
)
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.workers.agent_specialist_runtime import execute_typed_specialist_command


NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
WORKSPACE_ID = UUID("38000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("38000000-0000-4000-8000-000000000002")
TABLE_ID = UUID("38000000-0000-4000-8000-000000000003")
RECORD_ID = UUID("38000000-0000-4000-8000-000000000004")
FIELD_ID = UUID("38000000-0000-4000-8000-000000000005")
SCOPE = "a" * 64
SCHEMA = "b" * 64


def _query_artifact() -> StructuredQueryArtifactV1:
    plan = AuthorizedQueryPlanV1(
        version="authorized-query-plan.v1",
        query_intent_id="query-runtime",
        root_table_id=TABLE_ID,
        authorized_view_ids=(),
        entity_codes=(),
        predicate=None,
        traversals=(),
        projection_field_ids=(FIELD_ID,),
        group_by_field_ids=(),
        aggregates=(),
        sort_rules=(),
        limit=None,
        max_scan_rows=5000,
        max_relation_expansions=1000,
        scope_hash=SCOPE,
        schema_hash=SCHEMA,
        traversal_paths=(),
    )
    plan_hash = authorized_query_plan_sha256(plan)
    values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": plan_hash,
        "records": (
            {
                "record_id": str(RECORD_ID),
                "table_id": str(TABLE_ID),
                "values": ({"field_id": str(FIELD_ID), "value": "阻塞"},),
            },
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            {
                "table_id": str(TABLE_ID),
                "record_id": str(RECORD_ID),
                "record_version": 3,
            },
        ),
        "scope_hash": SCOPE,
        "schema_hash": SCHEMA,
        "scanned_record_count": 1,
        "traversed_edge_count": 0,
        "truncated": False,
    }
    values["result_hash"] = structured_query_result_sha256(values)
    return StructuredQueryArtifactV1(
        version="structured-query-artifact.v1",
        plan=plan,
        plan_hash=plan_hash,
        result=StructuredQueryResultV1.model_validate_json(json.dumps(values)),
    )


def test_real_typed_worker_persists_fact_claim_graph_and_terminal_composer() -> None:
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    owners = InMemoryStage06PlatformUnitOfWork()
    run = create_agent_run(
        runtime,
        workspace_id=WORKSPACE_ID,
        root_employee_id=EMPLOYEE_ID,
        scope_hash=SCOPE,
        idempotency_key_hash="c" * 64,
        deadline_at=NOW + timedelta(minutes=2),
        now=NOW,
        workflow_version="stage12.typed-specialists.v2",
    ).run
    query = _query_artifact()
    query_owner = persist_typed_artifact(
        owners,
        workspace_id=WORKSPACE_ID,
        run_id=run.id,
        artifact_kind="structured_query_artifact",
        payload=query,
        scope_hash=SCOPE,
    )
    query_ref = uuid4()
    runtime.add_artifact(
        AgentArtifact(
            id=query_ref,
            run_id=run.id,
            kind="structured_query_artifact",
            storage_ref=query_owner.storage_ref,
            content_hash=query_owner.content_hash,
            visibility_scope_hash=SCOPE,
            validation_status="validated",
            expires_at=None,
        )
    )
    input_values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-tabular",
        "capability_id": "platform.tabular.analyse",
        "task_spec_ref": "task-spec:sha256:" + "d" * 64,
        "input_artifact_refs": (query_ref,),
        "scope_hash": SCOPE,
        "schema_hash": SCHEMA,
        "data_version_hash": None,
    }
    input_values["content_hash"] = specialist_payload_sha256(input_values)
    objective = ObjectiveSpecialistInputV1.model_validate(input_values)
    input_owner = persist_typed_artifact(
        owners,
        workspace_id=WORKSPACE_ID,
        run_id=run.id,
        artifact_kind="objective_specialist_input",
        payload=objective,
        scope_hash=SCOPE,
    )
    command = dispatch_specialist_commands(
        runtime,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=input_owner.storage_ref,
                input_artifact_refs=(query_ref,),
                required=True,
            ),
        ),
        authorization_hash=SCOPE,
        now=NOW,
    )[0]
    envelope = AgentCommandEnvelope.model_validate_json(
        json.dumps(runtime.get_outbox_event_by_event_id(command.id).payload_json)
    )

    execute_typed_specialist_command(
        runtime,
        owners,
        envelope,
        handler=TabularSpecialistV2(),
        worker_id="typed-tabular",
        now=NOW + timedelta(seconds=1),
    )

    assert run.status == "completed"
    assert [item.event_type for item in runtime.events].count("run.completed") == 1
    assert {item.kind for item in runtime.artifacts} >= {
        "structured_query_artifact",
        "structured_fact_set",
        "claim_graph",
        "composer_result",
    }
    final = runtime.get_artifact(run.safe_result_ref)
    assert final is not None
    result = read_typed_artifact(
        owners,
        artifact=final,
        workspace_id=WORKSPACE_ID,
        current_scope_hash=SCOPE,
        expected_kind="composer_result",
        payload_type=ComposerResultV1,
    )
    assert result.status == "completed"
    assert "阻塞" in result.answer
    assert result.claim_ids


def test_real_typed_worker_executes_risk_handler_from_sealed_fact_and_policy() -> None:
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    owners = InMemoryStage06PlatformUnitOfWork()
    run = create_agent_run(
        runtime,
        workspace_id=WORKSPACE_ID,
        root_employee_id=EMPLOYEE_ID,
        scope_hash=SCOPE,
        idempotency_key_hash="e" * 64,
        deadline_at=NOW + timedelta(minutes=2),
        now=NOW,
        workflow_version="stage12.typed-specialists.v2",
    ).run
    fact_values = {
        "version": "structured-fact-set.v1",
        "objective_id": "obj-tabular",
        "records": (
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "阻塞"},),
            },
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            {"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": 3},
        ),
        "evidence_refs": ("query-result:sha256:" + "f" * 64,),
        "scope_hash": SCOPE,
        "schema_hash": SCHEMA,
        "complete": True,
        "truncated": False,
    }
    fact_values["content_hash"] = specialist_payload_sha256(fact_values)
    facts = StructuredFactSetV1.model_validate(fact_values)
    policy_values = {
        "version": "authorized-risk-policy.v1",
        "policy_version": "runtime-risk.v1",
        "rules": (
            {
                "rule_id": "blocked-high",
                "field_id": FIELD_ID,
                "operator": "eq",
                "expected_value": "阻塞",
                "severity": "high",
                "reason_code": "blocked",
            },
        ),
        "scope_hash": SCOPE,
    }
    policy_values["content_hash"] = risk_policy_sha256(policy_values)
    policy = AuthorizedRiskPolicyV1.model_validate(policy_values)
    refs = []
    for kind, payload in (
        ("structured_fact_set", facts),
        ("authorized_risk_policy", policy),
    ):
        owner = persist_typed_artifact(
            owners,
            workspace_id=WORKSPACE_ID,
            run_id=run.id,
            artifact_kind=kind,
            payload=payload,
            scope_hash=SCOPE,
        )
        artifact_ref = uuid4()
        refs.append(artifact_ref)
        runtime.add_artifact(
            AgentArtifact(
                id=artifact_ref,
                run_id=run.id,
                kind=kind,
                storage_ref=owner.storage_ref,
                content_hash=owner.content_hash,
                visibility_scope_hash=SCOPE,
                validation_status="validated",
                expires_at=None,
            )
        )
    input_values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-risk",
        "capability_id": "platform.risk.analyse",
        "task_spec_ref": "task-spec:sha256:" + "1" * 64,
        "input_artifact_refs": tuple(refs),
        "scope_hash": SCOPE,
        "schema_hash": SCHEMA,
        "data_version_hash": None,
    }
    input_values["content_hash"] = specialist_payload_sha256(input_values)
    input_owner = persist_typed_artifact(
        owners,
        workspace_id=WORKSPACE_ID,
        run_id=run.id,
        artifact_kind="objective_specialist_input",
        payload=ObjectiveSpecialistInputV1.model_validate(input_values),
        scope_hash=SCOPE,
    )
    command = dispatch_specialist_commands(
        runtime,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.risk.analyse",
                payload_ref=input_owner.storage_ref,
                input_artifact_refs=tuple(refs),
                required=False,
            ),
        ),
        authorization_hash=SCOPE,
        now=NOW,
    )[0]
    envelope = AgentCommandEnvelope.model_validate_json(
        json.dumps(runtime.get_outbox_event_by_event_id(command.id).payload_json)
    )

    execute_typed_specialist_command(
        runtime,
        owners,
        envelope,
        handler=RiskSpecialistV2(),
        worker_id="typed-risk",
        now=NOW + timedelta(seconds=1),
    )

    assert run.status == "completed"
    assert "risk_assessment_set" in {item.kind for item in runtime.artifacts}
    final = runtime.get_artifact(run.safe_result_ref)
    result = read_typed_artifact(
        owners,
        artifact=final,
        workspace_id=WORKSPACE_ID,
        current_scope_hash=SCOPE,
        expected_kind="composer_result",
        payload_type=ComposerResultV1,
    )
    assert "high" in result.answer
