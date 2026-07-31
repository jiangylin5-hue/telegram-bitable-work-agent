from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas.agent_specialist_results import (
    AuthorizedCandidateSetV1,
    ControlledActionProposalV1,
    CurrentVersionProofV1,
    ObjectiveSpecialistInputV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import (
    ActionAssignment,
    ActionSlotV1,
    ActionTargetSelector,
    SourceSpan,
)
from app.schemas.retrieval_v2 import EvidenceBundleV2, canonical_retrieval_sha256
from app.services.agent_specialists_v2.action import ActionSpecialistV2
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2


TABLE_ID = UUID("35000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("35000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("35000000-0000-4000-8000-000000000003")
HASH = "a" * 64


def _slot() -> ActionSlotV1:
    span = SourceSpan(start=0, end=4, text="更新状态")
    return ActionSlotV1(
        slot_id="slot-01",
        objective_id="obj-action",
        action_kind="record.update",
        target=ActionTargetSelector(
            table_id=TABLE_ID,
            record_codes=("REC-001",),
            source_entity_codes=(),
            query_spec_ref=None,
            expansion_policy="none",
            resolution_status="resolved",
        ),
        assignments=(
            ActionAssignment(
                field_id=FIELD_ID,
                field_key="status",
                value="处理中",
                source_span=span,
            ),
        ),
        required_field_keys=("status",),
        confirmation_policy="required",
        deadline_start_utc=None,
        deadline_end_utc=None,
        conflict_group_id=None,
        planning_outcome="planned",
        denial_reason=None,
    )


def _candidates() -> AuthorizedCandidateSetV1:
    values = {
        "version": "authorized-candidate-set.v1",
        "objective_id": "obj-action",
        "slot_id": "slot-01",
        "candidates": (
            {
                "table_id": TABLE_ID,
                "record_id": RECORD_ID,
                "record_version": 3,
                "writable_field_ids": (FIELD_ID,),
            },
        ),
        "scope_hash": HASH,
        "complete": True,
    }
    values["candidate_set_hash"] = specialist_payload_sha256(values)
    return AuthorizedCandidateSetV1.model_validate(values)


def _evidence() -> EvidenceBundleV2:
    values = {
        "version": "evidence-bundle.v2",
        "objective_id": "obj-action",
        "query_result_ref": None,
        "nodes": (
            {
                "evidence_id": "ev-01",
                "kind": "record",
                "source_id": "record:REC-001",
                "source_version": 3,
                "table_id": TABLE_ID,
                "record_id": RECORD_ID,
                "fields": (),
                "content_hash": "b" * 64,
            },
        ),
        "relations": (),
        "aggregates": (),
        "scope_hash": HASH,
        "complete": True,
        "truncated": False,
    }
    values["bundle_hash"] = canonical_retrieval_sha256(values)
    return EvidenceBundleV2.model_validate(values)


def _proof(version: int = 3) -> CurrentVersionProofV1:
    values = {
        "version": "current-version-proof.v1",
        "record_versions": (
            {"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": version},
        ),
        "scope_hash": HASH,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return CurrentVersionProofV1.model_validate(values)


def _command(refs) -> ObjectiveSpecialistInputV1:
    values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-action",
        "capability_id": "platform.action.propose",
        "task_spec_ref": "task-spec:sha256:" + "c" * 64,
        "input_artifact_refs": refs,
        "scope_hash": HASH,
        "schema_hash": HASH,
        "data_version_hash": None,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ObjectiveSpecialistInputV1.model_validate(values)


class _Bomb:
    def __getattr__(self, name):
        raise AssertionError(f"action_must_not_call_{name}")


def test_action_handler_proposes_only_authorized_candidates_without_write() -> None:
    refs = tuple(uuid4() for _ in range(4))
    artifacts = dict(
        zip(refs, (_slot(), _candidates(), _evidence(), _proof()), strict=True)
    )
    context = SpecialistExecutionContextV2(
        artifact_reader=artifacts.__getitem__,
        model_gateway=_Bomb(),
        tool_gateway=_Bomb(),
        clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = ActionSpecialistV2().execute(_command(refs), context)

    assert isinstance(result.payload, ControlledActionProposalV1)
    assert result.payload.status == "proposed"
    assert result.payload.target_record_ids == (RECORD_ID,)
    assert result.payload.execution_status == "not_executed"
    assert result.metrics == {"targets": 1, "provider_calls": 0, "writes": 0}


def test_action_handler_denies_record_version_drift_without_payload() -> None:
    refs = tuple(uuid4() for _ in range(4))
    artifacts = dict(
        zip(refs, (_slot(), _candidates(), _evidence(), _proof(4)), strict=True)
    )
    context = SpecialistExecutionContextV2(
        artifact_reader=artifacts.__getitem__,
        clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = ActionSpecialistV2().execute(_command(refs), context)

    assert result.payload.status == "denied"
    assert result.payload.target_record_ids == ()
    assert result.payload.assignments == ()
    assert result.payload.denial_reason == "record_version_drift"


def test_action_handler_denies_planner_conflict_before_proposal() -> None:
    refs = tuple(uuid4() for _ in range(4))
    slot = _slot().model_copy(
        update={
            "planning_outcome": "denied",
            "denial_reason": "conflicting_assignments",
        }
    )
    artifacts = dict(
        zip(refs, (slot, _candidates(), _evidence(), _proof()), strict=True)
    )
    context = SpecialistExecutionContextV2(
        artifact_reader=artifacts.__getitem__,
        clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = ActionSpecialistV2().execute(_command(refs), context)

    assert result.payload.status == "denied"
    assert result.payload.denial_reason == "conflicting_assignments"
    assert result.payload.target_record_ids == ()
    assert result.payload.assignments == ()


def test_action_handler_denies_unwritable_assignment_before_validation() -> None:
    refs = tuple(uuid4() for _ in range(4))
    candidates = _candidates()
    values = candidates.model_dump(mode="python", exclude={"candidate_set_hash"})
    values["candidates"] = tuple(
        {**item.model_dump(mode="python"), "writable_field_ids": ()}
        for item in candidates.candidates
    )
    values["candidate_set_hash"] = specialist_payload_sha256(values)
    candidates = AuthorizedCandidateSetV1.model_validate(values)
    artifacts = dict(
        zip(refs, (_slot(), candidates, _evidence(), _proof()), strict=True)
    )
    context = SpecialistExecutionContextV2(
        artifact_reader=artifacts.__getitem__,
        clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = ActionSpecialistV2().execute(_command(refs), context)

    assert result.payload.status == "denied"
    assert result.payload.denial_reason == "field_not_allowed"
    assert result.payload.target_record_ids == ()
    assert result.payload.assignments == ()
