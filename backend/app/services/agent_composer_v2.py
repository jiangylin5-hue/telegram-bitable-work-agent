from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import json
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.agent_task_spec_v2 import AuthorizedSchemaSnapshot
from app.schemas.agent_specialist_results import (
    ClaimGraphV1,
    ComposerResultV1,
    FinalAnswerRenderReceiptV1,
    ProviderFailureCode,
    specialist_payload_sha256,
)


class ComposerProviderDraftV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    answer: str = Field(min_length=1, max_length=4000)
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


class ComposerObjectiveContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    objective_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    required: bool


class ComposerPresentationContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    query: str = Field(min_length=1, max_length=4000)
    objectives: tuple[ComposerObjectiveContextV1, ...]
    subject_labels: dict[str, str]
    predicate_labels: dict[str, str]


class ComposerAnswerSectionPlanV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    section_id: str = Field(min_length=1, max_length=80)
    section_kind: Literal[
        "summary", "facts", "risks", "daily", "actions", "denial", "degradation"
    ]
    objective_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    action_slot_ids: tuple[str, ...]
    connector_code: Literal["direct", "next", "however", "safety_boundary"]

    @model_validator(mode="after")
    def validate_references(self) -> "ComposerAnswerSectionPlanV2":
        if not (self.objective_ids or self.claim_ids or self.action_slot_ids):
            raise ValueError("composer_plan_section_empty")
        if any(
            len(set(values)) != len(values)
            for values in (
                self.objective_ids,
                self.claim_ids,
                self.action_slot_ids,
            )
        ):
            raise ValueError("composer_plan_section_reference_duplicate")
        return self


class ComposerAnswerPlanV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    version: Literal["composer-answer-plan.v2"] = "composer-answer-plan.v2"
    sections: tuple[ComposerAnswerSectionPlanV2, ...] = Field(
        min_length=1, max_length=12
    )

    @model_validator(mode="after")
    def validate_sections(self) -> "ComposerAnswerPlanV2":
        section_ids = tuple(item.section_id for item in self.sections)
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("composer_plan_section_identity_duplicate")
        section_kinds = tuple(item.section_kind for item in self.sections)
        if len(set(section_kinds)) != len(section_kinds):
            raise ValueError("composer_plan_section_kind_duplicate")
        return self


ConnectorCode = Literal["direct", "next", "however", "safety_boundary"]
SectionKind = Literal[
    "summary", "facts", "risks", "daily", "actions", "denial", "degradation"
]
ObjectiveStatus = Literal["completed", "proposed", "degraded", "denied", "failed"]

_SECTION_HANDLE_PATTERN = r"^section:sha256:[0-9a-f]{64}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_OBJECTIVE_STATUS_RANK = {
    "completed": 0,
    "proposed": 1,
    "degraded": 2,
    "denied": 3,
    "failed": 4,
}
_ALLOWED_CONNECTORS_BY_SECTION_KIND: dict[SectionKind, tuple[ConnectorCode, ...]] = {
    "summary": ("direct", "next"),
    "facts": ("direct", "next"),
    "risks": ("direct", "next", "however"),
    "daily": ("direct", "next"),
    "actions": ("direct", "next", "safety_boundary"),
    "denial": ("direct", "however", "safety_boundary"),
    "degradation": ("direct", "however", "safety_boundary"),
}


def _section_handle(values: Mapping[str, object]) -> str:
    return "section:sha256:" + specialist_payload_sha256(values)


def _section_handle_values(
    *,
    section: ComposerAnswerSectionPlanV2,
    default_rank: int,
    allowed_connector_codes: tuple[ConnectorCode, ...],
) -> dict[str, object]:
    return {
        "section": section.model_dump(mode="json"),
        "default_rank": default_rank,
        "allowed_connector_codes": allowed_connector_codes,
    }


class DeterministicComposerSectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["deterministic-composer-section.v1"] = (
        "deterministic-composer-section.v1"
    )
    section_handle: str = Field(pattern=_SECTION_HANDLE_PATTERN)
    section: ComposerAnswerSectionPlanV2
    default_rank: int = Field(ge=0, le=6)
    allowed_connector_codes: tuple[ConnectorCode, ...] = Field(
        min_length=1, max_length=4
    )
    content_hash: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_section(self) -> "DeterministicComposerSectionV1":
        if len(set(self.allowed_connector_codes)) != len(self.allowed_connector_codes):
            raise ValueError("deterministic_section_connector_duplicate")
        expected_connectors = _ALLOWED_CONNECTORS_BY_SECTION_KIND[
            self.section.section_kind
        ]
        if self.allowed_connector_codes != expected_connectors:
            raise ValueError("deterministic_section_connector_policy_invalid")
        if self.section.connector_code not in self.allowed_connector_codes:
            raise ValueError("deterministic_section_default_connector_invalid")
        expected_handle = _section_handle(
            _section_handle_values(
                section=self.section,
                default_rank=self.default_rank,
                allowed_connector_codes=self.allowed_connector_codes,
            )
        )
        if self.section_handle != expected_handle:
            raise ValueError("deterministic_section_handle_mismatch")
        expected_hash = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected_hash:
            raise ValueError("deterministic_section_hash_mismatch")
        return self


class DeterministicSectionSetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["deterministic-section-set.v1"] = "deterministic-section-set.v1"
    sections: tuple[DeterministicComposerSectionV1, ...] = Field(
        min_length=1, max_length=7
    )
    content_hash: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="before")
    @classmethod
    def validate_raw_identity(cls, values: object) -> object:
        if not isinstance(values, Mapping):
            return values
        raw_sections = values.get("sections")
        if not isinstance(raw_sections, (list, tuple)):
            return values
        handles = tuple(
            item.get("section_handle")
            for item in raw_sections
            if isinstance(item, Mapping)
        )
        if len(handles) == len(raw_sections) and len(set(handles)) != len(handles):
            raise ValueError("deterministic_section_handle_duplicate")
        ranks = tuple(
            item.get("default_rank")
            for item in raw_sections
            if isinstance(item, Mapping)
        )
        if len(ranks) == len(raw_sections) and ranks != tuple(range(len(ranks))):
            raise ValueError("deterministic_section_rank_invalid")
        return values

    @model_validator(mode="after")
    def validate_sections(self) -> "DeterministicSectionSetV1":
        handles = tuple(item.section_handle for item in self.sections)
        kinds = tuple(item.section.section_kind for item in self.sections)
        ranks = tuple(item.default_rank for item in self.sections)
        if len(set(handles)) != len(handles):
            raise ValueError("deterministic_section_handle_duplicate")
        if len(set(kinds)) != len(kinds):
            raise ValueError("deterministic_section_kind_duplicate")
        if ranks != tuple(range(len(self.sections))):
            raise ValueError("deterministic_section_rank_invalid")
        expected_hash = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected_hash:
            raise ValueError("deterministic_section_set_hash_mismatch")
        return self


class ComposerSectionCandidateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    section_handle: str = Field(pattern=_SECTION_HANDLE_PATTERN)
    section_kind: SectionKind
    objective_statuses: tuple[ObjectiveStatus, ...] = Field(max_length=5)
    default_rank: int = Field(ge=0, le=6)
    allowed_connector_codes: tuple[ConnectorCode, ...] = Field(
        min_length=1, max_length=4
    )

    @model_validator(mode="after")
    def validate_candidate(self) -> "ComposerSectionCandidateV1":
        if len(set(self.objective_statuses)) != len(self.objective_statuses):
            raise ValueError("composer_section_objective_status_duplicate")
        if (
            tuple(
                sorted(self.objective_statuses, key=_OBJECTIVE_STATUS_RANK.__getitem__)
            )
            != self.objective_statuses
        ):
            raise ValueError("composer_section_objective_status_order_invalid")
        if len(set(self.allowed_connector_codes)) != len(self.allowed_connector_codes):
            raise ValueError("composer_section_connector_duplicate")
        if (
            self.allowed_connector_codes
            != _ALLOWED_CONNECTORS_BY_SECTION_KIND[self.section_kind]
        ):
            raise ValueError("composer_section_connector_policy_invalid")
        return self


class ComposerSectionOrderingRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["composer-section-ordering-request.v1"] = (
        "composer-section-ordering-request.v1"
    )
    candidates: tuple[ComposerSectionCandidateV1, ...] = Field(
        min_length=1, max_length=7
    )
    default_order: tuple[str, ...] = Field(min_length=1, max_length=7)
    scope_hash: str = Field(pattern=_SHA256_PATTERN)
    schema_hash: str = Field(pattern=_SHA256_PATTERN)
    field_policy_version: Literal["stage12-field-policy.v2"]
    field_policy_hash: str = Field(pattern=_SHA256_PATTERN)
    content_hash: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_request(self) -> "ComposerSectionOrderingRequestV1":
        handles = tuple(item.section_handle for item in self.candidates)
        kinds = tuple(item.section_kind for item in self.candidates)
        ranks = tuple(item.default_rank for item in self.candidates)
        if len(set(handles)) != len(handles):
            raise ValueError("composer_section_handle_duplicate")
        if len(set(kinds)) != len(kinds):
            raise ValueError("composer_section_kind_duplicate")
        if ranks != tuple(range(len(self.candidates))):
            raise ValueError("composer_section_rank_invalid")
        if len(set(self.default_order)) != len(handles) or set(
            self.default_order
        ) != set(handles):
            raise ValueError("composer_section_default_order_invalid")
        expected_hash = specialist_payload_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected_hash:
            raise ValueError("composer_section_ordering_request_hash_mismatch")
        return self


class ComposerSectionOrderingPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["composer-section-ordering-plan.v1"] = (
        "composer-section-ordering-plan.v1"
    )
    ordered_section_handles: tuple[str, ...] = Field(min_length=1, max_length=7)
    connector_by_handle: dict[str, ConnectorCode]

    @model_validator(mode="after")
    def validate_plan(self) -> "ComposerSectionOrderingPlanV1":
        handles = self.ordered_section_handles
        if any(
            not isinstance(handle, str)
            or not handle.startswith("section:sha256:")
            or len(handle) != len("section:sha256:") + 64
            for handle in handles
        ):
            raise ValueError("composer_section_handle_invalid")
        if len(set(handles)) != len(handles):
            raise ValueError("composer_section_handle_duplicate")
        if set(self.connector_by_handle) != set(handles):
            raise ValueError("composer_section_connector_map_invalid")
        if self.connector_by_handle[handles[0]] != "direct" or any(
            self.connector_by_handle[handle] == "direct" for handle in handles[1:]
        ):
            raise ValueError("composer_section_connector_position_invalid")
        return self


def build_deterministic_section_set(
    plan: ComposerAnswerPlanV2,
    graph: ClaimGraphV1,
) -> DeterministicSectionSetV1:
    known_objective_ids = {item.objective_id for item in graph.objective_statuses}
    sections = []
    for default_rank, section in enumerate(plan.sections):
        if not set(section.objective_ids) <= known_objective_ids:
            raise ValueError("deterministic_section_objective_unknown")
        allowed_connector_codes = _ALLOWED_CONNECTORS_BY_SECTION_KIND[
            section.section_kind
        ]
        handle_values = _section_handle_values(
            section=section,
            default_rank=default_rank,
            allowed_connector_codes=allowed_connector_codes,
        )
        section_handle = _section_handle(handle_values)
        hash_values: dict[str, object] = {
            "version": "deterministic-composer-section.v1",
            "section_handle": section_handle,
            "section": section.model_dump(mode="json"),
            "default_rank": default_rank,
            "allowed_connector_codes": allowed_connector_codes,
        }
        values: dict[str, object] = {
            **hash_values,
            "section": section,
            "content_hash": specialist_payload_sha256(hash_values),
        }
        sections.append(DeterministicComposerSectionV1.model_validate(values))
    set_hash_values: dict[str, object] = {
        "version": "deterministic-section-set.v1",
        "sections": tuple(item.model_dump(mode="json") for item in sections),
    }
    set_values: dict[str, object] = {
        **set_hash_values,
        "sections": tuple(sections),
        "content_hash": specialist_payload_sha256(set_hash_values),
    }
    return DeterministicSectionSetV1.model_validate(set_values)


