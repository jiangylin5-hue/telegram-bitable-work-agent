from datetime import UTC, datetime, timedelta
import base64
import json
from uuid import UUID, uuid4

import pytest

from app.models.stage06_platform import WorkspaceMember
from app.models.agent_event_runtime import (
    AgentArtifact,
    AgentPrivateInput,
    AgentWorkflowRun,
)
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.schemas.stage12_action_runtime import (
    ActionConfirmRequestV1,
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
    DurableAuthorizedCandidateSetV1,
    action_candidate_sha256,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage12_action_materialization import materialize_action_slot
from app.services.stage12_action_confirmation import confirm_stage12_action
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from app.services.agent_orchestrator import dispatch_specialist_command
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.agent_typed_artifacts import persist_typed_artifact
from app.services.stage12_action_private_payload import (
    seal_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import (
    InMemoryStage12ActionRuntimeRepository,
    create_action_slot,
    create_objective_run,
    Stage12ActionConflict,
)
from app.workers.stage12_action_runtime import process_stage12_action_command


def _fixture(*, with_record: bool, action_kind: str):
    platform = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    operator = Actor(actor_type="user", actor_id="operator-1", role="operator")
    workspace = create_workspace(
        platform, name="Stage12 Action", owner_user_id=owner.actor_id, actor=owner
    )
    platform.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=operator.actor_id,
            role=operator.role,
            status="active",
            version=1,
        )
    )
    base = create_base(platform, workspace.id, name="Action", actor=owner)
    table = create_table(platform, base.id, name="Tasks", key="tasks", actor=owner)
    field = create_field(
        platform,
        table.id,
        name="Status",
        key="status",
        field_type="status",
        permission_policy={"operator": "write", "owner": "write"},
        actor=owner,
    )
    record = (
        create_record(platform, table.id, values={"status": "open"}, actor=owner)
        if with_record
        else None
    )
    employee = create_digital_employee(
        platform,
        base.id,
        name="Action Employee",
        description="Stage12 action test",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        allowed_actions=[
            "draft_update" if action_kind == "record.update" else "draft_create"
        ],
        actor=owner,
    )
    runtime = InMemoryStage12ActionRuntimeRepository()
    run_id = uuid4()
    objective = create_objective_run(
        runtime,
        run_id=run_id,
        objective_key="obj-01",
        kind="action",
        required=True,
        dependency_keys=(),
    )
    control = ActionSlotControlV1(
        action_kind=action_kind,
        confirmation_policy="required",
        dependency_keys=(),
        evidence_refs=("ev-01",),
        editable_fields=(
            {
                "field_id": field.id,
                "field_key": "status",
                "label": "状态",
                "field_type": "status",
                "required": True,
            },
        ),
        safe_summary="待确认动作",
    )
    slot = create_action_slot(
        runtime,
        run_id=run_id,
        objective_run_id=objective.id,
        slot_key="act-01",
        action_kind=action_kind,
        control=control,
        private_payload_ref="agent-private-input:" + str(uuid4()),
        target_scope_hash="a" * 64,
        data_version_hash="b" * 64 if with_record else None,
        idempotency_key_hash="c" * 64,
    )
    payload = ActionPrivatePayloadV1(
        actor_user_id="operator-1",
        objective_key="obj-01",
        slot_key="act-01",
        action_kind=action_kind,
        candidate_set_hash="d" * 64,
        target_table_id=table.id,
        target_record_ids=() if record is None else (record.id,),
        assignments=(
            {
                "record_id": None if record is None else record.id,
                "field_id": field.id,
                "value": "closed",
            },
        ),
        record_versions=(
            ()
            if record is None
            else (
                {
                    "table_id": table.id,
                    "record_id": record.id,
                    "record_version": record.version,
                },
            )
        ),
        evidence_ids=("ev-01",),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    return platform, runtime, workspace, employee, operator, record, slot, payload


def test_task_materialization_only_creates_pending_draft_and_replays() -> None:
    platform, runtime, workspace, employee, actor, _record, slot, payload = _fixture(
        with_record=False, action_kind="task.create"
    )

    result = materialize_action_slot(
        runtime,
        platform,
        slot_id=slot.id,
        expected_proposal_version=1,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        private_payload=payload,
    )

    assert result.resource_status == "pending_confirmation"
    assert result.external_send_count == 0
    assert platform.records == []
    assert len(platform.record_change_drafts) == 1
    assert slot.status == "pending_confirmation"

    replayed = materialize_action_slot(
        runtime,
        platform,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        private_payload=payload,
    )
    assert replayed.replayed is True
    assert len(platform.record_change_drafts) == 1


def test_update_materialization_preserves_record_and_version_before_confirmation() -> (
    None
):
    platform, runtime, workspace, employee, actor, record, slot, payload = _fixture(
        with_record=True, action_kind="record.update"
    )
    assert record is not None
    original_version = record.version

    result = materialize_action_slot(
        runtime,
        platform,
        slot_id=slot.id,
        expected_proposal_version=1,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        private_payload=payload,
    )

    assert result.resource_status == "pending_confirmation"
    assert record.values == {"status": "open"}
    assert record.version == original_version
    assert platform.record_change_drafts[0].proposed_values == {"status": "closed"}


def test_confirmed_task_creates_record_once_through_existing_confirmation_service() -> (
    None
):
    platform, action_runtime, workspace, employee, actor, _record, slot, payload = (
        _fixture(with_record=False, action_kind="task.create")
    )
    materialize_action_slot(
        action_runtime,
        platform,
        slot_id=slot.id,
        expected_proposal_version=1,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        private_payload=payload,
    )
    runtime = _runtime_for_slot(slot, workspace.id, employee.id)

    receipt = confirm_stage12_action(
        action_runtime,
        runtime,
        platform,
        run_id=slot.run_id,
        slot_id=slot.id,
        request=ActionConfirmRequestV1(
            proposal_version=slot.proposal_version,
            record_version=None,
            proposed_values={"status": "done"},
        ),
        private_payload=payload,
        actor=actor,
    )

    assert receipt.status == "executed"
    assert len(platform.records) == 1
    assert platform.records[0].values == {"status": "done"}
    assert platform.record_change_drafts[0].status == "confirmed"


def test_update_confirmation_detects_record_version_drift_without_overwrite() -> None:
    platform, action_runtime, workspace, employee, actor, record, slot, payload = (
        _fixture(with_record=True, action_kind="record.update")
    )
    assert record is not None
    materialize_action_slot(
        action_runtime,
        platform,
        slot_id=slot.id,
        expected_proposal_version=1,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        private_payload=payload,
    )
    runtime = _runtime_for_slot(slot, workspace.id, employee.id)
    record.version += 1

    with pytest.raises(Stage12ActionConflict, match="action_version_conflict"):
        confirm_stage12_action(
            action_runtime,
            runtime,
            platform,
            run_id=slot.run_id,
            slot_id=slot.id,
            request=ActionConfirmRequestV1(
                proposal_version=slot.proposal_version,
                record_version=payload.record_versions[0].record_version,
                proposed_values={"status": "closed"},
            ),
            private_payload=payload,
            actor=actor,
        )

    assert record.values == {"status": "open"}
    assert platform.record_change_drafts[0].status == "pending_confirmation"


def test_durable_action_command_materializes_once_and_emits_pending_event() -> None:
    platform, action_runtime, workspace, employee, _actor, _record, slot, payload = (
        _fixture(with_record=False, action_kind="task.create")
    )
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    now = datetime.now(UTC)
    run = AgentWorkflowRun(
        id=slot.run_id,
        workspace_id=workspace.id,
        root_employee_id=employee.id,
        target_record_id=None,
        parent_run_id=None,
        workflow_version="stage12.action.v1",
        status="accepted",
        scope_hash="a" * 64,
        data_version_hash=None,
        deadline_at=now + timedelta(minutes=2),
        lease_owner=None,
        lease_expires_at=None,
        idempotency_key_hash="e" * 64,
        safe_result_ref=None,
        version=1,
    )
    runtime.add_run(run)
    snapshot = build_authorized_schema_snapshot(
        platform,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=_actor,
    )
    candidate_values = {
        "version": "stage12-authorized-candidates.v1",
        "objective_key": payload.objective_key,
        "slot_key": payload.slot_key,
        "action_kind": payload.action_kind,
        "status": "resolved",
        "target_table_ids": [str(payload.target_table_id)],
        "candidates": [],
        "assignment_field_ids": [str(item.field_id) for item in payload.assignments],
        "scope_hash": snapshot.scope_hash,
        "schema_hash": snapshot.schema_hash,
        "result_hash": None,
        "complete": True,
        "denial_reason": None,
    }
    candidate_set = DurableAuthorizedCandidateSetV1.model_validate_json(
        json.dumps(
            {
                **candidate_values,
                "candidate_set_hash": action_candidate_sha256(candidate_values),
            }
        )
    )
    payload = payload.model_copy(
        update={"candidate_set_hash": candidate_set.candidate_set_hash}
    )
    owner = persist_typed_artifact(
        platform,
        workspace_id=workspace.id,
        run_id=run.id,
        artifact_kind="authorized_candidate_set",
        payload=candidate_set,
        scope_hash=run.scope_hash,
    )
    candidate_artifact = AgentArtifact(
        id=uuid4(),
        run_id=run.id,
        kind="authorized_candidate_set",
        storage_ref=owner.storage_ref,
        content_hash=owner.content_hash,
        visibility_scope_hash=run.scope_hash,
        validation_status="validated",
        expires_at=run.deadline_at,
    )
    runtime.add_artifact(candidate_artifact)
    command_id = uuid4()
    input_id = UUID(slot.private_payload_ref.removeprefix("agent-private-input:"))
    command = dispatch_specialist_command(
        runtime,
        run_id=run.id,
        target_capability="platform.action.propose",
        payload_ref=slot.private_payload_ref,
        authorization_hash=run.scope_hash,
        now=now,
        command_id=command_id,
        input_artifact_refs=(candidate_artifact.id,),
    )
    key = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
    sealed = seal_stage12_action_private_payload(
        payload,
        key_b64=key,
        key_version="test-v1",
        run_id=run.id,
        command_id=command.id,
        scope_hash=run.scope_hash,
    )
    runtime.add_private_input(
        AgentPrivateInput(
            id=input_id,
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
    )
    outbox = runtime.get_outbox_event_by_event_id(command.id)
    assert outbox is not None
    envelope = AgentCommandEnvelope.model_validate_json(json.dumps(outbox.payload_json))

    first = process_stage12_action_command(
        runtime,
        action_runtime,
        platform,
        envelope,
        private_key_b64=key,
        worker_id="stage12-action-test",
        now=now,
    )
    second = process_stage12_action_command(
        runtime,
        action_runtime,
        platform,
        envelope,
        private_key_b64=key,
        worker_id="stage12-action-test",
        now=now + timedelta(seconds=1),
    )

    assert first.external_send_count == 0
    assert second.replayed is True
    assert len(platform.record_change_drafts) == 1
    assert [
        item.event_type
        for item in runtime.events
        if item.event_type == "action.pending_confirmation"
    ] == ["action.pending_confirmation"]
    assert run.status == "waiting_approval"


def _runtime_for_slot(slot, workspace_id, employee_id):
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    runtime.add_run(
        AgentWorkflowRun(
            id=slot.run_id,
            workspace_id=workspace_id,
            root_employee_id=employee_id,
            target_record_id=None,
            parent_run_id=None,
            workflow_version="stage12.action.v1",
            status="waiting_approval",
            scope_hash=slot.target_scope_hash,
            data_version_hash=slot.data_version_hash,
            deadline_at=datetime.now(UTC) + timedelta(minutes=2),
            lease_owner=None,
            lease_expires_at=None,
            idempotency_key_hash="f" * 64,
            safe_result_ref=None,
            version=1,
        )
    )
    return runtime
