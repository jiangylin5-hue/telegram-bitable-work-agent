from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from app.schemas.agent_specialist_results import (
    ActionStatusV1,
    ClaimGraphV1,
    ClaimV1,
    ObjectiveStatusV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import JsonValue


@dataclass(frozen=True, slots=True)
class ClaimInputV1:
    objective_id: str
    subject_ref: str
    predicate: str
    value: JsonValue
    evidence_ids: tuple[str, ...]
    source_version: int


@dataclass(frozen=True, slots=True)
class ObjectiveOutcomeInputV1:
    objective_id: str
    state: Literal["completed", "proposed", "denied", "failed", "deadline"]
    required: bool
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class ActionDependencyV1:
    slot_id: str
    proposal_status: Literal["proposed", "denied", "deferred"]
    required_claim_refs: tuple[tuple[str, str], ...]
    reason_code: str | None = None


def _canonical(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _claim_id(subject_ref: str, predicate: str, canonical_value: str) -> str:
    digest = hashlib.sha256(
        f"{subject_ref}\x1f{predicate}\x1f{canonical_value}".encode("utf-8")
    ).hexdigest()
    return f"claim:{digest}"


def _objective_status(outcome: ObjectiveOutcomeInputV1) -> ObjectiveStatusV1:
    if outcome.state in {"completed", "proposed", "denied"}:
        return ObjectiveStatusV1(
            objective_id=outcome.objective_id,
            status=outcome.state,
            reason_code=(
                None
                if outcome.state != "denied"
                else (outcome.reason_code or "action_denied")
            ),
        )
    if outcome.state == "deadline":
        return ObjectiveStatusV1(
            objective_id=outcome.objective_id,
            status="degraded",
            reason_code="deadline_exhausted",
        )
    return ObjectiveStatusV1(
        objective_id=outcome.objective_id,
        status="failed" if outcome.required else "degraded",
        reason_code=outcome.reason_code or "specialist_failed",
    )


def build_claim_graph(
    *,
    claims: tuple[ClaimInputV1, ...],
    outcomes: tuple[ObjectiveOutcomeInputV1, ...],
    actions: tuple[ActionDependencyV1, ...],
    scope_hash: str,
    source_artifacts: tuple[StructuredFactSetV1 | RiskAssessmentSetV1, ...],
) -> ClaimGraphV1:
    if len({item.objective_id for item in outcomes}) != len(outcomes):
        raise ValueError("claim_graph_objective_duplicate")
    outcome_ids = {item.objective_id for item in outcomes}
    if any(item.objective_id not in outcome_ids for item in claims):
        raise ValueError("claim_graph_objective_unknown")
    if any(item.scope_hash != scope_hash for item in source_artifacts):
        raise ValueError("claim_graph_source_scope_mismatch")
    if any(not _claim_is_supported(item, source_artifacts) for item in claims):
        raise ValueError("claim_graph_claim_unsupported")

    merged: dict[tuple[str, str, str], dict[str, object]] = {}
    for item in claims:
        if (
            not item.subject_ref
            or not item.predicate
            or not item.evidence_ids
            or item.source_version < 1
        ):
            raise ValueError("claim_graph_claim_invalid")
        key = (item.subject_ref, item.predicate, _canonical(item.value))
        current = merged.setdefault(
            key,
            {
                "value": item.value,
                "version": item.source_version,
                "evidence": set(),
                "objectives": set(),
            },
        )
        current["version"] = max(int(current["version"]), item.source_version)
        current["evidence"].update(item.evidence_ids)  # type: ignore[union-attr]
        current["objectives"].add(item.objective_id)  # type: ignore[union-attr]

    by_field: dict[
        tuple[str, str], list[tuple[tuple[str, str, str], dict[str, object]]]
    ] = {}
    for key, value in merged.items():
        by_field.setdefault((key[0], key[1]), []).append((key, value))

    rendered_claims: list[ClaimV1] = []
    conflicted_refs: set[tuple[str, str]] = set()
    for field_ref in sorted(by_field):
        values = by_field[field_ref]
        newest = max(int(item[1]["version"]) for item in values)
        newest_values = [item for item in values if int(item[1]["version"]) == newest]
        conflict = len(newest_values) > 1
        if conflict:
            conflicted_refs.add(field_ref)
        for key, data in sorted(values, key=lambda item: item[0][2]):
            version = int(data["version"])
            status: Literal["valid", "stale", "conflicted"]
            status = (
                "stale" if version < newest else ("conflicted" if conflict else "valid")
            )
            rendered_claims.append(
                ClaimV1(
                    claim_id=_claim_id(key[0], key[1], key[2]),
                    subject_ref=key[0],
                    predicate=key[1],
                    value=data["value"],  # type: ignore[arg-type]
                    evidence_ids=tuple(sorted(data["evidence"])),  # type: ignore[arg-type]
                    objective_ids=tuple(sorted(data["objectives"])),  # type: ignore[arg-type]
                    source_version=version,
                    status=status,
                )
            )

    action_statuses = []
    for action in actions:
        if any(ref in conflicted_refs for ref in action.required_claim_refs):
            action_statuses.append(
                ActionStatusV1(
                    slot_id=action.slot_id,
                    status="conflicted",
                    reason_code="conflicted_claim",
                )
            )
        else:
            action_statuses.append(
                ActionStatusV1(
                    slot_id=action.slot_id,
                    status=action.proposal_status,
                    reason_code=(
                        None
                        if action.proposal_status == "proposed"
                        else action.reason_code or f"action_{action.proposal_status}"
                    ),
                )
            )

    values: dict[str, object] = {
        "version": "claim-graph.v1",
        "claims": tuple(item.model_dump(mode="json") for item in rendered_claims),
        "objective_statuses": tuple(
            _objective_status(item).model_dump(mode="json") for item in outcomes
        ),
        "action_statuses": tuple(
            item.model_dump(mode="json") for item in action_statuses
        ),
        "scope_hash": scope_hash,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ClaimGraphV1.model_validate_json(
        json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    )


def _claim_is_supported(
    claim: ClaimInputV1,
    artifacts: tuple[StructuredFactSetV1 | RiskAssessmentSetV1, ...],
) -> bool:
    evidence = set(claim.evidence_ids)
    canonical_value = _canonical(claim.value)
    fact_sets = tuple(
        item for item in artifacts if isinstance(item, StructuredFactSetV1)
    )
    for facts in fact_sets:
        versions = {
            (item.table_id, item.record_id): item.record_version
            for item in facts.source_versions
        }
        if evidence.issubset(facts.evidence_refs):
            for record in facts.records:
                if claim.subject_ref != f"record:{record.record_id}":
                    continue
                if (
                    versions.get((record.table_id, record.record_id))
                    != claim.source_version
                ):
                    continue
                for value in record.values:
                    if (
                        claim.predicate == f"field:{value.field_id}"
                        and canonical_value == _canonical(value.value)
                    ):
                        return True
            aggregate_version = max(
                (item.record_version for item in facts.source_versions),
                default=1,
            )
            for aggregate in facts.aggregates:
                if (
                    claim.subject_ref == f"aggregate:{aggregate.aggregate_id}"
                    and claim.predicate
                    in {
                        "value",
                        "group:"
                        + json.dumps(
                            aggregate.group_key,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                    and claim.source_version == aggregate_version
                    and canonical_value == _canonical(aggregate.value)
                ):
                    return True

    fact_versions_by_hash = {
        item.content_hash: {
            str(version.record_id): version.record_version
            for version in item.source_versions
        }
        for item in fact_sets
    }
    for risks in (item for item in artifacts if isinstance(item, RiskAssessmentSetV1)):
        source_versions = fact_versions_by_hash.get(risks.fact_set_hash, {})
        for assessment in risks.assessments:
            subject_ref = (
                assessment.subject_ref
                if ":" in assessment.subject_ref
                else f"record:{assessment.subject_ref}"
            )
            if (
                claim.subject_ref == subject_ref
                and source_versions.get(assessment.subject_ref) == claim.source_version
                and claim.predicate == "risk_severity"
                and canonical_value == _canonical(assessment.severity)
                and evidence.issubset(assessment.evidence_ids)
            ):
                return True
    return False


__all__ = [
    "ActionDependencyV1",
    "ClaimInputV1",
    "ObjectiveOutcomeInputV1",
    "build_claim_graph",
]
