"""Strict private contracts for Stage12 Grounded Answer Provider V2."""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Annotated, Literal, TypeAlias

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
    ActionStatusV1,
    FinalAnswerRenderReceiptV1,
    specialist_payload_sha256,
)


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
ClaimHandle = Annotated[StrictStr, Field(pattern=r"^claim:sha256:[0-9a-f]{64}$")]
EvidenceHandle = Annotated[StrictStr, Field(pattern=r"^evidence:sha256:[0-9a-f]{64}$")]
ActionHandle = Annotated[StrictStr, Field(pattern=r"^action:sha256:[0-9a-f]{64}$")]
ObjectiveHandle = Annotated[
    StrictStr, Field(pattern=r"^objective:sha256:[0-9a-f]{64}$")
]

AnswerSource: TypeAlias = Literal["real_provider", "deterministic_fallback"]
ProviderResultStatus: TypeAlias = Literal[
    "completed",
    "transport_failed",
    "schema_failed",
    "grounding_failed",
    "language_failed",
]
GroundedStatementKind: TypeAlias = Literal[
    "fact", "analysis", "recommendation", "action_status", "limitation"
]
GroundedSectionKind: TypeAlias = Literal[
    "answer", "facts", "analysis", "risks", "daily", "actions", "limitations"
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _duplicates(values: tuple[str, ...]) -> bool:
    return len(set(values)) != len(values)


class GroundedObjectiveCandidateV2(_StrictFrozenModel):
    objective_handle: ObjectiveHandle
    kind: NonEmptyStr
    status: Literal["completed", "proposed", "denied", "degraded", "failed"]
    required: StrictBool
    reason_code: StrictStr | None


class GroundedClaimCandidateV2(_StrictFrozenModel):
    claim_handle: ClaimHandle
    objective_handles: tuple[ObjectiveHandle, ...] = Field(min_length=1, max_length=16)
    subject_label: NonEmptyStr
    predicate_label: NonEmptyStr
    value_type: Literal[
        "string",
        "integer",
        "number",
        "boolean",
        "date",
        "datetime",
        "enum",
        "list",
        "object",
        "null",
    ]
    value_text: NonEmptyStr
    qualifiers: tuple[NonEmptyStr, ...] = Field(max_length=16)
    evidence_handles: tuple[EvidenceHandle, ...] = Field(min_length=1, max_length=32)
    source_versions: tuple[NonEmptyStr, ...] = Field(min_length=1, max_length=32)
    status: Literal["valid", "stale", "conflicted"]

    @model_validator(mode="after")
    def validate_references(self) -> "GroundedClaimCandidateV2":
        if any(
            _duplicates(values)
            for values in (
                self.objective_handles,
                self.qualifiers,
                self.evidence_handles,
                self.source_versions,
            )
        ):
            raise ValueError("grounded_claim_reference_duplicate")
        return self


class GroundedEvidenceCandidateV2(_StrictFrozenModel):
    evidence_handle: EvidenceHandle
    display_label: NonEmptyStr
    source_version: NonEmptyStr


class GroundedActionCandidateV2(_StrictFrozenModel):
    action_handle: ActionHandle
    action_kind: NonEmptyStr
    status: Literal["proposed", "denied", "deferred", "conflicted"]
    safe_summary: NonEmptyStr
    reason_code: StrictStr | None


class GroundedSpecialistFindingV2(_StrictFrozenModel):
    finding_handle: Annotated[
        StrictStr, Field(pattern=r"^finding:sha256:[0-9a-f]{64}$")
    ]
    finding_kind: Literal["tabular", "risk", "daily"]
    safe_text: NonEmptyStr
    claim_handles: tuple[ClaimHandle, ...] = Field(min_length=1, max_length=16)
    evidence_handles: tuple[EvidenceHandle, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_references(self) -> "GroundedSpecialistFindingV2":
        if _duplicates(self.claim_handles) or _duplicates(self.evidence_handles):
            raise ValueError("grounded_finding_reference_duplicate")
        return self


class GroundedPresentationPolicyV2(_StrictFrozenModel):
    max_sections: StrictInt = Field(ge=1, le=7)
    max_statements_per_section: StrictInt = Field(ge=1, le=12)
    allowed_section_kinds: tuple[GroundedSectionKind, ...] = Field(
        min_length=1, max_length=7
    )
    allowed_statement_kinds: tuple[GroundedStatementKind, ...] = Field(
        min_length=1, max_length=5
    )
    require_chinese: Literal[True]
    require_objective_coverage: Literal[True]

    @model_validator(mode="after")
    def validate_policy(self) -> "GroundedPresentationPolicyV2":
        if _duplicates(self.allowed_section_kinds) or _duplicates(
            self.allowed_statement_kinds
        ):
            raise ValueError("grounded_presentation_policy_duplicate")
        return self


class GroundedAnswerProviderRequestV2(_StrictFrozenModel):
    version: Literal["grounded-answer-provider-request.v2"]
    language: Literal["zh-CN"]
    query: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    objectives: tuple[GroundedObjectiveCandidateV2, ...] = Field(
        min_length=1, max_length=16
    )
    claims: tuple[GroundedClaimCandidateV2, ...] = Field(max_length=128)
    specialist_findings: tuple[GroundedSpecialistFindingV2, ...] = Field(max_length=64)
    actions: tuple[GroundedActionCandidateV2, ...] = Field(max_length=32)
    citations: tuple[GroundedEvidenceCandidateV2, ...] = Field(max_length=256)
    presentation_policy: GroundedPresentationPolicyV2
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    field_policy_version: Literal["stage12-field-policy.v2"]
    field_policy_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_request(self) -> "GroundedAnswerProviderRequestV2":
        identity_groups = (
            tuple(item.objective_handle for item in self.objectives),
            tuple(item.claim_handle for item in self.claims),
            tuple(item.finding_handle for item in self.specialist_findings),
            tuple(item.action_handle for item in self.actions),
            tuple(item.evidence_handle for item in self.citations),
        )
        if any(_duplicates(values) for values in identity_groups):
            raise ValueError("grounded_request_identity_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("grounded_request_hash_mismatch")
        return self


class GroundedAnswerStatementV2(_StrictFrozenModel):
    statement_kind: GroundedStatementKind = Field(
        description="How the statement must be interpreted and validated."
    )
    text: Annotated[
        StrictStr,
        Field(
            min_length=1,
            max_length=1000,
            description="Chinese user-visible prose authored by the model.",
        ),
    ]
    claim_handles: tuple[ClaimHandle, ...] = Field(
        max_length=16,
        description="Exact canonical claims supporting this statement.",
    )
    evidence_handles: tuple[EvidenceHandle, ...] = Field(
        max_length=32,
        description="Exact evidence closure for the referenced claims.",
    )
    action_handles: tuple[ActionHandle, ...] = Field(
        max_length=16,
        description="Pending or denied action statuses described by this statement.",
    )

    @model_validator(mode="after")
    def validate_references(self) -> "GroundedAnswerStatementV2":
        if any(
            _duplicates(values)
            for values in (
                self.claim_handles,
                self.evidence_handles,
                self.action_handles,
            )
        ):
            raise ValueError("grounded_statement_reference_duplicate")
        if self.statement_kind in {"fact", "analysis", "recommendation"} and (
            not self.claim_handles or not self.evidence_handles
        ):
            raise ValueError("grounded_statement_claim_required")
        if self.statement_kind == "action_status" and not self.action_handles:
            raise ValueError("grounded_statement_action_required")
        return self


class GroundedAnswerSectionV2(_StrictFrozenModel):
    section_kind: GroundedSectionKind = Field(
        description="Stable semantic role of this answer section."
    )
    heading: Annotated[
        StrictStr,
        Field(
            min_length=1,
            max_length=80,
            description="Short Chinese heading shown to the user.",
        ),
    ]
    statements: tuple[GroundedAnswerStatementV2, ...] = Field(
        min_length=1,
        max_length=12,
        description="Ordered model-authored statements in this section.",
    )


class GroundedAnswerPlanV2(_StrictFrozenModel):
    version: Literal["grounded-answer-plan.v2"] = Field(
        default="grounded-answer-plan.v2",
        description="Exact version of the grounded answer response contract.",
    )
    sections: tuple[GroundedAnswerSectionV2, ...] = Field(
        min_length=1,
        max_length=7,
        description="Ordered sections that form the complete final answer.",
    )

    @model_validator(mode="after")
    def validate_sections(self) -> "GroundedAnswerPlanV2":
        kinds = tuple(item.section_kind for item in self.sections)
        if _duplicates(kinds):
            raise ValueError("grounded_answer_section_kind_duplicate")
        return self


class ProviderResponseFingerprintV1(_StrictFrozenModel):
    version: Literal["provider-response-fingerprint.v1"]
    attempt: StrictInt = Field(ge=1, le=2)
    top_level_type: Literal[
        "object", "array", "string", "number", "boolean", "null", "invalid_json"
    ]
    top_level_keys: tuple[NonEmptyStr, ...] = Field(max_length=64)
    section_count: StrictInt = Field(ge=0)
    statement_count: StrictInt = Field(ge=0)
    response_bytes: StrictInt = Field(ge=0)
    response_sha256: Sha256Hex
    validation_error_types: tuple[NonEmptyStr, ...] = Field(max_length=64)
    validation_paths: tuple[NonEmptyStr, ...] = Field(max_length=64)
    repair: StrictBool
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_fingerprint(self) -> "ProviderResponseFingerprintV1":
        if any(
            _duplicates(values)
            for values in (
                self.top_level_keys,
                self.validation_error_types,
                self.validation_paths,
            )
        ):
            raise ValueError("provider_response_fingerprint_duplicate")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("provider_response_fingerprint_hash_mismatch")
        return self


class GroundedComposerResultV2(_StrictFrozenModel):
    version: Literal["grounded-composer-result.v2"]
    status: Literal["completed", "degraded", "denied", "failed"]
    answer: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    answer_source: AnswerSource
    provider_result_status: ProviderResultStatus
    claim_ids: tuple[NonEmptyStr, ...]
    evidence_ids: tuple[NonEmptyStr, ...]
    action_statuses: tuple[ActionStatusV1, ...]
    degradation_codes: tuple[NonEmptyStr, ...]
    render_receipt: FinalAnswerRenderReceiptV1
    provider_call_count: StrictInt = Field(ge=0, le=2)
    scope_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_result(self) -> "GroundedComposerResultV2":
        if re.search(r"[\u3400-\u9fff]", self.answer) is None:
            raise ValueError("grounded_composer_language_invalid")
        if any(
            _duplicates(values)
            for values in (
                self.claim_ids,
                self.evidence_ids,
                self.degradation_codes,
            )
        ):
            raise ValueError("grounded_composer_value_duplicate")
        if (self.answer_source == "real_provider") != (
            self.provider_result_status == "completed"
        ):
            raise ValueError("grounded_composer_answer_source_mismatch")
        if self.answer_source == "real_provider" and self.provider_call_count < 1:
            raise ValueError("grounded_composer_provider_call_required")
        if (
            self.render_receipt.answer_hash
            != sha256(self.answer.encode("utf-8")).hexdigest()
            or self.render_receipt.scope_hash != self.scope_hash
            or set(self.render_receipt.covered_claim_ids) != set(self.claim_ids)
            or set(self.render_receipt.covered_action_slot_ids)
            != {item.slot_id for item in self.action_statuses}
        ):
            raise ValueError("grounded_composer_receipt_mismatch")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("grounded_composer_hash_mismatch")
        return self


def provider_response_sha256(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def canonical_json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    raise TypeError("provider_response_json_type_invalid")


__all__ = [
    "ActionHandle",
    "AnswerSource",
    "ClaimHandle",
    "EvidenceHandle",
    "GroundedActionCandidateV2",
    "GroundedAnswerPlanV2",
    "GroundedAnswerProviderRequestV2",
    "GroundedAnswerSectionV2",
    "GroundedAnswerStatementV2",
    "GroundedClaimCandidateV2",
    "GroundedComposerResultV2",
    "GroundedEvidenceCandidateV2",
    "GroundedObjectiveCandidateV2",
    "GroundedPresentationPolicyV2",
    "GroundedSectionKind",
    "GroundedSpecialistFindingV2",
    "GroundedStatementKind",
    "ObjectiveHandle",
    "ProviderResponseFingerprintV1",
    "ProviderResultStatus",
    "canonical_json_type",
    "provider_response_sha256",
]
