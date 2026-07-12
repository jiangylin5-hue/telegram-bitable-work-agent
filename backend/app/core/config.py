from dataclasses import dataclass
import os
import re


PRODUCTION_LIKE_ENVIRONMENTS = {"staging", "production"}
REQUIRED_PRODUCTION_LIKE_ENV_VARS = (
    "DATABASE_URL",
    "REDIS_URL",
    "TELEGRAM_WEBHOOK_SECRET",
)


@dataclass(frozen=True)
class Settings:
    app_name: str = "telegram-bitable-work-agent"
    environment: str = "local"
    redis_url: str = "redis://localhost:6379/0"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/auto"
    database_url: str = (
        "postgresql+psycopg://ads_agent:ads_agent@127.0.0.1:5432/"
        "ads_agent?connect_timeout=3"
    )
    telegram_bot_token: str | None = None
    telegram_mini_app_init_max_age_seconds: int = 300
    telegram_webhook_secret: str | None = None
    telegram_allowed_chat_ids: tuple[str, ...] = ()
    telegram_allowed_user_ids: tuple[str, ...] = ()
    telegram_send_mode: str = "dry_run"
    telegram_test_send_allowed_chat_ids: tuple[str, ...] = ()
    stage07_telegram_bot_username: str | None = None
    provider_mode: str = "disabled"
    stage06_notification_mode: str = "disabled"
    stage06_notification_allowed_chat_ids: tuple[str, ...] = ()
    llm_enabled: bool = False
    agent_workflow_mode: str = "fake"
    agent_llm_timeout_seconds: int = 30
    agent_save_full_prompt: bool = False
    agent_save_full_response: bool = False


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", Settings.app_name),
        environment=os.getenv("APP_ENV", Settings.environment),
        redis_url=os.getenv("REDIS_URL", Settings.redis_url),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL",
            Settings.openrouter_base_url,
        ),
        openrouter_model=os.getenv("OPENROUTER_MODEL", Settings.openrouter_model),
        database_url=os.getenv("DATABASE_URL", Settings.database_url),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_mini_app_init_max_age_seconds=_env_int(
            "TELEGRAM_MINI_APP_INIT_MAX_AGE_SECONDS",
            Settings.telegram_mini_app_init_max_age_seconds,
        ),
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
        telegram_allowed_chat_ids=_env_csv_tuple("TELEGRAM_ALLOWED_CHAT_IDS"),
        telegram_allowed_user_ids=_env_csv_tuple("TELEGRAM_ALLOWED_USER_IDS"),
        telegram_send_mode=os.getenv(
            "TELEGRAM_SEND_MODE",
            Settings.telegram_send_mode,
        ),
        telegram_test_send_allowed_chat_ids=_env_csv_tuple(
            "TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS"
        ),
        stage07_telegram_bot_username=os.getenv("STAGE07_TELEGRAM_BOT_USERNAME"),
        provider_mode=os.getenv("PROVIDER_MODE", Settings.provider_mode),
        stage06_notification_mode=os.getenv(
            "STAGE06_NOTIFICATION_MODE",
            Settings.stage06_notification_mode,
        ),
        stage06_notification_allowed_chat_ids=_env_csv_tuple(
            "STAGE06_NOTIFICATION_ALLOWED_CHAT_IDS"
        ),
        llm_enabled=_env_bool("LLM_ENABLED", Settings.llm_enabled),
        agent_workflow_mode=os.getenv(
            "AGENT_WORKFLOW_MODE",
            Settings.agent_workflow_mode,
        ),
        agent_llm_timeout_seconds=_env_int(
            "AGENT_LLM_TIMEOUT_SECONDS",
            Settings.agent_llm_timeout_seconds,
        ),
        agent_save_full_prompt=_env_bool(
            "AGENT_SAVE_FULL_PROMPT",
            Settings.agent_save_full_prompt,
        ),
        agent_save_full_response=_env_bool(
            "AGENT_SAVE_FULL_RESPONSE",
            Settings.agent_save_full_response,
        ),
    )


def validate_runtime_settings(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
    if not 1 <= settings.telegram_mini_app_init_max_age_seconds <= 900:
        raise RuntimeError(
            "Invalid TELEGRAM_MINI_APP_INIT_MAX_AGE_SECONDS: expected 1..900"
        )
    if (
        settings.agent_workflow_mode == "real_openrouter"
        and not settings.openrouter_api_key
    ):
        raise RuntimeError(
            "Missing required Stage 05 OpenRouter environment variables: "
            "OPENROUTER_API_KEY"
        )
    if settings.environment in PRODUCTION_LIKE_ENVIRONMENTS:
        missing = [
            name
            for name in REQUIRED_PRODUCTION_LIKE_ENV_VARS
            if not os.getenv(name)
        ]
        if missing:
            joined_names = ", ".join(missing)
            raise RuntimeError(
                "Missing required runtime environment variables: "
                f"{joined_names}"
            )
        unsafe = []
        if settings.telegram_send_mode not in {"dry_run", "restricted_test"}:
            unsafe.append("TELEGRAM_SEND_MODE")
        if (
            settings.llm_enabled
            and settings.agent_workflow_mode != "real_openrouter"
        ):
            unsafe.append("LLM_ENABLED")
        if settings.provider_mode != "disabled":
            unsafe.append("PROVIDER_MODE")
        if unsafe:
            joined_names = ", ".join(unsafe)
            raise RuntimeError(
                "Unsafe Stage 03 runtime settings are enabled: "
                f"{joined_names}"
            )
        if settings.telegram_send_mode == "restricted_test":
            missing_restricted_send = []
            if not settings.telegram_bot_token:
                missing_restricted_send.append("TELEGRAM_BOT_TOKEN")
            if not settings.telegram_test_send_allowed_chat_ids:
                missing_restricted_send.append("TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS")
            if missing_restricted_send:
                joined_names = ", ".join(missing_restricted_send)
                raise RuntimeError(
                    "Missing required restricted test send environment variables: "
                    f"{joined_names}"
                )
    return settings


def validate_stage07_telegram_controlled_delivery_settings(
    settings: Settings,
) -> str:
    if settings.telegram_send_mode != "restricted_test":
        raise RuntimeError(
            "Invalid telegram_send_mode: controlled delivery requires restricted_test"
        )
    if len(settings.telegram_test_send_allowed_chat_ids) != 1:
        raise RuntimeError(
            "Invalid telegram_test_send_allowed_chat_ids: expected exactly one value"
        )
    username = settings.stage07_telegram_bot_username
    if username is None or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]",
        username,
    ):
        raise RuntimeError(
            "Invalid stage07_telegram_bot_username: expected Telegram Bot username"
        )
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "Missing required controlled delivery setting: TELEGRAM_BOT_TOKEN"
        )
    return username


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value.strip())


def _env_csv_tuple(name: str) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())
