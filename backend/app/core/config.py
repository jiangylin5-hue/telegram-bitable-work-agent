from dataclasses import dataclass
import os


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
    telegram_webhook_secret: str | None = None
    telegram_allowed_chat_ids: tuple[str, ...] = ()
    telegram_allowed_user_ids: tuple[str, ...] = ()
    telegram_send_mode: str = "dry_run"
    provider_mode: str = "disabled"
    llm_enabled: bool = False


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
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
        telegram_allowed_chat_ids=_env_csv_tuple("TELEGRAM_ALLOWED_CHAT_IDS"),
        telegram_allowed_user_ids=_env_csv_tuple("TELEGRAM_ALLOWED_USER_IDS"),
        telegram_send_mode=os.getenv(
            "TELEGRAM_SEND_MODE",
            Settings.telegram_send_mode,
        ),
        provider_mode=os.getenv("PROVIDER_MODE", Settings.provider_mode),
        llm_enabled=_env_bool("LLM_ENABLED", Settings.llm_enabled),
    )


def validate_runtime_settings(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
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
        if settings.telegram_send_mode != "dry_run":
            unsafe.append("TELEGRAM_SEND_MODE")
        if settings.llm_enabled:
            unsafe.append("LLM_ENABLED")
        if settings.provider_mode != "disabled":
            unsafe.append("PROVIDER_MODE")
        if unsafe:
            joined_names = ", ".join(unsafe)
            raise RuntimeError(
                "Unsafe Stage 03 runtime settings are enabled: "
                f"{joined_names}"
            )
    return settings


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv_tuple(name: str) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())
