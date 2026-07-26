from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import math
import re
from typing import Final, Literal, Protocol, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.runtime.stage08_context_contracts import ContextIntent


AssistantRequestedAction: TypeAlias = Literal["read_only", "draft_update"]
AssistantSkillSelectionMode: TypeAlias = Literal["explicit", "auto"]
AnalysisAction: TypeAlias = Literal[
    "read_only",
    "draft_update",
    "general_advice",
    "deny",
]
AssistantTerminalStatus: TypeAlias = Literal[
    "completed",
    "draft_pending",
    "degraded",
    "denied",
    "failed",
    "cancelled",
    "timed_out",
]
CollaborationStatus: TypeAlias = Literal[
    "queued",
    "planning",
    "reading",
    "analysing",
    "policy_check",
    "completed",
    "draft_pending",
    "degraded",
    "denied",
    "failed",
    "cancelled",
    "timed_out",
]
AssistantCitationLabel: TypeAlias = Literal[
    "business_data",
    "confirmed_memory",
    "group_context",
    "retrieved_material",
    "analysis_from_current_material",
    "general_advice",
]
CollaborationDegradationCode: TypeAlias = Literal[
    "context_unavailable",
    "retrieval_unavailable",
    "compression_unavailable",
    "analysis_unavailable",
    "no_evidence",
    "policy_denied",
    "cancelled",
    "timed_out",
    "internal_failure",
]
PrivateMaterialKind: TypeAlias = Literal[
    "composite_context",
    "retrieval_evidence",
    "general_advice",
    "compressed_context",
    "analysis_material",
]
CollaborationReadBranch: TypeAlias = Literal[
    "composite_context",
    "retrieval",
    "general_advice",
]
CollaborationReadStatus: TypeAlias = Literal[
    "available",
    "degraded",
    "unavailable",
]

_PRIVATE_ISSUER: Final[object] = object()
_PRIVATE_SEAL: Final[object] = object()
_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "completed",
        "draft_pending",
        "degraded",
        "denied",
        "failed",
        "cancelled",
        "timed_out",
    }
)
_NONTERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {"queued", "planning", "reading", "analysing", "policy_check"}
)
_ALL_STATUSES: Final[frozenset[str]] = _TERMINAL_STATUSES | _NONTERMINAL_STATUSES
_UUID_FRAGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])"
)
_SAFE_TRACE_HASH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:stage08:collaboration:)?[0-9a-f]{32,64}"
)
_SAFE_SUMMARY_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"[a-z][a-z0-9_.]{0,119}"
)
_SENSITIVE_PRIVATE_KEYS: Final[frozenset[str]] = frozenset(
    {"prompt", "response", "api_key", "token", "raw_text"}
)
_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    hide_input_in_errors=True,
    arbitrary_types_allowed=True,
)


@dataclass(frozen=True, slots=True)
class _CommandSnapshot:
    seal: object
    workspace_id: UUID
    employee_id: UUID
    actor_user_id: str
    intent: ContextIntent
    query: str
    requested_action: AssistantRequestedAction
    target_record_id: UUID | None
    idempotency_key: str
    skill_profile: _ResolvedAssistantSkillProfile | None


@dataclass(frozen=True, slots=True)
class _ResolvedAssistantSkillProfile:
    manifest_version: str
    primary_skill_id: str
    source_skill: str
    selection_mode: AssistantSkillSelectionMode
    supporting_skill_ids: tuple[str, ...]
    allowed_intents: tuple[ContextIntent, ...]
    allowed_provider_actions: tuple[AnalysisAction, ...]
    manifest_allowed_actions: tuple[str, ...]
    output_contract: str
    confirmation_policy: str
    safe_label: str


@dataclass(frozen=True, slots=True)
class _MaterialSnapshot:
    seal: object
    kind: PrivateMaterialKind
    payload: object


@dataclass(frozen=True, slots=True)
class _ProviderInputSnapshot:
    seal: object
    material: _Stage08PrivateMaterial


@dataclass(frozen=True, slots=True)
class _DraftIntentSnapshot:
    seal: object
    field_key: str
    value: object


@dataclass(frozen=True, slots=True)
class _SafeExecutionContextSnapshot:
    seal: object
    mode: Literal["stage08_e3_safe"]
    trace_hash: str


@dataclass(frozen=True, slots=True)
class _CompressedDigestSnapshot:
    seal: object
    text: str


