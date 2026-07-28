"""Prepare and evaluate the isolated Stage10 distributed acceptance fixture.

This harness uses only the fictional multi-table dataset.  It never sends
Telegram messages or writes provider-side data.  `prepare` creates one scoped
view and read-only digital employee through domain services.  `report` calls
the real HTTP run/SSE contract so Redis publisher/worker execution is covered.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.database import get_session_factory
from app.models.stage06_platform import BitableBase, PlatformTable, Workspace
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_form_view,
)
from scripts.stage09_multitable_chinese_eval import (
    build_chinese_cases,
    build_multitable_fixture,
)


_WORKSPACE_NAME = "Stage09 Multi-table LLM Evaluation"
_VIEW_NAME = "Stage10 分布式中文评测视图"
_EMPLOYEE_NAME = "Stage10 分布式只读分析员工"
_CODE_RE = re.compile(r"(?<![A-Z0-9])MT-\d{3}(?![A-Z0-9])", re.IGNORECASE)
_SKILL_CHAINS = {
    "platform-base": ("platform-base", "platform-shared-policy"),
    "platform-tabular-analysis": (
        "platform-tabular-analysis",
        "platform-base",
        "platform-shared-policy",
    ),
}
_ENUM_EQUIVALENTS = {
    "in_progress": ("进行中",),
    "medium": ("中等", "中"),
    "low": ("低",),
    "high": ("高",),
    "done": ("已完成", "完成"),
    "blocked": ("已阻塞", "阻塞"),
    "planned": ("计划中", "待计划"),
}


def prepare() -> dict[str, object]:
    session = get_session_factory()()
    try:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = session.scalar(
            select(Workspace).where(Workspace.name == _WORKSPACE_NAME)
        )
        if workspace is None:
            raise RuntimeError("stage10_acceptance_fixture_missing")
        base = session.scalar(
            select(BitableBase).where(BitableBase.workspace_id == workspace.id)
        )
        if base is None:
            raise RuntimeError("stage10_acceptance_base_missing")
        tables = list(
            session.scalars(
                select(PlatformTable)
                .where(PlatformTable.base_id == base.id)
                .order_by(PlatformTable.key)
            )
        )
        work_items = next((item for item in tables if item.key == "work_items"), None)
        if work_items is None:
            raise RuntimeError("stage10_acceptance_work_items_missing")
        actor = Actor(
            actor_type="user",
            actor_id=workspace.owner_user_id,
            role="owner",
        )
        view = next(
            (item for item in uow.list_views(work_items.id) if item.name == _VIEW_NAME),
            None,
        )
        if view is None:
            view = create_form_view(
                uow,
                base.id,
                work_items.id,
                name=_VIEW_NAME,
                view_type="grid",
                config={
                    "fields": [field.key for field in uow.list_fields(work_items.id)]
                },
                actor=actor,
            )
            session.flush()
        employee = next(
            (
                item
                for item in uow.list_digital_employees(base.id)
                if item.name == _EMPLOYEE_NAME
            ),
            None,
        )
        if employee is None:
            employee = create_digital_employee(
                uow,
                base.id,
                name=_EMPLOYEE_NAME,
                description="仅分析虚构多表评测数据；只读；禁止外部发送",
                telegram_alias=None,
                accessible_tables=[str(item.id) for item in tables],
                accessible_views=[str(view.id)],
                allowed_actions=["query", "summarize"],
                actor=actor,
            )
        session.commit()
        return {
            "workspace_id": str(workspace.id),
            "base_id": str(base.id),
            "employee_id": str(employee.id),
            "view_id": str(view.id),
            "owner_user_id": workspace.owner_user_id,
            "table_count": len(tables),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_report(
    *,
    api_base_url: str,
    workspace_id: UUID,
    employee_id: UUID,
    user_id: str,
) -> dict[str, object]:
    fixture = build_multitable_fixture(
        InMemoryStage06PlatformUnitOfWork(),
        Actor(actor_type="user", actor_id="stage10-case-builder", role="owner"),
    )
    cases = build_chinese_cases(fixture)
    results: list[dict[str, object]] = []
    headers = {"X-Stage06-User-Id": user_id, "Accept": "application/json"}
    with httpx.Client(base_url=api_base_url, headers=headers, timeout=120.0) as client:
        for index, case in enumerate(cases, start=1):
            started = time.monotonic()
            created = client.post(
                "/api/stage10/agent-runs",
                json={
                    "workspace_id": str(workspace_id),
                    "employee_id": str(employee_id),
                    "intent": "business_fact",
                    "query": case.prompt,
                    "requested_action": "read_only",
                    "target_record_id": None,
                    "idempotency_key": f"stage10-real-{index:02d}-{int(started * 1000)}",
                    "skill_id": _case_primary_skill(case),
                },
            )
            if created.status_code != 202:
                results.append(_failed_case(case, created.status_code, started))
                continue
            run_id = created.json()["run_id"]
            stream = client.get(
                f"/api/stage10/agent-runs/{run_id}/events",
                headers={**headers, "Accept": "text/event-stream"},
            )
            safe_view = _last_safe_view(stream.text) if stream.status_code == 200 else None
            results.append(
                _score_case(
                    case,
                    safe_view,
                    status_code=stream.status_code,
                    latency_ms=round((time.monotonic() - started) * 1000),
                )
            )
    return _summarize(results)


def _last_safe_view(stream_text: str) -> dict[str, Any] | None:
    views: list[dict[str, Any]] = []
    for line in stream_text.splitlines():
        if not line.startswith("data: "):
            continue
        value = json.loads(line.removeprefix("data: "))
        if value.get("event") == "result" and isinstance(value.get("safe_view"), dict):
            views.append(value["safe_view"])
    return views[-1] if views else None


def _score_case(
    case: Any,
    safe_view: dict[str, Any] | None,
    *,
    status_code: int,
    latency_ms: int,
) -> dict[str, object]:
    answer = "" if safe_view is None else str(safe_view.get("answer") or "")
    safe_status = None if safe_view is None else safe_view.get("status")
    degradation_codes = (
        [] if safe_view is None else list(safe_view.get("degradation_codes") or [])
    )
    acceptable_terminal = safe_status == "completed" or (
        str(case.case_id).startswith("guard_") and safe_status == "denied"
    )
    if not acceptable_terminal or degradation_codes:
        return {
            "case_id": case.case_id,
            "query": case.prompt,
            "answer": answer,
            "expected_codes": sorted(case.truth_codes),
            "answer_codes": sorted(_CODE_RE.findall(answer)),
            "expected_primary_skill": _case_primary_skill(case),
            "required_skills": list(case.required_skill_ids),
            "skills": _safe_view_skills(safe_view),
            "skill_hit": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "retrieval_readiness": 0.0,
            "answer_accuracy": 0.0,
            "score": 0.0,
            "latency_ms": latency_ms,
            "http_status": status_code,
            "outcome": "failed",
            "degradation_codes": degradation_codes or [str(safe_status or "missing_result")],
        }
    found = set(_CODE_RE.findall(answer))
    expected = set(case.truth_codes)
    skills = _safe_view_skills(safe_view)
    required_skills = set(case.required_skill_ids)
    skill_hit = 1.0 if required_skills.issubset(set(skills)) else 0.0
    kind = str(getattr(case, "kind", ""))
    if kind in {"negative", "guard"}:
        permitted = {
            str(value).upper()
            for value in getattr(case, "permitted_answer_codes", ())
        }
        mentioned = {value.upper() for value in found}
        normalized = answer.casefold()
        markers = (
            ("未找到", "没有找到", "不存在", "无记录", "not found", "does not exist", "no record")
            if kind == "negative"
            else (
                "没有",
                "未找到",
                "无权",
                "不能",
                "不可",
                "不可用",
                "unavailable",
                "not found",
                "does not have",
                "not permitted",
            )
        )
        citations = [] if safe_view is None else safe_view.get("citations") or []
        fact_hit = bool(answer.strip()) and mentioned.issubset(permitted) and any(
            marker in normalized for marker in markers
        )
        if kind == "negative" and citations:
            fact_hit = False
        quality = 1.0 if fact_hit else 0.0
        score = round(100 * (quality * 0.85 + skill_hit * 0.15), 2)
        return {
            "case_id": case.case_id,
            "query": case.prompt,
            "answer": answer,
            "expected_codes": [],
            "answer_codes": sorted(found),
            "expected_primary_skill": _case_primary_skill(case),
            "required_skills": list(case.required_skill_ids),
            "skills": skills,
            "skill_hit": skill_hit,
            "precision": quality,
            "recall": quality,
            "retrieval_readiness": quality,
            "answer_accuracy": quality,
            "score": score,
            "latency_ms": latency_ms,
            "http_status": status_code,
            "outcome": "completed" if fact_hit else "failed",
            "degradation_codes": degradation_codes,
        }
    correct = found & expected
    precision = 1.0 if not found and not expected else len(correct) / max(1, len(found))
    recall = 1.0 if not expected else len(correct) / len(expected)
    fragments = tuple(str(value) for value in case.expected_fragments)
    fragment_accuracy = (
        1.0
        if not fragments
        else sum(_fragment_present(fragment, answer) for fragment in fragments)
        / len(fragments)
    )
    citations = [] if safe_view is None else safe_view.get("citations") or []
    retrieval_readiness = 1.0 if citations or not expected else 0.0
    expected_primary_skill = _case_primary_skill(case)
    score = round(
        100
        * (
            precision * 0.2
            + recall * 0.25
            + fragment_accuracy * 0.25
            + retrieval_readiness * 0.15
            + skill_hit * 0.15
        ),
        2,
    )
    return {
        "case_id": case.case_id,
        "query": case.prompt,
        "answer": answer,
        "expected_codes": sorted(expected),
        "answer_codes": sorted(found),
        "expected_primary_skill": expected_primary_skill,
        "required_skills": list(case.required_skill_ids),
        "skills": skills,
        "skill_hit": skill_hit,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "retrieval_readiness": round(retrieval_readiness, 4),
        "answer_accuracy": round(fragment_accuracy, 4),
        "score": score,
        "latency_ms": latency_ms,
        "http_status": status_code,
        "outcome": "completed",
        "degradation_codes": degradation_codes,
    }


def _failed_case(case: Any, status_code: int, started: float) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "query": case.prompt,
        "answer": "",
        "expected_codes": sorted(case.truth_codes),
        "answer_codes": [],
        "expected_primary_skill": _case_primary_skill(case),
        "required_skills": list(case.required_skill_ids),
        "skills": [],
        "skill_hit": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "retrieval_readiness": 0.0,
        "answer_accuracy": 0.0,
        "score": 0.0,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "http_status": status_code,
        "outcome": "failed",
        "degradation_codes": ["http_failure"],
    }


def _case_primary_skill(case: Any) -> str:
    required = tuple(str(value) for value in case.required_skill_ids)
    if "platform-tabular-analysis" in required:
        return "platform-tabular-analysis"
    return "platform-base"


def _safe_view_skills(safe_view: dict[str, Any] | None) -> list[str]:
    skill = None if safe_view is None else safe_view.get("skill")
    skill_id = skill.get("skill_id") if isinstance(skill, dict) else None
    if not isinstance(skill_id, str):
        return []
    return list(_SKILL_CHAINS.get(skill_id, (skill_id,)))


def _fragment_present(fragment: str, answer: str) -> bool:
    normalized_fragment = fragment.casefold()
    normalized_answer = answer.casefold()
    if normalized_fragment in normalized_answer:
        return True
    return any(
        equivalent in answer
        for equivalent in _ENUM_EQUIVALENTS.get(normalized_fragment, ())
    )


def _summarize(results: list[dict[str, object]]) -> dict[str, object]:
    completed = [item for item in results if item["outcome"] == "completed"]
    metric_names = (
        "precision",
        "recall",
        "retrieval_readiness",
        "answer_accuracy",
        "score",
        "latency_ms",
    )
    metrics = {
        name: round(
            sum(float(item[name]) for item in results) / max(1, len(results)), 4
        )
        for name in metric_names
    }
    return {
        "case_count": len(results),
        "completed_count": len(completed),
        "metrics": metrics,
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    report = subparsers.add_parser("report")
    report.add_argument("--api-base-url", required=True)
    report.add_argument("--workspace-id", type=UUID, required=True)
    report.add_argument("--employee-id", type=UUID, required=True)
    report.add_argument("--user-id", required=True)
    args = parser.parse_args()
    result = (
        prepare()
        if args.command == "prepare"
        else run_report(
            api_base_url=args.api_base_url,
            workspace_id=args.workspace_id,
            employee_id=args.employee_id,
            user_id=args.user_id,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
