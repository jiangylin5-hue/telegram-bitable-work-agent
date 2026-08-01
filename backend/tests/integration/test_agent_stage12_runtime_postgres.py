from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import json
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.base import Base
from app.models.agent_event_runtime import AgentArtifact, AgentOutboxEvent
from app.models.audit import OpsAuditEvent
from app.schemas.agent_stage12_runtime import Stage12RuntimeAdmissionRequest
from app.schemas.agent_grounded_answer_v2 import GroundedComposerResultV2
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.schemas.agent_specialist_results import (
    AuthorizedCandidateSetV1,
    CurrentVersionProofV1,
    ObjectiveSpecialistInputV1,
    StructuredFactSetV1,
)
from app.schemas.agent_task_spec_v2 import ActionSlotV1
from app.schemas.retrieval_v2 import EvidenceBundleV2
from app.services.agent_event_runtime import SqlAlchemyAgentEventRuntimeUnitOfWork
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_orchestrator import build_authorization_hash
from app.services.agent_stage12_runtime_admission import admit_stage12_runtime_run
from app.services.agent_typed_artifacts import read_typed_artifact
from app.services.agent_specialists_v2.tabular import TabularSpecialistV2
from app.services.agent_specialists_v2.risk import RiskSpecialistV2
from app.services.agent_specialists_v2.daily import DailySpecialistV2
from app.services.agent_specialists_v2.action import ActionSpecialistV2
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
)
from app.services.stage12_action_runtime import SqlAlchemyStage12ActionRuntimeRepository
from scripts.stage06_local_postgres_migration_smoke import classify_local_postgres_url
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture
from app.workers.agent_specialist_runtime import (
    process_stage12_typed_specialist_command,
)


DATABASE_URL_ENV = "STAGE06_LOCAL_DATABASE_URL"
pytestmark = pytest.mark.postgres


class _OfflineFallbackProvider:
    slot_observations = ()

    def __init__(self) -> None:
        self.calls = 0
        self.requests = []

    def __call__(self, request):
        self.calls += 1
        self.requests.append(request)
        error = RuntimeError("offline_test_provider")
        error.code = "provider_schema_invalid"
        raise error