def build_section_ordering_request(
    section_set: DeterministicSectionSetV1,
    *,
    graph: ClaimGraphV1,
    authorized_schema: AuthorizedSchemaSnapshot,
) -> ComposerSectionOrderingRequestV1:
    if (
        authorized_schema.scope_hash != graph.scope_hash
        or authorized_schema.field_policy_version != "stage12-field-policy.v2"
        or authorized_schema.field_policy_hash is None
    ):
        raise ValueError("composer_section_authority_proof_invalid")
    status_by_objective = {
        item.objective_id: item.status for item in graph.objective_statuses
    }
    candidates = []
    for item in section_set.sections:
        if not set(item.section.objective_ids) <= set(status_by_objective):
            raise ValueError("composer_section_objective_unknown")
        statuses = tuple(
            sorted(
                {status_by_objective[value] for value in item.section.objective_ids},
                key=_OBJECTIVE_STATUS_RANK.__getitem__,
            )
        )
        candidates.append(
            ComposerSectionCandidateV1(
                section_handle=item.section_handle,
                section_kind=item.section.section_kind,
                objective_statuses=statuses,
                default_rank=item.default_rank,
                allowed_connector_codes=item.allowed_connector_codes,
            )
        )
    hash_values: dict[str, object] = {
        "version": "composer-section-ordering-request.v1",
        "candidates": tuple(item.model_dump(mode="json") for item in candidates),
        "default_order": tuple(item.section_handle for item in candidates),
        "scope_hash": graph.scope_hash,
        "schema_hash": authorized_schema.schema_hash,
        "field_policy_version": authorized_schema.field_policy_version,
        "field_policy_hash": authorized_schema.field_policy_hash,
    }
    values: dict[str, object] = {
        **hash_values,
        "candidates": tuple(candidates),
        "content_hash": specialist_payload_sha256(hash_values),
    }
    return ComposerSectionOrderingRequestV1.model_validate(values)


def expand_ordering_plan(
    section_set: DeterministicSectionSetV1,
    ordering: ComposerSectionOrderingPlanV1,
) -> ComposerAnswerPlanV2:
    section_by_handle = {item.section_handle: item for item in section_set.sections}
    expected_handles = set(section_by_handle)
    ordered_handles = ordering.ordered_section_handles
    if (
        len(ordered_handles) != len(expected_handles)
        or len(set(ordered_handles)) != len(expected_handles)
        or set(ordered_handles) != expected_handles
        or set(ordering.connector_by_handle) != expected_handles
    ):
        raise ValueError("composer_section_ordering_invalid")
    sections = []
    for rank, handle in enumerate(ordered_handles):
        private = section_by_handle[handle]
        connector = ordering.connector_by_handle[handle]
        if (
            connector not in private.allowed_connector_codes
            or (rank == 0 and connector != "direct")
            or (rank > 0 and connector == "direct")
        ):
            raise ValueError("composer_section_ordering_invalid")
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id=private.section.section_id,
                section_kind=private.section.section_kind,
                objective_ids=private.section.objective_ids,
                claim_ids=private.section.claim_ids,
                action_slot_ids=private.section.action_slot_ids,
                connector_code=connector,
            )
        )
    return ComposerAnswerPlanV2(sections=tuple(sections))


def _deterministic_answer(
    graph: ClaimGraphV1,
    claim_ids: tuple[str, ...] | None = None,
) -> str:
    valid = {item.claim_id: item for item in graph.claims if item.status == "valid"}
    claims = (
        list(valid.values())
        if claim_ids is None
        else [valid[claim_id] for claim_id in claim_ids]
    )
    if not claims:
        if any(item.status == "conflicted" for item in graph.claims):
            return "当前证据存在冲突，无法给出确定事实；相关动作未执行。"
        return "当前没有足够的已验证事实可供回答。"
    rendered = [
        f"{item.subject_ref} 的 {item.predicate} 为 "
        f"{json.dumps(item.value, ensure_ascii=False, sort_keys=True)}"
        for item in claims
    ]
    suffix = "；相关动作仅为建议，尚未执行。" if graph.action_statuses else "。"
    return "已验证事实：" + "；".join(rendered) + suffix


def _default_presentation(graph: ClaimGraphV1) -> ComposerPresentationContextV1:
    return ComposerPresentationContextV1(
        query="基于已验证事实回答。",
        objectives=tuple(
            ComposerObjectiveContextV1(
                objective_id=item.objective_id,
                kind="fact_query",
                required=True,
            )
            for item in graph.objective_statuses
        ),
        subject_labels={},
        predicate_labels={},
    )


