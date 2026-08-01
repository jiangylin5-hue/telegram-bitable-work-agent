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
    ProviderFailureCode,
    specialist_payload_sha256,
)


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
ClaimHandle = Annotated[StrictStr, Field(pattern=r"^c[0-9]{3}$")]
EvidenceHandle = Annotated[StrictStr, Field(pattern=r"^e[0-9]{3}$")]
ActionHandle = Annotated[StrictStr, Field(pattern=r"^a[0-9]{3}$")]
ObjectiveHandle = Annotated[StrictStr, Field(pattern=r"^o[0-9]{3}$")]
FindingHandle = Annotated[StrictStr, Field(pattern=r"^f[0-9]{3}$")]
VersionHandle = Annotated[StrictStr, Field(pattern=r"^v[0-9]{3}$")]
SlotHandle = Annotated[StrictStr, Field(pattern=r"^s[0-9]{3}$")]

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
    coverage_role: Literal["user_result", "action_prerequisite"] = "user_result"


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
    source_versions: tuple[VersionHandle, ...] = Field(min_length=1, max_length=32)
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
    source_version: VersionHandle


class GroundedActionCandidateV2(_StrictFrozenModel):
    action_handle: ActionHandle
    action_kind: NonEmptyStr
    status: Literal["proposed", "denied", "deferred", "conflicted"]
    safe_summary: NonEmptyStr
    reason_code: StrictStr | None


class GroundedSpecialistFindingV2(_StrictFrozenModel):
    finding_handle: FindingHandle
    objective_handle: ObjectiveHandle
    finding_kind: Literal["tabular", "risk", "daily"]
    safe_text: NonEmptyStr
    claim_handles: tuple[ClaimHandle, ...] = Field(min_length=1, max_length=128)
    evidence_handles: tuple[EvidenceHandle, ...] = Field(min_length=1, max_length=256)

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


class GroundedRenderSlotV1(_StrictFrozenModel):
    """Backend-owned semantic and reference closure for one model text slot."""

    slot_handle: SlotHandle
    section_kind: GroundedSectionKind
    statement_kind: GroundedStatementKind
    objective_handles: tuple[ObjectiveHandle, ...] = Field(min_length=1, max_length=16)
    claim_handles: tuple[ClaimHandle, ...] = Field(max_length=128)
    evidence_handles: tuple[EvidenceHandle, ...] = Field(max_length=256)
    finding_handles: tuple[FindingHandle, ...] = Field(max_length=64)
    action_handles: tuple[ActionHandle, ...] = Field(max_length=32)
    context_claim_handles: tuple[ClaimHandle, ...] = Field(default=(), max_length=128)
    context_evidence_handles: tuple[EvidenceHandle, ...] = Field(
        default=(), max_length=256
    )
    required: StrictBool

    @model_validator(mode="after")
    def validate_slot_shape(self) -> "GroundedRenderSlotV1":
        if any(
            _duplicates(values)
            for values in (
                self.objective_handles,
                self.claim_handles,
                self.evidence_handles,
                self.finding_handles,
                self.action_handles,
                self.context_claim_handles,
                self.context_evidence_handles,
            )
        ):
            raise ValueError("grounded_render_slot_reference_duplicate")
        factual = self.statement_kind in {"fact", "analysis", "recommendation"}
        if factual and (
            not self.claim_handles
            or not self.evidence_handles
            or self.action_handles
            or self.context_claim_handles
            or self.context_evidence_handles
        ):
            raise ValueError("grounded_render_slot_fact_closure_invalid")
        if self.statement_kind == "action_status" and (
            self.section_kind != "actions"
            or not self.action_handles
            or self.claim_handles
            or self.evidence_handles
            or self.finding_handles
        ):
            raise ValueError("grounded_render_slot_action_closure_invalid")
        if self.statement_kind == "limitation" and (
            self.section_kind != "limitations"
            or self.claim_handles
            or self.evidence_handles
            or self.finding_handles
            or self.action_handles
            or self.context_claim_handles
            or self.context_evidence_handles
        ):
            raise ValueError("grounded_render_slot_limitation_closure_invalid")
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
    runtime_binding_hash: Sha256Hex
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_request(self) -> "GroundedAnswerProviderRequestV2":
        identity_groups = (
            ("o", tuple(item.objective_handle for item in self.objectives)),
            ("c", tuple(item.claim_handle for item in self.claims)),
            ("f", tuple(item.finding_handle for item in self.specialist_findings)),
            ("a", tuple(item.action_handle for item in self.actions)),
            ("e", tuple(item.evidence_handle for item in self.citations)),
        )
        if any(_duplicates(values) for _, values in identity_groups):
            raise ValueError("grounded_request_identity_duplicate")
        if any(
            values
            != tuple(f"{prefix}{index:03d}" for index in range(1, len(values) + 1))
            for prefix, values in identity_groups
        ):
            raise ValueError("grounded_request_reference_order")
        if any(
            item.source_versions != (f"v{index:03d}",)
            for index, item in enumerate(self.claims, start=1)
        ) or any(
            item.source_version != f"v{len(self.claims) + index:03d}"
            for index, item in enumerate(self.citations, start=1)
        ):
            raise ValueError("grounded_request_version_reference_order")
        objective_handles = {item.objective_handle for item in self.objectives}
        if any(
            item.objective_handle not in objective_handles
            for item in self.specialist_findings
        ):
            raise ValueError("grounded_request_finding_objective_unknown")
        claim_handles = {item.claim_handle for item in self.claims}
        evidence_handles = {item.evidence_handle for item in self.citations}
        if any(
            not set(item.claim_handles).issubset(claim_handles)
            or not set(item.evidence_handles).issubset(evidence_handles)
            for item in self.specialist_findings
        ):
            raise ValueError("grounded_request_finding_reference_unknown")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("grounded_request_hash_mismatch")
        return self


