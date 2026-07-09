from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    bind_telegram_context,
    create_digital_employee,
    resolve_telegram_mention,
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


REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "STAGE06_TELEGRAM_TEST_CHAT_ID",
)


def build_telegram_preflight(env: Mapping[str, str]) -> dict[str, object]:
    chat_id = _configured_chat_id(env)
    auto_discover = _env_bool(env.get("STAGE06_TELEGRAM_AUTO_DISCOVER"))
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if chat_id or auto_discover:
        missing = [name for name in missing if name != "STAGE06_TELEGRAM_TEST_CHAT_ID"]
    if missing:
        return {
            "ok": False,
            "status": "blocked",
            "missing": missing,
            "message": (
                "Set a test bot token and allowlisted chat/user before running "
                "the real Stage06 Telegram entry smoke."
            ),
        }
    return {
        "ok": True,
        "status": "ready",
        "missing": [],
        "telegram_chat_id": chat_id,
        "telegram_user_id": env.get("STAGE06_TELEGRAM_TEST_USER_ID"),
        "discovery_mode": "auto" if chat_id is None else "configured",
    }


def main() -> int:
    loaded_keys = load_default_stage06_env(BACKEND_ROOT)
    preflight = build_telegram_preflight(os.environ)
    if preflight["status"] == "blocked":
        preflight["loaded_key_names"] = safe_loaded_key_names(loaded_keys)
        return _emit(preflight, exit_code=2)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    configured_chat_id = preflight["telegram_chat_id"]
    chat_id = None if configured_chat_id is None else str(configured_chat_id)
    configured_user_id = os.getenv("STAGE06_TELEGRAM_TEST_USER_ID")
    alias = os.getenv("STAGE06_TELEGRAM_EMPLOYEE_ALIAS", "ops")
    temporary_polling = build_temporary_polling_config(os.environ)
    try:
        entry_evidence: dict[str, object] = {}
        if temporary_polling["enabled"]:
            update, entry_evidence = _find_matching_update_with_temporary_polling(
                token=token,
                chat_id=chat_id,
                user_id=configured_user_id,
                alias=alias,
                drop_pending_updates=bool(temporary_polling["drop_pending_updates"]),
                timeout_seconds=int(temporary_polling["timeout_seconds"]),
            )
        else:
            update = _find_matching_update(
                token=token,
                chat_id=chat_id,
                user_id=configured_user_id,
                alias=alias,
            )
        if update is None:
            target = "any recent chat" if chat_id is None else f"chat {chat_id}"
            payload = {
                "ok": False,
                "status": "blocked",
                "message": (
                    f"No recent Telegram update found for {target}, "
                    f"alias @{alias}. Send '@{alias} summarize' to the test "
                    "bot/chat, then rerun."
                ),
            }
            payload.update(entry_evidence)
            return _emit(payload, exit_code=2)
        if chat_id is None:
            chat_id = _message_chat_id(update)
        if not chat_id:
            return _emit(
                {
                    "ok": False,
                    "status": "blocked",
                    "message": "Matching Telegram update did not include a chat id.",
                },
                exit_code=2,
            )
        user_id = _message_user_id(update)
        if not user_id:
            return _emit(
                {
                    "ok": False,
                    "status": "blocked",
                    "message": "Matching Telegram update did not include a user id.",
                },
                exit_code=2,
            )

        uow, view, employee = _workspace_with_bound_employee(
            chat_id=chat_id,
            user_id=user_id,
            alias=alias,
        )
        response = resolve_telegram_mention(
            uow,
            telegram_chat_id=chat_id,
            telegram_user_id=user_id,
            alias=alias,
            text=_message_text(update),
        )
        payload = {
            "ok": True,
            "status": "passed",
            "telegram_update_id": str(update.get("update_id")),
            "telegram_chat_id": chat_id,
            "telegram_user_id": user_id,
            "employee_id": str(employee.id),
            "view_id": str(view.id),
            "action": response.get("action"),
            "record_count": response.get("record_count"),
            "send_mode": os.getenv("TELEGRAM_SEND_MODE", "dry_run"),
            "provider_mode": os.getenv("PROVIDER_MODE", "disabled"),
            "loaded_key_names": safe_loaded_key_names(loaded_keys),
        }
        payload.update(entry_evidence)
        return _emit(payload)
    except Exception as exc:
        payload = telegram_error_payload(exc, token=token)
        return _emit(payload, exit_code=2 if payload["status"] == "blocked" else 1)