def _validate_presentation(
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
) -> None:
    objective_ids = {item.objective_id for item in graph.objective_statuses}
    claim_subjects = {item.subject_ref for item in graph.claims}
    claim_predicates = {item.predicate for item in graph.claims}
    if (
        {item.objective_id for item in presentation.objectives} != objective_ids
        or len({item.objective_id for item in presentation.objectives})
        != len(presentation.objectives)
        or not set(presentation.subject_labels) <= claim_subjects
        or not set(presentation.predicate_labels) <= claim_predicates
    ):
        raise ValueError("composer_presentation_scope_invalid")


_ACTION_OBJECTIVE_KINDS = {
    "record_change",
    "task_creation",
    "reminder_request",
}


def _default_plan(
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
) -> ComposerAnswerPlanV2:
    valid_claims = tuple(item for item in graph.claims if item.status == "valid")
    claim_objective_ids = tuple(
        sorted({value for item in valid_claims for value in item.objective_ids})
    )
    status_by_objective = {item.objective_id: item for item in graph.objective_statuses}
    action_objective_ids = tuple(
        item.objective_id
        for item in presentation.objectives
        if item.kind in _ACTION_OBJECTIVE_KINDS
        and item.objective_id in status_by_objective
    )
    conflicted_objective_ids = {
        objective_id
        for claim in graph.claims
        if claim.status == "conflicted"
        for objective_id in claim.objective_ids
    }
    degraded_objective_ids = tuple(
        item.objective_id
        for item in graph.objective_statuses
        if item.status in {"degraded", "failed"}
        or item.objective_id in conflicted_objective_ids
        if item.objective_id not in action_objective_ids
    )
    denied_objective_ids = tuple(
        item.objective_id
        for item in graph.objective_statuses
        if item.status == "denied" and item.objective_id not in action_objective_ids
    )
    separately_disclosed_objective_ids = (
        set(action_objective_ids)
        | set(denied_objective_ids)
        | set(degraded_objective_ids)
    )
    facts_objective_ids = tuple(
        objective_id
        for objective_id in claim_objective_ids
        if objective_id not in separately_disclosed_objective_ids
    )
    sections = []
    if valid_claims:
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id="facts",
                section_kind="facts",
                objective_ids=facts_objective_ids,
                claim_ids=tuple(item.claim_id for item in valid_claims),
                action_slot_ids=(),
                connector_code="direct",
            )
        )
    if graph.action_statuses:
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id="actions",
                section_kind="actions",
                objective_ids=action_objective_ids,
                claim_ids=(),
                action_slot_ids=tuple(item.slot_id for item in graph.action_statuses),
                connector_code="safety_boundary",
            )
        )
    if denied_objective_ids:
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id="denial",
                section_kind="denial",
                objective_ids=denied_objective_ids,
                claim_ids=(),
                action_slot_ids=(),
                connector_code="safety_boundary",
            )
        )
    if degraded_objective_ids:
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id="degradation",
                section_kind="degradation",
                objective_ids=degraded_objective_ids,
                claim_ids=(),
                action_slot_ids=(),
                connector_code="however",
            )
        )
    covered_objectives = {
        objective_id for section in sections for objective_id in section.objective_ids
    }
    remaining_objectives = tuple(
        item.objective_id
        for item in graph.objective_statuses
        if item.objective_id not in covered_objectives
    )
    if remaining_objectives:
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id="summary",
                section_kind="summary",
                objective_ids=remaining_objectives,
                claim_ids=(),
                action_slot_ids=(),
                connector_code="direct",
            )
        )
    if not sections:
        sections.append(
            ComposerAnswerSectionPlanV2(
                section_id="summary",
                section_kind="summary",
                objective_ids=tuple(
                    item.objective_id for item in graph.objective_statuses
                ),
                claim_ids=(),
                action_slot_ids=(),
                connector_code="direct",
            )
        )
    return ComposerAnswerPlanV2(sections=tuple(sections))


_SECTION_TITLES = {
    "summary": "概览",
    "facts": "已验证事实",
    "risks": "风险",
    "daily": "日报",
    "actions": "待确认动作",
    "denial": "无法执行",
    "degradation": "降级说明",
}
_CONNECTOR_PREFIXES: dict[ConnectorCode, str] = {
    "direct": "",
    "next": "接下来，",
    "however": "不过，",
    "safety_boundary": "安全边界：",
}