class GroundedAnswerProviderRequestV3(GroundedAnswerProviderRequestV2):
    """Private V3 request with a backend-sealed ordered render plan."""

    version: Literal["grounded-answer-provider-request.v3"]
    render_slots: tuple[GroundedRenderSlotV1, ...] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def validate_render_slots(self) -> "GroundedAnswerProviderRequestV3":
        handles = tuple(item.slot_handle for item in self.render_slots)
        if _duplicates(handles):
            raise ValueError("grounded_render_slot_identity_duplicate")
        if handles != tuple(f"s{index:03d}" for index in range(1, len(handles) + 1)):
            raise ValueError("grounded_render_slot_reference_order")

        objective_handles = {item.objective_handle for item in self.objectives}
        claims = {item.claim_handle: item for item in self.claims}
        evidence_handles = {item.evidence_handle for item in self.citations}
        finding_handles = {
            item.finding_handle: item for item in self.specialist_findings
        }
        action_handles = {item.action_handle for item in self.actions}
        covered_claims: list[str] = []
        covered_actions: list[str] = []
        covered_objectives: set[str] = set()
        for slot in self.render_slots:
            if not set(slot.objective_handles).issubset(objective_handles):
                raise ValueError("grounded_render_slot_objective_unknown")
            if not set(slot.claim_handles).issubset(claims):
                raise ValueError("grounded_render_slot_claim_unknown")
            if not set(slot.evidence_handles).issubset(evidence_handles):
                raise ValueError("grounded_render_slot_evidence_unknown")
            if not set(slot.finding_handles).issubset(finding_handles):
                raise ValueError("grounded_render_slot_finding_unknown")
            if not set(slot.action_handles).issubset(action_handles):
                raise ValueError("grounded_render_slot_action_unknown")
            if not set(slot.context_claim_handles).issubset(claims):
                raise ValueError("grounded_render_slot_context_claim_unknown")
            if not set(slot.context_evidence_handles).issubset(evidence_handles):
                raise ValueError("grounded_render_slot_context_evidence_unknown")
            if slot.context_claim_handles:
                if slot.statement_kind != "action_status":
                    raise ValueError("grounded_render_slot_context_kind_invalid")
                context_claims = tuple(
                    claims[value] for value in slot.context_claim_handles
                )
                if any(
                    item.status != "valid"
                    or not set(item.objective_handles).intersection(
                        slot.objective_handles
                    )
                    for item in context_claims
                ):
                    raise ValueError("grounded_render_slot_context_binding_invalid")
                required_context_evidence = {
                    value for item in context_claims for value in item.evidence_handles
                }
                if set(slot.context_evidence_handles) != required_context_evidence:
                    raise ValueError("grounded_render_slot_context_evidence_invalid")
            elif slot.context_evidence_handles:
                raise ValueError("grounded_render_slot_context_evidence_invalid")
            if slot.statement_kind in {"fact", "analysis", "recommendation"}:
                required_claims = set(slot.claim_handles)
                required_evidence = {
                    value
                    for handle in slot.claim_handles
                    for value in claims[handle].evidence_handles
                }
                for handle in slot.finding_handles:
                    finding = finding_handles[handle]
                    if not set(finding.claim_handles).issubset(required_claims):
                        raise ValueError("grounded_render_slot_finding_claim_mismatch")
                    required_evidence.update(finding.evidence_handles)
                if set(slot.evidence_handles) != required_evidence:
                    raise ValueError("grounded_render_slot_evidence_closure_invalid")
            covered_claims.extend(slot.claim_handles)
            covered_actions.extend(slot.action_handles)
            covered_objectives.update(slot.objective_handles)

        valid_claims = {
            item.claim_handle for item in self.claims if item.status == "valid"
        }
        if (
            len(covered_claims) != len(set(covered_claims))
            or set(covered_claims) != valid_claims
        ):
            raise ValueError("grounded_render_slot_claim_coverage_invalid")
        if (
            len(covered_actions) != len(set(covered_actions))
            or set(covered_actions) != action_handles
        ):
            raise ValueError("grounded_render_slot_action_coverage_invalid")
        if any(
            item.required and item.objective_handle not in covered_objectives
            for item in self.objectives
        ):
            raise ValueError("grounded_render_slot_objective_coverage_invalid")
        return self


