import json

import pytest

from app.core.config import get_settings
from app.core.runtime_summary import build_redacted_runtime_summary, main


RUNTIME_ENV_VARS = [
    "APP_ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_SEND_MODE",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS",
    "LLM_ENABLED",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_BASE_URL",
    "AGENT_WORKFLOW_MODE",
    "AGENT_SAVE_FULL_PROMPT",
    "AGENT_SAVE_FULL_RESPONSE",
    "PROVIDER_MODE",
]


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in RUNTIME_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _set_stage05_rehearsal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage:secret@db/app")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "stage-webhook-secret")
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "real_openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-stage-secret")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/stage05-model")
    monkeypatch.setenv("TELEGRAM_SEND_MODE", "restricted_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:stage05-token")
    monkeypatch.setenv("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS", "private-test-chat")
    monkeypatch.setenv("PROVIDER_MODE", "disabled")


def test_redacted_runtime_summary_exposes_presence_without_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_stage05_rehearsal_env(monkeypatch)

    summary = build_redacted_runtime_summary(get_settings())
    encoded = json.dumps(summary, sort_keys=True)

    assert summary == {
        "app_env": "staging",
        "llm_enabled": True,
        "agent_workflow_mode": "real_openrouter",
        "openrouter_key_present": True,
        "openrouter_model_present": True,
        "agent_save_full_prompt": False,
        "agent_save_full_response": False,
        "telegram_send_mode": "restricted_test",
        "telegram_bot_token_present": True,
        "telegram_test_send_allowlist_present": True,
        "provider_mode": "disabled",
        "runtime_settings_valid": True,
        "validation_error": None,
    }
    assert "openrouter-stage-secret" not in encoded
    assert "123456:stage05-token" not in encoded
    assert "private-test-chat" not in encoded
    assert "stage-webhook-secret" not in encoded
    assert "postgresql+psycopg" not in encoded


def test_redacted_runtime_summary_keeps_validation_errors_secret_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_stage05_rehearsal_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_MODE", "sandbox")

    summary = build_redacted_runtime_summary(get_settings())
    encoded = json.dumps(summary, sort_keys=True)

    assert summary["runtime_settings_valid"] is False
    assert summary["validation_error"] == (
        "Unsafe Stage 03 runtime settings are enabled: PROVIDER_MODE"
    )
    assert "openrouter-stage-secret" not in encoded
    assert "123456:stage05-token" not in encoded
    assert "private-test-chat" not in encoded


def test_runtime_summary_cli_prints_json_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_stage05_rehearsal_env(monkeypatch)

    exit_code = main()
    output = capsys.readouterr().out
    summary = json.loads(output)

    assert exit_code == 0
    assert summary["runtime_settings_valid"] is True
    assert summary["openrouter_key_present"] is True
    assert "openrouter-stage-secret" not in output
    assert "123456:stage05-token" not in output
    assert "private-test-chat" not in output
