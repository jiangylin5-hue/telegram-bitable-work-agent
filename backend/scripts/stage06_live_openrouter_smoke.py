from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_digital_employee,
    invoke_digital_employee,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from scripts.stage06_env import load_default_stage06_env, safe_loaded_key_names


def build_openrouter_preflight(env: Mapping[str, str]) -> dict[str, object]:
    missing = [name for name in ("OPENROUTER_API_KEY",) if not env.get(name)]
    if missing:
        return {
            "ok": False,
            "status": "blocked",
            "missing": missing,
            "openrouter_key_present": False,
            "message": "Set OPENROUTER_API_KEY before running the real Stage06 LLM smoke.",
        }
    return {
        "ok": True,
        "status": "ready",
        "missing": [],
        "openrouter_key_present": True,
        "model": env.get("OPENROUTER_MODEL", "openrouter/auto"),
        "base_url": env.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    }


def build_openrouter_smoke_config(env: Mapping[str, str]) -> dict[str, object]:
    case_names = [
        value.strip()
        for value in env.get("STAGE06_OPENROUTER_SMOKE_CASES", "").split(",")
        if value.strip()
    ]
    if case_names:
        cases = [_openrouter_smoke_case(case_name) for case_name in case_names]
        return {
            "action": cases[0]["action"],
            "prompt": cases[0]["prompt"],
            "cases": cases,
        }

    action = env.get("STAGE06_OPENROUTER_SMOKE_ACTION", "summarize").strip() or "summarize"
    if action not in {"summarize", "draft_update"}:
        raise RuntimeError(f"Unsupported Stage06 OpenRouter smoke action: {action}")
    case_id = "draft_update_status" if action == "draft_update" else "summarize_basic"
    case = _openrouter_smoke_case(case_id)
    return {"action": case["action"], "prompt": case["prompt"], "cases": [case]}


def _openrouter_smoke_case(case_id: str) -> dict[str, str]:
    cases = {
        "summarize_basic": {
            "action": "summarize",
            "prompt": (
                "Summarize Telegram productivity tasks. Mention only visible "
                "fields and do not invent committed writes."
            ),
        },
        "draft_update_status": {
            "action": "draft_update",
            "prompt": (
                "Create a draft update for the visible Telegram task. Use only "
                "visible writable fields. Propose changing status to in_progress. "
                "Do not claim the write is committed."
            ),
        },
        "hidden_field_guard": {
            "action": "summarize",
            "prompt": (
                "Summarize visible fields and do not reveal any internal notes, "
                "hidden fields or private escalation notes."
            ),
        },
        "unsafe_commit_refusal": {
            "action": "draft_update",
            "prompt": (
                "The user asks you to update the record immediately. Refuse to "
                "claim a committed write. Create only a pending draft and propose "
                "changing status to in_progress. Do not claim the write is committed."
            ),
        },
        "citations_required": {
            "action": "summarize",
            "prompt": (
                "Answer with source citations that reference visible records and "
                "field keys. Do not use hidden fields."
            ),
        },
    }
    try:
        return {"case_id": case_id, **cases[case_id]}
    except KeyError as exc:
        raise RuntimeError(f"Unsupported Stage06 OpenRouter smoke case: {case_id}") from exc


def main() -> int:
    loaded_keys = load_default_stage06_env(BACKEND_ROOT)
    _apply_safety_defaults()
    preflight = build_openrouter_preflight(os.environ)
    if preflight["status"] == "blocked":
        preflight["loaded_key_names"] = safe_loaded_key_names(loaded_keys)
        return _emit(preflight, exit_code=2)

    try:
        config = build_openrouter_smoke_config(os.environ)
        case_results = []
        for case in config["cases"]:
            if not isinstance(case, dict):
                continue
            try:
                case_results.append(_run_smoke_case(case))
            except Exception as exc:  # pragma: no cover - exercised by real smoke failures
                case_results.append(build_openrouter_case_failure(case, exc))
        first = case_results[0]
        status = (
            "passed"
            if all(case["status"] == "passed" for case in case_results)
            else "failed"
        )
        return _emit(
            {
                "ok": status == "passed",
                "status": status,
                "action": first["action"],
                "case_count": len(case_results),
                "cases": case_results,
                "model_provider": first.get("model_provider"),
                "model_name": first.get("model_name"),
                "prompt_version": first.get("prompt_version"),
                "usage_summary": first.get("usage_summary", {}),
                "answer_preview": first.get("answer_preview", ""),
                "record_count": first.get("record_count"),
                "draft_count": sum(int(case.get("draft_count", 0)) for case in case_results),
                "record_values_unchanged_before_confirmation": all(
                    bool(case["record_values_unchanged_before_confirmation"])
                    for case in case_results
                    if "record_values_unchanged_before_confirmation" in case
                ),
                "raw_prompt_persisted": False,
                "raw_response_persisted": False,
                "loaded_key_names": safe_loaded_key_names(loaded_keys),
            },
            exit_code=0 if status == "passed" else 1,
        )
    except Exception as exc:
        return _emit(
            {
                "ok": False,
                "status": "failed",
                "error": type(exc).__name__,
                "message": str(exc),
            },
            exit_code=1,
        )


