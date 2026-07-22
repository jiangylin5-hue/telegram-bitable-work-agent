from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

try:
    from scripts.stage06_telegram_entry_smoke import (
        build_acknowledge_update_params,
        build_restore_webhook_payload,
    )
except ModuleNotFoundError:  # Direct `python scripts/...` execution in the image.
    from stage06_telegram_entry_smoke import (
        build_acknowledge_update_params,
        build_restore_webhook_payload,
    )


DEFAULT_MARKER = "/stage07-bind"


def extract_private_marker_target(
    update: Mapping[str, Any], *, marker: str = DEFAULT_MARKER
) -> dict[str, str] | None:
    message = update.get("message") or {}
    if not isinstance(message, Mapping):
        return None
    text = str(message.get("text") or "").strip()
    first_token = text.split(maxsplit=1)[0] if text else ""
    if first_token != marker and not first_token.startswith(f"{marker}@"):
        return None
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    if not isinstance(chat, Mapping) or not isinstance(sender, Mapping):
        return None
    if chat.get("type") != "private":
        return None
    chat_id = chat.get("id")
    user_id = sender.get("id")
    if chat_id is None or user_id is None:
        return None
    return {"chat_id": str(chat_id), "user_id": str(user_id)}


def build_capture_receipt(
    *, status: str, webhook_restore_status: str
) -> dict[str, object]:
    return {
        "ok": status == "captured",
        "status": status,
        "private_target_captured": status == "captured",
        "webhook_restore_status": webhook_restore_status,
    }


def write_private_target_to_env(
    env_file: Path, target: Mapping[str, str]
) -> None:
    chat_id = str(target.get("chat_id") or "").strip()
    user_id = str(target.get("user_id") or "").strip()
    if not chat_id or not user_id:
        raise ValueError("Private target is incomplete")

    values = {
        "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS": chat_id,
        "STAGE06_TELEGRAM_TEST_CHAT_ID": chat_id,
        "STAGE06_TELEGRAM_TEST_USER_ID": user_id,
    }
    existing_lines = env_file.read_text(encoding="utf-8").splitlines()
    remaining = set(values)
    rendered: list[str] = []
    for line in existing_lines:
        key, separator, _ = line.partition("=")
        if separator and key in values:
            rendered.append(f"{key}={values[key]}")
            remaining.discard(key)
        else:
            rendered.append(line)
    rendered.extend(f"{key}={values[key]}" for key in sorted(remaining))

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=env_file.parent,
        delete=False,
    ) as temporary_file:
        temporary_file.write("\n".join(rendered) + "\n")
        temporary_path = Path(temporary_file.name)
    os.chmod(temporary_path, 0o600)
    temporary_path.replace(env_file)


def _load_env_file(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and not key.lstrip().startswith("#"):
            values[key] = value
    return values


def _telegram_api_request(
    token: str, method: str, endpoint: str, **kwargs: Any
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
        raise RuntimeError("Telegram API rejected the request")
    return payload


def _poll_for_private_marker(
    token: str, *, marker: str, timeout_seconds: int
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    deadline = time.monotonic() + timeout_seconds
    offset: int | None = None
    while time.monotonic() < deadline:
        timeout = max(1, min(10, int(deadline - time.monotonic())))
        payload = _telegram_api_request(
            token,
            "GET",
            "getUpdates",
            params={"limit": 20, "timeout": timeout, "allowed_updates": '["message"]', **({"offset": offset} if offset is not None else {})},
        )
        for update in payload.get("result", []):
            if not isinstance(update, Mapping):
                continue
            update_id = update.get("update_id")
            if update_id is not None:
                offset = int(update_id) + 1
            target = extract_private_marker_target(update, marker=marker)
            if target is not None:
                return dict(update), target
    return None, None


def capture_private_target(
    *, env_file: Path, marker: str, timeout_seconds: int
) -> dict[str, object]:
    values = _load_env_file(env_file)
    token = values.get("TELEGRAM_BOT_TOKEN")
    webhook_secret = values.get("TELEGRAM_WEBHOOK_SECRET") or None
    if not token or not webhook_secret:
        return build_capture_receipt(status="blocked", webhook_restore_status="not-attempted")

    original_payload = _telegram_api_request(token, "GET", "getWebhookInfo")
    original_webhook = original_payload.get("result") or {}
    target: dict[str, str] | None = None
    restore_status = "not-attempted"
    status = "blocked"
    try:
        _telegram_api_request(
            token,
            "POST",
            "deleteWebhook",
            data={"drop_pending_updates": "false"},
        )
        update, target = _poll_for_private_marker(
            token, marker=marker, timeout_seconds=timeout_seconds
        )
        if update is not None:
            acknowledgement = build_acknowledge_update_params(update)
            if acknowledgement is not None:
                _telegram_api_request(token, "GET", "getUpdates", params=acknowledgement)
    except Exception:
        status = "failed"
    finally:
        restore_payload = build_restore_webhook_payload(
            original_webhook,
            webhook_secret=webhook_secret,
        )
        if restore_payload is None:
            restore_status = "skipped"
        else:
            try:
                _telegram_api_request(token, "POST", "setWebhook", data=restore_payload)
                restore_status = "restored"
            except Exception:
                restore_status = "failed"

    if status != "failed" and target is not None and restore_status in {"restored", "skipped"}:
        write_private_target_to_env(env_file, target)
        status = "captured"
    elif restore_status == "failed":
        status = "failed"
    return build_capture_receipt(
        status=status,
        webhook_restore_status=restore_status,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--marker", default=DEFAULT_MARKER)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 120:
        print(json.dumps(build_capture_receipt(status="blocked", webhook_restore_status="not-attempted")))
        return 2
    try:
        receipt = capture_private_target(
            env_file=args.env_file,
            marker=args.marker,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception:
        receipt = build_capture_receipt(status="failed", webhook_restore_status="not-attempted")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "captured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
