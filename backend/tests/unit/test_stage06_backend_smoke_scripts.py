import os
from pathlib import Path

import pytest

from scripts.stage06_env import load_env_file, safe_loaded_key_names
from scripts.stage06_live_openrouter_smoke import (
    build_openrouter_case_failure,
    build_openrouter_preflight,
    build_openrouter_smoke_config,
)
from scripts.stage06_local_postgres_migration_smoke import (
    classify_local_postgres_schema_target,
    classify_local_postgres_url,
)
from scripts.stage06_telegram_entry_smoke import (
    build_acknowledge_update_params,
    build_restore_webhook_payload,
    build_telegram_preflight,
    build_temporary_polling_config,
    build_webhook_snapshot,
    telegram_error_payload,
)


def test_stage06_local_postgres_smoke_accepts_only_local_disposable_database() -> None:
    classification = classify_local_postgres_url(
        "postgresql+psycopg://agent:secret@127.0.0.1:5432/stage06_smoke"
    )

    assert classification.host == "127.0.0.1"
    assert classification.database == "stage06_smoke"
    assert classification.safe_url == (
        "postgresql+psycopg://agent:***@127.0.0.1:5432/stage06_smoke"
    )

    with pytest.raises(RuntimeError, match="local PostgreSQL"):
        classify_local_postgres_url(
            "postgresql+psycopg://agent:secret@db.example.com:5432/stage06_smoke"
        )

    with pytest.raises(RuntimeError, match="disposable"):
        classify_local_postgres_url(
            "postgresql+psycopg://agent:secret@127.0.0.1:5432/ads_agent"
        )


def test_stage06_local_postgres_smoke_can_use_disposable_schema_in_existing_local_database() -> None:
    classification = classify_local_postgres_schema_target(
        "postgresql+psycopg://agent:secret@127.0.0.1:5432/ads_agent",
        "stage06_smoke",
    )

    assert classification.host == "127.0.0.1"
    assert classification.database == "ads_agent"
    assert classification.schema == "stage06_smoke"
    assert classification.safe_url == (
        "postgresql+psycopg://agent:***@127.0.0.1:5432/ads_agent"
    )


def test_stage06_openrouter_smoke_preflight_reports_blocked_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    result = build_openrouter_preflight(os.environ)

    assert result["status"] == "blocked"
    assert "OPENROUTER_API_KEY" in result["missing"]
    assert result["openrouter_key_present"] is False


def test_stage06_openrouter_smoke_defaults_to_summarize() -> None:
    config = build_openrouter_smoke_config({})

    assert config["action"] == "summarize"
    assert config["prompt"]
    assert [case["case_id"] for case in config["cases"]] == ["summarize_basic"]

    script_source = Path("scripts/stage06_live_openrouter_smoke.py").read_text(
        encoding="utf-8"
    )

    assert "skill_evidence" in script_source
    assert "selected_skill_ids" in script_source
    assert "STAGE06_OPENROUTER_SMOKE_CASES" in script_source


def test_stage06_openrouter_smoke_accepts_explicit_draft_update() -> None:
    config = build_openrouter_smoke_config(
        {"STAGE06_OPENROUTER_SMOKE_ACTION": "draft_update"}
    )

    assert config["action"] == "draft_update"
    assert "draft" in str(config["prompt"]).lower()


def test_stage06_openrouter_smoke_accepts_explicit_case_list() -> None:
    config = build_openrouter_smoke_config(
        {
            "STAGE06_OPENROUTER_SMOKE_CASES": (
                "summarize_basic,draft_update_status,hidden_field_guard"
            )
        }
    )

    assert [case["case_id"] for case in config["cases"]] == [
        "summarize_basic",
        "draft_update_status",
        "hidden_field_guard",
    ]
    assert config["cases"][0]["action"] == "summarize"
    assert config["cases"][1]["action"] == "draft_update"


def test_stage06_openrouter_unsafe_commit_case_requests_safe_pending_draft() -> None:
    config = build_openrouter_smoke_config(
        {"STAGE06_OPENROUTER_SMOKE_CASES": "unsafe_commit_refusal"}
    )

    case = config["cases"][0]

    assert case["action"] == "draft_update"
    assert "status to in_progress" in str(case["prompt"])
    assert "pending draft" in str(case["prompt"])
    assert "Do not claim the write is committed" in str(case["prompt"])


def test_stage06_openrouter_case_failure_payload_keeps_case_context() -> None:
    payload = build_openrouter_case_failure(
        {"case_id": "unsafe_commit_refusal", "action": "draft_update"},
        RuntimeError("Stage06 live draft_update requires proposed_values"),
    )

    assert payload == {
        "case_id": "unsafe_commit_refusal",
        "status": "failed",
        "action": "draft_update",
        "error": "RuntimeError",
        "message": "Stage06 live draft_update requires proposed_values",
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
    }


def test_stage06_openrouter_smoke_rejects_unsupported_action() -> None:
    with pytest.raises(RuntimeError, match="Unsupported Stage06 OpenRouter smoke action"):
        build_openrouter_smoke_config({"STAGE06_OPENROUTER_SMOKE_ACTION": "delete"})


