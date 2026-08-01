from __future__ import annotations

from hashlib import sha256
from uuid import UUID, uuid4

import pytest

from app.models.agent_event_runtime import AgentArtifact
from app.schemas.agent_specialist_results import (
    ComposerResultV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import ActionSlotV1, ActionTargetSelector
from app.schemas.retrieval_v2 import EvidenceBundleV2, canonical_retrieval_sha256
from app.services.agent_typed_artifacts import (
    persist_typed_artifact,
    read_typed_artifact,
    read_typed_artifact_owner_ref,
)
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


WORKSPACE_ID = UUID("31000000-0000-4000-8000-000000000001")
RUN_ID = UUID("31000000-0000-4000-8000-000000000002")
HASH = "a" * 64


def _composer() -> ComposerResultV1:
    answer = "当前有一项阻塞记录。"
    receipt = {
        "version": "final-answer-render-receipt.v1",
        "covered_objective_ids": ("obj-01",),
        "covered_claim_ids": ("claim-01",),
        "covered_action_slot_ids": (),
        "citation_edges": ({"claim_id": "claim-01", "evidence_id": "ev-01"},),
        "section_kinds": ("facts",),
        "disclosure_codes": (),
        "language": "zh-Hans",
        "answer_hash": sha256(answer.encode("utf-8")).hexdigest(),
        "claim_graph_hash": HASH,
        "presentation_hash": HASH,
        "scope_hash": HASH,
    }
    receipt["content_hash"] = specialist_payload_sha256(receipt)
    payload = {
        "version": "composer-result.v1",
        "status": "completed",
        "answer": answer,
        "claim_ids": ("claim-01",),
        "evidence_ids": ("ev-01",),
        "action_statuses": (),
        "degradation_codes": (),
        "render_receipt": receipt,
        "provider_call_count": 0,
        "scope_hash": HASH,
    }
    payload["content_hash"] = specialist_payload_sha256(payload)
    return ComposerResultV1.model_validate(payload)


def _metadata(storage_ref: str, content_hash: str) -> AgentArtifact:
    return AgentArtifact(
        id=uuid4(),
        run_id=RUN_ID,
        kind="composer_result",
        storage_ref=storage_ref,
        content_hash=content_hash,
        visibility_scope_hash=HASH,
        validation_status="validated",
        expires_at=None,
    )


def test_typed_artifact_uses_existing_idempotency_owner_and_replays() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    payload = _composer()

    first = persist_typed_artifact(
        uow,
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
        artifact_kind="composer_result",
        payload=payload,
        scope_hash=HASH,
    )
    second = persist_typed_artifact(
        uow,
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
        artifact_kind="composer_result",
        payload=payload,
        scope_hash=HASH,
    )

    assert first.storage_ref == second.storage_ref
    assert len(uow.idempotency_records) == 1
    owner = uow.idempotency_records[0]
    assert owner.operation == "stage12.specialist-artifact.v1"
    assert owner.response_ref is not None
    assert set(owner.response_ref) == {
        "version",
        "artifact_kind",
        "payload_version",
        "scope_hash",
        "content_hash",
        "payload",
    }
    metadata = _metadata(first.storage_ref, payload.content_hash)
    assert (
        read_typed_artifact(
            uow,
            artifact=metadata,
            workspace_id=WORKSPACE_ID,
            current_scope_hash=HASH,
            expected_kind="composer_result",
            payload_type=ComposerResultV1,
        )
        == payload
    )


def test_typed_artifact_read_fails_closed_on_scope_or_owner_tamper() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    payload = _composer()
    owner = persist_typed_artifact(
        uow,
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
        artifact_kind="composer_result",
        payload=payload,
        scope_hash=HASH,
    )
    metadata = _metadata(owner.storage_ref, payload.content_hash)

    with pytest.raises(ValueError, match="typed_artifact_owner_invalid"):
        read_typed_artifact(
            uow,
            artifact=metadata,
            workspace_id=uuid4(),
            current_scope_hash=HASH,
            expected_kind="composer_result",
            payload_type=ComposerResultV1,
        )

    with pytest.raises(ValueError, match="typed_artifact_scope_mismatch"):
        read_typed_artifact(
            uow,
            artifact=metadata,
            workspace_id=WORKSPACE_ID,
            current_scope_hash="b" * 64,
            expected_kind="composer_result",
            payload_type=ComposerResultV1,
        )

    uow.idempotency_records[0].response_ref["payload"]["answer"] = "被篡改"
    with pytest.raises(ValueError, match="typed_artifact_payload_hash_mismatch"):
        read_typed_artifact(
            uow,
            artifact=metadata,
            workspace_id=WORKSPACE_ID,
            current_scope_hash=HASH,
            expected_kind="composer_result",
            payload_type=ComposerResultV1,
        )


def test_typed_artifact_rejects_metadata_kind_and_storage_ref_drift() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    payload = _composer()
    owner = persist_typed_artifact(
        uow,
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
        artifact_kind="composer_result",
        payload=payload,
        scope_hash=HASH,
    )
    metadata = _metadata(owner.storage_ref, payload.content_hash)
    metadata.kind = "risk_assessment_set"
    with pytest.raises(ValueError, match="typed_artifact_kind_mismatch"):
        read_typed_artifact(
            uow,
            artifact=metadata,
            workspace_id=WORKSPACE_ID,
            current_scope_hash=HASH,
            expected_kind="composer_result",
            payload_type=ComposerResultV1,
        )

    metadata.kind = "composer_result"
    metadata.storage_ref = "record-snapshot:" + str(uuid4())
    with pytest.raises(ValueError, match="typed_artifact_storage_ref_invalid"):
        read_typed_artifact(
            uow,
            artifact=metadata,
            workspace_id=WORKSPACE_ID,
            current_scope_hash=HASH,
            expected_kind="composer_result",
            payload_type=ComposerResultV1,
        )


def test_typed_owner_supports_bundle_hash_and_direct_sealed_input_read() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    values = {
        "version": "evidence-bundle.v2",
        "objective_id": "obj-1",
        "query_result_ref": None,
        "nodes": (),
        "relations": (),
        "aggregates": (),
        "scope_hash": HASH,
        "complete": True,
        "truncated": False,
    }
    values["bundle_hash"] = canonical_retrieval_sha256(values)
    bundle = EvidenceBundleV2.model_validate(values)

    owner = persist_typed_artifact(
        uow,
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
        artifact_kind="evidence_bundle",
        payload=bundle,
        scope_hash=HASH,
    )

    assert (
        read_typed_artifact_owner_ref(
            uow,
            storage_ref=owner.storage_ref,
            workspace_id=WORKSPACE_ID,
            current_scope_hash=HASH,
            expected_kind="evidence_bundle",
            payload_type=EvidenceBundleV2,
        )
        == bundle
    )


def test_typed_owner_seals_versionless_action_slot_with_explicit_owner_version() -> (
    None
):
    uow = InMemoryStage06PlatformUnitOfWork()
    slot = ActionSlotV1(
        slot_id="slot-1",
        objective_id="obj-action",
        action_kind="record.update",
        target=ActionTargetSelector(
            table_id=uuid4(),
            record_codes=("REC-1",),
            source_entity_codes=(),
            query_spec_ref=None,
            expansion_policy="none",
            resolution_status="resolved",
        ),
        assignments=(),
        required_field_keys=(),
        confirmation_policy="required",
        deadline_start_utc=None,
        deadline_end_utc=None,
        conflict_group_id=None,
        planning_outcome="planned",
        denial_reason=None,
    )

    owner = persist_typed_artifact(
        uow,
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
        artifact_kind="action_slot",
        payload=slot,
        scope_hash=HASH,
    )

    assert (
        uow.idempotency_records[0].response_ref["payload_version"] == "action-slot.v1"
    )
    assert (
        read_typed_artifact_owner_ref(
            uow,
            storage_ref=owner.storage_ref,
            workspace_id=WORKSPACE_ID,
            current_scope_hash=HASH,
            expected_kind="action_slot",
            payload_type=ActionSlotV1,
        )
        == slot
    )
