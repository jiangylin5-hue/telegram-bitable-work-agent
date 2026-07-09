from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.stage06_skill_matching import build_stage06_skill_evidence


DEFAULT_FIXTURE_PATH = BACKEND_ROOT / "tests" / "fixtures" / "stage06_skill_matching_cases.json"

DEFAULT_GATES = {
    "top1_accuracy": 0.85,
    "top3_recall": 0.95,
    "high_risk_false_commit_routes": 0,
    "hidden_or_unauthorized_false_positive": 0,
    "missing_context_clarification_rate": 0.90,
    "evidence_presence_rate": 1.0,
}

L0_SKILLS = {"platform-shared-policy"}


def load_cases(path: Path = DEFAULT_FIXTURE_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for skill_id, group_payload in payload.get("skill_cases", {}).items():
        for group in ("positive", "negative"):
            for index, raw_case in enumerate(group_payload.get(group, []), start=1):
                case = _normalize_case(
                    raw_case,
                    case_id=f"{skill_id}.{group}.{index:02d}",
                    skill_id=skill_id,
                    group=group,
                )
                cases.append(case)
    for group in ("ambiguous", "high_risk", "permission", "missing_context", "inactive"):
        for index, raw_case in enumerate(payload.get(group, []), start=1):
            case = _normalize_case(
                raw_case,
                case_id=f"{group}.{index:02d}",
                skill_id=str(raw_case.get("skill_id", group)),
                group=group,
            )
            cases.append(case)
    return cases


def evaluate_cases(
    cases: list[dict[str, Any]],
    *,
    gates: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    gates = dict(gates or DEFAULT_GATES)
    failures: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()

    for case in cases:
        evidence = build_stage06_skill_evidence(
            action=str(case["action"]),
            source_text=str(case["source_text"]),
            source_context=dict(case.get("source_context", {})),
        )
        selected_ids = [
            str(item["skill_id"]) for item in evidence.get("selected_skills", [])
        ]
        inactive_ids = [
            str(item["skill_id"]) for item in evidence.get("inactive_candidates", [])
        ]
        ranked_ids = _ranked_selected_skill_ids(evidence)

        if _has_evidence_shape(evidence):
            counters["evidence_present"] += 1
        else:
            failures.append(_failure(case, "missing_evidence_shape", evidence))

        expected_primary = set(case.get("expected_primary_skill_ids", []))
        if expected_primary:
            counters["top1_denominator"] += 1
            first = ranked_ids[0] if ranked_ids else None
            if first in expected_primary:
                counters["top1_numerator"] += 1
            else:
                diagnostics.append(
                    _failure(
                        case,
                        "top1_miss",
                        {"expected": sorted(expected_primary), "ranked": ranked_ids},
                    )
                )

        expected_top3 = set(case.get("expected_top3_skill_ids", []))
        if expected_top3:
            counters["top3_denominator"] += 1
            top3 = set(ranked_ids[:3])
            if expected_top3.issubset(top3):
                counters["top3_numerator"] += 1
            else:
                diagnostics.append(
                    _failure(
                        case,
                        "top3_miss",
                        {"expected": sorted(expected_top3), "ranked": ranked_ids},
                    )
                )

        expected_selected = set(case.get("expected_selected_skill_ids", []))
        if not expected_selected.issubset(set(selected_ids)):
            failures.append(
                _failure(
                    case,
                    "expected_selected_missing",
                    {"expected": sorted(expected_selected), "selected": selected_ids},
                )
            )

        forbidden_selected = set(case.get("expected_not_selected_skill_ids", []))
        selected_forbidden = sorted(forbidden_selected.intersection(selected_ids))
        if selected_forbidden:
            failures.append(
                _failure(case, "forbidden_skill_selected", selected_forbidden)
            )

        forbidden_primary = set(case.get("expected_not_primary_skill_ids", []))
        if ranked_ids and ranked_ids[0] in forbidden_primary:
            failures.append(_failure(case, "forbidden_primary_skill", ranked_ids[0]))

        expected_inactive = set(case.get("expected_inactive_skill_ids", []))
        if not expected_inactive.issubset(set(inactive_ids)):
            failures.append(
                _failure(
                    case,
                    "expected_inactive_missing",
                    {"expected": sorted(expected_inactive), "inactive": inactive_ids},
                )
            )

        if "expect_requires_confirmation" in case and bool(
            evidence.get("requires_confirmation")
        ) != bool(case["expect_requires_confirmation"]):
            failures.append(
                _failure(
                    case,
                    "confirmation_expectation_miss",
                    evidence.get("requires_confirmation"),
                )
            )

        if "expect_requires_clarification" in case:
            counters["missing_context_denominator"] += 1
            if bool(evidence.get("requires_clarification")) == bool(
                case["expect_requires_clarification"]
            ):
                counters["missing_context_numerator"] += 1
            else:
                failures.append(
                    _failure(
                        case,
                        "clarification_expectation_miss",
                        evidence.get("requires_clarification"),
                    )
                )

        if case["group"] == "high_risk":
            if not bool(evidence.get("requires_confirmation")):
                counters["high_risk_false_commit_routes"] += 1
                failures.append(_failure(case, "high_risk_without_confirmation", evidence))

        if case["group"] == "permission":
            forbidden = set(case.get("hidden_false_positive_skill_ids", []))
            if forbidden.intersection(selected_ids):
                counters["hidden_or_unauthorized_false_positive"] += 1
                failures.append(_failure(case, "permission_false_positive", selected_ids))

        counters[f"group.{case['group']}"] += 1

    metrics = {
        "top1_accuracy": _ratio(counters["top1_numerator"], counters["top1_denominator"]),
        "top3_recall": _ratio(counters["top3_numerator"], counters["top3_denominator"]),
        "high_risk_false_commit_routes": counters["high_risk_false_commit_routes"],
        "hidden_or_unauthorized_false_positive": counters[
            "hidden_or_unauthorized_false_positive"
        ],
        "missing_context_clarification_rate": _ratio(
            counters["missing_context_numerator"],
            counters["missing_context_denominator"],
        ),
        "evidence_presence_rate": _ratio(counters["evidence_present"], len(cases)),
    }
    gate_failures = _gate_failures(metrics, gates)
    return {
        "ok": not failures and not gate_failures,
        "case_count": len(cases),
        "group_counts": {
            key.removeprefix("group."): value
            for key, value in counters.items()
            if key.startswith("group.")
        },
        "gates": gates,
        "metrics": metrics,
        "diagnostics": diagnostics,
        "failures": failures + gate_failures,
    }


def _normalize_case(
    raw_case: dict[str, Any],
    *,
    case_id: str,
    skill_id: str,
    group: str,
) -> dict[str, Any]:
    normalized = {
        "case_id": raw_case.get("case_id", case_id),
        "skill_id": skill_id,
        "group": group,
        "action": raw_case.get("action", "query"),
        "source_text": raw_case["source_text"],
        "source_context": raw_case.get("source_context", {}),
    }
    normalized.update(
        {
            key: value
            for key, value in raw_case.items()
            if key not in normalized
        }
    )
    if group == "positive":
        normalized.setdefault("expected_primary_skill_ids", [skill_id])
        normalized.setdefault("expected_top3_skill_ids", [skill_id])
        normalized.setdefault("expected_selected_skill_ids", [skill_id])
    if group == "negative" and skill_id not in L0_SKILLS:
        normalized.setdefault("expected_not_selected_skill_ids", [skill_id])
    if group == "negative" and skill_id in L0_SKILLS:
        normalized.setdefault("expected_not_primary_skill_ids", [skill_id])
    return normalized


def _ranked_selected_skill_ids(evidence: dict[str, Any]) -> list[str]:
    selected = list(evidence.get("selected_skills", []))
    indexed = list(enumerate(selected))

    def sort_key(pair: tuple[int, dict[str, Any]]) -> tuple[float, int, int]:
        index, item = pair
        skill_id = str(item.get("skill_id", ""))
        confidence = float(item.get("confidence", "0"))
        l0_penalty = 1 if skill_id in L0_SKILLS else 0
        return (-confidence, l0_penalty, index)

    return [str(item["skill_id"]) for _, item in sorted(indexed, key=sort_key)]


def _has_evidence_shape(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("manifest_version") == "stage06-larksuite-skills-v1"
        and isinstance(evidence.get("selected_skills"), list)
        and isinstance(evidence.get("candidate_skills"), list)
        and isinstance(evidence.get("baseline_metrics"), dict)
    )


def _gate_failures(
    metrics: dict[str, float | int],
    gates: dict[str, float | int],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    minimum_gates = {
        "top1_accuracy",
        "top3_recall",
        "missing_context_clarification_rate",
        "evidence_presence_rate",
    }
    maximum_gates = {
        "high_risk_false_commit_routes",
        "hidden_or_unauthorized_false_positive",
    }
    for key in minimum_gates:
        if float(metrics[key]) < float(gates[key]):
            failures.append({"case_id": "__gate__", "reason": key, "metrics": metrics})
    for key in maximum_gates:
        if int(metrics[key]) > int(gates[key]):
            failures.append({"case_id": "__gate__", "reason": key, "metrics": metrics})
    return failures


def _failure(case: dict[str, Any], reason: str, detail: Any) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "group": case["group"],
        "skill_id": case["skill_id"],
        "reason": reason,
        "detail": detail,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def main() -> int:
    result = evaluate_cases(load_cases(DEFAULT_FIXTURE_PATH), gates=DEFAULT_GATES)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
