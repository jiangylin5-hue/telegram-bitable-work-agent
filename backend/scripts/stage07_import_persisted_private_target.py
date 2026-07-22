from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class PersistedMarkerCandidate:
    chat_id: str
    user_id: str
    text: str
    message_type: str
    received_at: datetime


def select_eligible_persisted_marker(
    candidates: Iterable[PersistedMarkerCandidate],
    *,
    marker: str,
    not_before: datetime,
    now: datetime,
) -> PersistedMarkerCandidate | None:
    normalized_not_before = _as_utc(not_before)
    normalized_now = _as_utc(now)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.text == marker
        and candidate.message_type == "text"
        and bool(candidate.chat_id)
        and candidate.chat_id == candidate.user_id
        and normalized_not_before <= _as_utc(candidate.received_at) <= normalized_now
    ]
    return eligible[0] if len(eligible) == 1 else None


def build_persisted_marker_receipt(*, status: str) -> dict[str, object]:
    return {
        "ok": status == "captured",
        "status": status,
        "source": "stage03_persisted_marker",
    }


def parse_selected_candidate(payload: Mapping[str, Any]) -> dict[str, str] | None:
    candidate = payload.get("candidate")
    if payload.get("status") != "candidate" or not isinstance(candidate, Mapping):
        return None
    chat_id = str(candidate.get("chat_id") or "").strip()
    user_id = str(candidate.get("user_id") or "").strip()
    if not chat_id or chat_id != user_id:
        return None
    return {"chat_id": chat_id, "user_id": user_id}


def apply_persisted_target(env_file: Path, target: Mapping[str, str]) -> None:
    try:
        from scripts.stage07_capture_restricted_test_target import (
            write_private_target_to_env,
        )
    except ModuleNotFoundError:
        from stage07_capture_restricted_test_target import (
            write_private_target_to_env,
        )

    write_private_target_to_env(env_file, target)


def select_persisted_marker_from_stage03(
    *, marker: str, not_before: datetime, now: datetime
) -> PersistedMarkerCandidate | None:
    from sqlalchemy import select

    from app.core.database import get_session_factory
    from app.models.telegram import Message

    session = get_session_factory()()
    try:
        messages = session.scalars(
            select(Message).where(
                Message.raw_text == marker,
                Message.message_type == "text",
                Message.received_at >= _as_utc(not_before),
                Message.received_at <= _as_utc(now),
            )
        ).all()
        return select_eligible_persisted_marker(
            (
                PersistedMarkerCandidate(
                    chat_id=str(message.telegram_chat_id or ""),
                    user_id=str(message.telegram_user_id or ""),
                    text=str(message.raw_text or ""),
                    message_type=str(message.message_type or ""),
                    received_at=message.received_at,
                )
                for message in messages
            ),
            marker=marker,
            not_before=not_before,
            now=now,
        )
    finally:
        session.close()


def _parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _select_command(not_before_utc: str) -> dict[str, object]:
    not_before = _parse_utc_timestamp(not_before_utc)
    candidate = select_persisted_marker_from_stage03(
        marker="/stage07-bind",
        not_before=not_before,
        now=datetime.now(UTC),
    )
    if candidate is None:
        return build_persisted_marker_receipt(status="blocked")
    return {
        "status": "candidate",
        "candidate": {"chat_id": candidate.chat_id, "user_id": candidate.user_id},
    }


def _apply_command(env_file: Path, payload: Mapping[str, Any]) -> dict[str, object]:
    target = parse_selected_candidate(payload)
    if target is None:
        return build_persisted_marker_receipt(status="blocked")
    apply_persisted_target(env_file, target)
    return build_persisted_marker_receipt(status="captured")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--select", action="store_true")
    mode.add_argument("--apply-stdin", action="store_true")
    parser.add_argument("--not-before-utc")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()

    if args.select:
        if not args.not_before_utc:
            print(json.dumps(build_persisted_marker_receipt(status="blocked")))
            return 2
        try:
            payload = _select_command(args.not_before_utc)
        except Exception:
            payload = build_persisted_marker_receipt(status="failed")
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload.get("status") == "candidate" else 2

    if args.env_file is None:
        print(json.dumps(build_persisted_marker_receipt(status="blocked")))
        return 2
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, Mapping):
            raise ValueError("selection payload must be an object")
        receipt = _apply_command(args.env_file, payload)
    except Exception:
        receipt = build_persisted_marker_receipt(status="failed")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "captured" else 2


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
