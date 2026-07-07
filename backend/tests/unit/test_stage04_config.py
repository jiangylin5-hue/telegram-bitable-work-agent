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


def _set_required_staging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://stage:secret@db/app")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-token")


def test_restricted_test_send_requires_bot_token_and_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_SEND_MODE", "restricted_test")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" in message
    assert "super-secret-token" not in message


def test_restricted_test_send_passes_with_bot_token_and_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_SEND_MODE", "restricted_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:stage04-token")
    monkeypatch.setenv("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS", "test-chat-1,test-chat-2")

    settings = get_settings()

    assert settings.telegram_send_mode == "restricted_test"
    assert settings.telegram_test_send_allowed_chat_ids == (
        "test-chat-1",
        "test-chat-2",
    )
    validate_runtime_settings(settings)


@pytest.mark.parametrize("send_mode", ["real", "broadcast", "enabled"])
def test_staging_rejects_unrestricted_send_modes(
    monkeypatch: pytest.MonkeyPatch,
    send_mode: str,
) -> None:
    _clear_runtime_env(monkeypatch)
    _set_required_staging_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_SEND_MODE", send_mode)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:stage04-token")
    monkeypatch.setenv("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS", "test-chat-1")

    settings = get_settings()

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    assert "TELEGRAM_SEND_MODE" in str(exc_info.value)
