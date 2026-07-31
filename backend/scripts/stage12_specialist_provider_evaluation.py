"""Focused synthetic-only Stage12-E Specialist and fan-in diagnostic."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from time import perf_counter_ns
from typing import Annotated, Literal, get_args
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_specialist_results import (
    AuthorizedCandidateSetV1,
    CurrentVersionProofV1,
    ObjectiveSpecialistInputV1,
    ProviderFailureCode,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import (
    ActionAssignment,
    ActionSlotV1,
    ActionTargetSelector,
    SourceSpan,
)
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    StructuredAggregate,
    StructuredFieldValue,
    StructuredQueryArtifactV1,
    StructuredQueryResultV1,
    StructuredRecord,
    authorized_query_plan_sha256,
    structured_query_result_sha256,
)
from app.schemas.retrieval_v2 import EvidenceBundleV2, canonical_retrieval_sha256
from app.services.agent_claim_graph import (
    ActionDependencyV1,
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
)
from app.services.agent_composer_v2 import compose_claim_graph
from app.services.agent_risk_policy import AuthorizedRiskPolicyV1, risk_policy_sha256
from app.services.agent_specialists_v2.action import ActionSpecialistV2
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.agent_specialists_v2.daily import DailySpecialistV2
from app.services.agent_specialists_v2.risk import RiskSpecialistV2
from app.services.agent_specialists_v2.tabular import TabularSpecialistV2


TABLE_ID = UUID("36000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("36000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("36000000-0000-4000-8000-000000000003")
SCOPE_HASH = "a" * 64
SCHEMA_HASH = "b" * 64
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]


class SpecialistProviderEvaluationReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["specialist-provider-evaluation.v1"]
    handler_count: StrictInt
    contract_exact_count: StrictInt
    typed_artifact_count: StrictInt
    claim_count: StrictInt
    valid_evidence_count: StrictInt
    partial_failure_safe: StrictBool
    stable_failure_class_count: StrictInt
    chinese_answer_grounded: StrictBool
    provider_attempt_count: StrictInt
    provider_failure_count: StrictInt
    action_proposal_count: StrictInt
    write_count: StrictInt
    send_count: StrictInt
    duration_ms: StrictInt
    report_hash: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def validate_report(self) -> "SpecialistProviderEvaluationReportV1":
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"report_hash"})
        )
        if self.report_hash != expected:
            raise ValueError("specialist_evaluation_hash_mismatch")
        if self.write_count or self.send_count:
            raise ValueError("specialist_evaluation_side_effect_detected")
        return self


def _command(
    objective_id: str,
    capability_id: str,
    refs: tuple[UUID, ...],
) -> ObjectiveSpecialistInputV1:
    values: dict[str, object] = {
        "version": "objective-specialist-input.v1",
        "objective_id": objective_id,
        "capability_id": capability_id,
        "task_spec_ref": "task-spec:sha256:" + "c" * 64,
        "input_artifact_refs": refs,
        "scope_hash": SCOPE_HASH,
        "schema_hash": SCHEMA_HASH,
        "data_version_hash": None,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ObjectiveSpecialistInputV1.model_validate(values)


def _query_artifact() -> StructuredQueryArtifactV1:
    plan = AuthorizedQueryPlanV1(
        version="authorized-query-plan.v1",
        query_intent_id="synthetic-query-01",
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
        max_scan_rows=10,
        max_relation_expansions=10,
        scope_hash=SCOPE_HASH,
        schema_hash=SCHEMA_HASH,
        traversal_paths=(),
    )
    plan_hash = authorized_query_plan_sha256(plan)
    values: dict[str, object] = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": plan_hash,
        "records": (
            StructuredRecord(
                record_id=RECORD_ID,
                table_id=TABLE_ID,
                values=(StructuredFieldValue(field_id=FIELD_ID, value="阻塞"),),
            ).model_dump(mode="json"),
        ),
        "groups": (),
        "aggregates": (
            StructuredAggregate(
                aggregate_id="synthetic-count", group_key=None, value=1
            ).model_dump(mode="json"),
        ),
        "relation_paths": (),
        "source_versions": (
            {
                "table_id": str(TABLE_ID),
                "record_id": str(RECORD_ID),
                "record_version": 3,
            },
        ),
        "scope_hash": SCOPE_HASH,
        "schema_hash": SCHEMA_HASH,
        "scanned_record_count": 1,
        "traversed_edge_count": 0,
        "truncated": False,
    }
    values["result_hash"] = structured_query_result_sha256(values)
    result = StructuredQueryResultV1.model_validate_json(json.dumps(values))
    return StructuredQueryArtifactV1(
        version="structured-query-artifact.v1",
        plan=plan,
        plan_hash=plan_hash,
        result=result,
    )


def _risk_policy() -> AuthorizedRiskPolicyV1:
    values: dict[str, object] = {
        "version": "authorized-risk-policy.v1",
        "policy_version": "synthetic-risk.v1",
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
        "scope_hash": SCOPE_HASH,
    }
    values["content_hash"] = risk_policy_sha256(values)
    return AuthorizedRiskPolicyV1.model_validate(values)


def _action_artifacts() -> tuple[object, ...]:
    slot = ActionSlotV1(
        slot_id="slot-01",
        objective_id="obj-action",
        action_kind="record.update",
        target=ActionTargetSelector(
            table_id=TABLE_ID,
            record_codes=("SYN-001",),
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
                source_span=SourceSpan(start=0, end=4, text="更新状态"),
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
    candidate_values: dict[str, object] = {
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
        "scope_hash": SCOPE_HASH,
        "complete": True,
    }
    candidate_values["candidate_set_hash"] = specialist_payload_sha256(candidate_values)
    candidates = AuthorizedCandidateSetV1.model_validate(candidate_values)
    evidence_values: dict[str, object] = {
        "version": "evidence-bundle.v2",
        "objective_id": "obj-action",
        "query_result_ref": None,
        "nodes": (
            {
                "evidence_id": "synthetic-action-proof",
                "kind": "record",
                "source_id": "record:SYN-001",
                "source_version": 3,
                "table_id": TABLE_ID,
                "record_id": RECORD_ID,
                "fields": (),
                "content_hash": "d" * 64,
            },
        ),
        "relations": (),
        "aggregates": (),
        "scope_hash": SCOPE_HASH,
        "complete": True,
        "truncated": False,
    }
    evidence_values["bundle_hash"] = canonical_retrieval_sha256(evidence_values)
    evidence = EvidenceBundleV2.model_validate(evidence_values)
    proof_values: dict[str, object] = {
        "version": "current-version-proof.v1",
        "record_versions": (
            {
                "table_id": TABLE_ID,
                "record_id": RECORD_ID,
                "record_version": 3,
            },
        ),
        "scope_hash": SCOPE_HASH,
    }
    proof_values["content_hash"] = specialist_payload_sha256(proof_values)
    proof = CurrentVersionProofV1.model_validate(proof_values)
    return slot, candidates, evidence, proof


def run_specialist_provider_evaluation(
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SpecialistProviderEvaluationReportV1:
    started = perf_counter_ns()
    query_ref = uuid4()
    tabular = TabularSpecialistV2().execute(
        _command("obj-tabular", "platform.tabular.analyse", (query_ref,)),
        SpecialistExecutionContextV2(
            artifact_reader=lambda ref: _query_artifact() if ref == query_ref else None,
            clock=now,
            metrics=lambda _key, _value: None,
        ),
    )
    fact_ref = uuid4()
    risk = RiskSpecialistV2().execute(
        _command("obj-risk", "platform.risk.analyse", (fact_ref,)),
        SpecialistExecutionContextV2(
            artifact_reader=lambda ref: tabular.payload if ref == fact_ref else None,
            risk_policy_reader=lambda _objective: _risk_policy(),
            clock=now,
            metrics=lambda _key, _value: None,
        ),
    )
    risk_ref = uuid4()
    daily_artifacts = {fact_ref: tabular.payload, risk_ref: risk.payload}
    daily = DailySpecialistV2().execute(
        _command("obj-daily", "platform.daily.summarise", (fact_ref, risk_ref)),
        SpecialistExecutionContextV2(
            artifact_reader=daily_artifacts.__getitem__,
            clock=now,
            metrics=lambda _key, _value: None,
        ),
    )
    action_objects = _action_artifacts()
    action_refs = tuple(uuid4() for _item in action_objects)
    action_map = dict(zip(action_refs, action_objects, strict=True))
    action = ActionSpecialistV2().execute(
        _command("obj-action", "platform.action.propose", action_refs),
        SpecialistExecutionContextV2(
            artifact_reader=action_map.__getitem__,
            clock=now,
            metrics=lambda _key, _value: None,
        ),
    )

    fact_claim = ClaimInputV1(
        objective_id="obj-tabular",
        subject_ref=f"record:{RECORD_ID}",
        predicate=f"field:{FIELD_ID}",
        value=tabular.payload.records[0].values[0].value,
        evidence_ids=tabular.payload.evidence_refs,
        source_version=tabular.payload.source_versions[0].record_version,
    )
    risk_claim = ClaimInputV1(
        objective_id="obj-risk",
        subject_ref=f"record:{RECORD_ID}",
        predicate="risk_severity",
        value=risk.payload.assessments[0].severity,
        evidence_ids=risk.payload.assessments[0].evidence_ids,
        source_version=tabular.payload.source_versions[0].record_version,
    )
    graph = build_claim_graph(
        claims=(fact_claim, risk_claim),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-tabular", "completed", True),
            ObjectiveOutcomeInputV1("obj-risk", "completed", False),
            ObjectiveOutcomeInputV1("obj-daily", "completed", False),
            ObjectiveOutcomeInputV1("obj-action", "proposed", True),
        ),
        actions=(
            ActionDependencyV1(
                slot_id=action.payload.slot_id,
                proposal_status=action.payload.status,
                required_claim_refs=((fact_claim.subject_ref, fact_claim.predicate),),
            ),
        ),
        scope_hash=SCOPE_HASH,
        source_artifacts=(tabular.payload, risk.payload),
    )
    composed = compose_claim_graph(graph)
    partial_graph = build_claim_graph(
        claims=(fact_claim,),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-tabular", "completed", True),
            ObjectiveOutcomeInputV1("obj-risk", "failed", False, "risk_failed"),
        ),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=(tabular.payload,),
    )
    partial = compose_claim_graph(partial_graph)
    evidence_count = len(
        {value for claim in graph.claims for value in claim.evidence_ids}
    )
    values: dict[str, object] = {
        "version": "specialist-provider-evaluation.v1",
        "handler_count": 4,
        "contract_exact_count": sum(
            int(
                result.payload.content_hash
                == specialist_payload_sha256(
                    result.payload.model_dump(mode="json", exclude={"content_hash"})
                )
            )
            for result in (tabular, risk, daily, action)
        ),
        "typed_artifact_count": 6,
        "claim_count": len(graph.claims),
        "valid_evidence_count": evidence_count,
        "partial_failure_safe": partial.status == "degraded"
        and bool(partial.claim_ids),
        "stable_failure_class_count": len(get_args(ProviderFailureCode)),
        "chinese_answer_grounded": (
            composed.status == "completed"
            and set(composed.claim_ids).issubset(
                {item.claim_id for item in graph.claims}
            )
        ),
        "provider_attempt_count": 0,
        "provider_failure_count": 0,
        "action_proposal_count": int(action.payload.status == "proposed"),
        "write_count": action.metrics["writes"],
        "send_count": 0,
        "duration_ms": max(0, (perf_counter_ns() - started) // 1_000_000),
    }
    values["report_hash"] = specialist_payload_sha256(values)
    return SpecialistProviderEvaluationReportV1.model_validate(values)


def main(
    argv: list[str] | None = None,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(description="Run focused Stage12-E diagnostic.")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_specialist_provider_evaluation(now=now)
    output = args.output_json.expanduser().resolve()
    if not output.parent.is_dir():
        raise ValueError("specialist_evaluation_output_parent_missing")
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SpecialistProviderEvaluationReportV1",
    "main",
    "run_specialist_provider_evaluation",
]
