from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_team_bot_smoke_preflight(env: Mapping[str, str]) -> dict[str, object]:
    if not env.get("OPENROUTER_API_KEY"):
        return {
            "ok": False,
            "status": "blocked",
            "missing": ["OPENROUTER_API_KEY"],
            "openrouter_key_present": False,
        }
    return {
        "ok": True,
        "status": "ready",
        "missing": [],
        "openrouter_key_present": True,
        "model_configured": bool(env.get("OPENROUTER_MODEL")),
        "base_url_configured": bool(env.get("OPENROUTER_BASE_URL")),
    }


def main() -> int:
    from scripts.stage06_env import load_default_stage06_env, safe_loaded_key_names

    loaded_keys = load_default_stage06_env(BACKEND_ROOT)
    _apply_safety_defaults()
    preflight = build_team_bot_smoke_preflight(os.environ)
    preflight["loaded_key_names"] = safe_loaded_key_names(loaded_keys)
    if not preflight["ok"]:
        return _emit(preflight, exit_code=2)

    try:
        result = _run_team_bot_route_smoke()
    except Exception as exc:  # pragma: no cover - exercised only by the real provider path
        return _emit(
            {
                "ok": False,
                "status": "failed",
                "error": type(exc).__name__,
                "message": "team_bot_live_smoke_failed",
                "raw_prompt_persisted": False,
                "raw_response_persisted": False,
                "loaded_key_names": safe_loaded_key_names(loaded_keys),
            },
            exit_code=1,
        )

    return _emit(
        {
            "ok": True,
            "status": "passed",
            "route": "mini_app_team_bot_summary",
            **result,
            "raw_prompt_persisted": False,
            "raw_response_persisted": False,
            "loaded_key_names": safe_loaded_key_names(loaded_keys),
        },
        exit_code=0,
    )


def _run_team_bot_route_smoke() -> dict[str, object]:
    from fastapi.testclient import TestClient

    from app.api.routes.stage06_platform import get_stage06_platform_uow
    from app.api.routes.stage06_runtime import get_stage06_runtime_uow
    from app.main import create_app
    from app.services.permissions import Actor
    from app.services.stage06_digital_employees import create_digital_employee
    from app.services.stage06_platform import (
        InMemoryStage06PlatformUnitOfWork,
        create_base,
        create_field,
        create_form_view,
        create_record,
        create_table,
        create_workspace,
    )

    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="stage07-live-team-bot-owner", role="owner")
    workspace = create_workspace(
        uow,
        name="Stage07 Live Team Bot Smoke",
        owner_user_id=owner.actor_id,
        actor=owner,
    )
    base = create_base(uow, workspace.id, name="Project Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    create_field(uow, table.id, name="Status", key="status", field_type="status", actor=owner)
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Open Tasks",
        view_type="grid",
        config={"fields": ["title", "status"]},
        actor=owner,
    )
    record = create_record(
        uow,
        table.id,
        values={"title": "Synthetic delivery follow-up", "status": "in_progress"},
        actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Project Progress Assistant",
        description="Summarizes one permitted Project task view.",
        telegram_alias="",
        accessible_tables=[str(table.id)],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=owner,
    )
    before_values = dict(record.values)

    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        contacts = client.get(f"/mini-app/workspaces/{workspace.id}/team-bot-contacts")
        contexts = client.get(f"/mini-app/team-bots/{employee.id}/knowledge-contexts")
        response = client.post(
            f"/mini-app/team-bots/{employee.id}/summaries",
            headers={"Idempotency-Key": "stage07-live-team-bot-summary-1"},
            json={
                "base_id": str(base.id),
                "view_id": str(view.id),
                "instruction": "Summarize the permitted project tasks. Do not claim a committed write.",
            },
        )

    if contacts.status_code != 200 or contexts.status_code != 200 or response.status_code != 200:
        raise RuntimeError("team_bot_safe_route_unavailable")
    payload = response.json()
    answer = payload.get("answer")
    if payload.get("kind") != "summary" or not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("team_bot_summary_unavailable")
    if not uow.agent_runs or not uow.audit_events:
        raise RuntimeError("team_bot_audit_or_run_missing")

    run = uow.agent_runs[-1]
    return {
        "contacts_route_status": contacts.status_code,
        "contexts_route_status": contexts.status_code,
        "summary_route_status": response.status_code,
        "summary_kind": payload.get("kind"),
        "answer_nonempty": True,
        "citation_count": len(payload.get("citations", [])),
        "audit_receipt_present": bool(payload.get("audit_event_id")),
        "agent_run_present": True,
        "model_provider_present": bool(getattr(run, "model_provider", None)),
        "model_name_present": bool(getattr(run, "model_name", None)),
        "record_values_unchanged_before_confirmation": record.values == before_values,
        "synthetic_record_count": 1,
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


def _emit(payload: dict[str, object], *, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
