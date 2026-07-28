from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import subprocess

from scripts.stage07_import_persisted_private_target import (
    PersistedMarkerCandidate,
    apply_persisted_target,
    build_persisted_marker_receipt,
    parse_selected_candidate,
    select_eligible_persisted_marker,
)


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
WINDOW_START = NOW - timedelta(minutes=2)


def make_candidate(**overrides: object) -> PersistedMarkerCandidate:
    values: dict[str, object] = {
        "chat_id": "private-user",
        "user_id": "private-user",
        "text": "/stage07-bind",
        "message_type": "text",
        "received_at": NOW,
    }
    values.update(overrides)
    return PersistedMarkerCandidate(**values)  # type: ignore[arg-type]


def test_selects_one_fresh_exact_private_marker() -> None:
    candidate = make_candidate()

    assert (
        select_eligible_persisted_marker(
            [candidate],
            marker="/stage07-bind",
            not_before=WINDOW_START,
            now=NOW,
        )
        == candidate
    )


def test_rejects_stale_non_private_mismatched_non_text_and_ambiguous_candidates() -> None:
    invalid_candidates = [
        make_candidate(received_at=WINDOW_START - timedelta(seconds=1)),
        make_candidate(chat_id="group-chat", user_id="private-user"),
        make_candidate(text="/stage07-bind extra"),
        make_candidate(message_type="photo"),
    ]

    assert (
        select_eligible_persisted_marker(
            invalid_candidates,
            marker="/stage07-bind",
            not_before=WINDOW_START,
            now=NOW,
        )
        is None
    )
    assert (
        select_eligible_persisted_marker(
            [make_candidate(), make_candidate()],
            marker="/stage07-bind",
            not_before=WINDOW_START,
            now=NOW,
        )
        is None
    )


def test_persisted_marker_receipt_is_sanitized() -> None:
    receipt = build_persisted_marker_receipt(status="captured")

    assert receipt == {
        "ok": True,
        "status": "captured",
        "source": "stage03_persisted_marker",
    }
    assert "private-user" not in str(receipt)


def test_apply_persisted_target_writes_only_existing_target_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.stage07-acceptance"
    env_file.write_text(
        "UNCHANGED=kept\n"
        "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=\n"
        "STAGE06_TELEGRAM_TEST_CHAT_ID=\n"
        "STAGE06_TELEGRAM_TEST_USER_ID=\n",
        encoding="utf-8",
    )

    apply_persisted_target(
        env_file,
        {"chat_id": "private-user", "user_id": "private-user"},
    )

    values = dict(
        line.split("=", 1)
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line
    )
    assert values["UNCHANGED"] == "kept"
    assert values["TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS"] == "private-user"
    assert values["STAGE06_TELEGRAM_TEST_CHAT_ID"] == "private-user"
    assert values["STAGE06_TELEGRAM_TEST_USER_ID"] == "private-user"


def test_parse_selected_candidate_rejects_incomplete_or_non_private_payload() -> None:
    assert parse_selected_candidate({"status": "candidate", "candidate": {}}) is None
    assert (
        parse_selected_candidate(
            {
                "status": "candidate",
                "candidate": {"chat_id": "group", "user_id": "private-user"},
            }
        )
        is None
    )


def test_bridge_wrapper_never_echoes_the_target_payload() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    script = (
        repository_root
        / "deploy"
        / "stage07-acceptance"
        / "scripts"
        / "import-persisted-private-target.sh"
    ).read_text(encoding="utf-8")

    assert "set -x" not in script
    assert "printf '%s\\n' \"$candidate_json\"" not in script
    assert "docker exec -i" in script
    assert "docker run --rm -i" in script
    assert "--not-before-utc" in script
    assert '[ "$receipt" =' not in script


def test_c_runtime_layout_mounts_only_the_dedicated_runtime_directory() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    compose = (
        repository_root / "deploy" / "stage07-acceptance" / "compose.yml"
    ).read_text(encoding="utf-8")
    script = (
        repository_root
        / "deploy"
        / "stage07-acceptance"
        / "scripts"
        / "import-persisted-private-target.sh"
    ).read_text(encoding="utf-8")

    assert compose.count("${STAGE07_ENV_FILE:-runtime/.env.stage07-acceptance}") == 4
    assert 'runtime_dir="$deploy_dir/runtime"' in script
    assert '-v "$runtime_dir:/run/stage07:rw"' in script
    assert '-v "$env_file:/run/stage07/.env:rw"' not in script
    assert "/run/stage07/.env.stage07-acceptance" in script
    assert 'runtime_owner="$(id -u):$(id -g)"' in script
    assert 'sudo chown "$runtime_owner" "$env_file"' in script
    assert 'sudo chmod 600 "$env_file"' in script
    assert "stage03" not in "\n".join(
        line for line in script.splitlines() if line.lstrip().startswith("-v ")
    ).lower()


def test_runtime_preflight_requires_exactly_one_allowlist_value(tmp_path: Path) -> None:
    if shutil.which("sh") is None:
        script = (
            Path(__file__).resolve().parents[3]
            / "deploy"
            / "stage07-acceptance"
            / "scripts"
            / "validate-runtime-presence.sh"
        ).read_text(encoding="utf-8")
        assert 'IFS=","' in script or "not-exactly-one" in script
        assert "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" in script
        return
    repository_root = Path(__file__).resolve().parents[3]
    script = (
        repository_root
        / "deploy"
        / "stage07-acceptance"
        / "scripts"
        / "validate-runtime-presence.sh"
    )
    common = (
        "APP_ENV=staging\n"
        "DATABASE_URL=postgresql://isolated\n"
        "REDIS_URL=redis://isolated\n"
        "OPENROUTER_API_KEY=configured\n"
        "TELEGRAM_BOT_TOKEN=configured\n"
        "TELEGRAM_WEBHOOK_SECRET=configured\n"
        "TELEGRAM_SEND_MODE=restricted_test\n"
        "STAGE07_TELEGRAM_BOT_USERNAME=BitableAgentBot\n"
    )
    valid_env = tmp_path / "valid.env"
    valid_env.write_text(
        common + "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=private-user\n",
        encoding="utf-8",
    )
    invalid_env = tmp_path / "invalid.env"
    invalid_env.write_text(
        common + "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=one,two\n",
        encoding="utf-8",
    )

    valid = subprocess.run(
        ["sh", str(script), str(valid_env)],
        capture_output=True,
        text=True,
        check=False,
    )
    invalid = subprocess.run(
        ["sh", str(script), str(invalid_env)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert valid.returncode == 0
    assert "runtime_preflight=passed" in valid.stdout
    assert invalid.returncode == 2
    assert "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=not-exactly-one" in invalid.stdout
    assert "one,two" not in invalid.stdout
