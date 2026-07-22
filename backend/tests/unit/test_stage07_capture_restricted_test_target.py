from pathlib import Path
import subprocess
import sys

from scripts.stage07_capture_restricted_test_target import (
    build_capture_receipt,
    extract_private_marker_target,
    write_private_target_to_env,
)


def test_private_marker_returns_target_but_sanitized_receipt_never_exposes_it() -> None:
    update = {
        "message": {
            "text": "/stage07-bind",
            "chat": {"id": 987654, "type": "private"},
            "from": {"id": 123456},
        }
    }

    target = extract_private_marker_target(update)
    receipt = build_capture_receipt(status="captured", webhook_restore_status="restored")

    assert target == {"chat_id": "987654", "user_id": "123456"}
    assert receipt == {
        "ok": True,
        "status": "captured",
        "private_target_captured": True,
        "webhook_restore_status": "restored",
    }
    assert "987654" not in str(receipt)
    assert "123456" not in str(receipt)
    assert "stage07-bind" not in str(receipt)


def test_group_or_non_marker_update_cannot_create_a_private_target() -> None:
    group_update = {
        "message": {
            "text": "/stage07-bind",
            "chat": {"id": "group-id", "type": "group"},
            "from": {"id": "user-id"},
        }
    }
    other_update = {
        "message": {
            "text": "@ops summarize",
            "chat": {"id": "private-id", "type": "private"},
            "from": {"id": "user-id"},
        }
    }

    assert extract_private_marker_target(group_update) is None
    assert extract_private_marker_target(other_update) is None


def test_private_target_writer_changes_only_isolated_target_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.stage07-acceptance"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=runtime-only\n"
        "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=\n"
        "STAGE06_TELEGRAM_TEST_CHAT_ID=\n"
        "STAGE06_TELEGRAM_TEST_USER_ID=\n"
        "UNCHANGED_KEY=kept\n",
        encoding="utf-8",
    )

    write_private_target_to_env(
        env_file,
        {"chat_id": "private-chat", "user_id": "private-user"},
    )

    values = dict(
        line.split("=", 1)
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line
    )
    assert values["TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS"] == "private-chat"
    assert values["STAGE06_TELEGRAM_TEST_CHAT_ID"] == "private-chat"
    assert values["STAGE06_TELEGRAM_TEST_USER_ID"] == "private-user"
    assert values["TELEGRAM_BOT_TOKEN"] == "runtime-only"
    assert values["UNCHANGED_KEY"] == "kept"


def test_capture_script_is_directly_executable_in_the_container_style() -> None:
    backend_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/stage07_capture_restricted_test_target.py",
            "--help",
        ],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--env-file" in result.stdout
