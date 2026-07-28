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
    "AGENT_LLM_TIMEOUT_SECONDS",
    "AGENT_SAVE_FULL_PROMPT",
    "AGENT_SAVE_FULL_RESPONSE",
    "AGENT_EVENT_RUNTIME_ENABLED",
    "AGENT_EVENT_RUNTIME_MODE",
    "AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS",
    "AGENT_RUNTIME_INPUT_KEY",
    "AGENT_RUNTIME_INPUT_KEY_VERSION",
    "AGENT_RUNTIME_INPUT_TTL_SECONDS",
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


def test_stage05_agent_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_env(monkeypatch)

    settings = get_settings()

    assert settings.llm_enabled is False
    assert settings.agent_workflow_mode == "fake"
    assert settings.agent_llm_timeout_seconds == 30
    assert settings.agent_save_full_prompt is False
    assert settings.agent_save_full_response is False
    assert settings.agent_event_runtime_enabled is False
    assert settings.telegram_send_mode == "dry_run"
    validate_runtime_settings(settings)


def test_real_openrouter_mode_requires_openrouter_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "real_openrouter")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "OPENROUTER_API_KEY" in message
    assert "stage-webhook-secret" not in message


def test_real_openrouter_mode_passes_with_server_side_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_MODE", "real_openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-stage-secret")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/stage05-model")
    monkeypatch.setenv("AGENT_LLM_TIMEOUT_SECONDS", "45")

    settings = get_settings()

    assert settings.llm_enabled is True
    assert settings.agent_workflow_mode == "real_openrouter"
    assert settings.openrouter_api_key == "openrouter-stage-secret"
    assert settings.openrouter_model == "openrouter/stage05-model"
    assert settings.agent_llm_timeout_seconds == 45
    assert settings.agent_save_full_prompt is False
    assert settings.agent_save_full_response is False
    validate_runtime_settings(settings)


def test_prompt_and_response_debug_storage_can_be_enabled_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("AGENT_SAVE_FULL_PROMPT", "true")
    monkeypatch.setenv("AGENT_SAVE_FULL_RESPONSE", "1")

    settings = get_settings()

    assert settings.agent_save_full_prompt is True
    assert settings.agent_save_full_response is True


def test_agent_event_runtime_requires_an_explicit_feature_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("AGENT_EVENT_RUNTIME_ENABLED", "true")

    assert get_settings().agent_event_runtime_enabled is True


def test_stage10_distributed_runtime_reads_mode_key_and_workspace_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64

    workspace_id = "11111111-1111-4111-8111-111111111111"
    monkeypatch.setenv("AGENT_EVENT_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("AGENT_EVENT_RUNTIME_MODE", "redis_worker")
    monkeypatch.setenv(
        "AGENT_RUNTIME_INPUT_KEY",
        base64.urlsafe_b64encode(b"k" * 32).decode("ascii"),
    )
    monkeypatch.setenv("AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS", workspace_id)

    settings = get_settings()

    assert settings.agent_event_runtime_mode == "redis_worker"
    assert settings.agent_runtime_input_key is not None
    assert settings.agent_event_runtime_allowed_workspace_ids == (workspace_id,)


def test_staging_stage10_fails_closed_without_distributed_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/9")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("AGENT_EVENT_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("AGENT_EVENT_RUNTIME_MODE", "embedded")

    with pytest.raises(RuntimeError, match="AGENT_EVENT_RUNTIME_MODE"):
        validate_runtime_settings()
