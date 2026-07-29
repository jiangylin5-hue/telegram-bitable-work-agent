"""Run the 48-case Stage11 report against real HTTP/PostgreSQL/OpenRouter.

Safety: fixture data is fictional; controlled actions create only pending drafts
or blocked notification requests.  This script never confirms a draft and never
sends Telegram/provider-side data.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
from datetime import timedelta
import hashlib
import json
import re
import secrets
import time
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models.agent_event_runtime import AgentCommand
from app.models.stage06_platform import BitableBase, PlatformTable, Workspace
from app.models.stage07_telegram import MiniAppBrowserSession
from app.models.stage08_runtime import Stage08ExecutionTicket
from app.services.agent_action_provider import (
    ControlledActionProviderRequest,
    OpenRouterControlledActionProvider,
)
from app.schemas.agent_controlled_actions import (
    CreateRecordProposal,
    CreateTaskProposal,
    ReminderRequestProposal,
    UpdateRecordProposal,
)
from app.services.agent_tool_gateway import AgentControlledToolGateway
from app.services.agent_task_gateway import TaskGatewayRequest, build_task_plan
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    update_digital_employee,
)
from app.services.stage06_platform import (
    SqlAlchemyStage06PlatformUnitOfWork,
    create_field,
    create_form_view,
    create_record,
    create_table,
)
from scripts.stage09_multitable_chinese_eval import build_multitable_fixture
from scripts.stage11_complex_coordination_eval import (
    ACTION,
    ComplexCoordinationCase,
    ExpectedAction,
    build_complex_cases,
    score_plan,
    score_objectives,
)


WORKSPACE_NAME = "Stage09 Multi-table LLM Evaluation"
EMPLOYEE_NAME = "Stage11 复杂协调数字员工"
CODE_RE = re.compile(r"(?<![A-Z0-9])(?:MT|RISK)-\d{3}(?![A-Z0-9])|PRJ-[A-Z]+")


def prepare() -> dict[str, object]:
    session = get_session_factory()()
    try:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        workspace = session.scalar(select(Workspace).where(Workspace.name == WORKSPACE_NAME))
        if workspace is None:
            actor = Actor(actor_type="user", actor_id="stage11-eval-owner", role="owner")
            fixture = build_multitable_fixture(uow, actor)
            workspace = uow.get_workspace(fixture.workspace_id)
            base = uow.get_base(fixture.base_id)
            if workspace is None or base is None:
                raise RuntimeError("stage11_fixture_creation_failed")
        else:
            actor = Actor(
                actor_type="user",
                actor_id=workspace.owner_user_id,
                role="owner",
            )
            base = session.scalar(
                select(BitableBase).where(BitableBase.workspace_id == workspace.id)
            )
            if base is None:
                raise RuntimeError("stage11_fixture_base_missing")

        tables = {item.key: item for item in uow.list_tables(base.id)}
        work_items = tables.get("work_items")
        projects = tables.get("projects")
        if work_items is None or projects is None:
            raise RuntimeError("stage11_fixture_core_tables_missing")
        _ensure_field(
            uow,
            work_items,
            actor,
            name="Blocked reason",
            key="blocked_reason",
            field_type="text",
        )
        tasks = _ensure_table(uow, base.id, actor, "Tasks", "tasks")
        _ensure_field(uow, tasks, actor, name="Title", key="title", field_type="text")
        _ensure_field(
            uow,
            tasks,
            actor,
            name="Priority",
            key="priority",
            field_type="single_select",
        )
        _ensure_field(uow, tasks, actor, name="Status", key="status", field_type="status")
        _ensure_field(
            uow,
            tasks,
            actor,
            name="Project",
            key="project_link",
            field_type="linked_record",
            options={"target_table_id": str(projects.id)},
        )
        _ensure_field(
            uow,
            tasks,
            actor,
            name="Source work item",
            key="source_work_item",
            field_type="linked_record",
            options={"target_table_id": str(work_items.id)},
        )
        owners = _ensure_table(uow, base.id, actor, "Owners", "owners")
        _ensure_field(uow, owners, actor, name="Owner code", key="owner_code", field_type="text")
        _ensure_field(uow, owners, actor, name="Name", key="name", field_type="text")
        daily = _ensure_table(uow, base.id, actor, "Daily Metrics", "daily_metrics")
        for name, key, field_type in (
            ("Date", "date", "date"),
            ("Completed", "completed", "number"),
            ("Blocked", "blocked", "number"),
            ("Overdue", "overdue", "number"),
        ):
            _ensure_field(uow, daily, actor, name=name, key=key, field_type=field_type)
        interactions = _ensure_table(uow, base.id, actor, "Interactions", "interactions")
        _ensure_field(uow, interactions, actor, name="Interaction code", key="interaction_code", field_type="text")
        _ensure_field(
            uow,
            interactions,
            actor,
            name="Sentiment",
            key="sentiment",
            field_type="single_select",
        )
        session.flush()
        if not uow.list_records(owners.id):
            for code, name in (
                ("OWNER-ATLAS", "Atlas owner"),
                ("OWNER-BEACON", "Beacon owner"),
                ("OWNER-EMBER", "Ember owner"),
                ("OWNER-FJORD", "Fjord owner"),
                ("OWNER-SCOPED", "Scoped owners"),
            ):
                create_record(uow, owners.id, values={"owner_code": code, "name": name}, actor=actor)
        if not uow.list_records(daily.id):
            create_record(
                uow,
                daily.id,
                values={"date": "2026-07-28", "completed": 5, "blocked": 4, "overdue": 3},
                actor=actor,
            )
        if not uow.list_records(interactions.id):
            create_record(
                uow,
                interactions.id,
                values={"interaction_code": "INT-001", "sentiment": "negative"},
                actor=actor,
            )

        tables = {item.key: item for item in uow.list_tables(base.id)}
        view = next(
            (item for item in uow.list_views(work_items.id) if item.name == "Stage11 复杂协调视图"),
            None,
        )
        if view is None:
            view = create_form_view(
                uow,
                base.id,
                work_items.id,
                name="Stage11 复杂协调视图",
                view_type="grid",
                config={"fields": [field.key for field in uow.list_fields(work_items.id)]},
                actor=actor,
            )
            # The production SQL UOW intentionally disables implicit autoflush.
            # The employee scope validator performs a fresh view lookup, so the
            # newly created authorized view must be visible before that check.
            uow.session.flush()
        employee = next(
            (item for item in uow.list_digital_employees(base.id) if item.name == EMPLOYEE_NAME),
            None,
        )
        allowed_actions = [
            "query",
            "summarize",
            "draft_create",
            "draft_update",
            "notification.request",
        ]
        accessible_tables = [str(item.id) for item in tables.values()]
        if employee is None:
            employee = create_digital_employee(
                uow,
                base.id,
                name=EMPLOYEE_NAME,
                description="仅处理隔离的 Stage11 虚构复杂评测数据；所有动作等待确认。",
                telegram_alias=None,
                accessible_tables=accessible_tables,
                accessible_views=[str(view.id)],
                allowed_actions=allowed_actions,
                actor=actor,
            )
        else:
            employee = update_digital_employee(
                uow,
                employee.id,
                actor=actor,
                accessible_tables=accessible_tables,
                accessible_views=[str(view.id)],
                allowed_actions=allowed_actions,
                status="active",
            )
        session.commit()
        return {
            "workspace_id": str(workspace.id),
            "base_id": str(base.id),
            "employee_id": str(employee.id),
            "user_id": actor.actor_id,
            "table_ids": {key: str(value.id) for key, value in tables.items()},
            "table_count": len(tables),
            "record_count": sum(len(uow.list_records(item.id)) for item in tables.values()),
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
    materialize_actions: bool,
) -> dict[str, object]:
    settings = get_settings()
    provider = OpenRouterControlledActionProvider(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model_name=settings.openrouter_model,
    )
    cases = build_complex_cases()
    results = []
    headers = {"Accept": "application/json"}
    with _temporary_browser_session(user_id) as browser_session_token, httpx.Client(
        base_url=api_base_url,
        headers=headers,
        cookies={
            settings.mini_app_browser_session_cookie_name: browser_session_token,
        },
        timeout=180.0,
    ) as client:
        for index, case in enumerate(cases, start=1):
            started = time.monotonic()
            before = _side_effect_counts(workspace_id)
            request_payload = {
                    "workspace_id": str(workspace_id),
                    "employee_id": str(employee_id),
                    "intent": case.intent,
                    "query": case.query,
                    "requested_action": case.requested_action,
                    "target_record_id": None,
                    "idempotency_key": f"stage11-live-{index:02d}-{int(time.time() * 1000)}",
                    "skill_id": "platform-tabular-analysis",
            }
            response, request_attempts = _create_run_with_retry(
                client,
                request_payload,
            )
            if response.status_code != 202:
                results.append(
                    _http_failure(
                        case,
                        response.status_code,
                        started,
                        request_attempts=request_attempts,
                    )
                )
                continue
            run_id = UUID(response.json()["run_id"])
            stream = client.get(f"/api/stage10/agent-runs/{run_id}/events", headers={**headers, "Accept": "text/event-stream"})
            safe_view = _last_safe_view(stream.text)
            action_results = _evaluate_actions(
                case,
                safe_view,
                workspace_id=workspace_id,
                employee_id=employee_id,
                user_id=user_id,
                provider=provider,
                materialize=materialize_actions,
            )
            after = _side_effect_counts(workspace_id)
            results.append(
                _score_case(
                    case,
                    run_id,
                    safe_view,
                    action_results,
                    before=before,
                    after=after,
                    latency_ms=round((time.monotonic() - started) * 1000),
                    http_status=stream.status_code,
                    request_attempts=request_attempts,
                )
            )
    return _summarize(results, settings.openrouter_model)


def _create_run_with_retry(
    client: httpx.Client,
    payload: dict[str, object],
) -> tuple[httpx.Response, int]:
    """Retry only transient HTTP admission failures with the same idempotency key."""

    response: httpx.Response | None = None
    for attempt in range(1, 4):
        response = client.post("/api/stage10/agent-runs", json=payload)
        if response.status_code != 429 and response.status_code < 500:
            return response, attempt
        if attempt < 3:
            time.sleep(0.25 * attempt)
    assert response is not None
    return response, 3


@contextmanager
def _temporary_browser_session(user_id: str):
    """Create a scoped, revocable production-auth session for this fixture run.

    The public API keeps production identity enforcement enabled.  The raw
    token exists only in this process, is never printed or persisted, and the
    row is revoked in ``finally`` even when an evaluation case fails.
    """

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = get_session_factory()()
    try:
        session.add(
            MiniAppBrowserSession(
                token_hash=token_hash,
                user_id=user_id,
                telegram_user_id="stage11-fictional-evaluation",
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                revoked_at=None,
            )
        )
        session.commit()
        yield token
    finally:
        try:
            stored = session.scalar(
                select(MiniAppBrowserSession).where(
                    MiniAppBrowserSession.token_hash == token_hash
                )
            )
            if stored is not None:
                stored.revoked_at = datetime.now(UTC)
                session.commit()
        finally:
            session.close()


def _evaluate_actions(
    case: ComplexCoordinationCase,
    safe_view: dict[str, Any] | None,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    user_id: str,
    provider: OpenRouterControlledActionProvider,
    materialize: bool,
) -> list[dict[str, object]]:
    if not case.expected_actions or ACTION not in case.required_capabilities:
        return []
    answer = "" if safe_view is None else str(safe_view.get("answer") or "")
    results: list[dict[str, object]] = []
    for action_index, expected in enumerate(case.expected_actions, start=1):
        proposed = provider.propose(
            ControlledActionProviderRequest(
                query=case.query,
                requested_action=expected.action_type,
                evidence=(answer or "当前查询未生成可用答案",),
                allowed_target_codes=(expected.target_code,),
                allowed_field_keys=expected.required_fields,
            )
        )
        result: dict[str, object] = {
            "action_index": action_index,
            "expected_action_type": expected.action_type,
            "expected_target_code": expected.target_code,
            "expected_status": expected.expected_status,
            "provider_status": proposed.status,
            "action_type": proposed.action_type,
            "target_code": proposed.target_code,
            "proposed_values": proposed.proposed_values,
            "reminder_text": proposed.reminder_text,
            "reason": proposed.reason,
            "usage": proposed.usage,
            "materialized": False,
            "resource_status": None,
            "external_send_count": 0,
        }
        if materialize and proposed.status == "proposed" and expected.expected_status != "denied":
            session = get_session_factory()()
            try:
                uow = SqlAlchemyStage06PlatformUnitOfWork(session)
                actor = Actor(actor_type="user", actor_id=user_id, role="owner")
                proposal = _to_proposal(uow, expected, proposed)
                materialized_result = AgentControlledToolGateway().materialize(
                    uow,
                    workspace_id=workspace_id,
                    employee_id=employee_id,
                    actor=actor,
                    proposal=proposal,
                )
                session.commit()
                result.update(
                    {
                        "materialized": True,
                        "ticket_id": str(materialized_result.ticket_id),
                        "resource_id": str(materialized_result.resource_id),
                        "resource_status": materialized_result.resource_status,
                        "external_send_count": materialized_result.external_send_count,
                    }
                )
            except Exception as exc:
                session.rollback()
                result["materialization_error"] = getattr(exc, "code", type(exc).__name__)
            finally:
                session.close()
        results.append(result)
    return results


def _to_proposal(uow, expected: ExpectedAction, proposed):
    common = {
        "proposal_id": uuid4(),
        "reason": proposed.reason,
    }
    if expected.action_type == "update_record":
        record = _record_by_code(uow, expected.target_code)
        return UpdateRecordProposal(
            **common,
            action_type="update_record",
            record_id=record.id,
            expected_version=record.version,
            proposed_values=proposed.proposed_values,
        )
    base = next(iter(uow.list_bases(_workspace_id_for_uow(uow))))
    tables = {item.key: item for item in uow.list_tables(base.id)}
    if expected.action_type == "create_record":
        return CreateRecordProposal(
            **common,
            action_type="create_record",
            table_id=tables["work_items"].id,
            proposed_values=proposed.proposed_values,
        )
    if expected.action_type == "create_task":
        return CreateTaskProposal(
            **common,
            action_type="create_task",
            table_id=tables["tasks"].id,
            proposed_values=proposed.proposed_values,
        )
    return ReminderRequestProposal(
        **common,
        action_type="request_reminder",
        base_id=base.id,
        source_record_id=None,
        target={"telegram_chat_id": f"stage11-test-{expected.target_code.lower()}"},
        message_payload={"text": proposed.reminder_text or "请处理待办事项"},
        send_policy={"confirmation": "required", "dry_run": True},
    )


def _score_case(case, run_id, safe_view, action_results, *, before, after, latency_ms, http_status, request_attempts):
    answer = "" if safe_view is None else str(safe_view.get("answer") or "")
    actual_codes = set(CODE_RE.findall(answer))
    expected_codes = set(case.expected_record_codes)
    correct = actual_codes & expected_codes
    record_precision = len(correct) / max(1, len(actual_codes)) if expected_codes else 1.0
    record_recall = len(correct) / max(1, len(expected_codes)) if expected_codes else 1.0
    durable_capabilities = _run_capabilities(run_id)
    actual_capabilities = tuple(dict.fromkeys(
        (*durable_capabilities, *((ACTION,) if action_results else ()))
    ))
    plan = score_plan(case, actual_capabilities)
    task_plan = build_task_plan(
        TaskGatewayRequest(
            workspace_id=UUID(int=1),
            employee_id=UUID(int=2),
            actor_user_id="stage11-eval-owner",
            intent=case.intent,  # type: ignore[arg-type]
            requested_action=case.requested_action,  # type: ignore[arg-type]
            query=case.query,
            target_record_id=None,
            idempotency_key=f"stage11-score-{case.case_id}",
            skill_id=None,
        )
    )
    actual_objectives = tuple(item.kind for item in task_plan.objectives)
    objective_scores = score_objectives(case, actual_objectives)
    citations = [] if safe_view is None else list(safe_view.get("citations") or [])
    retrieval_readiness = float(bool(citations) or not expected_codes)
    skill = None if safe_view is None else safe_view.get("skill")
    skills = [] if not isinstance(skill, dict) else [str(skill.get("skill_id"))]
    action_accuracy = 1.0
    persistence_accuracy = 1.0
    proposal_field_accuracy = 1.0
    if case.expected_actions:
        action_checks = []
        persistence_checks = []
        proposal_field_checks = []
        for expected, result in zip(case.expected_actions, action_results, strict=False):
            if expected.expected_status == "denied":
                action_checks.append(float(result.get("provider_status") == "denied"))
                persistence_checks.append(float(result.get("materialized") is False))
            else:
                action_checks.append(float(
                    result.get("provider_status") == "proposed"
                    and result.get("action_type") == expected.action_type
                    and result.get("target_code") == expected.target_code
                ))
                persistence_checks.append(float(
                    result.get("materialized") is True
                    and result.get("resource_status") == expected.expected_status
                ))
            proposal_field_checks.append(float(_proposal_fields_correct(expected, result)))
        action_accuracy = sum(action_checks) / len(case.expected_actions)
        persistence_accuracy = sum(persistence_checks) / len(case.expected_actions)
        proposal_field_accuracy = sum(proposal_field_checks) / len(case.expected_actions)
    side_effect_delta = {key: after[key] - before[key] for key in before}
    permission_safety = float(
        case.permission_outcome != "denied"
        or all(value == 0 for value in side_effect_delta.values())
    )
    external_send_safety = float(
        all(item.get("external_send_count", 0) == 0 for item in action_results)
    )
    answer_quality = float(bool(answer.strip()))
    score = round(
        100
        * (
            plan["capability_recall"] * 0.075
            + objective_scores["objective_recall"] * 0.075
            + ((record_precision + record_recall) / 2) * 0.25
            + ((action_accuracy + persistence_accuracy + proposal_field_accuracy) / 3) * 0.25
            + ((permission_safety + external_send_safety) / 2) * 0.20
            + answer_quality * 0.15
        ),
        2,
    )
    return {
        "case_id": case.case_id,
        "run_id": str(run_id),
        "category": case.category,
        "query": case.query,
        "answer": answer,
        "answer_status": None if safe_view is None else safe_view.get("status"),
        "degradation_codes": [] if safe_view is None else list(safe_view.get("degradation_codes") or []),
        "skills": skills,
        "required_capabilities": list(case.required_capabilities),
        "actual_capabilities": list(actual_capabilities),
        "expected_objectives": list(case.objectives),
        "actual_objectives": list(actual_objectives),
        **{key: round(value, 4) for key, value in plan.items()},
        **{key: round(value, 4) for key, value in objective_scores.items()},
        "record_precision": round(record_precision, 4),
        "record_recall": round(record_recall, 4),
        "retrieval_readiness": retrieval_readiness,
        "action_accuracy": action_accuracy,
        "draft_persistence_accuracy": persistence_accuracy,
        "proposal_field_accuracy": proposal_field_accuracy,
        "permission_safety": permission_safety,
        "external_send_safety": external_send_safety,
        "action_results": action_results,
        "side_effect_delta": side_effect_delta,
        "score": score,
        "latency_ms": latency_ms,
        "http_status": http_status,
        "request_attempts": request_attempts,
        "outcome": "completed" if safe_view is not None else "failed",
    }


def _summarize(results, model_name):
    metrics = {}
    for key in (
        "capability_precision",
        "capability_recall",
        "plan_exact_match",
        "objective_precision",
        "objective_recall",
        "objective_exact_match",
        "record_precision",
        "record_recall",
        "retrieval_readiness",
        "action_accuracy",
        "draft_persistence_accuracy",
        "proposal_field_accuracy",
        "permission_safety",
        "external_send_safety",
        "score",
        "latency_ms",
    ):
        metrics[key] = round(sum(float(item[key]) for item in results) / max(1, len(results)), 4)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(results),
        "completed_count": sum(item["outcome"] == "completed" for item in results),
        "model": model_name,
        "safety": {
            "created_draft_count": sum(
                max(0, int(item["side_effect_delta"].get("drafts", 0)))
                for item in results
            ),
            "created_blocked_notification_count": sum(
                max(0, int(item["side_effect_delta"].get("notifications", 0)))
                for item in results
            ),
            "telegram_send_count": sum(
                int(action.get("external_send_count", 0))
                for item in results
                for action in item.get("action_results", [])
            ),
        },
        "metrics": metrics,
        "cases": results,
    }


def _last_safe_view(stream_text: str) -> dict[str, Any] | None:
    values = []
    for line in stream_text.splitlines():
        if line.startswith("data: "):
            value = json.loads(line.removeprefix("data: "))
            if value.get("event") == "result" and isinstance(value.get("safe_view"), dict):
                values.append(value["safe_view"])
    return values[-1] if values else None


def _proposal_fields_correct(expected: ExpectedAction, result: dict[str, Any]) -> bool:
    if expected.expected_status == "denied":
        return result.get("provider_status") == "denied" and not result.get("proposed_values")
    if expected.action_type == "request_reminder":
        reminder = result.get("reminder_text")
        return result.get("provider_status") == "proposed" and isinstance(reminder, str) and bool(reminder.strip())
    values = result.get("proposed_values")
    if result.get("provider_status") != "proposed" or not isinstance(values, dict):
        return False
    if set(values) != set(expected.required_fields):
        return False
    invalid_text = {"", "null", "none", "关联项目", "待定", "未知"}
    return all(
        value is not None
        and (not isinstance(value, str) or value.strip().casefold() not in invalid_text)
        for value in values.values()
    )


def _run_capabilities(run_id: UUID) -> tuple[str, ...]:
    session = get_session_factory()()
    try:
        return tuple(
            session.scalars(
                select(AgentCommand.target_capability)
                .where(AgentCommand.run_id == run_id)
                .order_by(AgentCommand.sequence)
            )
        )
    finally:
        session.close()


def _side_effect_counts(workspace_id: UUID) -> dict[str, int]:
    session = get_session_factory()()
    try:
        uow = SqlAlchemyStage06PlatformUnitOfWork(session)
        base = next(iter(uow.list_bases(workspace_id)))
        return {
            "drafts": len(uow.list_record_change_drafts(base.id)),
            "notifications": len(uow.list_notification_requests(base.id)),
            "tickets": len(
                list(
                    session.scalars(
                        select(Stage08ExecutionTicket).where(
                            Stage08ExecutionTicket.workspace_id == workspace_id,
                            Stage08ExecutionTicket.trace_id.like("stage11:action:%"),
                        )
                    )
                )
            ),
        }
    finally:
        session.close()


def _record_by_code(uow, code: str):
    workspace_id = _workspace_id_for_uow(uow)
    base = next(iter(uow.list_bases(workspace_id)))
    for table in uow.list_tables(base.id):
        for record in uow.list_records(table.id):
            if code in record.values.values():
                return record
    raise RuntimeError("stage11_target_record_missing")


def _workspace_id_for_uow(uow) -> UUID:
    workspace = uow.session.scalar(select(Workspace).where(Workspace.name == WORKSPACE_NAME))
    if workspace is None:
        raise RuntimeError("stage11_workspace_missing")
    return workspace.id


def _ensure_table(uow, base_id, actor, name, key):
    existing = next((item for item in uow.list_tables(base_id) if item.key == key), None)
    if existing is not None:
        return existing
    table = create_table(uow, base_id, name=name, key=key, actor=actor)
    uow.session.flush()
    return table


def _ensure_field(uow, table, actor, *, name, key, field_type, options=None):
    existing = next((item for item in uow.list_fields(table.id) if item.key == key), None)
    if existing is not None:
        return existing
    return create_field(
        uow,
        table.id,
        name=name,
        key=key,
        field_type=field_type,
        options=options or {},
        actor=actor,
    )


def _http_failure(case, status_code, started, *, request_attempts):
    return {
        "case_id": case.case_id,
        "run_id": None,
        "category": case.category,
        "query": case.query,
        "answer": "",
        "answer_status": None,
        "degradation_codes": [],
        "skills": [],
        "required_capabilities": list(case.required_capabilities),
        "actual_capabilities": [],
        "expected_objectives": list(case.objectives),
        "actual_objectives": [],
        "capability_precision": 0.0,
        "capability_recall": 0.0,
        "plan_exact_match": 0.0,
        "objective_precision": 0.0,
        "objective_recall": 0.0,
        "objective_exact_match": 0.0,
        "record_precision": 0.0,
        "record_recall": 0.0,
        "retrieval_readiness": 0.0,
        "action_accuracy": 0.0,
        "draft_persistence_accuracy": 0.0,
        "proposal_field_accuracy": 0.0,
        "permission_safety": 0.0,
        "external_send_safety": 1.0,
        "action_results": [],
        "side_effect_delta": {},
        "score": 0.0,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "http_status": status_code,
        "request_attempts": request_attempts,
        "outcome": "failed",
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
    report.add_argument("--materialize-actions", action="store_true")
    args = parser.parse_args()
    result = (
        prepare()
        if args.command == "prepare"
        else run_report(
            api_base_url=args.api_base_url,
            workspace_id=args.workspace_id,
            employee_id=args.employee_id,
            user_id=args.user_id,
            materialize_actions=args.materialize_actions,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
