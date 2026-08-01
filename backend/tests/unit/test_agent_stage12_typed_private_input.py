from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import json
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.agent_event_runtime import AgentArtifact, AgentPrivateInput
from app.schemas.agent_event_runtime import (
    AgentCommandEnvelope,
    AgentPrivateInputPayload,
)
from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    specialist_payload_sha256,
)
from app.services.agent_event_runtime import (
    InMemoryAgentEventRuntimeUnitOfWork,
    create_agent_run,
)
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    dispatch_specialist_commands,
)
from app.services.agent_private_inputs import seal_agent_private_input
from app.services.agent_typed_artifacts import persist_typed_artifact
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.workers.agent_specialist_runtime import load_stage12_objective_dispatch


NOW = datetime(2026, 8, 1, 10, tzinfo=UTC)
WORKSPACE_ID = UUID("3a000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("3a000000-0000-4000-8000-000000000002")
SCOPE_HASH = "a" * 64
SCHEMA_HASH = "b" * 64
KEY = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")


def _fixture(*, expires_at: datetime | None = None):
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    owners = InMemoryStage06PlatformUnitOfWork()
    run = create_agent_run(
        runtime,
        workspace_id=WORKSPACE_ID,
        root_employee_id=EMPLOYEE_ID,
        scope_hash=SCOPE_HASH,
        idempotency_key_hash="c" * 64,
        deadline_at=NOW + timedelta(minutes=2),
        now=NOW,
        workflow_version="stage12.quality-v2.runtime.v1",
    ).run
    dependency_id = uuid4()
    runtime.add_artifact(
        AgentArtifact(
            id=dependency_id,
            run_id=run.id,
            kind="structured_query_artifact",
            storage_ref=f"stage08-idempotency:{uuid4()}",
            content_hash="d" * 64,
            visibility_scope_hash=SCOPE_HASH,
            validation_status="validated",
            expires_at=run.deadline_at,
        )
    )
    objective_values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-facts",
        "capability_id": "platform.tabular.analyse",
        "task_spec_ref": f"stage08-idempotency:{uuid4()}",
        "input_artifact_refs": (dependency_id,),
        "scope_hash": SCOPE_HASH,
        "schema_hash": SCHEMA_HASH,
        "data_version_hash": "e" * 64,
    }
    objective_values["content_hash"] = specialist_payload_sha256(objective_values)
    objective = ObjectiveSpecialistInputV1.model_validate(objective_values)
    owner = persist_typed_artifact(
        owners,
        workspace_id=WORKSPACE_ID,
        run_id=run.id,
        artifact_kind="objective_specialist_input",
        payload=objective,
        scope_hash=SCOPE_HASH,
    )
    objective_metadata_id = uuid4()
    runtime.add_artifact(
        AgentArtifact(
            id=objective_metadata_id,
            run_id=run.id,
            kind="objective_specialist_input",
            storage_ref=owner.storage_ref,
            content_hash=owner.content_hash,
            visibility_scope_hash=SCOPE_HASH,
            validation_status="validated",
            expires_at=run.deadline_at,
        )
    )
    private_input_id = uuid4()
    command = dispatch_specialist_commands(
        runtime,
        run_id=run.id,
        dispatches=(
            SpecialistCommandDispatch(
                target_capability="platform.tabular.analyse",
                payload_ref=f"agent-private-input:{private_input_id}",
                input_artifact_refs=(objective_metadata_id, dependency_id),
                required=True,
            ),
        ),
        authorization_hash=SCOPE_HASH,
        now=NOW,
    )[0]
    private_payload = AgentPrivateInputPayload(
        actor_user_id="owner-1",
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        intent="business_fact",
        query="列出阻塞事项",
        target_record_id=None,
        idempotency_key="stage12-worker-1",
        skill_id="platform-tabular-analysis",
    )
    sealed = seal_agent_private_input(
        private_payload,
        key_b64=KEY,
        key_version="test-v1",
        run_id=run.id,
        command_id=command.id,
        scope_hash=SCOPE_HASH,
        expires_at=expires_at or run.deadline_at,
    )
    private_input = AgentPrivateInput(
        id=private_input_id,
        run_id=run.id,
        command_id=command.id,
        ciphertext=sealed.ciphertext,
        nonce=sealed.nonce,
        key_version=sealed.key_version,
        aad_hash=sealed.aad_hash,
        scope_hash=sealed.scope_hash,
        expires_at=sealed.expires_at,
        consumed_at=None,
    )
    runtime.add_private_input(private_input)
    envelope = AgentCommandEnvelope.model_validate_json(
        json.dumps(runtime.get_outbox_event_by_event_id(command.id).payload_json)
    )
    return runtime, owners, run, command, envelope, private_input, objective_metadata_id


def test_loads_exact_objective_owner_dependencies_and_decrypted_private_input() -> None:
    runtime, owners, run, command, envelope, private_input, owner_id = _fixture()

    loaded = load_stage12_objective_dispatch(
        runtime,
        owners,
        run=run,
        command=command,
        envelope=envelope,
        settings=Settings(agent_runtime_input_key=KEY),
        now=NOW + timedelta(seconds=1),
    )

    assert loaded.dispatch.objective_artifact_id == owner_id
    assert loaded.dispatch.dependency_artifact_ids == tuple(
        envelope.input_artifact_refs[1:]
    )
    assert loaded.private_input.query == "列出阻塞事项"
    assert loaded.sealed_input is private_input


@pytest.mark.parametrize("drift", ["workspace", "employee", "scope", "envelope"])
def test_rejects_private_or_durable_scope_drift(drift: str) -> None:
    runtime, owners, run, command, envelope, private_input, _owner_id = _fixture()
    if drift == "workspace":
        run.workspace_id = uuid4()
    elif drift == "employee":
        run.root_employee_id = uuid4()
    elif drift == "scope":
        run.scope_hash = "f" * 64
    else:
        envelope = envelope.model_copy(update={"idempotency_key_hash": "f" * 64})

    with pytest.raises(RuntimeError):
        load_stage12_objective_dispatch(
            runtime,
            owners,
            run=run,
            command=command,
            envelope=envelope,
            settings=Settings(agent_runtime_input_key=KEY),
            now=NOW + timedelta(seconds=1),
        )


def test_rejects_missing_or_duplicate_objective_owner() -> None:
    runtime, owners, run, command, envelope, _private_input, owner_id = _fixture()
    dependency_id = envelope.input_artifact_refs[1]
    missing = envelope.model_copy(update={"input_artifact_refs": (dependency_id,)})
    duplicate = envelope.model_copy(
        update={"input_artifact_refs": (owner_id, owner_id, dependency_id)}
    )

    for invalid in (missing, duplicate):
        runtime.get_outbox_event_by_event_id(command.id).payload_json = (
            invalid.model_dump(mode="json")
        )
        with pytest.raises(RuntimeError, match="typed_specialist_objective_owner_invalid"):
            load_stage12_objective_dispatch(
                runtime,
                owners,
                run=run,
                command=command,
                envelope=invalid,
                settings=Settings(agent_runtime_input_key=KEY),
                now=NOW + timedelta(seconds=1),
            )


def test_rejects_expired_private_input() -> None:
    runtime, owners, run, command, envelope, _private_input, _owner_id = _fixture(
        expires_at=NOW + timedelta(seconds=1)
    )

    with pytest.raises(RuntimeError, match="agent_private_input_expired"):
        load_stage12_objective_dispatch(
            runtime,
            owners,
            run=run,
            command=command,
            envelope=envelope,
            settings=Settings(agent_runtime_input_key=KEY),
            now=NOW + timedelta(seconds=2),
        )
