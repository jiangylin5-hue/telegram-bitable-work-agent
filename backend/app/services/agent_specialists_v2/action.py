from __future__ import annotations

from app.schemas.agent_specialist_results import (
    AuthorizedCandidateSetV1,
    ControlledActionProposalV1,
    CurrentVersionProofV1,
    ObjectiveSpecialistInputV1,
    specialist_payload_sha256,
    validate_controlled_action_proposal,
)
from app.schemas.agent_task_spec_v2 import ActionSlotV1
from app.schemas.retrieval_v2 import EvidenceBundleV2
from app.services.agent_specialists_v2.base import (
    SpecialistExecutionContextV2,
    SpecialistHandlerResultV2,
)


class ActionSpecialistV2:
    capability_id = "platform.action.propose"
    input_schema_version = "objective-specialist-input.v1"
    output_schema_version = "controlled-action-proposal.v1"
    allowed_ports = frozenset(
        {"artifact_reader", "model_gateway", "tool_gateway", "clock", "metrics"}
    )

    def execute(
        self,
        command: ObjectiveSpecialistInputV1,
        context: SpecialistExecutionContextV2,
    ) -> SpecialistHandlerResultV2:
        if command.capability_id != self.capability_id:
            raise ValueError("action_specialist_capability_mismatch")
        artifacts = tuple(
            context.artifact_reader(ref) for ref in command.input_artifact_refs
        )
        slot = _one(artifacts, ActionSlotV1, "action_slot")
        candidates = _one(artifacts, AuthorizedCandidateSetV1, "candidate_set")
        evidence = _one(artifacts, EvidenceBundleV2, "evidence_bundle")
        versions = _one(artifacts, CurrentVersionProofV1, "version_proof")
        if (
            slot.objective_id != command.objective_id
            or candidates.objective_id != command.objective_id
            or evidence.objective_id != command.objective_id
            or slot.slot_id != candidates.slot_id
        ):
            raise ValueError("action_specialist_objective_mismatch")
        if any(
            value != command.scope_hash
            for value in (
                candidates.scope_hash,
                evidence.scope_hash,
                versions.scope_hash,
            )
        ):
            raise ValueError("action_specialist_scope_mismatch")
        current_versions = {
            item.record_id: (item.table_id, item.record_version)
            for item in versions.record_versions
        }
        denial_reason = None
        status = "proposed"
        candidate_fields = {
            item.record_id: set(item.writable_field_ids)
            for item in candidates.candidates
        }
        assignment_field_ids = {
            assignment.field_id
            for assignment in slot.assignments
            if assignment.field_id is not None
        }
        if slot.planning_outcome == "denied":
            status = "denied"
            denial_reason = slot.denial_reason or "action_denied"
        elif not candidates.complete or not candidates.candidates:
            status = "deferred"
            denial_reason = "candidate_set_incomplete"
        elif any(
            current_versions.get(item.record_id) != (item.table_id, item.record_version)
            for item in candidates.candidates
        ):
            status = "denied"
            denial_reason = "record_version_drift"
        elif any(assignment.field_id is None for assignment in slot.assignments):
            status = "denied"
            denial_reason = "field_not_allowed"
        elif any(
            not assignment_field_ids.issubset(candidate_fields[item.record_id])
            for item in candidates.candidates
        ):
            status = "denied"
            denial_reason = "field_not_allowed"
        target_record_ids = (
            tuple(item.record_id for item in candidates.candidates)
            if status == "proposed"
            else ()
        )
        assignments = ()
        if status == "proposed":
            assignments = tuple(
                {
                    "record_id": candidate.record_id,
                    "field_id": assignment.field_id,
                    "value": assignment.value,
                }
                for candidate in candidates.candidates
                for assignment in slot.assignments
            )
        values = {
            "version": "controlled-action-proposal.v1",
            "objective_id": command.objective_id,
            "slot_id": slot.slot_id,
            "status": status,
            "action_kind": slot.action_kind,
            "target_record_ids": target_record_ids,
            "assignments": assignments,
            "evidence_ids": (
                tuple(item.evidence_id for item in evidence.nodes)
                if status == "proposed"
                else ()
            ),
            "candidate_set_hash": candidates.candidate_set_hash,
            "confirmation_policy": "required",
            "execution_status": "not_executed",
            "denial_reason": denial_reason,
            "scope_hash": command.scope_hash,
            "provider_call_count": 0,
        }
        values["content_hash"] = specialist_payload_sha256(values)
        proposal = ControlledActionProposalV1.model_validate(values)
        validate_controlled_action_proposal(proposal, candidates)
        metrics = {
            "targets": len(proposal.target_record_ids),
            "provider_calls": 0,
            "writes": 0,
        }
        for key, value in metrics.items():
            context.metrics(key, value)
        return SpecialistHandlerResultV2(
            payload=proposal,
            safe_summary=(
                "受控动作建议已生成" if status == "proposed" else "受控动作建议未生成"
            ),
            metrics=metrics,
        )


def _one(artifacts: tuple[object, ...], value_type: type, label: str):
    matches = tuple(item for item in artifacts if isinstance(item, value_type))
    if len(matches) != 1:
        raise ValueError(f"action_specialist_{label}_invalid")
    return matches[0]


__all__ = ["ActionSpecialistV2"]