@dataclass(frozen=True, slots=True)
class _StateSnapshot:
    seal: object
    command: AssistantQueryCommand
    budget: CollaborationBudget
    status: CollaborationStatus
    read_outcomes: tuple[_Stage08ReadOutcome, ...]
    compressed_digest: _Stage08CompressedDigest | None
    analysis_decision: AnalysisDecision | None
    policy_draft_allowed: bool
    degradation_codes: tuple[CollaborationDegradationCode, ...]
    safe_view: AssistantQuerySafeView | None


@dataclass(frozen=True, slots=True)
class _ReadOutcomeSnapshot:
    seal: object
    branch: CollaborationReadBranch
    status: CollaborationReadStatus
    reason_code: str
    material: _Stage08PrivateMaterial | None


class _OpaqueCarrier:
    __slots__ = ()
    _error_code = "collaboration_private_carrier_unavailable"
    _repr_name = "Stage08PrivateCarrier"

    def __new__(cls, issuer: object = None, snapshot: object = None):
        if issuer is not _PRIVATE_ISSUER:
            raise TypeError(cls._error_code)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(self, issuer: object = None, snapshot: object = None) -> None:
        del issuer, snapshot

    def __getattribute__(self, name: str):
        if name == "__class__":
            return type(self)
        if name in {"__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError(type(self)._error_code)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError(type(self)._error_code)

    def __repr__(self) -> str:
        return f"<{type(self)._repr_name} opaque>"

    def __copy__(self):
        return self

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError(type(self)._error_code)


class AssistantQueryCommand(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "collaboration_command_unavailable"
    _repr_name = "AssistantQueryCommand"


class _Stage08PrivateMaterial(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "private_material_unavailable"
    _repr_name = "Stage08PrivateMaterial"


class _Stage08ProviderInput(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "provider_input_unavailable"
    _repr_name = "Stage08ProviderInput"


class _Stage08ReadOutcome(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "read_outcome_unavailable"
    _repr_name = "Stage08ReadOutcome"


class _Stage08DraftIntent(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "draft_intent_unavailable"
    _repr_name = "Stage08DraftIntent"


class Stage08SafeExecutionContext(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "stage08_safe_execution_context_unavailable"
    _repr_name = "Stage08SafeExecutionContext"


class _Stage08CompressedDigest(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "compressed_digest_unavailable"
    _repr_name = "Stage08CompressedDigest"


class Stage08CollaborationState(_OpaqueCarrier):
    __slots__ = ("_sealed_snapshot",)
    _error_code = "collaboration_state_unavailable"
    _repr_name = "Stage08CollaborationState"


class CollaborationBudget(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    max_graph_depth: Literal[3] = 3
    max_parallel_reads: Literal[3] = 3
    max_retrieval_chunks: Literal[12] = 12
    max_wall_time_ms: Literal[30_000] = 30_000
    max_provider_time_ms: Literal[20_000] = 20_000
    max_retries: Literal[2] = 2


class AnalysisDecision(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    answer: StrictStr = Field(min_length=1, max_length=2000)
    citation_ordinals: tuple[StrictInt, ...] = Field(max_length=12)
    action: AnalysisAction
    draft_intent: _Stage08DraftIntent | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> "AnalysisDecision":
        if _UUID_FRAGMENT_RE.search(self.answer):
            raise ValueError("analysis_answer_private_identifier_forbidden")
        ordinals = self.citation_ordinals
        if any(ordinal < 1 or ordinal > 12 for ordinal in ordinals):
            raise ValueError("analysis_citation_ordinal_invalid")
        if tuple(sorted(set(ordinals))) != ordinals:
            raise ValueError("analysis_citation_ordinals_invalid")
        if self.action == "draft_update":
            _draft_intent_snapshot(self.draft_intent)
        elif self.draft_intent is not None:
            raise ValueError("analysis_draft_intent_forbidden")
        return self


class CompressionOutcome(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    status: Literal["available", "unavailable"]
    reason_code: Literal["none", "compressor_unavailable", "invalid_input"]
    digest: _Stage08CompressedDigest | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "CompressionOutcome":
        if self.status == "available":
            _compressed_digest_snapshot(self.digest)
            if self.reason_code != "none":
                raise ValueError("compression_outcome_invalid")
        elif self.digest is not None or self.reason_code == "none":
            raise ValueError("compression_outcome_invalid")
        return self


class AnalysisProviderOutcome(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    status: Literal["available", "unavailable"]
    reason_code: Literal["none", "analysis_provider_unavailable", "invalid_input"]
    decision: AnalysisDecision | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "AnalysisProviderOutcome":
        if self.status == "available":
            if self.decision is None or self.reason_code != "none":
                raise ValueError("analysis_provider_outcome_invalid")
            validate_analysis_decision(self.decision)
        elif self.decision is not None or self.reason_code == "none":
            raise ValueError("analysis_provider_outcome_invalid")
        return self


class AssistantQuerySafeCitation(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    ordinal: StrictInt = Field(ge=1, le=12)
    label: AssistantCitationLabel


class AssistantSkillSafeSummary(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    skill_id: StrictStr = Field(min_length=1, max_length=120)
    label: StrictStr = Field(min_length=1, max_length=120)
    manifest_version: StrictStr = Field(min_length=1, max_length=120)
    selection_mode: AssistantSkillSelectionMode


class AssistantQuerySafeView(BaseModel):
    model_config = _STRICT_FROZEN_CONFIG

    status: AssistantTerminalStatus
    answer: StrictStr | None = Field(default=None, max_length=2000)
    citations: tuple[AssistantQuerySafeCitation, ...] = Field(max_length=12)
    degradation_codes: tuple[CollaborationDegradationCode, ...] = Field(max_length=12)
    draft_id: UUID | None = None
    skill: AssistantSkillSafeSummary | None = None

    @model_validator(mode="after")
    def validate_safe_view(self) -> "AssistantQuerySafeView":
        if self.answer is not None and _UUID_FRAGMENT_RE.search(self.answer):
            raise ValueError("assistant_safe_answer_private_identifier_forbidden")
        ordinals = tuple(citation.ordinal for citation in self.citations)
        if tuple(sorted(set(ordinals))) != ordinals:
            raise ValueError("assistant_safe_citations_invalid")
        if len(set(self.degradation_codes)) != len(self.degradation_codes):
            raise ValueError("assistant_safe_degradation_codes_invalid")
        if self.status == "draft_pending":
            if self.draft_id is None:
                raise ValueError("assistant_safe_draft_reference_required")
        elif self.draft_id is not None:
            raise ValueError("assistant_safe_draft_reference_forbidden")
        if self.status == "degraded" and (
            self.answer is not None
            or self.citations
            or self.degradation_codes != ("analysis_unavailable",)
            or self.draft_id is not None
        ):
            raise ValueError("assistant_safe_degraded_shape_invalid")
        return self


class ContextCompressor(Protocol):
    def compress(
        self,
        material: object,
        *,
        budget: CollaborationBudget,
    ) -> CompressionOutcome: ...


class AnalysisProvider(Protocol):
    def analyse(
        self,
        material: object,
        command: object,
        *,
        budget: CollaborationBudget,
    ) -> AnalysisProviderOutcome: ...


class UnavailableContextCompressor:
    __slots__ = ()

    def compress(
        self,
        material: object,
        *,
        budget: CollaborationBudget,
    ) -> CompressionOutcome:
        _provider_input_snapshot(material)
        validate_collaboration_budget(budget)
        return CompressionOutcome(
            status="unavailable",
            reason_code="compressor_unavailable",
            digest=None,
        )


class UnavailableAnalysisProvider:
    __slots__ = ()

    def analyse(
        self,
        material: object,
        command: object,
        *,
        budget: CollaborationBudget,
    ) -> AnalysisProviderOutcome:
        _provider_input_snapshot(material)
        _command_snapshot(command)
        validate_collaboration_budget(budget)
        return AnalysisProviderOutcome(
            status="unavailable",
            reason_code="analysis_provider_unavailable",
            decision=None,
        )


class Stage08CollaborationContractFactory:
    __slots__ = ()

    @staticmethod
    def command(
        *,
        workspace_id: UUID,
        employee_id: UUID,
        actor_user_id: str,
        intent: ContextIntent,
        query: str,
        requested_action: AssistantRequestedAction,
        target_record_id: UUID | None,
        idempotency_key: str,
        skill_profile: _ResolvedAssistantSkillProfile | None = None,
    ) -> AssistantQueryCommand:
        if type(workspace_id) is not UUID or type(employee_id) is not UUID:
            raise ValueError("collaboration_command_identifier_invalid")
        if target_record_id is not None and type(target_record_id) is not UUID:
            raise ValueError("collaboration_command_identifier_invalid")
        if type(actor_user_id) is not str or not 1 <= len(actor_user_id) <= 128:
            raise ValueError("collaboration_command_actor_invalid")
        if intent not in {"business_fact", "memory_lookup", "mixed", "general_advice"}:
            raise ValueError("collaboration_command_intent_invalid")
        if type(query) is not str or not query.strip() or len(query) > 600:
            raise ValueError("collaboration_command_query_invalid")
        if requested_action not in {"read_only", "draft_update"}:
            raise ValueError("collaboration_command_action_invalid")
        if requested_action == "draft_update" and target_record_id is None:
            raise ValueError("collaboration_command_target_required")
        if type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 128:
            raise ValueError("collaboration_command_idempotency_invalid")
        if skill_profile is not None and type(skill_profile) is not _ResolvedAssistantSkillProfile:
            raise ValueError("collaboration_command_skill_profile_invalid")
        snapshot = _CommandSnapshot(
            seal=_PRIVATE_SEAL,
            workspace_id=workspace_id,
            employee_id=employee_id,
            actor_user_id=actor_user_id,
            intent=intent,
            query=query,
            requested_action=requested_action,
            target_record_id=target_record_id,
            idempotency_key=idempotency_key,
            skill_profile=skill_profile,
        )
        return AssistantQueryCommand(_PRIVATE_ISSUER, snapshot)

    @staticmethod
    def resolved_skill_profile(
        *,
        manifest_version: str,
        primary_skill_id: str,
        source_skill: str,
        selection_mode: AssistantSkillSelectionMode,
        supporting_skill_ids: tuple[str, ...],
        allowed_intents: tuple[ContextIntent, ...],
        allowed_provider_actions: tuple[AnalysisAction, ...],
        manifest_allowed_actions: tuple[str, ...],
        output_contract: str,
        confirmation_policy: str,
        safe_label: str,
    ) -> _ResolvedAssistantSkillProfile:
        tokens = (
            manifest_version,
            primary_skill_id,
            source_skill,
            output_contract,
            confirmation_policy,
            safe_label,
            *supporting_skill_ids,
            *manifest_allowed_actions,
        )
        if (
            any(type(value) is not str or not 1 <= len(value) <= 120 for value in tokens)
            or selection_mode not in {"explicit", "auto"}
            or not supporting_skill_ids
            or len(set(supporting_skill_ids)) != len(supporting_skill_ids)
            or not allowed_intents
            or any(value not in {"business_fact", "memory_lookup", "mixed", "general_advice"} for value in allowed_intents)
            or not allowed_provider_actions
            or any(value not in {"read_only", "draft_update", "general_advice", "deny"} for value in allowed_provider_actions)
            or not manifest_allowed_actions
            or len(set(manifest_allowed_actions)) != len(manifest_allowed_actions)
        ):
            raise ValueError("collaboration_skill_profile_invalid")
        return _ResolvedAssistantSkillProfile(
            manifest_version=manifest_version,
            primary_skill_id=primary_skill_id,
            source_skill=source_skill,
            selection_mode=selection_mode,
            supporting_skill_ids=supporting_skill_ids,
            allowed_intents=allowed_intents,
            allowed_provider_actions=allowed_provider_actions,
            manifest_allowed_actions=manifest_allowed_actions,
            output_contract=output_contract,
            confirmation_policy=confirmation_policy,
            safe_label=safe_label,
        )

    @staticmethod
    def safe_skill_summary(command: object) -> AssistantSkillSafeSummary | None:
        profile = _command_snapshot(command).skill_profile
        if profile is None:
            return None
        return AssistantSkillSafeSummary(
            skill_id=profile.primary_skill_id,
            label=profile.safe_label,
            manifest_version=profile.manifest_version,
            selection_mode=profile.selection_mode,
        )

    @staticmethod
    def private_material(
        payload: object,
        *,
        kind: PrivateMaterialKind = "analysis_material",
    ) -> _Stage08PrivateMaterial:
        if kind not in {
            "composite_context",
            "retrieval_evidence",
            "general_advice",
            "compressed_context",
            "analysis_material",
        }:
            raise ValueError("private_material_kind_invalid")
        return _Stage08PrivateMaterial(
            _PRIVATE_ISSUER,
            _MaterialSnapshot(seal=_PRIVATE_SEAL, kind=kind, payload=payload),
        )

    @staticmethod
    def provider_input(material: object) -> _Stage08ProviderInput:
        _material_snapshot(material)
        return _Stage08ProviderInput(
            _PRIVATE_ISSUER,
            _ProviderInputSnapshot(seal=_PRIVATE_SEAL, material=material),
        )

    @staticmethod
    def draft_intent(*, field_key: str, value: object) -> _Stage08DraftIntent:
        if (
            type(field_key) is not str
            or not field_key.strip()
            or field_key != field_key.strip()
            or field_key.strip().casefold() in _SENSITIVE_PRIVATE_KEYS
        ):
            raise ValueError("draft_intent_field_key_invalid")
        if not _is_json_safe_value(value):
            raise ValueError("draft_intent_value_invalid")
        return _Stage08DraftIntent(
            _PRIVATE_ISSUER,
            _DraftIntentSnapshot(
                seal=_PRIVATE_SEAL,
                field_key=field_key,
                value=deepcopy(value),
            ),
        )

    @staticmethod
    def safe_execution_context(
        *,
        trace_hash: str,
        mode: str = "stage08_e3_safe",
    ) -> Stage08SafeExecutionContext:
        if mode != "stage08_e3_safe":
            raise ValueError("stage08_safe_execution_mode_invalid")
        if (
            type(trace_hash) is not str
            or _SAFE_TRACE_HASH_RE.fullmatch(trace_hash) is None
        ):
            raise ValueError("stage08_safe_execution_trace_invalid")
        return Stage08SafeExecutionContext(
            _PRIVATE_ISSUER,
            _SafeExecutionContextSnapshot(
                seal=_PRIVATE_SEAL,
                mode="stage08_e3_safe",
                trace_hash=trace_hash,
            ),
        )

    @staticmethod
    def compressed_digest(*, text: str) -> _Stage08CompressedDigest:
        if type(text) is not str or not text.strip() or len(text) > 12_000:
            raise ValueError("compressed_digest_invalid")
        return _Stage08CompressedDigest(
            _PRIVATE_ISSUER,
            _CompressedDigestSnapshot(seal=_PRIVATE_SEAL, text=text),
        )

    @staticmethod
    def read_outcome(
        *,
        branch: CollaborationReadBranch,
        status: CollaborationReadStatus,
        reason_code: str,
        material: object | None,
    ) -> _Stage08ReadOutcome:
        if branch not in {"composite_context", "retrieval", "general_advice"}:
            raise ValueError("collaboration_read_branch_invalid")
        if status not in {"available", "degraded", "unavailable"}:
            raise ValueError("collaboration_read_status_invalid")
        if (
            type(reason_code) is not str
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", reason_code)
        ):
            raise ValueError("collaboration_read_reason_invalid")
        if status == "available":
            _material_snapshot(material)
            if reason_code != "none":
                raise ValueError("collaboration_read_outcome_invalid")
        elif material is not None:
            _material_snapshot(material)
        return _Stage08ReadOutcome(
            _PRIVATE_ISSUER,
            _ReadOutcomeSnapshot(
                seal=_PRIVATE_SEAL,
                branch=branch,
                status=status,
                reason_code=reason_code,
                material=material,
            ),
        )

    @staticmethod
    def initial_state(command: object) -> Stage08CollaborationState:
        _command_snapshot(command)
        return _state(
            _StateSnapshot(
                seal=_PRIVATE_SEAL,
                command=command,
                budget=CollaborationBudget(),
                status="queued",
                read_outcomes=(),
                compressed_digest=None,
                analysis_decision=None,
                policy_draft_allowed=False,
                degradation_codes=(),
                safe_view=None,
            )
        )

    @staticmethod
    def transition(
        state: object,
        *,
        status: CollaborationStatus,
    ) -> Stage08CollaborationState:
        snapshot = _state_snapshot(state)
        if status not in _ALL_STATUSES:
            raise ValueError("collaboration_status_invalid")
        if snapshot.status in _TERMINAL_STATUSES and status != snapshot.status:
            raise ValueError("collaboration_terminal_transition_invalid")
        return _state(replace(snapshot, status=status))

    @staticmethod
    def record_read_outcome(
        state: object,
        outcome: object,
    ) -> Stage08CollaborationState:
        snapshot = _state_snapshot(state)
        read = _read_outcome_snapshot(outcome)
        existing = tuple(
            _read_outcome_snapshot(item).branch for item in snapshot.read_outcomes
        )
        if read.branch in existing:
            raise ValueError("collaboration_read_branch_duplicate")
        if len(snapshot.read_outcomes) >= 3:
            raise ValueError("collaboration_parallel_read_budget_exceeded")
        ordered = tuple(
            sorted(
                (*snapshot.read_outcomes, outcome),
                key=lambda item: {
                    "composite_context": 0,
                    "retrieval": 1,
                    "general_advice": 2,
                }[_read_outcome_snapshot(item).branch],
            )
        )
        return _state(replace(snapshot, read_outcomes=ordered))

    @staticmethod
    def read_outcome_count(state: object) -> int:
        return len(_state_snapshot(state).read_outcomes)

    @staticmethod
    def record_compressed_digest(
        state: object,
        digest: object,
    ) -> Stage08CollaborationState:
        snapshot = _state_snapshot(state)
        _compressed_digest_snapshot(digest)
        return _state(replace(snapshot, compressed_digest=digest))

    @staticmethod
    def record_analysis(
        state: object,
        decision: object,
    ) -> Stage08CollaborationState:
        snapshot = _state_snapshot(state)
        validated = validate_analysis_decision(decision)
        return _state(
            replace(
                snapshot,
                analysis_decision=validated,
                policy_draft_allowed=False,
            )
        )

    @staticmethod
    def analysis_decision(state: object) -> AnalysisDecision | None:
        decision = _state_snapshot(state).analysis_decision
        return validate_analysis_decision(decision) if decision is not None else None

    @staticmethod
    def record_policy_result(
        state: object,
        *,
        draft_allowed: bool,
    ) -> Stage08CollaborationState:
        snapshot = _state_snapshot(state)
        if type(draft_allowed) is not bool:
            raise ValueError("collaboration_policy_result_invalid")
        if draft_allowed:
            command = _command_snapshot(snapshot.command)
            decision = snapshot.analysis_decision
            if (
                command.requested_action != "draft_update"
                or decision is None
                or validate_analysis_decision(decision).action != "draft_update"
            ):
                raise ValueError("collaboration_policy_result_invalid")
        return _state(replace(snapshot, policy_draft_allowed=draft_allowed))

    @staticmethod
    def policy_allows_draft(state: object) -> bool:
        return _state_snapshot(state).policy_draft_allowed

    @staticmethod
    def record_safe_view(
        state: object,
        view: object,
    ) -> Stage08CollaborationState:
        snapshot = _state_snapshot(state)
        validated = validate_assistant_query_safe_view(view)
        return _state(replace(snapshot, safe_view=validated))

    @staticmethod
    def terminal_status(state: object) -> AssistantTerminalStatus | None:
        status = _state_snapshot(state).status
        return status if status in _TERMINAL_STATUSES else None  # type: ignore[return-value]

    @staticmethod
    def requested_action(state: object) -> AssistantRequestedAction:
        snapshot = _state_snapshot(state)
        return _command_snapshot(snapshot.command).requested_action


def validate_collaboration_budget(value: object) -> CollaborationBudget:
    payload = _exact_model_payload(
        value,
        CollaborationBudget,
        error_code="collaboration_budget_shape_invalid",
    )
    return CollaborationBudget.model_validate(payload)


def validate_analysis_decision(value: object) -> AnalysisDecision:
    payload = _exact_model_payload(
        value,
        AnalysisDecision,
        error_code="analysis_decision_shape_invalid",
    )
    draft_intent = payload.get("draft_intent")
    if draft_intent is not None:
        _draft_intent_snapshot(draft_intent)
    return AnalysisDecision.model_validate(payload)


def validate_assistant_query_safe_view(value: object) -> AssistantQuerySafeView:
    payload = _exact_model_payload(
        value,
        AssistantQuerySafeView,
        error_code="assistant_safe_view_shape_invalid",
    )
    raw_citations = payload.get("citations")
    if type(raw_citations) is not tuple:
        raise ValueError("assistant_safe_view_shape_invalid")
    payload["citations"] = tuple(
        AssistantQuerySafeCitation.model_validate(
            _exact_model_payload(
                citation,
                AssistantQuerySafeCitation,
                error_code="assistant_safe_view_shape_invalid",
            )
        )
        for citation in raw_citations
    )
    return AssistantQuerySafeView.model_validate(payload)


def _exact_model_payload(
    value: object,
    model_type: type[BaseModel],
    *,
    error_code: str,
) -> dict[str, object]:
    if type(value) is not model_type:
        raise ValueError(error_code)
    fields = set(model_type.model_fields)
    values = object.__getattribute__(value, "__dict__")
    if set(values) != fields:
        raise ValueError(error_code)
    return {field: values[field] for field in fields}


def _private_snapshot(
    value: object,
    carrier_type: type[_OpaqueCarrier],
    snapshot_type: type[object],
    error_code: str,
) -> object:
    if type(value) is not carrier_type:
        raise TypeError(error_code)
    try:
        snapshot = object.__getattribute__(value, "_sealed_snapshot")
    except (AttributeError, TypeError):
        raise TypeError(error_code) from None
    if type(snapshot) is not snapshot_type or getattr(snapshot, "seal", None) is not _PRIVATE_SEAL:
        raise TypeError(error_code)
    return snapshot


def _command_snapshot(value: object) -> _CommandSnapshot:
    return _private_snapshot(
        value,
        AssistantQueryCommand,
        _CommandSnapshot,
        "collaboration_command_unavailable",
    )  # type: ignore[return-value]


def _material_snapshot(value: object) -> _MaterialSnapshot:
    return _private_snapshot(
        value,
        _Stage08PrivateMaterial,
        _MaterialSnapshot,
        "private_material_unavailable",
    )  # type: ignore[return-value]


def _provider_input_snapshot(value: object) -> _ProviderInputSnapshot:
    snapshot = _private_snapshot(
        value,
        _Stage08ProviderInput,
        _ProviderInputSnapshot,
        "provider_input_unavailable",
    )
    _material_snapshot(snapshot.material)  # type: ignore[attr-defined]
    return snapshot  # type: ignore[return-value]


def _read_outcome_snapshot(value: object) -> _ReadOutcomeSnapshot:
    snapshot = _private_snapshot(
        value,
        _Stage08ReadOutcome,
        _ReadOutcomeSnapshot,
        "read_outcome_unavailable",
    )
    if snapshot.material is not None:  # type: ignore[attr-defined]
        _material_snapshot(snapshot.material)  # type: ignore[attr-defined]
    return snapshot  # type: ignore[return-value]


def _draft_intent_snapshot(value: object) -> _DraftIntentSnapshot:
    snapshot = _private_snapshot(
        value,
        _Stage08DraftIntent,
        _DraftIntentSnapshot,
        "draft_intent_unavailable",
    )
    if (
        type(snapshot.field_key) is not str  # type: ignore[attr-defined]
        or not snapshot.field_key.strip()  # type: ignore[attr-defined]
        or snapshot.field_key != snapshot.field_key.strip()  # type: ignore[attr-defined]
        or snapshot.field_key.strip().casefold() in _SENSITIVE_PRIVATE_KEYS  # type: ignore[attr-defined]
        or not _is_json_safe_value(snapshot.value)  # type: ignore[attr-defined]
    ):
        raise TypeError("draft_intent_unavailable")
    return snapshot  # type: ignore[return-value]


def _safe_execution_context_snapshot(
    value: object,
) -> _SafeExecutionContextSnapshot:
    snapshot = _private_snapshot(
        value,
        Stage08SafeExecutionContext,
        _SafeExecutionContextSnapshot,
        "stage08_safe_execution_context_unavailable",
    )
    if (
        snapshot.mode != "stage08_e3_safe"  # type: ignore[attr-defined]
        or type(snapshot.trace_hash) is not str  # type: ignore[attr-defined]
        or _SAFE_TRACE_HASH_RE.fullmatch(snapshot.trace_hash) is None  # type: ignore[attr-defined]
    ):
        raise TypeError("stage08_safe_execution_context_unavailable")
    return snapshot  # type: ignore[return-value]


def _stage08_safe_execution_summary(
    safe_context: object,
    *,
    graph: str,
    status: str,
    action: str,
    counts: dict[str, int],
    code: str | None,
    latency_ms: int,
    ticket_present: bool,
    draft_present: bool,
) -> dict[str, object]:
    snapshot = _safe_execution_context_snapshot(safe_context)
    tokens = (graph, status, action)
    if any(
        type(token) is not str or _SAFE_SUMMARY_TOKEN_RE.fullmatch(token) is None
        for token in tokens
    ):
        raise ValueError("stage08_safe_execution_summary_invalid")
    if code is not None and (
        type(code) is not str or _SAFE_SUMMARY_TOKEN_RE.fullmatch(code) is None
    ):
        raise ValueError("stage08_safe_execution_summary_invalid")
    if type(counts) is not dict or any(
        type(key) is not str
        or re.fullmatch(r"[a-z][a-z0-9_]{0,79}", key) is None
        or (not key.endswith("_count") and key != "confirmation_required")
        or type(count) is not int
        or count < 0
        for key, count in counts.items()
    ):
        raise ValueError("stage08_safe_execution_summary_invalid")
    if (
        type(latency_ms) is not int
        or latency_ms < 0
        or type(ticket_present) is not bool
        or type(draft_present) is not bool
    ):
        raise ValueError("stage08_safe_execution_summary_invalid")
    return {
        "graph": graph,
        "status": status,
        "action": action,
        "counts": dict(sorted(counts.items())),
        "code": code,
        "trace_hash": snapshot.trace_hash,
        "latency_ms": latency_ms,
        "ticket_present": ticket_present,
        "draft_present": draft_present,
    }


def _is_json_safe_value(value: object) -> bool:
    if value is None or type(value) in {str, int, bool}:
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_is_json_safe_value(item) for item in value)
    if type(value) is dict:
        return all(
            type(key) is str
            and key.strip().casefold() not in _SENSITIVE_PRIVATE_KEYS
            and _is_json_safe_value(item)
            for key, item in value.items()
        )
    return False


def _compressed_digest_snapshot(value: object) -> _CompressedDigestSnapshot:
    return _private_snapshot(
        value,
        _Stage08CompressedDigest,
        _CompressedDigestSnapshot,
        "compressed_digest_unavailable",
    )  # type: ignore[return-value]


def _state_snapshot(value: object) -> _StateSnapshot:
    snapshot = _private_snapshot(
        value,
        Stage08CollaborationState,
        _StateSnapshot,
        "collaboration_state_unavailable",
    )
    _command_snapshot(snapshot.command)  # type: ignore[attr-defined]
    validate_collaboration_budget(snapshot.budget)  # type: ignore[attr-defined]
    if snapshot.status not in _ALL_STATUSES:  # type: ignore[attr-defined]
        raise TypeError("collaboration_state_unavailable")
    outcomes = snapshot.read_outcomes  # type: ignore[attr-defined]
    if type(outcomes) is not tuple or len(outcomes) > 3:
        raise TypeError("collaboration_state_unavailable")
    branches = tuple(_read_outcome_snapshot(item).branch for item in outcomes)
    if len(set(branches)) != len(branches):
        raise TypeError("collaboration_state_unavailable")
    if snapshot.compressed_digest is not None:  # type: ignore[attr-defined]
        _compressed_digest_snapshot(snapshot.compressed_digest)  # type: ignore[attr-defined]
    if snapshot.analysis_decision is not None:  # type: ignore[attr-defined]
        validate_analysis_decision(snapshot.analysis_decision)  # type: ignore[attr-defined]
    if type(snapshot.policy_draft_allowed) is not bool:  # type: ignore[attr-defined]
        raise TypeError("collaboration_state_unavailable")
    if snapshot.safe_view is not None:  # type: ignore[attr-defined]
        validate_assistant_query_safe_view(snapshot.safe_view)  # type: ignore[attr-defined]
    return snapshot  # type: ignore[return-value]


def _state(snapshot: _StateSnapshot) -> Stage08CollaborationState:
    return Stage08CollaborationState(_PRIVATE_ISSUER, snapshot)


__all__ = [
    "AnalysisAction",
    "AnalysisDecision",
    "AnalysisProvider",
    "AnalysisProviderOutcome",
    "AssistantQueryCommand",
    "AssistantQuerySafeCitation",
    "AssistantQuerySafeView",
    "AssistantRequestedAction",
    "AssistantTerminalStatus",
    "CollaborationBudget",
    "CollaborationDegradationCode",
    "CollaborationStatus",
    "CompressionOutcome",
    "ContextCompressor",
    "Stage08CollaborationContractFactory",
    "Stage08CollaborationState",
    "Stage08SafeExecutionContext",
    "UnavailableAnalysisProvider",
    "UnavailableContextCompressor",
    "validate_analysis_decision",
    "validate_assistant_query_safe_view",
    "validate_collaboration_budget",
]