def telegram_error_payload(exc: Exception, *, token: str) -> dict[str, object]:
    raw_message = _redact_token(str(exc), token=token)
    if "409 Conflict" in raw_message:
        return {
            "ok": False,
            "status": "blocked",
            "error": type(exc).__name__,
            "message": (
                "Telegram getUpdates conflict. The bot likely has an active "
                "webhook or another polling consumer. Use a configured test "
                "chat/user with the backend mention API, or explicitly confirm "
                "a temporary webhook/polling switch before rerunning real "
                "getUpdates smoke."
            ),
        }
    return {
        "ok": False,
        "status": "failed",
        "error": type(exc).__name__,
        "message": raw_message,
    }


def build_temporary_polling_config(env: Mapping[str, str]) -> dict[str, object]:
    timeout_seconds = 120
    raw_timeout = env.get("STAGE06_TELEGRAM_POLL_TIMEOUT_SECONDS")
    if raw_timeout:
        try:
            timeout_seconds = max(1, int(raw_timeout))
        except ValueError:
            timeout_seconds = 120
    return {
        "enabled": _env_bool(env.get("STAGE06_TELEGRAM_TEMPORARY_POLLING")),
        "drop_pending_updates": _env_bool(env.get("STAGE06_TELEGRAM_DROP_PENDING_UPDATES")),
        "timeout_seconds": timeout_seconds,
    }


def build_webhook_snapshot(result: Mapping[str, Any]) -> dict[str, object]:
    url = str(result.get("url") or "")
    parsed = urlsplit(url) if url else None
    return {
        "has_webhook_url": bool(url),
        "webhook_host": parsed.netloc if parsed else None,
        "webhook_path_present": bool(parsed and parsed.path and parsed.path != "/"),
        "pending_update_count": result.get("pending_update_count"),
        "max_connections": result.get("max_connections"),
        "allowed_updates": result.get("allowed_updates"),
    }


def build_restore_webhook_payload(
    original_webhook: Mapping[str, Any],
    *,
    webhook_secret: str | None,
) -> dict[str, str] | None:
    original_url = str(original_webhook.get("url") or "")
    if not original_url:
        return None
    payload = {
        "url": original_url,
        "drop_pending_updates": "false",
    }
    if webhook_secret:
        payload["secret_token"] = webhook_secret
    if original_webhook.get("max_connections"):
        payload["max_connections"] = str(original_webhook["max_connections"])
    allowed_updates = original_webhook.get("allowed_updates")
    if allowed_updates:
        payload["allowed_updates"] = json.dumps(allowed_updates)
    return payload


def build_acknowledge_update_params(update: Mapping[str, Any]) -> dict[str, object] | None:
    update_id = update.get("update_id")
    if update_id is None:
        return None
    return {
        "offset": int(update_id) + 1,
        "limit": 1,
        "timeout": 0,
        "allowed_updates": json.dumps(["message"]),
    }


def _find_matching_update(
    *,
    token: str,
    chat_id: str | None,
    user_id: str | None,
    alias: str,
) -> dict[str, Any] | None:
    payload = _telegram_api_request(
        token,
        "GET",
        "getUpdates",
        params={"limit": 20, "allowed_updates": json.dumps(["message"])},
    )
    return _find_matching_update_in_payload(
        payload,
        chat_id=chat_id,
        user_id=user_id,
        alias=alias,
    )


def _find_matching_update_with_temporary_polling(
    *,
    token: str,
    chat_id: str | None,
    user_id: str | None,
    alias: str,
    drop_pending_updates: bool,
    timeout_seconds: int,
) -> tuple[dict[str, Any] | None, dict[str, object]]:
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or None
    original_payload = _telegram_api_request(token, "GET", "getWebhookInfo")
    original_webhook = original_payload.get("result") or {}
    evidence: dict[str, object] = {
        "temporary_polling": {
            "enabled": True,
            "drop_pending_updates": drop_pending_updates,
            "original_webhook": build_webhook_snapshot(original_webhook),
        }
    }
    try:
        _telegram_api_request(
            token,
            "POST",
            "deleteWebhook",
            data={"drop_pending_updates": "true" if drop_pending_updates else "false"},
        )
        update = _poll_matching_update(
            token=token,
            chat_id=chat_id,
            user_id=user_id,
            alias=alias,
            timeout_seconds=timeout_seconds,
        )
        return update, evidence
    finally:
        temporary_polling = evidence["temporary_polling"]
        if not isinstance(temporary_polling, dict):
            raise RuntimeError("Invalid temporary polling evidence.")
        restore_payload = build_restore_webhook_payload(
            original_webhook,
            webhook_secret=webhook_secret,
        )
        if restore_payload is None:
            temporary_polling["webhook_restore_status"] = "skipped"
        else:
            _telegram_api_request(token, "POST", "setWebhook", data=restore_payload)
            temporary_polling["webhook_restore_status"] = "restored"