@pytest.mark.skipif(
    not os.getenv(DATABASE_URL_ENV),
    reason=f"{DATABASE_URL_ENV} is required for Stage12 SQL admission evidence",
)
@pytest.mark.parametrize(
    ("query", "expected_capabilities", "expected_objective_statuses"),
    [
        (
            "哪些项目同时有两个以上未完成事项？说明潜在交付风险。",
            ("platform.tabular.analyse", "platform.risk.analyse"),
            ("completed", "completed"),
        ),
        (
            "生成暂停项目专项日报，说明事实、风险和下一步建议，不要声称已执行。",
            (
                "platform.tabular.analyse",
                "platform.risk.analyse",
                "platform.daily.summarise",
            ),
            ("completed", "completed", "completed"),
        ),
        (
            "为 PRJ-ATLAS 创建高优先级范围确认任务并指派项目负责人，等待确认。",
            ("platform.tabular.analyse", "platform.action.propose"),
            ("completed", "completed"),
        ),
        (
            "为 MT-012 补充 blocked_reason 为依赖未交付，只生成草稿。",
            ("platform.tabular.analyse",),
            ("completed", "denied"),
        ),
        (
            "提醒 MT-001 的负责人今天反馈阻塞原因，不要直接发送。",
            ("platform.tabular.analyse", "platform.action.propose"),
            ("completed", "completed"),
        ),
    ],
)
def test_sql_admission_persists_authorized_zero_dependency_dispatch_atomically(
    query: str,
    expected_capabilities: tuple[str, ...],
    expected_objective_statuses: tuple[str, ...],
) -> None:
    database_url = os.environ[DATABASE_URL_ENV]
    classify_local_postgres_url(database_url)
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    schema_name = f"stage12_admission_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.execute(
                text(f'SET LOCAL search_path TO "{schema_name}", public')
            )
            Base.metadata.create_all(connection)
            session = Session(
                connection,
                autoflush=True,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            platform = SqlAlchemyStage06PlatformUnitOfWork(session)
            runtime = SqlAlchemyAgentEventRuntimeUnitOfWork(session)
            objectives = SqlAlchemyStage12ActionRuntimeRepository(session)
            actor = Actor(
                actor_type="user",
                actor_id="stage12-eval-owner",
                role="owner",
            )
            fixture = materialize_stage12_evaluation_fixture(platform, actor)
            employee = create_digital_employee(
                platform,
                fixture.base_id,
                name="Stage12 Evaluator",
                description="Read-only deployed runtime evaluator",
                telegram_alias=None,
                accessible_tables=[str(value) for value in fixture.table_ids.values()],
                accessible_views=[],
                allowed_actions=[
                    "schema_inspect",
                    "query",
                    "summarize",
                    "draft_create",
                    "task_create",
                    "notification.request",
                ],
                actor=actor,
            )
            readable = tuple(
                field.id
                for table_id in fixture.table_ids.values()
                for field in platform.list_fields(table_id)
                if field.key not in {"customer_secret", "internal_note"}
            )
            writable = tuple(
                field.id
                for field in platform.list_fields(fixture.table_ids["tasks"])
                if field.key not in {"customer_secret", "internal_note"}
            )
            employee.field_policy = build_stage12_field_policy_v2(
                readable_field_ids=readable,
                writable_field_ids=writable,
            )
            session.flush()
            record_count_before = sum(
                len(platform.list_records(table_id))
                for table_id in fixture.table_ids.values()
            )
            now = datetime(2026, 8, 1, 9, tzinfo=UTC)
            scope = build_authorization_hash(
                workspace_id=fixture.core.workspace_id,
                employee_id=employee.id,
                target_record_id=None,
                actor_user_id=actor.actor_id,
            )
            request = Stage12RuntimeAdmissionRequest(
                run_id=uuid4(),
                actor_user_id=actor.actor_id,
                workspace_id=fixture.core.workspace_id,
                digital_employee_id=employee.id,
                intent="business_fact",
                query=query,
                target_record_id=None,
                idempotency_key="stage12-sql-admission-1",
                skill_id="platform-tabular-analysis",
                authorization_hash=scope,
                deadline_at=now + timedelta(seconds=90),
            )
            key = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
            settings = Settings(
                agent_runtime_input_key=key,
                agent_runtime_input_key_version="stage12-test-v1",
                agent_runtime_input_ttl_seconds=90,
            )

            first = admit_stage12_runtime_run(
                platform,
                runtime,
                objectives,
                request=request,
                settings=settings,
                actor=actor,
                now=now,
            )
            replay = admit_stage12_runtime_run(
                platform,
                runtime,
                objectives,
                request=request,
                settings=settings,
                actor=actor,
                now=now,
            )
            with pytest.raises(PlatformValidationError) as conflict:
                admit_stage12_runtime_run(
                    platform,
                    runtime,
                    objectives,
                    request=request.model_copy(update={"query": "列出全部工作项"}),
                    settings=settings,
                    actor=actor,
                    now=now,
                )
            assert conflict.value.code == "idempotency_conflict"
            session.flush()

            run = runtime.get_run(first.run_id)
            assert run is not None
            assert first.status == "queued"
            assert replay.replayed is True
            assert replay.run_id == first.run_id
            assert run.workflow_version == "stage12.quality-v2.runtime.v1"
            commands = runtime.list_commands(run.id)
            assert len(commands) == 1
            assert commands[0].target_capability == "platform.tabular.analyse"
            assert commands[0].payload_ref.startswith("agent-private-input:")
            private_ref = commands[0].payload_ref.removeprefix("agent-private-input:")
            private_input_id = UUID(private_ref)
            private_input = runtime.get_private_input(private_input_id)
            assert private_input is not None
            assert request.query.encode("utf-8") not in private_input.ciphertext
            artifact_kinds = {
                item.kind
                for item in session.scalars(
                    select(AgentArtifact).where(AgentArtifact.run_id == run.id)
                )
            }
            assert artifact_kinds >= {
                "authorized_schema_snapshot",
                "task_spec_v2",
                "structured_query_artifact",
                "objective_specialist_input",
            }
            objective_runs = objectives.list_objectives(run.id)
            expected_kinds = {
                "platform.tabular.analyse": {"fact_query"},
                "platform.risk.analyse": {"risk_analysis"},
                "platform.daily.summarise": {"daily_summary"},
                "platform.action.propose": {
                    "record_change",
                    "task_creation",
                    "reminder_request",
                },
            }
            actual_objective_kinds = {item.kind for item in objective_runs}
            assert all(
                actual_objective_kinds.intersection(expected_kinds[item])
                for item in expected_capabilities
            )
            outbox = tuple(
                session.scalars(
                    select(AgentOutboxEvent).where(
                        AgentOutboxEvent.aggregate_id == run.id
                    )
                )
            )
            assert len(outbox) >= 2
            audits = tuple(
                session.scalars(
                    select(OpsAuditEvent).where(
                        OpsAuditEvent.event_type == "stage12.isolated_runtime_admitted"
                    )
                )
            )
            assert len(audits) == 1
            retained_text = repr(
                [
                    *(item.payload_json for item in outbox),
                    *(item.after_state for item in audits),
                ]
            )
            assert request.query not in retained_text
            assert (
                sum(
                    len(platform.list_records(table_id))
                    for table_id in fixture.table_ids.values()
                )
                == record_count_before
            )
            envelope = AgentCommandEnvelope.model_validate_json(
                json.dumps(
                    runtime.get_outbox_event_by_event_id(commands[0].id).payload_json
                )
            )
            provider = _OfflineFallbackProvider()
            process_stage12_typed_specialist_command(
                session,
                envelope,
                handler=TabularSpecialistV2(),
                settings=settings,
                worker_id="stage12-postgres-tabular",
                now=now + timedelta(seconds=1),
                stage12_provider=provider,
            )
            commands_after_tabular = runtime.list_commands(run.id)
            assert (
                tuple(item.target_capability for item in commands_after_tabular)
                == expected_capabilities[: len(commands_after_tabular)]
            )
            assert len(commands_after_tabular) == min(2, len(expected_capabilities))
            assert runtime.get_run(run.id).status in {
                "queued",
                "running",
                "completed",
            }
            event_count = len(runtime.list_events(run.id))
            process_stage12_typed_specialist_command(
                session,
                envelope,
                handler=TabularSpecialistV2(),
                settings=settings,
                worker_id="stage12-postgres-tabular",
                now=now + timedelta(seconds=120),
                stage12_provider=provider,
            )
            assert len(runtime.list_events(run.id)) == event_count
            assert len(runtime.list_commands(run.id)) == len(commands_after_tabular)
            handlers = {
                "platform.risk.analyse": RiskSpecialistV2(),
                "platform.daily.summarise": DailySpecialistV2(),
                "platform.action.propose": ActionSpecialistV2(),
            }
            processed_command_ids = {commands[0].id}
            next_second = 3
            while len(processed_command_ids) < len(expected_capabilities):
                available = runtime.list_commands(run.id)
                downstream = next(
                    item for item in available if item.id not in processed_command_ids
                )
                downstream_envelope = AgentCommandEnvelope.model_validate_json(
                    json.dumps(
                        runtime.get_outbox_event_by_event_id(downstream.id).payload_json
                    )
                )
                if downstream.target_capability == "platform.action.propose":
                    assert {
                        runtime.get_artifact(ref).kind
                        for ref in downstream_envelope.input_artifact_refs
                        if runtime.get_artifact(ref).kind
                        != "objective_specialist_input"
                    } == {
                        "structured_fact_set",
                        "action_slot",
                        "authorized_candidate_set",
                        "evidence_bundle",
                        "current_version_proof",
                    }
                    types = {
                        "objective_specialist_input": ObjectiveSpecialistInputV1,
                        "structured_fact_set": StructuredFactSetV1,
                        "action_slot": ActionSlotV1,
                        "authorized_candidate_set": AuthorizedCandidateSetV1,
                        "evidence_bundle": EvidenceBundleV2,
                        "current_version_proof": CurrentVersionProofV1,
                    }
                    payloads = {
                        ref: read_typed_artifact(
                            platform,
                            artifact=runtime.get_artifact(ref),
                            workspace_id=run.workspace_id,
                            current_scope_hash=run.scope_hash,
                            expected_kind=runtime.get_artifact(ref).kind,
                            payload_type=types[runtime.get_artifact(ref).kind],
                        )
                        for ref in downstream_envelope.input_artifact_refs
                    }
                    action_objective = next(
                        item
                        for item in payloads.values()
                        if isinstance(item, ObjectiveSpecialistInputV1)
                    )
                    direct = ActionSpecialistV2().execute(
                        action_objective,
                        SpecialistExecutionContextV2(
                            artifact_reader=payloads.__getitem__,
                            clock=lambda: now + timedelta(seconds=next_second),
                            metrics=lambda _name, _value: None,
                        ),
                    )
                    assert direct.payload.status == "proposed"
                process_stage12_typed_specialist_command(
                    session,
                    downstream_envelope,
                    handler=handlers[downstream.target_capability],
                    settings=settings,
                    worker_id=f"stage12-postgres-{downstream.target_capability}",
                    now=now + timedelta(seconds=next_second),
                    stage12_provider=provider,
                )
                processed_command_ids.add(downstream.id)
                next_second += 1
            assert (
                tuple(item.target_capability for item in runtime.list_commands(run.id))
                == expected_capabilities
            )
            session.expire_all()
            terminal_run = runtime.get_run(run.id)
            terminal_private_input = runtime.get_private_input(private_input_id)
            terminal_objective = objectives.get_objective_by_command(
                run.id,
                commands[0].id,
            )
            assert terminal_run is not None and terminal_run.status == "completed", [
                (item.kind, item.status, item.error_code)
                for item in objectives.list_objectives(run.id)
            ] + [("provider_calls", provider.calls)]
            final_artifact = runtime.get_artifact(terminal_run.safe_result_ref)
            assert final_artifact is not None
            assert final_artifact.kind == "grounded_composer_result"
            terminal_events = runtime.list_events(run.id)
            result_event = next(
                item
                for item in terminal_events
                if item.event_type == "result.available"
            )
            completed_event = next(
                item for item in terminal_events if item.event_type == "run.completed"
            )
            assert result_event.sequence < completed_event.sequence
            assert result_event.artifact_ref == final_artifact.id
            grounded = read_typed_artifact(
                platform,
                artifact=final_artifact,
                workspace_id=run.workspace_id,
                current_scope_hash=run.scope_hash,
                expected_kind="grounded_composer_result",
                payload_type=GroundedComposerResultV2,
            )
            assert provider.calls == 1, grounded.degradation_codes
            assert provider.requests
            assert all(
                "record:" not in claim.subject_label
                for claim in provider.requests[0].claims
            )
            final_command = runtime.list_commands(run.id)[-1]
            final_envelope = AgentCommandEnvelope.model_validate_json(
                json.dumps(
                    runtime.get_outbox_event_by_event_id(final_command.id).payload_json
                )
            )
            process_stage12_typed_specialist_command(
                session,
                final_envelope,
                handler={
                    "platform.tabular.analyse": TabularSpecialistV2(),
                    "platform.risk.analyse": RiskSpecialistV2(),
                    "platform.daily.summarise": DailySpecialistV2(),
                    "platform.action.propose": ActionSpecialistV2(),
                }[final_command.target_capability],
                settings=settings,
                worker_id="stage12-postgres-terminal-replay",
                now=now + timedelta(seconds=150),
                stage12_provider=provider,
            )
            assert provider.calls == 1
            assert terminal_private_input is not None
            assert terminal_private_input.consumed_at is not None
            assert terminal_objective is not None
            assert terminal_objective.status == "completed"
            assert terminal_objective.result_artifact_id is not None
            assert (
                tuple(item.status for item in objectives.list_objectives(run.id))
                == expected_objective_statuses
            )
            assert all(
                runtime.get_private_input(
                    UUID(item.payload_ref.removeprefix("agent-private-input:"))
                ).consumed_at
                is not None
                for item in runtime.list_commands(run.id)
            )
            assert (
                sum(
                    len(platform.list_records(table_id))
                    for table_id in fixture.table_ids.values()
                )
                == record_count_before
            )
            transaction.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        engine.dispose()
