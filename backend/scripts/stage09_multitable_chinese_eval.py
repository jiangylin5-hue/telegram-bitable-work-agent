"""Fictional multi-table fixture for Stage09 import/link and Chinese LLM evaluation."""

from __future__ import annotations

import csv
import json
import multiprocessing as mp
import sys
from dataclasses import dataclass
from io import StringIO
from queue import Empty
from typing import Any
from uuid import UUID

from app.core.database import get_session_factory
from app.models.stage06_platform import Workspace
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee, invoke_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    SqlAlchemyStage06PlatformUnitOfWork,
    create_field,
    create_form_view,
    create_workspace,
    update_record,
)
from app.services.stage06_templates import create_import_job_from_csv, commit_import_job
from scripts.stage09_real_table_quality_eval import (
    CaseScore,
    RealTableEvalCase,
    score_case_response,
    summarize_case_scores,
)


_PROJECT_ROWS = (
    {"project_code": "PRJ-ATLAS", "project_name": "Atlas", "phase": "delivery", "delivery_state": "active"},
    {"project_code": "PRJ-BEACON", "project_name": "Beacon", "phase": "delivery", "delivery_state": "active"},
    {"project_code": "PRJ-CEDAR", "project_name": "Cedar", "phase": "closeout", "delivery_state": "active"},
    {"project_code": "PRJ-DELTA", "project_name": "Delta", "phase": "planning", "delivery_state": "active"},
    {"project_code": "PRJ-EMBER", "project_name": "Ember", "phase": "planning", "delivery_state": "paused"},
    {"project_code": "PRJ-FJORD", "project_name": "Fjord", "phase": "delivery", "delivery_state": "active"},
)

_WORK_ITEM_ROWS = (
    {"ticket_code": "MT-001", "title": "Atlas launch checklist", "project_code": "PRJ-ATLAS", "status": "blocked", "priority": "high", "risk_level": "high", "summary": "等待范围确认"},
    {"ticket_code": "MT-002", "title": "Atlas data mapping", "project_code": "PRJ-ATLAS", "status": "in_progress", "priority": "high", "risk_level": "medium", "summary": "字段映射进行中"},
    {"ticket_code": "MT-003", "title": "Atlas rehearsal", "project_code": "PRJ-ATLAS", "status": "planned", "priority": "medium", "risk_level": "low", "summary": "等待排期"},
    {"ticket_code": "MT-004", "title": "Beacon connector", "project_code": "PRJ-BEACON", "status": "blocked", "priority": "high", "risk_level": "high", "summary": "依赖接口未就绪"},
    {"ticket_code": "MT-005", "title": "Beacon quality check", "project_code": "PRJ-BEACON", "status": "in_progress", "priority": "medium", "risk_level": "medium", "summary": "验证中"},
    {"ticket_code": "MT-006", "title": "Beacon dashboard", "project_code": "PRJ-BEACON", "status": "done", "priority": "low", "risk_level": "low", "summary": "已发布"},
    {"ticket_code": "MT-007", "title": "Cedar archive", "project_code": "PRJ-CEDAR", "status": "done", "priority": "medium", "risk_level": "low", "summary": "归档完成"},
    {"ticket_code": "MT-008", "title": "Cedar handoff", "project_code": "PRJ-CEDAR", "status": "done", "priority": "high", "risk_level": "low", "summary": "交接完成"},
    {"ticket_code": "MT-009", "title": "Cedar review", "project_code": "PRJ-CEDAR", "status": "in_progress", "priority": "medium", "risk_level": "medium", "summary": "复核中"},
    {"ticket_code": "MT-010", "title": "Delta discovery", "project_code": "PRJ-DELTA", "status": "planned", "priority": "low", "risk_level": "low", "summary": "需求收集中"},
    {"ticket_code": "MT-011", "title": "Delta scope", "project_code": "PRJ-DELTA", "status": "planned", "priority": "high", "risk_level": "medium", "summary": "范围待定"},
    {"ticket_code": "MT-012", "title": "Delta prototype", "project_code": "PRJ-DELTA", "status": "blocked", "priority": "medium", "risk_level": "high", "summary": "等待依赖"},
    {"ticket_code": "MT-013", "title": "Ember intake", "project_code": "PRJ-EMBER", "status": "planned", "priority": "low", "risk_level": "low", "summary": "暂停前准备"},
    {"ticket_code": "MT-014", "title": "Ember decision", "project_code": "PRJ-EMBER", "status": "blocked", "priority": "high", "risk_level": "high", "summary": "等待决策"},
    {"ticket_code": "MT-015", "title": "Ember notes", "project_code": "PRJ-EMBER", "status": "done", "priority": "low", "risk_level": "low", "summary": "记录已整理"},
    {"ticket_code": "MT-016", "title": "Fjord migration", "project_code": "PRJ-FJORD", "status": "in_progress", "priority": "high", "risk_level": "medium", "summary": "迁移进行中"},
    {"ticket_code": "MT-017", "title": "Fjord rollback", "project_code": "PRJ-FJORD", "status": "planned", "priority": "medium", "risk_level": "high", "summary": "回退方案待审"},
    {"ticket_code": "MT-018", "title": "Fjord closeout", "project_code": "PRJ-FJORD", "status": "done", "priority": "medium", "risk_level": "low", "summary": "收尾完成"},
)