def _render_plan(
    graph: ClaimGraphV1,
    plan: ComposerAnswerPlanV2,
    presentation: ComposerPresentationContextV1,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    claims = {item.claim_id: item for item in graph.claims if item.status == "valid"}
    actions = {item.slot_id: item for item in graph.action_statuses}
    objectives = {item.objective_id: item for item in graph.objective_statuses}
    rendered_sections = []
    claim_ids = []
    objective_ids = []
    action_ids = []
    for section in plan.sections:
        objective_ids.extend(section.objective_ids)
        claim_ids.extend(section.claim_ids)
        action_ids.extend(section.action_slot_ids)
        sentences = []
        for claim_id in section.claim_ids:
            claim = claims[claim_id]
            subject = presentation.subject_labels.get(
                claim.subject_ref, claim.subject_ref
            )
            predicate = presentation.predicate_labels.get(
                claim.predicate, claim.predicate
            )
            evidence = "、".join(claim.evidence_ids)
            sentences.append(
                f"{subject} 的 {predicate} 为 "
                f"{json.dumps(claim.value, ensure_ascii=False, sort_keys=True)}"
                f"【证据：{evidence}】"
            )
        for slot_id in section.action_slot_ids:
            action = actions[slot_id]
            suffix = {
                "proposed": "已生成待确认提议，尚未执行",
                "denied": "已拒绝，未执行",
                "deferred": "已延后，未执行",
                "conflicted": "存在冲突，未执行",
            }[action.status]
            sentences.append(f"{slot_id}：{suffix}")
        if section.section_kind in {"denial", "degradation"}:
            for objective_id in section.objective_ids:
                objective = objectives[objective_id]
                reason = objective.reason_code or objective.status
                if section.section_kind == "denial":
                    sentences.append(f"{objective_id}：已拒绝（{reason}），未执行")
                else:
                    conflicted = any(
                        claim.status == "conflicted"
                        and objective_id in claim.objective_ids
                        for claim in graph.claims
                    )
                    reason = "conflicted_claim" if conflicted else reason
                    sentences.append(
                        f"{objective_id}：已降级（{reason}），" "仅保留可验证结果"
                    )
        if not sentences:
            sentences.append("当前没有可展示的已验证事实。")
        rendered_sections.append(
            f"{_CONNECTOR_PREFIXES[section.connector_code]}"
            f"{_SECTION_TITLES[section.section_kind]}：" + "；".join(sentences) + "。"
        )
    return (
        "\n".join(rendered_sections),
        tuple(objective_ids),
        tuple(claim_ids),
        tuple(action_ids),
    )


def _render_receipt(
    *,
    graph: ClaimGraphV1,
    presentation: ComposerPresentationContextV1,
    plan: ComposerAnswerPlanV2,
    answer: str,
    objective_ids: tuple[str, ...],
    claim_ids: tuple[str, ...],
    action_ids: tuple[str, ...],
) -> FinalAnswerRenderReceiptV1:
    claims = {item.claim_id: item for item in graph.claims}
    disclosure_codes = {
        item.reason_code
        for item in graph.objective_statuses
        if item.reason_code is not None
    }
    disclosure_codes.update(f"action_{item.status}" for item in graph.action_statuses)
    if any(item.status == "conflicted" for item in graph.claims):
        disclosure_codes.add("conflicted_claim")
    values: dict[str, object] = {
        "version": "final-answer-render-receipt.v1",
        "covered_objective_ids": objective_ids,
        "covered_claim_ids": claim_ids,
        "covered_action_slot_ids": action_ids,
        "citation_edges": tuple(
            {"claim_id": claim_id, "evidence_id": evidence_id}
            for claim_id in claim_ids
            for evidence_id in claims[claim_id].evidence_ids
        ),
        "section_kinds": tuple(item.section_kind for item in plan.sections),
        "disclosure_codes": tuple(sorted(disclosure_codes)),
        "language": "zh-Hans",
        "answer_hash": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "claim_graph_hash": graph.content_hash,
        "presentation_hash": specialist_payload_sha256(
            presentation.model_dump(mode="json")
        ),
        "scope_hash": graph.scope_hash,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return FinalAnswerRenderReceiptV1.model_validate(values)


def _base_status(graph: ClaimGraphV1) -> tuple[str, tuple[str, ...]]:
    objective_codes = tuple(
        sorted(
            {
                item.reason_code
                for item in graph.objective_statuses
                if item.reason_code is not None
            }
        )
    )
    has_valid = any(item.status == "valid" for item in graph.claims)
    has_conflict = any(item.status == "conflicted" for item in graph.claims)
    if (
        any(item.status == "failed" for item in graph.objective_statuses)
        and not has_valid
    ):
        return "failed", objective_codes
    if (
        graph.objective_statuses
        and all(item.status == "denied" for item in graph.objective_statuses)
        and not has_valid
    ):
        return "denied", objective_codes
    if has_conflict or any(
        item.status in {"degraded", "failed"} for item in graph.objective_statuses
    ):
        codes = set(objective_codes)
        if has_conflict:
            codes.add("conflicted_claim")
        return "degraded", tuple(sorted(codes))
    return "completed", ()


def compose_claim_graph(
    graph: ClaimGraphV1,
    *,
    provider: (
        Callable[[ComposerSectionOrderingRequestV1], ComposerSectionOrderingPlanV1]
        | None
    ) = None,
    authorized_schema: AuthorizedSchemaSnapshot | None = None,
    presentation: ComposerPresentationContextV1 | None = None,
) -> ComposerResultV1:
    valid_claims = tuple(item for item in graph.claims if item.status == "valid")
    allowed_evidence = {
        evidence_id for item in valid_claims for evidence_id in item.evidence_ids
    }
    presentation = presentation or _default_presentation(graph)
    _validate_presentation(graph, presentation)
    plan = _default_plan(graph, presentation)
    answer, objective_ids, claim_ids, action_ids = _render_plan(
        graph, plan, presentation
    )
    evidence_ids = tuple(sorted(allowed_evidence))
    status, degradation_codes = _base_status(graph)
    provider_calls = 0

    if provider is not None:
        if (
            authorized_schema is None
            or authorized_schema.field_policy_version is None
            or authorized_schema.field_policy_hash is None
            or authorized_schema.scope_hash != graph.scope_hash
        ):
            status = "failed" if status == "failed" else "degraded"
            degradation_codes = tuple(
                sorted(set(degradation_codes) | {"policy_denied"})
            )
        else:
            provider_calls = 1
            section_set = build_deterministic_section_set(plan, graph)
            request = build_section_ordering_request(
                section_set,
                graph=graph,
                authorized_schema=authorized_schema,
            )
            try:
                ordering = provider(request)
                if not isinstance(ordering, ComposerSectionOrderingPlanV1):
                    raise ValueError("composer_provider_ordering_invalid")
                expanded_plan = expand_ordering_plan(section_set, ordering)
            except Exception as exc:
                provider_code = getattr(exc, "code", None)
                if provider_code not in set(get_args(ProviderFailureCode)):
                    provider_code = "provider_semantic_invalid"
                status = "failed" if status == "failed" else "degraded"
                degradation_codes = tuple(
                    sorted(set(degradation_codes) | {provider_code})
                )
            else:
                plan = expanded_plan
                answer, objective_ids, claim_ids, action_ids = _render_plan(
                    graph, plan, presentation
                )

    receipt = _render_receipt(
        graph=graph,
        presentation=presentation,
        plan=plan,
        answer=answer,
        objective_ids=objective_ids,
        claim_ids=claim_ids,
        action_ids=action_ids,
    )

    values: dict[str, object] = {
        "version": "composer-result.v1",
        "status": status,
        "answer": answer,
        "claim_ids": claim_ids,
        "evidence_ids": evidence_ids,
        "action_statuses": tuple(
            item.model_dump(mode="json") for item in graph.action_statuses
        ),
        "degradation_codes": degradation_codes,
        "render_receipt": receipt.model_dump(mode="json"),
        "provider_call_count": provider_calls,
        "scope_hash": graph.scope_hash,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ComposerResultV1.model_validate_json(
        json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    )


__all__ = [
    "ComposerAnswerPlanV2",
    "ComposerAnswerSectionPlanV2",
    "ComposerObjectiveContextV1",
    "ComposerPresentationContextV1",
    "ComposerProviderDraftV1",
    "ComposerSectionCandidateV1",
    "ComposerSectionOrderingPlanV1",
    "ComposerSectionOrderingRequestV1",
    "ConnectorCode",
    "DeterministicComposerSectionV1",
    "DeterministicSectionSetV1",
    "build_deterministic_section_set",
    "build_section_ordering_request",
    "compose_claim_graph",
    "expand_ordering_plan",
]
