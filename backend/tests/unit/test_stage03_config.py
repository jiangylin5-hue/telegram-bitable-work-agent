import pytest

from app.core.config import get_settings, validate_runtime_settings


RUNTIME_ENV_VARS = [
    "APP_ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_SEND_MODE",
    "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS",
    "LLM_ENABLED",
    "PROVIDER_MODE",
]


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in RUNTIME_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_stage03_runtime_defaults_are_safe_for_local_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)

    settings = get_settings()

    assert settings.environment == "local"
    assert settings.database_url == (
        "postgresql+psycopg://ads_agent:ads_agent@127.0.0.1:5432/"
        "ads_agent?connect_timeout=3"
    )
    assert settings.telegram_send_mode == "dry_run"
    assert settings.provider_mode == "disabled"
    assert settings.llm_enabled is False
    assert settings.telegram_webhook_secret is None
    validate_runtime_settings(settings)


def test_staging_runtime_requires_explicit_database_redis_and_webhook_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "staging")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message
    assert "TELEGRAM_WEBHOOK_SECRET" in message
    assert "TELEGRAM_BOT_TOKEN" not in message


def test_staging_runtime_validation_does_not_leak_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage:secret@db/app")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "REDIS_URL" in message
    assert "super-secret-token" not in message
    assert "stage:secret" not in message


def test_staging_runtime_passes_with_required_receive_only_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage:secret@db/app")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-token")

    settings = get_settings()

    assert settings.telegram_bot_token is None
    assert settings.telegram_webhook_secret == "super-secret-token"
    assert settings.telegram_send_mode == "dry_run"
    assert settings.provider_mode == "disabled"
    assert settings.llm_enabled is False
    validate_runtime_settings(settings)


@pytest.mark.parametrize(
    ("env_name", "env_value", "expected_name"),
    [
        ("TELEGRAM_SEND_MODE", "real", "TELEGRAM_SEND_MODE"),
        ("LLM_ENABLED", "true", "LLM_ENABLED"),
        ("PROVIDER_MODE", "sandbox", "PROVIDER_MODE"),
    ],
)
def test_staging_runtime_rejects_external_action_modes(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    env_value: str,
    expected_name: str,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage:secret@db/app")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-token")
    monkeypatch.setenv(env_name, env_value)

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    assert expected_name in str(exc_info.value)


def test_create_app_validates_staging_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    from app.main import create_app

    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(RuntimeError, match="TELEGRAM_WEBHOOK_SECRET"):
        create_app()