def _poll_matching_update(
    *,
    token: str,
    chat_id: str | None,
    user_id: str | None,
    alias: str,
    timeout_seconds: int,
) -> dict[str, Any] | None:
    offset: int | None = None
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        remaining = max(1, min(10, int(deadline - time.monotonic())))
        params: dict[str, Any] = {
            "limit": 20,
            "timeout": remaining,
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            params["offset"] = offset
        payload = _telegram_api_request(token, "GET", "getUpdates", params=params)
        for update in payload.get("result", []):
            update_id = update.get("update_id")
            if update_id is not None:
                offset = int(update_id) + 1
        matched = _find_matching_update_in_payload(
            payload,
            chat_id=chat_id,
            user_id=user_id,
            alias=alias,
        )
        if matched is not None:
            acknowledge_params = build_acknowledge_update_params(matched)
            if acknowledge_params is not None:
                _telegram_api_request(
                    token,
                    "GET",
                    "getUpdates",
                    params=acknowledge_params,
                )
            return matched
    return None


def _find_matching_update_in_payload(
    payload: Mapping[str, Any],
    *,
    chat_id: str | None,
    user_id: str | None,
    alias: str,
) -> dict[str, Any] | None:
    for update in reversed(payload.get("result", [])):
        message = update.get("message") or {}
        if chat_id is not None and str((message.get("chat") or {}).get("id")) != str(chat_id):
            continue
        if user_id and str((message.get("from") or {}).get("id")) != str(user_id):
            continue
        text = _message_text(update)
        if f"@{alias}" in text or alias in text:
            return update
    return None


def _telegram_api_request(
    token: str,
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = httpx.request(
        method,
        f"https://api.telegram.org/bot{token}/{endpoint}",
        timeout=25,
        **kwargs,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(str(payload))
    return payload


def _workspace_with_bound_employee(
    *,
    chat_id: str,
    user_id: str,
    alias: str,
):
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Telegram Entry Smoke", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Telegram Productivity")
    table = create_table(uow, base.id, name="Telegram Tasks", key="telegram_tasks")
    create_field(uow, table.id, name="Message", key="message", field_type="text")
    create_field(uow, table.id, name="Status", key="status", field_type="status")
    create_field(uow, table.id, name="Source Chat", key="source_chat", field_type="text")
    create_record(
        uow,
        table.id,
        values={
            "message": "Smoke-test Telegram mention entry.",
            "status": "open",
            "source_chat": chat_id,
        },
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Telegram Task Grid",
        view_type="grid",
        config={"fields": ["message", "status", "source_chat"]},
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Telegram Ops Helper",
        description="Smoke-test Telegram mention resolution",
        telegram_alias=alias,
        accessible_tables=[],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    bind_telegram_context(
        uow,
        workspace.id,
        workspace_member_id=uow.workspace_members[0].id,
        telegram_chat_id=chat_id,
        telegram_user_id=user_id,
        default_base_id=base.id,
        default_digital_employee_id=employee.id,
        scope_policy={"views": [str(view.id)]},
    )
    return uow, view, employee


def _message_text(update: dict[str, Any]) -> str:
    return str((update.get("message") or {}).get("text") or "")


def _message_chat_id(update: dict[str, Any]) -> str | None:
    chat_id = ((update.get("message") or {}).get("chat") or {}).get("id")
    return None if chat_id is None else str(chat_id)


def _message_user_id(update: dict[str, Any]) -> str | None:
    user_id = ((update.get("message") or {}).get("from") or {}).get("id")
    return None if user_id is None else str(user_id)


def _configured_chat_id(env: Mapping[str, str]) -> str | None:
    if env.get("STAGE06_TELEGRAM_TEST_CHAT_ID"):
        return env["STAGE06_TELEGRAM_TEST_CHAT_ID"]
    allowed_chats = env.get("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS")
    if not allowed_chats:
        return None
    return next(
        (part.strip() for part in allowed_chats.split(",") if part.strip()),
        None,
    )


def _env_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_token(message: str, *, token: str) -> str:
    redacted = message.replace(token, "***")
    return redacted.replace(f"bot{token}", "bot***")


def _emit(payload: dict[str, object], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
