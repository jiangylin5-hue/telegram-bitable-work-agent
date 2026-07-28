"""Run the retained Stage09 fixture through the real retrieval-first runtime.

The runner intentionally builds an in-memory table from the committed non-personal
fixture.  Each case gets a separate process and only its score projection crosses
the process boundary: prompts, record values, provider request IDs, and answers
are never printed or written by this script.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import time
from dataclasses import asdict
from queue import Empty
from typing import Any

from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    invoke_digital_employee,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
try:  # Supports both ``python scripts/...`` and package-style test imports.
    from scripts.stage09_real_table_quality_eval import (
        CaseScore,
        RealTableEvalCase,
        build_fixture_cases,
        load_fixture_rows,
        score_case_response,
        summarize_case_scores,
    )
except ModuleNotFoundError:
    from stage09_real_table_quality_eval import (
        CaseScore,
        RealTableEvalCase,
        build_fixture_cases,
        load_fixture_rows,
        score_case_response,
        summarize_case_scores,
    )


MAX_CONCURRENCY = 4
CASE_TIMEOUT_SECONDS = 60


def run_live_retrieval_evaluation() -> dict[str, Any]:
    """Return redacted quality metrics from real OpenRouter calls where permitted."""

    rows = load_fixture_rows()
    cases = build_fixture_cases(rows)
    context = mp.get_context("fork")
    pending = [case.case_id for case in cases]
    results: list[dict[str, object]] = []
    timed_out: list[str] = []
    while pending:
        batch = pending[:MAX_CONCURRENCY]
        pending = pending[MAX_CONCURRENCY:]
        queue: Any = context.Queue()
        processes = [
            (case_id, context.Process(target=_run_case, args=(case_id, queue)))
            for case_id in batch
        ]
        for _, process in processes:
            process.start()
        for case_id, process in processes:
            process.join(CASE_TIMEOUT_SECONDS)
            if process.is_alive():
                process.terminate()
                process.join(5)
                timed_out.append(case_id)
            elif process.exitcode != 0:
                timed_out.append(case_id)
        for case_id, _ in processes:
            try:
                results.append(queue.get(timeout=2))
            except Empty:
                if case_id not in timed_out:
                    timed_out.append(case_id)

    scores = [CaseScore(**item["score"]) for item in results]
    outcomes = [str(item["outcome"]) for item in results]
    return {
        "case_count": len(cases),
        "completed_count": len(results),
        "timeout_count": len(timed_out),
        "timeout_case_ids": sorted(timed_out),
        "outcome_counts": {outcome: outcomes.count(outcome) for outcome in sorted(set(outcomes))},
        "case_signals": {
            str(item["case_id"]): {
                "outcome": item["outcome"],
                "fact_correct": item["score"]["fact_correct"],
                "citation_safe": item["score"]["citation_safe"],
                "retrieval_recall": [
                    item["score"]["retrieval_recall_numerator"],
                    item["score"]["retrieval_recall_denominator"],
                ],
                "required_skills_hit": item["score"]["required_skills_hit"],
                "forbidden_skills_absent": item["score"]["forbidden_skills_absent"],
                "runtime_mode": item["runtime_mode"],
                "selected_skill_ids": item["selected_skill_ids"],
                "citation_diagnostic": item["citation_diagnostic"],
            }
            for item in sorted(results, key=lambda item: str(item["case_id"]))
        },
        "metrics": summarize_case_scores(scores),
        "passing_case_ids": sorted(
            item["case_id"]
            for item in results
            if CaseScore(**item["score"]).exact_match
        ),
        "failing_case_ids": sorted(
            item["case_id"]
            for item in results
            if not CaseScore(**item["score"]).exact_match
        ),
    }


def _run_case(case_id: str, queue: Any) -> None:
    rows = load_fixture_rows()
    cases = build_fixture_cases(rows)
    case = next(candidate for candidate in cases if candidate.case_id == case_id)
    uow, employee_id, view_id, actor, record_code_by_id, field_keys = _build_runtime(rows)
    try:
        response = invoke_digital_employee(
            uow,
            employee_id,
            action="summarize",
            view_id=view_id,
            actor=actor,
            runtime_mode="live_openrouter",
            prompt=case.prompt,
        )
        outcome = "completed"
    except PlatformValidationError as exc:
        response = _empty_scoring_response(case)
        outcome = f"platform_error:{exc.code}"
    except Exception:
        response = _empty_scoring_response(case)
        outcome = "runtime_error"
    score = score_case_response(
        case,
        response,
        record_code_by_id=record_code_by_id,
        allowed_field_keys=set(field_keys),
    )
    queue.put(
        {
            "case_id": case_id,
            "outcome": outcome,
            "score": asdict(score),
            "runtime_mode": _runtime_mode(response),
            "selected_skill_ids": _selected_skill_ids(response),
            "citation_diagnostic": _citation_diagnostic(
                response,
                record_code_by_id=record_code_by_id,
                allowed_field_keys=set(field_keys),
            ),
        }
    )


def _build_runtime(
    rows: list[dict[str, str]],
) -> tuple[
    InMemoryStage06PlatformUnitOfWork,
    Any,
    Any,
    Actor,
    dict[str, str],
    tuple[str, ...],
]:
    field_keys = tuple(rows[0])
    actor = Actor(actor_type="user", actor_id="stage09-eval-owner", role="owner")
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Stage09 Evaluation", owner_user_id=actor.actor_id)
    base = create_base(uow, workspace.id, name="Fixture Base")
    table = create_table(uow, base.id, name="Work Items", key="evaluation_work_items")
    for key in field_keys:
        create_field(uow, table.id, name=key.replace("_", " ").title(), key=key, field_type="text")
    record_code_by_id: dict[str, str] = {}
    for row in rows:
        record = create_record(uow, table.id, values=dict(row), actor=actor)
        record_code_by_id[str(record.id)] = row["ticket_code"]
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Evaluation Grid",
        view_type="grid",
        config={"fields": list(field_keys)},
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Evaluation Analyst",
        description="Bounded fixture analysis",
        telegram_alias="eval",
        accessible_tables=[],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=actor,
    )
    return uow, employee.id, view.id, actor, record_code_by_id, field_keys


def _empty_scoring_response(case: RealTableEvalCase) -> dict[str, object]:
    skills = (
        [{"skill_id": "platform-shared-policy"}]
        if case.kind == "guard"
        else [
            {"skill_id": "platform-base"},
            {"skill_id": "platform-tabular-analysis"},
        ]
    )
    return {"answer": "", "citations": [], "skill_evidence": {"selected_skills": skills}}


def _runtime_mode(response: dict[str, object]) -> str:
    runtime = response.get("runtime")
    return str(runtime.get("mode")) if isinstance(runtime, dict) else "none"


def _selected_skill_ids(response: dict[str, object]) -> list[str]:
    evidence = response.get("skill_evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("selected_skills"), list):
        return []
    return sorted(
        item["skill_id"]
        for item in evidence["selected_skills"]
        if isinstance(item, dict) and isinstance(item.get("skill_id"), str)
    )


def _citation_diagnostic(
    response: dict[str, object],
    *,
    record_code_by_id: dict[str, str],
    allowed_field_keys: set[str],
) -> str:
    citations = response.get("citations")
    if not isinstance(citations, list):
        return "not_list"
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"record_id", "field_keys"}:
            return "shape"
        if citation.get("record_id") not in record_code_by_id:
            return "unknown_record"
        fields = citation.get("field_keys")
        if not isinstance(fields, list) or not fields:
            return "empty_fields"
        if any(not isinstance(field, str) or field not in allowed_field_keys for field in fields):
            return "unknown_field"
    return "valid"


if __name__ == "__main__":
    print(json.dumps(run_live_retrieval_evaluation(), sort_keys=True))