def test_stage06_telegram_entry_smoke_preflight_reports_blocked_without_test_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "STAGE06_TELEGRAM_TEST_CHAT_ID",
        "STAGE06_TELEGRAM_TEST_USER_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    result = build_telegram_preflight(os.environ)

    assert result["status"] == "blocked"
    assert result["missing"] == [
        "TELEGRAM_BOT_TOKEN",
        "STAGE06_TELEGRAM_TEST_CHAT_ID",
    ]


def test_stage06_telegram_entry_smoke_preflight_reuses_restricted_test_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS", "chat-a,chat-b")
    monkeypatch.delenv("STAGE06_TELEGRAM_TEST_CHAT_ID", raising=False)
    monkeypatch.delenv("STAGE06_TELEGRAM_TEST_USER_ID", raising=False)

    result = build_telegram_preflight(os.environ)

    assert result["status"] == "ready"
    assert result["telegram_chat_id"] == "chat-a"
    assert result["telegram_user_id"] is None


def test_stage06_telegram_entry_smoke_preflight_allows_explicit_auto_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("STAGE06_TELEGRAM_AUTO_DISCOVER", "true")
    monkeypatch.delenv("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.delenv("STAGE06_TELEGRAM_TEST_CHAT_ID", raising=False)
    monkeypatch.delenv("STAGE06_TELEGRAM_TEST_USER_ID", raising=False)

    result = build_telegram_preflight(os.environ)

    assert result["status"] == "ready"
    assert result["telegram_chat_id"] is None
    assert result["telegram_user_id"] is None
    assert result["discovery_mode"] == "auto"


def test_stage06_env_loader_redacts_secret_key_names(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENROUTER_API_KEY=secret-value",
                "TELEGRAM_BOT_TOKEN=bot-secret",
                "STAGE06_TELEGRAM_EMPLOYEE_ALIAS=ops",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_env_file(env_file)

    assert "OPENROUTER_API_KEY" in loaded
    assert safe_loaded_key_names(loaded) == ["STAGE06_TELEGRAM_EMPLOYEE_ALIAS"]


def test_stage06_env_loader_replaces_empty_existing_env_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("STAGE06_TELEGRAM_TEST_CHAT_ID=chat-from-file", encoding="utf-8")
    monkeypatch.setenv("STAGE06_TELEGRAM_TEST_CHAT_ID", "")

    load_env_file(env_file)

    assert os.environ["STAGE06_TELEGRAM_TEST_CHAT_ID"] == "chat-from-file"


def test_stage06_telegram_error_payload_redacts_bot_token() -> None:
    payload = telegram_error_payload(
        RuntimeError("failed for https://api.telegram.org/botsecret-token/getUpdates"),
        token="secret-token",
    )

    assert payload["status"] == "failed"
    assert "secret-token" not in str(payload)
    assert "bot***/getUpdates" in str(payload)


def test_stage06_telegram_error_payload_marks_conflict_as_blocked() -> None:
    payload = telegram_error_payload(
        RuntimeError("409 Conflict for https://api.telegram.org/botsecret-token/getUpdates"),
        token="secret-token",
    )

    assert payload["status"] == "blocked"
    assert "Telegram getUpdates conflict" in payload["message"]
    assert "secret-token" not in str(payload)


def test_stage06_temporary_polling_config_is_safe_by_default() -> None:
    config = build_temporary_polling_config({})

    assert config == {
        "enabled": False,
        "drop_pending_updates": False,
        "timeout_seconds": 120,
    }


def test_stage06_temporary_polling_config_requires_explicit_enable() -> None:
    config = build_temporary_polling_config(
        {
            "STAGE06_TELEGRAM_TEMPORARY_POLLING": "true",
            "STAGE06_TELEGRAM_DROP_PENDING_UPDATES": "true",
            "STAGE06_TELEGRAM_POLL_TIMEOUT_SECONDS": "30",
        }
    )

    assert config == {
        "enabled": True,
        "drop_pending_updates": True,
        "timeout_seconds": 30,
    }


def test_stage06_webhook_snapshot_does_not_expose_path_or_secret() -> None:
    snapshot = build_webhook_snapshot(
        {
            "url": "https://api.example.test/telegram/super-secret-path",
            "pending_update_count": 1,
            "max_connections": 40,
            "allowed_updates": ["message"],
        }
    )

    assert snapshot == {
        "has_webhook_url": True,
        "webhook_host": "api.example.test",
        "webhook_path_present": True,
        "pending_update_count": 1,
        "max_connections": 40,
        "allowed_updates": ["message"],
    }
    assert "super-secret-path" not in str(snapshot)


def test_stage06_restore_webhook_payload_preserves_recoverable_settings() -> None:
    payload = build_restore_webhook_payload(
        {
            "url": "https://api.example.test/telegram/webhook",
            "max_connections": 40,
            "allowed_updates": ["message"],
        },
        webhook_secret="secret-token",
    )

    assert payload == {
        "url": "https://api.example.test/telegram/webhook",
        "drop_pending_updates": "false",
        "secret_token": "secret-token",
        "max_connections": "40",
        "allowed_updates": "[\"message\"]",
    }


def test_stage06_acknowledge_update_params_advances_offset() -> None:
    params = build_acknowledge_update_params({"update_id": 184365921})

    assert params == {
        "offset": 184365922,
        "limit": 1,
        "timeout": 0,
        "allowed_updates": "[\"message\"]",
    }
    assert build_acknowledge_update_params({}) is None