class GroundedRenderSlotProviderRequestV1(_StrictFrozenModel):
    """Minimal provider payload for exactly one backend-sealed render slot."""

    version: Literal["grounded-render-slot-provider-request.v1"]
    language: Literal["zh-CN"]
    slot: GroundedRenderSlotV1
    objectives: tuple[GroundedObjectiveCandidateV2, ...] = Field(max_length=16)
    claims: tuple[GroundedClaimCandidateV2, ...] = Field(max_length=128)
    specialist_findings: tuple[GroundedSpecialistFindingV2, ...] = Field(max_length=64)
    actions: tuple[GroundedActionCandidateV2, ...] = Field(max_length=32)
    citations: tuple[GroundedEvidenceCandidateV2, ...] = Field(max_length=256)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_isolated_closure(self) -> "GroundedRenderSlotProviderRequestV1":
        expected_claims = tuple(
            dict.fromkeys((*self.slot.claim_handles, *self.slot.context_claim_handles))
        )
        expected_evidence = tuple(
            dict.fromkeys(
                (*self.slot.evidence_handles, *self.slot.context_evidence_handles)
            )
        )
        actual = (
            tuple(item.objective_handle for item in self.objectives),
            tuple(item.claim_handle for item in self.claims),
            tuple(item.finding_handle for item in self.specialist_findings),
            tuple(item.action_handle for item in self.actions),
            tuple(item.evidence_handle for item in self.citations),
        )
        expected = (
            self.slot.objective_handles,
            expected_claims,
            self.slot.finding_handles,
            self.slot.action_handles,
            expected_evidence,
        )
        if actual != expected:
            raise ValueError("grounded_render_slot_provider_closure_mismatch")
        computed = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != computed:
            raise ValueError("grounded_render_slot_provider_hash_mismatch")
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
        description="Exact request-local claims supporting this statement.",
    )
    evidence_handles: tuple[EvidenceHandle, ...] = Field(
        max_length=32,
        description="Exact evidence closure for the referenced claims.",
    )
    finding_handles: tuple[FindingHandle, ...] = Field(
        default=(),
        max_length=16,
        description="Exact typed findings supporting analysis or synthesis.",
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
                self.finding_handles,
                self.action_handles,
            )
        ):
            raise ValueError("grounded_statement_reference_duplicate")
        if self.statement_kind in {"fact", "analysis", "recommendation"}:
            partial_claim_closure = bool(self.claim_handles) != bool(
                self.evidence_handles
            )
            if partial_claim_closure or (
                not self.claim_handles and not self.finding_handles
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


class GroundedRenderSlotTextV1(_StrictFrozenModel):
    slot_handle: SlotHandle = Field(
        description="Exact ordered request-local render slot being filled."
    )
    text: Annotated[
        StrictStr,
        Field(
            min_length=1,
            max_length=1600,
            description="Chinese user-visible prose authored by the model for this slot.",
        ),
    ]


class GroundedAnswerPlanV3(_StrictFrozenModel):
    version: Literal["grounded-answer-plan.v3"] = Field(
        default="grounded-answer-plan.v3",
        description="Exact version of the sealed render-slot response contract.",
    )
    slot_outputs: tuple[GroundedRenderSlotTextV1, ...] = Field(
        min_length=1,
        max_length=7,
        description="Text-only outputs in the exact request slot order.",
    )


class ProviderResponseFingerprintV1(_StrictFrozenModel):
    version: Literal["provider-response-fingerprint.v1"]
    slot_handle: SlotHandle | None = None
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
            self.model_dump(mode="json", exclude={"content_hash"}, exclude_none=True)
        )
        if self.content_hash != expected:
            raise ValueError("provider_response_fingerprint_hash_mismatch")
        return self


