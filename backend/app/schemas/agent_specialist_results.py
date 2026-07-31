"""Strict Stage12-E typed Specialist, ClaimGraph and Composer contracts."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_task_spec_v2 import ActionKindV1, JsonValue
from app.schemas.authorized_query_plan import (
    RelationPathProof,
    SourceRecordVersion,
    StructuredAggregate,
    StructuredGroup,
    StructuredRecord,
)


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
ProviderRole: TypeAlias = Literal["planner", "risk", "daily", "action", "composer"]
ProviderFailureCode: TypeAlias = Literal[
    "provider_timeout",
    "provider_rate_limited",
    "provider_quota_exhausted",
    "provider_http_error",
    "provider_schema_invalid",
    "provider_semantic_invalid",
    "provider_language_invalid",
    "provider_citation_invalid",
    "insufficient_evidence",
    "ambiguous_target",
    "action_not_allowed",
    "field_not_allowed",
    "deadline_exhausted",
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def specialist_payload_sha256(value: BaseModel | dict[str, object]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value

    def json_default(item: object) -> str:
        if isinstance(item, datetime):
            rendered = item.isoformat()
            return (
                rendered.removesuffix("+00:00") + "Z"
                if rendered.endswith("+00:00")
                else rendered
            )
        return str(item)

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


class ObjectiveSpecialistInputV1(_StrictFrozenModel):
    version: Literal["objective-specialist-input.v1"]
    objective_id: NonEmptyStr
    capability_id: Literal[
        "platform.tabular.analyse",
        "platform.risk.analyse",
        "platform.daily.summarise",
        "platform.action.propose",
    ]
    task_spec_ref: NonEmptyStr
    input_artifact_refs: tuple[UUID, ...] = Field(max_length=16)
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    data_version_hash: Sha256Hex | None
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_input(self) -> "ObjectiveSpecialistInputV1":
        if len(set(self.input_artifact_refs)) != len(self.input_artifact_refs):
            raise ValueError("specialist_input_artifact_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_input_hash_mismatch")
        return self


class StructuredFactSetV1(_StrictFrozenModel):
    version: Literal["structured-fact-set.v1"]
    objective_id: NonEmptyStr
    records: tuple[StructuredRecord, ...]
    groups: tuple[StructuredGroup, ...]
    aggregates: tuple[StructuredAggregate, ...]
    relation_paths: tuple[RelationPathProof, ...]
    source_versions: tuple[SourceRecordVersion, ...]
    evidence_refs: tuple[NonEmptyStr, ...]
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    complete: StrictBool
    truncated: StrictBool
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_fact_set(self) -> "StructuredFactSetV1":
        if self.complete and self.truncated:
            raise ValueError("specialist_fact_completeness_invalid")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("specialist_fact_evidence_duplicate")
        record_keys = tuple((item.table_id, item.record_id) for item in self.records)
        version_keys = tuple(
            (item.table_id, item.record_id) for item in self.source_versions
        )
        aggregate_keys = tuple(
            (
                item.aggregate_id,
                json.dumps(
                    item.group_key,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
            for item in self.aggregates
        )
        if (
            len(set(record_keys)) != len(record_keys)
            or len(set(version_keys)) != len(version_keys)
            or len(set(aggregate_keys)) != len(aggregate_keys)
        ):
            raise ValueError("specialist_fact_identity_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_fact_hash_mismatch")
        return self


class RiskAssessmentV1(_StrictFrozenModel):
    assessment_id: NonEmptyStr
    subject_ref: NonEmptyStr
    severity: Literal["low", "medium", "high", "critical"]
    reason_codes: tuple[NonEmptyStr, ...] = Field(min_length=1)
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_collections(self) -> "RiskAssessmentV1":
        if len(set(self.reason_codes)) != len(self.reason_codes) or len(
            set(self.evidence_ids)
        ) != len(self.evidence_ids):
            raise ValueError("specialist_risk_value_duplicate")
        return self


class RiskAssessmentSetV1(_StrictFrozenModel):
    version: Literal["risk-assessment-set.v1"]
    objective_id: NonEmptyStr
    fact_set_hash: Sha256Hex
    policy_version: NonEmptyStr
    available_evidence_ids: tuple[NonEmptyStr, ...]
    assessments: tuple[RiskAssessmentV1, ...]
    scope_hash: Sha256Hex
    provider_call_count: StrictInt = Field(ge=0, le=2)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_assessments(self) -> "RiskAssessmentSetV1":
        if len(set(self.available_evidence_ids)) != len(self.available_evidence_ids):
            raise ValueError("specialist_risk_evidence_duplicate")
        assessment_ids = tuple(item.assessment_id for item in self.assessments)
        if len(set(assessment_ids)) != len(assessment_ids):
            raise ValueError("specialist_risk_assessment_duplicate")
        available = set(self.available_evidence_ids)
        if any(
            not set(item.evidence_ids).issubset(available) for item in self.assessments
        ):
            raise ValueError("specialist_risk_evidence_unknown")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_risk_hash_mismatch")
        return self


class DailyStatementV1(_StrictFrozenModel):
    statement_id: NonEmptyStr
    kind: Literal["fact", "anomaly", "risk", "recommendation"]
    text: NonEmptyStr = Field(max_length=1000)
    evidence_ids: tuple[NonEmptyStr, ...]
    aggregate_id: NonEmptyStr | None

    @model_validator(mode="after")
    def validate_statement(self) -> "DailyStatementV1":
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("specialist_daily_evidence_duplicate")
        if self.kind == "recommendation" and self.aggregate_id is not None:
            raise ValueError("specialist_daily_recommendation_aggregate_invalid")
        return self


class DailyBriefV1(_StrictFrozenModel):
    version: Literal["daily-brief.v1"]
    objective_id: NonEmptyStr
    fact_set_hash: Sha256Hex
    risk_set_hash: Sha256Hex | None
    available_evidence_ids: tuple[NonEmptyStr, ...]
    statements: tuple[DailyStatementV1, ...]
    as_of_utc: datetime
    scope_hash: Sha256Hex
    provider_call_count: StrictInt = Field(ge=0, le=2)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_brief(self) -> "DailyBriefV1":
        if self.as_of_utc.tzinfo is None or self.as_of_utc.utcoffset() is None:
            raise ValueError("specialist_daily_timezone_required")
        if self.as_of_utc.utcoffset().total_seconds() != 0:
            raise ValueError("specialist_daily_utc_required")
        if len(set(self.available_evidence_ids)) != len(self.available_evidence_ids):
            raise ValueError("specialist_daily_evidence_duplicate")
        statement_ids = tuple(item.statement_id for item in self.statements)
        if len(set(statement_ids)) != len(statement_ids):
            raise ValueError("specialist_daily_statement_duplicate")
        available = set(self.available_evidence_ids)
        if any(
            not set(item.evidence_ids).issubset(available) for item in self.statements
        ):
            raise ValueError("specialist_daily_evidence_unknown")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_daily_hash_mismatch")
        return self


class AuthorizedActionCandidateV1(_StrictFrozenModel):
    table_id: UUID
    record_id: UUID
    record_version: StrictInt = Field(ge=1)
    writable_field_ids: tuple[UUID, ...]

    @model_validator(mode="after")
    def validate_fields(self) -> "AuthorizedActionCandidateV1":
        if len(set(self.writable_field_ids)) != len(self.writable_field_ids):
            raise ValueError("specialist_candidate_field_duplicate")
        return self


class AuthorizedCandidateSetV1(_StrictFrozenModel):
    version: Literal["authorized-candidate-set.v1"]
    objective_id: NonEmptyStr
    slot_id: NonEmptyStr
    candidates: tuple[AuthorizedActionCandidateV1, ...]
    scope_hash: Sha256Hex
    complete: StrictBool
    candidate_set_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_candidates(self) -> "AuthorizedCandidateSetV1":
        identities = tuple(item.record_id for item in self.candidates)
        if len(set(identities)) != len(identities):
            raise ValueError("specialist_candidate_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"candidate_set_hash"})
        )
        if self.candidate_set_hash != expected:
            raise ValueError("specialist_candidate_hash_mismatch")
        return self


class CurrentRecordVersionV1(_StrictFrozenModel):
    table_id: UUID
    record_id: UUID
    record_version: StrictInt = Field(ge=1)


class CurrentVersionProofV1(_StrictFrozenModel):
    version: Literal["current-version-proof.v1"]
    record_versions: tuple[CurrentRecordVersionV1, ...]
    scope_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_proof(self) -> "CurrentVersionProofV1":
        identities = tuple(item.record_id for item in self.record_versions)
        if len(set(identities)) != len(identities):
            raise ValueError("specialist_version_proof_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_version_proof_hash_mismatch")
        return self


class ActionProposalAssignmentV1(_StrictFrozenModel):
    record_id: UUID
    field_id: UUID
    value: JsonValue


class ControlledActionProposalV1(_StrictFrozenModel):
    version: Literal["controlled-action-proposal.v1"]
    objective_id: NonEmptyStr
    slot_id: NonEmptyStr
    status: Literal["proposed", "denied", "deferred"]
    action_kind: ActionKindV1
    target_record_ids: tuple[UUID, ...]
    assignments: tuple[ActionProposalAssignmentV1, ...]
    evidence_ids: tuple[NonEmptyStr, ...]
    candidate_set_hash: Sha256Hex
    confirmation_policy: Literal["required"]
    execution_status: Literal["not_executed"]
    denial_reason: StrictStr | None
    scope_hash: Sha256Hex
    provider_call_count: StrictInt = Field(ge=0, le=2)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_proposal(self) -> "ControlledActionProposalV1":
        if len(set(self.target_record_ids)) != len(self.target_record_ids) or len(
            set(self.evidence_ids)
        ) != len(self.evidence_ids):
            raise ValueError("specialist_action_value_duplicate")
        assignment_keys = tuple(
            (item.record_id, item.field_id) for item in self.assignments
        )
        if len(set(assignment_keys)) != len(assignment_keys):
            raise ValueError("specialist_action_assignment_duplicate")
        if self.status == "proposed":
            if not self.target_record_ids or self.denial_reason is not None:
                raise ValueError("specialist_action_proposal_invalid")
        elif self.target_record_ids or self.assignments or self.evidence_ids:
            raise ValueError("specialist_action_denial_payload_invalid")
        elif not self.denial_reason:
            raise ValueError("specialist_action_denial_reason_required")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_action_hash_mismatch")
        return self


def validate_controlled_action_proposal(
    proposal: ControlledActionProposalV1,
    candidate_set: AuthorizedCandidateSetV1,
) -> ControlledActionProposalV1:
    if (
        proposal.objective_id != candidate_set.objective_id
        or proposal.slot_id != candidate_set.slot_id
        or proposal.scope_hash != candidate_set.scope_hash
        or proposal.candidate_set_hash != candidate_set.candidate_set_hash
    ):
        raise ValueError("specialist_action_candidate_set_mismatch")
    candidates = {item.record_id: item for item in candidate_set.candidates}
    if any(record_id not in candidates for record_id in proposal.target_record_ids):
        raise ValueError("specialist_action_candidate_invalid")
    if any(
        item.record_id not in candidates
        or item.field_id not in candidates[item.record_id].writable_field_ids
        for item in proposal.assignments
    ):
        raise ValueError("specialist_action_field_invalid")
    return proposal


class ClaimV1(_StrictFrozenModel):
    claim_id: NonEmptyStr
    subject_ref: NonEmptyStr
    predicate: NonEmptyStr
    value: JsonValue
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    objective_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    source_version: StrictInt = Field(ge=1)
    status: Literal["valid", "stale", "conflicted"]


class ObjectiveStatusV1(_StrictFrozenModel):
    objective_id: NonEmptyStr
    status: Literal["completed", "proposed", "denied", "degraded", "failed"]
    reason_code: StrictStr | None

    @model_validator(mode="after")
    def validate_reason(self) -> "ObjectiveStatusV1":
        if (self.status in {"completed", "proposed"}) == (self.reason_code is not None):
            raise ValueError("specialist_objective_reason_invalid")
        return self


class ActionStatusV1(_StrictFrozenModel):
    slot_id: NonEmptyStr
    status: Literal["proposed", "denied", "deferred", "conflicted"]
    reason_code: StrictStr | None


class ClaimGraphV1(_StrictFrozenModel):
    version: Literal["claim-graph.v1"]
    claims: tuple[ClaimV1, ...]
    objective_statuses: tuple[ObjectiveStatusV1, ...]
    action_statuses: tuple[ActionStatusV1, ...]
    scope_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_graph(self) -> "ClaimGraphV1":
        claim_ids = tuple(item.claim_id for item in self.claims)
        objective_ids = tuple(item.objective_id for item in self.objective_statuses)
        action_ids = tuple(item.slot_id for item in self.action_statuses)
        if any(
            len(set(values)) != len(values)
            for values in (claim_ids, objective_ids, action_ids)
        ):
            raise ValueError("specialist_claim_identity_duplicate")
        grouped: dict[tuple[str, str, int], list[ClaimV1]] = {}
        for claim in self.claims:
            grouped.setdefault(
                (claim.subject_ref, claim.predicate, claim.source_version), []
            ).append(claim)
        for claims in grouped.values():
            values = {
                json.dumps(
                    item.value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                for item in claims
            }
            if len(values) > 1 and any(item.status != "conflicted" for item in claims):
                raise ValueError("specialist_claim_conflict_unmarked")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_claim_graph_hash_mismatch")
        return self


class FinalAnswerCitationEdgeV1(_StrictFrozenModel):
    claim_id: NonEmptyStr
    evidence_id: NonEmptyStr


class FinalAnswerRenderReceiptV1(_StrictFrozenModel):
    version: Literal["final-answer-render-receipt.v1"]
    covered_objective_ids: tuple[NonEmptyStr, ...]
    covered_claim_ids: tuple[NonEmptyStr, ...]
    covered_action_slot_ids: tuple[NonEmptyStr, ...]
    citation_edges: tuple[FinalAnswerCitationEdgeV1, ...]
    section_kinds: tuple[NonEmptyStr, ...]
    disclosure_codes: tuple[NonEmptyStr, ...]
    language: Literal["zh-Hans"]
    answer_hash: Sha256Hex
    claim_graph_hash: Sha256Hex
    presentation_hash: Sha256Hex
    scope_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_receipt(self) -> "FinalAnswerRenderReceiptV1":
        for values in (
            self.covered_objective_ids,
            self.covered_claim_ids,
            self.covered_action_slot_ids,
            self.section_kinds,
            self.disclosure_codes,
        ):
            if len(set(values)) != len(values):
                raise ValueError("specialist_render_receipt_value_duplicate")
        edge_keys = tuple(
            (item.claim_id, item.evidence_id) for item in self.citation_edges
        )
        if len(set(edge_keys)) != len(edge_keys):
            raise ValueError("specialist_render_receipt_citation_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_render_receipt_hash_mismatch")
        return self


class ComposerResultV1(_StrictFrozenModel):
    version: Literal["composer-result.v1"]
    status: Literal["completed", "degraded", "denied", "failed"]
    answer: NonEmptyStr = Field(max_length=4000)
    claim_ids: tuple[NonEmptyStr, ...]
    evidence_ids: tuple[NonEmptyStr, ...]
    action_statuses: tuple[ActionStatusV1, ...]
    degradation_codes: tuple[NonEmptyStr, ...]
    render_receipt: FinalAnswerRenderReceiptV1
    provider_call_count: StrictInt = Field(ge=0, le=2)
    scope_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_result(self) -> "ComposerResultV1":
        if re.search(r"[\u3400-\u9fff]", self.answer) is None:
            raise ValueError("specialist_composer_language_invalid")
        if any(
            len(set(values)) != len(values)
            for values in (
                self.claim_ids,
                self.evidence_ids,
                self.degradation_codes,
            )
        ):
            raise ValueError("specialist_composer_value_duplicate")
        if self.status == "completed" and self.degradation_codes:
            raise ValueError("specialist_composer_degradation_invalid")
        if (
            self.render_receipt.answer_hash
            != sha256(self.answer.encode("utf-8")).hexdigest()
        ):
            raise ValueError("specialist_composer_answer_hash_mismatch")
        if (
            self.render_receipt.scope_hash != self.scope_hash
            or set(self.render_receipt.covered_claim_ids) != set(self.claim_ids)
            or set(self.render_receipt.covered_action_slot_ids)
            != {item.slot_id for item in self.action_statuses}
        ):
            raise ValueError("specialist_composer_receipt_mismatch")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("specialist_composer_hash_mismatch")
        return self


class ProviderAttemptObservationV1(_StrictFrozenModel):
    version: Literal["provider-attempt.v1"]
    role: ProviderRole
    profile_id: NonEmptyStr
    provider: NonEmptyStr
    model_id: NonEmptyStr
    attempt: StrictInt = Field(ge=1, le=2)
    status: Literal["completed", "failed"]
    failure_code: ProviderFailureCode | None
    latency_ms: StrictInt = Field(ge=0)
    input_tokens: StrictInt | None = Field(default=None, ge=0)
    output_tokens: StrictInt | None = Field(default=None, ge=0)
    repair: StrictBool
    observation_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_observation(self) -> "ProviderAttemptObservationV1":
        if (self.status == "completed") != (self.failure_code is None):
            raise ValueError("specialist_provider_status_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"observation_hash"})
        )
        if self.observation_hash != expected:
            raise ValueError("specialist_provider_observation_hash_mismatch")
        return self


__all__ = [
    "ActionProposalAssignmentV1",
    "ActionStatusV1",
    "AuthorizedActionCandidateV1",
    "AuthorizedCandidateSetV1",
    "ClaimGraphV1",
    "ClaimV1",
    "ComposerResultV1",
    "ControlledActionProposalV1",
    "CurrentRecordVersionV1",
    "CurrentVersionProofV1",
    "DailyBriefV1",
    "DailyStatementV1",
    "ObjectiveSpecialistInputV1",
    "ObjectiveStatusV1",
    "ProviderAttemptObservationV1",
    "ProviderFailureCode",
    "ProviderRole",
    "RiskAssessmentSetV1",
    "RiskAssessmentV1",
    "StructuredFactSetV1",
    "specialist_payload_sha256",
    "validate_controlled_action_proposal",
]