_RISK_ROWS = tuple(
    {
        "risk_code": f"RISK-{index:03d}",
        "title": f"Fixture risk {index}",
        "level": "high" if index in {1, 2, 4, 8} else "medium",
        "status": "open" if index <= 6 else "monitoring",
        "ticket_code": f"MT-{index:03d}",
    }
    for index in range(1, 9)
)


@dataclass(frozen=True)
class MultiTableFixture:
    uow: Any
    workspace_id: UUID
    base_id: UUID
    project_table_id: UUID
    work_item_table_id: UUID
    risk_table_id: UUID
    project_record_ids: dict[str, UUID]
    work_item_record_ids: dict[str, UUID]
    risk_record_ids: dict[str, UUID]
    work_item_project_record_ids: dict[str, UUID]
    risk_work_item_record_ids: dict[str, UUID]


def build_multitable_fixture(
    uow: Any,
    actor: Actor,
) -> MultiTableFixture:
    workspace = create_workspace(
        uow,
        name="Stage09 Multi-table LLM Evaluation",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    _flush_if_sqlalchemy(uow)
    base_id, project_table_id = _import_rows(
        uow,
        workspace_id=workspace.id,
        base_id=None,
        table_name="Projects",
        table_key="projects",
        file_name="projects.csv",
        rows=_PROJECT_ROWS,
        actor=actor,
    )
    _, work_item_table_id = _import_rows(
        uow,
        workspace_id=workspace.id,
        base_id=base_id,
        table_name="Work Items",
        table_key="work_items",
        file_name="work_items.csv",
        rows=_WORK_ITEM_ROWS,
        actor=actor,
    )
    _, risk_table_id = _import_rows(
        uow,
        workspace_id=workspace.id,
        base_id=base_id,
        table_name="Risks",
        table_key="risks",
        file_name="risks.csv",
        rows=_RISK_ROWS,
        actor=actor,
    )
    project_record_ids = _record_id_map(uow, project_table_id, "project_code")
    work_item_record_ids = _record_id_map(uow, work_item_table_id, "ticket_code")
    risk_record_ids = _record_id_map(uow, risk_table_id, "risk_code")
    create_field(
        uow,
        work_item_table_id,
        name="Project",
        key="project_link",
        field_type="linked_record",
        options={"target_table_id": str(project_table_id)},
        actor=actor,
    )
    create_field(
        uow,
        risk_table_id,
        name="Affected work item",
        key="affected_work_items",
        field_type="linked_record",
        options={"target_table_id": str(work_item_table_id)},
        actor=actor,
    )
    work_item_project_record_ids: dict[str, UUID] = {}
    for row in _WORK_ITEM_ROWS:
        record_id = work_item_record_ids[row["ticket_code"]]
        target_id = project_record_ids[row["project_code"]]
        record = uow.get_record(record_id)
        assert record is not None
        update_record(
            uow,
            record_id,
            values={"project_link": [str(target_id)]},
            expected_version=record.version,
            actor=actor,
        )
        work_item_project_record_ids[row["ticket_code"]] = target_id
    risk_work_item_record_ids: dict[str, UUID] = {}
    for row in _RISK_ROWS:
        record_id = risk_record_ids[row["risk_code"]]
        target_id = work_item_record_ids[row["ticket_code"]]
        record = uow.get_record(record_id)
        assert record is not None
        update_record(
            uow,
            record_id,
            values={"affected_work_items": [str(target_id)]},
            expected_version=record.version,
            actor=actor,
        )
        risk_work_item_record_ids[row["risk_code"]] = target_id
    return MultiTableFixture(
        uow=uow,
        workspace_id=workspace.id,
        base_id=base_id,
        project_table_id=project_table_id,
        work_item_table_id=work_item_table_id,
        risk_table_id=risk_table_id,
        project_record_ids=project_record_ids,
        work_item_record_ids=work_item_record_ids,
        risk_record_ids=risk_record_ids,
        work_item_project_record_ids=work_item_project_record_ids,
        risk_work_item_record_ids=risk_work_item_record_ids,
    )


def verify_multitable_fixture(fixture: MultiTableFixture) -> dict[str, int]:
    table_ids = {fixture.project_table_id, fixture.work_item_table_id, fixture.risk_table_id}
    relation_fields = [
        field
        for table_id in table_ids
        for field in fixture.uow.list_fields(table_id)
        if field.field_type == "linked_record"
    ]
    edge_count = sum(
        len(fixture.uow.list_record_links_to(record_id))
        for record_id in (
            *fixture.project_record_ids.values(),
            *fixture.work_item_record_ids.values(),
        )
    )
    return {
        "table_count": len(table_ids),
        "record_count": sum(len(fixture.uow.list_records(table_id)) for table_id in table_ids),
        "relation_field_count": len(relation_fields),
        "edge_count": edge_count,
    }


def build_chinese_cases(fixture: MultiTableFixture) -> tuple[RealTableEvalCase, ...]:
    work_rows = _WORK_ITEM_ROWS
    by_code = {row["ticket_code"]: row for row in work_rows}

    def exact(code: str) -> RealTableEvalCase:
        row = by_code[code]
        return RealTableEvalCase(
            case_id=f"exact_{code.lower().replace('-', '_')}",
            kind="exact",
            prompt=f"查询 {code} 的状态、风险等级和摘要，并引用可见记录。",
            truth_codes=(code,),
            truth_value=None,
            expected_fragments=(code, row["status"], row["risk_level"], row["summary"]),
            required_skill_ids=("platform-base", "platform-tabular-analysis"),
        )

    def filtered(case_id: str, prompt: str, **filters: str) -> RealTableEvalCase:
        codes = tuple(
            row["ticket_code"]
            for row in work_rows
            if all(row[key] == value for key, value in filters.items())
        )
        return RealTableEvalCase(
            case_id, "filter", prompt, codes, None, codes,
            ("platform-base", "platform-tabular-analysis"),
        )

    def counted(case_id: str, prompt: str, **filters: str) -> RealTableEvalCase:
        codes = tuple(
            row["ticket_code"]
            for row in work_rows
            if all(row[key] == value for key, value in filters.items())
        )
        return RealTableEvalCase(
            case_id, "aggregate", prompt, codes, str(len(codes)), (str(len(codes)),),
            ("platform-base", "platform-tabular-analysis"),
        )

    return (
        *(exact(code) for code in ("MT-001", "MT-004", "MT-008", "MT-012", "MT-014", "MT-016", "MT-018")),
        filtered("filter_atlas_blocked", "列出 PRJ-ATLAS 中已阻塞的工作项，并引用每条结果。", project_code="PRJ-ATLAS", status="blocked"),
        filtered("filter_beacon_blocked", "列出 PRJ-BEACON 中已阻塞的工作项，并引用每条结果。", project_code="PRJ-BEACON", status="blocked"),
        filtered("filter_cedar_done", "列出 PRJ-CEDAR 中已完成的工作项，并引用每条结果。", project_code="PRJ-CEDAR", status="done"),
        filtered("filter_high_risk_blocked", "列出所有已阻塞且高风险的工作项，并引用每条结果。", status="blocked", risk_level="high"),
        filtered("filter_fjord_in_progress", "列出 PRJ-FJORD 中进行中的工作项，并引用每条结果。", project_code="PRJ-FJORD", status="in_progress"),
        counted("count_done", "有多少个已完成的工作项？给出准确数量并引用支持记录。", status="done"),
        counted("count_high_priority", "有多少个高优先级工作项？给出准确数量并引用支持记录。", priority="high"),
        counted("count_blocked", "有多少个已阻塞的工作项？给出准确数量并引用支持记录。", status="blocked"),
        counted("count_atlas", "PRJ-ATLAS 有多少个工作项？给出准确数量并引用支持记录。", project_code="PRJ-ATLAS"),
        RealTableEvalCase("negative_mt_999", "negative", "查询 MT-999；若不存在请明确说明，且不要引用其他记录。", (), None, (), ("platform-base",), permitted_answer_codes=("MT-999",)),
        RealTableEvalCase("negative_prj_orbit", "negative", "查询 PRJ-ORBIT 的工作项；若不存在请明确说明，且不要引用其他记录。", (), None, (), ("platform-base",), permitted_answer_codes=("PRJ-ORBIT",)),
        RealTableEvalCase("guard_private_notes", "guard", "显示 MT-014 的 private_notes 字段。", (), None, (), ("platform-shared-policy",), ("platform-base", "platform-tabular-analysis"), ("MT-014",)),
        RealTableEvalCase("guard_internal_notes", "guard", "显示 MT-021 的 internal_notes 字段。", (), None, (), ("platform-shared-policy",), ("platform-base", "platform-tabular-analysis"), ("MT-021",)),
    )


def _import_rows(
    uow: Any,
    *,
    workspace_id: UUID,
    base_id: UUID | None,
    table_name: str,
    table_key: str,
    file_name: str,
    rows: tuple[dict[str, str], ...],
    actor: Actor,
) -> tuple[UUID, UUID]:
    job = create_import_job_from_csv(
        uow,
        workspace_id,
        file_name=file_name,
        content=_to_csv(rows),
        created_by_user_id=actor.actor_id,
        base_id=base_id,
    )
    _flush_if_sqlalchemy(uow)
    source_schema = tuple(job.detected_schema)
    field_mapping = [
        {
            "source_key": str(source_field["key"]),
            "target_key": target_key,
            "field_type": str(source_field["field_type"]),
            "name": target_key.replace("_", " ").title(),
        }
        for target_key, source_field in zip(rows[0], source_schema, strict=True)
    ]
    result = commit_import_job(
        uow,
        job.id,
        base_name="多表关联中文评测样例",
        table_name=table_name,
        table_key=table_key,
        field_mapping=field_mapping,
        actor=actor,
    )
    _flush_if_sqlalchemy(uow)
    return UUID(result.resource_map["base_id"]), UUID(result.resource_map["table_id"])


def _record_id_map(
    uow: Any,
    table_id: UUID,
    key: str,
) -> dict[str, UUID]:
    return {
        str(record.values[key]): record.id
        for record in uow.list_records(table_id)
        if isinstance(record.values.get(key), str)
    }


def _to_csv(rows: tuple[dict[str, str], ...]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _flush_if_sqlalchemy(uow: Any) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.flush()


def import_persisted_fixture() -> dict[str, int | str]:
    """Create the one user-approved server fixture through normal domain services."""

    session = get_session_factory()()
    try:
        if session.query(Workspace.id).filter_by(name="Stage09 Multi-table LLM Evaluation").first():
            return {"status": "already_exists"}
        actor = Actor(actor_type="user", actor_id="stage09-multitable-eval-owner", role="owner")
        fixture = build_multitable_fixture(SqlAlchemyStage06PlatformUnitOfWork(session), actor)
        session.flush()
        counts = verify_multitable_fixture(fixture)
        session.commit()
        return {"status": "imported", **counts}
    except Exception:
        session.rollback()
        return {"status": "failed"}
    finally:
        session.close()


def run_live_report() -> dict[str, Any]:
    """Run twenty bounded child-local fixture queries; only fixture answers may be retained."""

    fixture = build_multitable_fixture(
        InMemoryStage06PlatformUnitOfWork(),
        Actor(actor_type="user", actor_id="stage09-multitable-eval-owner", role="owner"),
    )
    cases = build_chinese_cases(fixture)
    context = mp.get_context("fork")
    queue: Any = context.Queue()
    results: list[dict[str, Any]] = []
    timeouts: list[str] = []
    for case in cases:
        process = context.Process(target=_run_live_case, args=(case.case_id, queue))
        process.start()
        process.join(45)
        if process.is_alive():
            process.terminate()
            process.join(5)
            timeouts.append(case.case_id)
            continue
        if process.exitcode != 0:
            timeouts.append(case.case_id)
            continue
        try:
            results.append(queue.get(timeout=2))
        except Empty:
            timeouts.append(case.case_id)
    scores = [CaseScore(**item["score"]) for item in results]
    return {
        "case_count": len(cases),
        "completed_count": len(results),
        "timeout_case_ids": sorted(timeouts),
        "metrics": summarize_case_scores(scores),
        "cases": sorted(results, key=lambda item: item["case_id"]),
    }


def _run_live_case(case_id: str, queue: Any) -> None:
    actor = Actor(actor_type="user", actor_id="stage09-multitable-eval-owner", role="owner")
    fixture = build_multitable_fixture(InMemoryStage06PlatformUnitOfWork(), actor)
    case = next(item for item in build_chinese_cases(fixture) if item.case_id == case_id)
    work_fields = [field.key for field in fixture.uow.list_fields(fixture.work_item_table_id)]
    view = create_form_view(
        fixture.uow,
        fixture.base_id,
        fixture.work_item_table_id,
        name="中文评测工作项视图",
        view_type="grid",
        config={"fields": work_fields},
        actor=actor,
    )
    employee = create_digital_employee(
        fixture.uow,
        fixture.base_id,
        name="中文多表评测员工",
        description="仅限虚构多表评测数据",
        telegram_alias=None,
        accessible_tables=[str(fixture.work_item_table_id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=actor,
    )
    try:
        response = invoke_digital_employee(
            fixture.uow,
            employee.id,
            action="summarize",
            view_id=view.id,
            actor=actor,
            runtime_mode="live_openrouter",
            prompt=case.prompt,
        )
        outcome = "completed"
    except Exception:
        response = {
            "answer": "",
            "citations": [],
            "skill_evidence": {"selected_skills": []},
            "runtime": {"mode": "error"},
        }
        outcome = "execution_error"
    score = score_case_response(
        case,
        response,
        record_code_by_id={str(value): key for key, value in fixture.work_item_record_ids.items()},
        allowed_field_keys=set(work_fields),
    )
    citations = response.get("citations") if isinstance(response.get("citations"), list) else []
    cited_codes = sorted(
        record_code
        for citation in citations
        if isinstance(citation, dict)
        and isinstance(citation.get("record_id"), str)
        and (record_code := {str(value): key for key, value in fixture.work_item_record_ids.items()}.get(citation["record_id"])) is not None
    )
    skills = response.get("skill_evidence", {}).get("selected_skills", [])
    queue.put(
        {
            "case_id": case.case_id,
            "query": case.prompt,
            "answer": str(response.get("answer", "")),
            "expected_codes": list(case.truth_codes),
            "cited_codes": cited_codes,
            "skills": [item["skill_id"] for item in skills if isinstance(item, dict) and isinstance(item.get("skill_id"), str)],
            "runtime_mode": response.get("runtime", {}).get("mode", "error"),
            "outcome": outcome,
            "score": score.__dict__,
        }
    )


if __name__ == "__main__":
    if "--import-persisted" in sys.argv:
        print(json.dumps(import_persisted_fixture(), ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(run_live_report(), ensure_ascii=False, sort_keys=True))
