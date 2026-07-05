from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "telegram-bitable-work-agent"
    environment: str = "local"
    redis_url: str = "redis://localhost:6379/0"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/auto"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/"
        "telegram_bitable_agent"
    )


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
    )