class GroundedSlotProviderObservationV1(_StrictFrozenModel):
    version: Literal["grounded-slot-provider-observation.v1"]
    slot_handle: SlotHandle
    status: Literal["completed", "failed"]
    attempt_count: StrictInt = Field(ge=0, le=2)
    latency_ms: StrictInt = Field(ge=0)
    failure_code: ProviderFailureCode | None
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_observation(self) -> "GroundedSlotProviderObservationV1":
        if (self.status == "completed") != (self.failure_code is None):
            raise ValueError("grounded_slot_provider_status_invalid")
        expected = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("grounded_slot_provider_hash_mismatch")
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
    provider_call_count: StrictInt = Field(ge=0, le=6)
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
    "GroundedAnswerPlanV3",
    "GroundedAnswerProviderRequestV2",
    "GroundedAnswerProviderRequestV3",
    "GroundedAnswerSectionV2",
    "GroundedAnswerStatementV2",
    "GroundedClaimCandidateV2",
    "GroundedComposerResultV2",
    "GroundedEvidenceCandidateV2",
    "GroundedObjectiveCandidateV2",
    "GroundedPresentationPolicyV2",
    "GroundedRenderSlotTextV1",
    "GroundedRenderSlotProviderRequestV1",
    "GroundedRenderSlotV1",
    "GroundedSectionKind",
    "GroundedSpecialistFindingV2",
    "GroundedSlotProviderObservationV1",
    "GroundedStatementKind",
    "ObjectiveHandle",
    "ProviderResponseFingerprintV1",
    "ProviderResultStatus",
    "SlotHandle",
    "canonical_json_type",
    "provider_response_sha256",
]
