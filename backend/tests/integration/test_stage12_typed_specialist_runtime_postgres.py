from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.agent_event_runtime import AgentArtifact, AgentWorkflowRun
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_event_runtime import (
    SqlAlchemyAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    dispatch_specialist_commands,
)
from app.services.agent_risk_policy import (
    AuthorizedRiskPolicyV1,
    risk_policy_sha256,
)
from app.services.agent_specialists_v2.risk import RiskSpecialistV2
from app.services.agent_typed_artifacts import persist_typed_artifact
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_table,
    create_workspace,
)
from app.workers.agent_specialist_runtime import execute_typed_specialist_command
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
pytestmark = pytest.mark.postgres


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12 typed-worker evidence",
)
def test_postgres_real_risk_worker_persists_typed_fan_in_and_one_terminal() -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    now = datetime.now(UTC)
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            platform = SqlAlchemyStage06PlatformUnitOfWork(session)
            actor = Actor(
                actor_type="user",
                actor_id=f"stage12-typed-{uuid4()}",
                role="owner",
            )
            workspace = create_workspace(
                platform,
                name=f"Typed worker {uuid4().hex}",
                owner_user_id=actor.actor_id,
                actor=actor,
            )
            platform.flush()
            base = create_base(platform, workspace.id, name="Quality", actor=actor)
            platform.flush()
            table = create_table(
                platform,
                base.id,
                name="Tasks",
                key=f"tasks_{uuid4().hex[:10]}",
                actor=actor,
            )
            field = create_field(
                platform,
                table.id,
                name="Status",
                key="status",
                field_type="text",
                actor=actor,
            )
            employee = create_digital_employee(
                platform,
                base.id,
                name="Risk worker",
                description="typed worker persistence evidence",
                telegram_alias=None,
                accessible_tables=[str(table.id)],
                accessible_views=[],
                allowed_actions=["record.query"],
                actor=actor,
            )
            platform.flush()
            scope_hash = "a" * 64
            schema_hash = "b" * 64
            run = create_agent_run(
                runtime,
                workspace_id=workspace.id,
                root_employee_id=employee.id,
                scope_hash=scope_hash,
                idempotency_key_hash=uuid4().hex + uuid4().hex,
                deadline_at=now + timedelta(minutes=2),
                now=now,
                workflow_version="stage12.typed-specialists.v2",
            ).run
            record_id = uuid4()
            fact_values = {
                "version": "structured-fact-set.v1",
                "objective_id": "obj-tabular",
                "records": (
                    {
                        "record_id": record_id,
                        "table_id": table.id,
                        "values": ({"field_id": field.id, "value": "阻塞"},),
                    },
                ),
                "groups": (),
                "aggregates": (),
                "relation_paths": (),
                "source_versions": (
                    {
                        "table_id": table.id,
                        "record_id": record_id,
                        "record_version": 3,
                    },
                ),
                "evidence_refs": ("query-result:sha256:" + "c" * 64,),
                "scope_hash": scope_hash,
                "schema_hash": schema_hash,
                "complete": True,
                "truncated": False,
            }
            fact_values["content_hash"] = specialist_payload_sha256(fact_values)
            facts = StructuredFactSetV1.model_validate(fact_values)
            policy_values = {
                "version": "authorized-risk-policy.v1",
                "policy_version": "postgres-risk.v1",
                "rules": (
                    {
                        "rule_id": "blocked-high",
                        "field_id": field.id,
                        "operator": "eq",
                        "expected_value": "阻塞",
                        "severity": "high",
                        "reason_code": "blocked",
                    },
                ),
                "scope_hash": scope_hash,
            }
            policy_values["content_hash"] = risk_policy_sha256(policy_values)
            policy = AuthorizedRiskPolicyV1.model_validate(policy_values)
            refs = []
            for kind, payload in (
                ("structured_fact_set", facts),
                ("authorized_risk_policy", policy),
            ):
                owner = persist_typed_artifact(
                    platform,
                    workspace_id=workspace.id,
                    run_id=run.id,
                    artifact_kind=kind,
                    payload=payload,
                    scope_hash=scope_hash,
                )
                ref = uuid4()
                refs.append(ref)
                runtime.add_artifact(
                    AgentArtifact(
                        id=ref,
                        run_id=run.id,
                        kind=kind,
                        storage_ref=owner.storage_ref,
                        content_hash=owner.content_hash,
                        visibility_scope_hash=scope_hash,
                        validation_status="validated",
                        expires_at=None,
                    )
                )
            input_values = {
                "version": "objective-specialist-input.v1",
                "objective_id": "obj-risk",
                "capability_id": "platform.risk.analyse",
                "task_spec_ref": "task-spec:sha256:" + "d" * 64,
                "input_artifact_refs": tuple(refs),
                "scope_hash": scope_hash,
                "schema_hash": schema_hash,
                "data_version_hash": None,
            }
            input_values["content_hash"] = specialist_payload_sha256(input_values)
            input_owner = persist_typed_artifact(
                platform,
                workspace_id=workspace.id,
                run_id=run.id,
                artifact_kind="objective_specialist_input",
                payload=ObjectiveSpecialistInputV1.model_validate(input_values),
                scope_hash=scope_hash,
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
                authorization_hash=scope_hash,
                now=now,
            )[0]
            envelope = AgentCommandEnvelope.model_validate_json(
                json.dumps(
                    runtime.get_outbox_event_by_event_id(command.id).payload_json
                )
            )

            execute_typed_specialist_command(
                runtime,
                platform,
                envelope,
                handler=RiskSpecialistV2(),
                worker_id="postgres-risk-worker",
                now=now + timedelta(seconds=1),
            )
            session.flush()

            persisted_run = session.scalar(
                select(AgentWorkflowRun).where(AgentWorkflowRun.id == run.id)
            )
            kinds = set(
                session.scalars(
                    select(AgentArtifact.kind).where(AgentArtifact.run_id == run.id)
                )
            )
            assert persisted_run.status == "completed"
            assert kinds >= {
                "structured_fact_set",
                "authorized_risk_policy",
                "risk_assessment_set",
                "claim_graph",
                "composer_result",
            }
            assert persisted_run.safe_result_ref is not None
            session.rollback()
    finally:
        engine.dispose()