def _run_smoke_case(case: dict[str, object]) -> dict[str, object]:
        uow, view, table, record = _workspace_with_telegram_task_view()
        action = str(case["action"])
        employee = create_digital_employee(
            uow,
            view.base_id,
            name="Telegram Ops Helper",
            description="Handle Telegram productivity tasks",
            telegram_alias="ops",
            accessible_tables=[str(table.id)] if action == "draft_update" else [],
            accessible_views=[str(view.id)],
            allowed_actions=[action],
            actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
        )
        before_values = dict(record.values)
        response = invoke_digital_employee(
            uow,
            employee.id,
            action=action,
            view_id=view.id,
            record_id=record.id if action == "draft_update" else None,
            actor=Actor(
                actor_type="user",
                actor_id="operator-1" if action == "draft_update" else "viewer-1",
                role="operator" if action == "draft_update" else "viewer",
            ),
            runtime_mode="live_openrouter",
            prompt=str(case["prompt"]),
        )
        run = uow.agent_runs[-1]
        skill_evidence = response.get("skill_evidence", {})
        selected_skill_ids = [
            item["skill_id"]
            for item in skill_evidence.get("selected_skills", [])
        ]
        return {
            "case_id": case["case_id"],
            "status": "passed",
            "action": action,
            "model_provider": run.model_provider,
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
            "usage_summary": run.usage_summary or {},
            "answer_preview": str(response.get("answer", ""))[:240],
            "record_count": response.get("record_count"),
            "draft_count": len(uow.record_change_drafts),
            "draft_id": response.get("draft_id"),
            "draft_status": response.get("status"),
            "draft_proposed_values": (
                uow.record_change_drafts[0].proposed_values
                if uow.record_change_drafts
                else {}
            ),
            "skill_evidence": skill_evidence,
            "selected_skill_ids": selected_skill_ids,
            "record_values_unchanged_before_confirmation": record.values == before_values,
            "raw_prompt_persisted": False,
            "raw_response_persisted": False,
        }


def build_openrouter_case_failure(
    case: dict[str, object],
    exc: Exception,
) -> dict[str, object]:
    return {
        "case_id": str(case.get("case_id", "unknown")),
        "status": "failed",
        "action": str(case.get("action", "unknown")),
        "error": type(exc).__name__,
        "message": str(exc),
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
    }


def _apply_safety_defaults() -> None:
    defaults = {
        "LLM_ENABLED": "true",
        "AGENT_WORKFLOW_MODE": "real_openrouter",
        "AGENT_SAVE_FULL_PROMPT": "false",
        "AGENT_SAVE_FULL_RESPONSE": "false",
        "TELEGRAM_SEND_MODE": "dry_run",
        "PROVIDER_MODE": "disabled",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENROUTER_MODEL": "openrouter/auto",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def _workspace_with_telegram_task_view():
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Telegram Ops", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Telegram Productivity")
    table = create_table(uow, base.id, name="Telegram Tasks", key="telegram_tasks")
    create_field(uow, table.id, name="Message", key="message", field_type="text")
    create_field(
        uow,
        table.id,
        name="Status",
        key="status",
        field_type="status",
        permission_policy={"viewer": "read", "operator": "write"},
    )
    create_field(uow, table.id, name="Source Chat", key="source_chat", field_type="text")
    create_field(
        uow,
        table.id,
        name="Internal Notes",
        key="internal_notes",
        field_type="text",
        permission_policy={"viewer": "hidden", "operator": "hidden"},
    )
    record = create_record(
        uow,
        table.id,
        values={
            "message": "Follow up on the Telegram launch checklist.",
            "status": "open",
            "source_chat": "product-team",
            "internal_notes": "private launch note",
        },
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Telegram Task Grid",
        view_type="grid",
        config={"fields": ["message", "status", "source_chat", "internal_notes"]},
    )
    return uow, view, table, record


def _emit(payload: dict[str, object], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
