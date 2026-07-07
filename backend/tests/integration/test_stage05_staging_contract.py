import pytest

from app.core.config import get_settings, validate_runtime_settings


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


def _set_required_staging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage:secret@db/app")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "stage-webhook-secret")


def _set_stage05_rehearsal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "real_openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-stage-secret")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/stage05-model")
    monkeypatch.setenv("TELEGRAM_SEND_MODE", "restricted_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:stage05-token")
    monkeypatch.setenv("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS", "private-test-chat")
    monkeypatch.setenv("PROVIDER_MODE", "disabled")


def test_stage05_staging_rehearsal_env_contract_passes_without_raw_debug_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_stage05_rehearsal_env(monkeypatch)

    settings = get_settings()

    assert settings.environment == "staging"
    assert settings.llm_enabled is True
    assert settings.agent_workflow_mode == "real_openrouter"
    assert settings.telegram_send_mode == "restricted_test"
    assert settings.telegram_test_send_allowed_chat_ids == ("private-test-chat",)
    assert settings.provider_mode == "disabled"
    assert settings.agent_save_full_prompt is False
    assert settings.agent_save_full_response is False
    validate_runtime_settings(settings)


def test_stage05_staging_rehearsal_rejects_provider_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_stage05_rehearsal_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_MODE", "sandbox")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "PROVIDER_MODE" in message
    assert "openrouter-stage-secret" not in message
    assert "123456:stage05-token" not in message
    assert "private-test-chat" not in message


def test_stage05_staging_rehearsal_rejects_llm_enabled_without_real_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "fake")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-stage-secret")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    assert "LLM_ENABLED" in str(exc_info.value)
    assert "openrouter-stage-secret" not in str(exc_info.value)


def test_stage05_staging_rehearsal_rejects_restricted_send_without_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "real_openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-stage-secret")
    monkeypatch.setenv("TELEGRAM_SEND_MODE", "restricted_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:stage05-token")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" in message
    assert "123456:stage05-token" not in message
    assert "openrouter-stage-secret" not in message


def test_stage05_staging_safety_close_contract_is_dry_run_and_provider_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "fake")
    monkeypatch.setenv("TELEGRAM_SEND_MODE", "dry_run")
    monkeypatch.setenv("PROVIDER_MODE", "disabled")

    settings = get_settings()

    assert settings.llm_enabled is False
    assert settings.telegram_send_mode == "dry_run"
    assert settings.telegram_test_send_allowed_chat_ids == ()
    assert settings.provider_mode == "disabled"
    validate_runtime_settings(settings)
