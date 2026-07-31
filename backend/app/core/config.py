from dataclasses import dataclass
import base64
import os
import re
from typing import Literal
from uuid import UUID


PRODUCTION_LIKE_ENVIRONMENTS = {"staging", "production"}
REQUIRED_PRODUCTION_LIKE_ENV_VARS = (
    "DATABASE_URL",
    "REDIS_URL",
    "TELEGRAM_WEBHOOK_SECRET",
)
STAGE12_RETRIEVAL_ACTIVE_PROFILE = "stage12.openrouter-bge-m3-v1"
STAGE12_PROVIDER_V2_BASELINE_PROFILE = "stage12.openrouter-gemini-2.5-flash-v1"


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
    mini_app_browser_session_cookie_name: str = "mini_app_browser_session"
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
    agent_event_runtime_enabled: bool = False
    agent_event_runtime_mode: str = "embedded"
    agent_event_runtime_allowed_workspace_ids: tuple[str, ...] = ()
    agent_runtime_input_key: str | None = None
    agent_runtime_input_key_version: str = "stage10-v1"
    agent_runtime_input_ttl_seconds: int = 300
    agent_task_planner_v2_mode: str = "disabled"
    agent_task_planner_v2_shadow_workspace_ids: tuple[str, ...] = ()
    authorized_query_engine_v1_mode: Literal["off", "shadow"] = "off"
    authorized_query_engine_v1_workspace_allowlist: tuple[str, ...] = ()
    retrieval_v2_mode: Literal["off", "shadow"] = "off"
    retrieval_v2_workspace_allowlist: tuple[str, ...] = ()
    retrieval_v2_active_profile: str | None = None
    stage12_provider_v2_mode: Literal["off", "benchmark"] = "off"
    stage12_provider_v2_profile: str | None = None
    typed_specialists_v2_mode: Literal["off", "shadow"] = "off"
    typed_specialists_v2_workspace_allowlist: tuple[str, ...] = ()
    durable_action_v1_mode: Literal["off", "isolated", "active"] = "off"
    durable_action_v1_workspace_allowlist: tuple[str, ...] = ()


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
        agent_event_runtime_enabled=_env_bool(
            "AGENT_EVENT_RUNTIME_ENABLED",
            Settings.agent_event_runtime_enabled,
        ),
        agent_event_runtime_mode=os.getenv(
            "AGENT_EVENT_RUNTIME_MODE", Settings.agent_event_runtime_mode
        ),
        agent_event_runtime_allowed_workspace_ids=_env_csv_tuple(
            "AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS"
        ),
        agent_runtime_input_key=os.getenv("AGENT_RUNTIME_INPUT_KEY"),
        agent_runtime_input_key_version=os.getenv(
            "AGENT_RUNTIME_INPUT_KEY_VERSION", Settings.agent_runtime_input_key_version
        ),
        agent_runtime_input_ttl_seconds=_env_int(
            "AGENT_RUNTIME_INPUT_TTL_SECONDS", Settings.agent_runtime_input_ttl_seconds
        ),
        agent_task_planner_v2_mode=os.getenv(
            "AGENT_TASK_PLANNER_V2_MODE",
            Settings.agent_task_planner_v2_mode,
        ),
        agent_task_planner_v2_shadow_workspace_ids=_env_csv_tuple(
            "AGENT_TASK_PLANNER_V2_SHADOW_WORKSPACE_IDS"
        ),
        authorized_query_engine_v1_mode=os.getenv(
            "AUTHORIZED_QUERY_ENGINE_V1_MODE",
            Settings.authorized_query_engine_v1_mode,
        ),
        authorized_query_engine_v1_workspace_allowlist=_env_csv_tuple(
            "AUTHORIZED_QUERY_ENGINE_V1_WORKSPACE_ALLOWLIST"
        ),
        retrieval_v2_mode=os.getenv(
            "RETRIEVAL_V2_MODE",
            Settings.retrieval_v2_mode,
        ),
        retrieval_v2_workspace_allowlist=_env_csv_tuple(
            "RETRIEVAL_V2_WORKSPACE_ALLOWLIST"
        ),
        retrieval_v2_active_profile=os.getenv("RETRIEVAL_V2_ACTIVE_PROFILE"),
        stage12_provider_v2_mode=os.getenv(
            "STAGE12_PROVIDER_V2_MODE",
            Settings.stage12_provider_v2_mode,
        ),
        stage12_provider_v2_profile=os.getenv("STAGE12_PROVIDER_V2_PROFILE"),
        typed_specialists_v2_mode=os.getenv(
            "TYPED_SPECIALISTS_V2_MODE",
            Settings.typed_specialists_v2_mode,
        ),
        typed_specialists_v2_workspace_allowlist=_env_csv_tuple(
            "TYPED_SPECIALISTS_V2_WORKSPACE_ALLOWLIST"
        ),
        durable_action_v1_mode=os.getenv(
            "DURABLE_ACTION_V1_MODE",
            Settings.durable_action_v1_mode,
        ),
        durable_action_v1_workspace_allowlist=_env_csv_tuple(
            "DURABLE_ACTION_V1_WORKSPACE_ALLOWLIST"
        ),
    )


def validate_runtime_settings(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
    if settings.durable_action_v1_mode not in {"off", "isolated", "active"}:
        raise RuntimeError(
            "Invalid DURABLE_ACTION_V1_MODE: expected off, isolated or active"
        )
    if (
        settings.durable_action_v1_mode == "isolated"
        and not settings.durable_action_v1_workspace_allowlist
    ):
        raise RuntimeError("Missing DURABLE_ACTION_V1_WORKSPACE_ALLOWLIST")
    for value in settings.durable_action_v1_workspace_allowlist:
        try:
            UUID(value)
        except ValueError as exc:
            raise RuntimeError("Invalid DURABLE_ACTION_V1_WORKSPACE_ALLOWLIST") from exc
    if settings.typed_specialists_v2_mode not in {"off", "shadow"}:
        raise RuntimeError("Invalid TYPED_SPECIALISTS_V2_MODE: expected off or shadow")
    if settings.typed_specialists_v2_mode == "shadow":
        if not settings.typed_specialists_v2_workspace_allowlist:
            raise RuntimeError("Missing TYPED_SPECIALISTS_V2_WORKSPACE_ALLOWLIST")
        for value in settings.typed_specialists_v2_workspace_allowlist:
            try:
                UUID(value)
            except ValueError as exc:
                raise RuntimeError(
                    "Invalid TYPED_SPECIALISTS_V2_WORKSPACE_ALLOWLIST"
                ) from exc
        if settings.stage12_provider_v2_profile != STAGE12_PROVIDER_V2_BASELINE_PROFILE:
            raise RuntimeError(
                "Invalid STAGE12_PROVIDER_V2_PROFILE: expected confirmed baseline"
            )
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "Missing required Stage12 Provider environment variable: "
                "OPENROUTER_API_KEY"
            )
    if settings.stage12_provider_v2_mode not in {"off", "benchmark"}:
        raise RuntimeError(
            "Invalid STAGE12_PROVIDER_V2_MODE: expected off or benchmark"
        )
    if settings.stage12_provider_v2_mode == "benchmark":
        if settings.stage12_provider_v2_profile != STAGE12_PROVIDER_V2_BASELINE_PROFILE:
            raise RuntimeError(
                "Invalid STAGE12_PROVIDER_V2_PROFILE: expected confirmed baseline"
            )
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "Missing required Stage12 Provider environment variable: "
                "OPENROUTER_API_KEY"
            )
    if settings.retrieval_v2_mode not in {"off", "shadow"}:
        raise RuntimeError("Invalid RETRIEVAL_V2_MODE: expected off or shadow")
    if settings.retrieval_v2_mode == "shadow":
        if not settings.retrieval_v2_workspace_allowlist:
            raise RuntimeError("Missing RETRIEVAL_V2_WORKSPACE_ALLOWLIST")
        for value in settings.retrieval_v2_workspace_allowlist:
            try:
                UUID(value)
            except ValueError as exc:
                raise RuntimeError("Invalid RETRIEVAL_V2_WORKSPACE_ALLOWLIST") from exc
        if settings.retrieval_v2_active_profile != STAGE12_RETRIEVAL_ACTIVE_PROFILE:
            raise RuntimeError(
                "Invalid RETRIEVAL_V2_ACTIVE_PROFILE: expected confirmed Stage12 profile"
            )
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "Missing required Stage12 retrieval environment variable: "
                "OPENROUTER_API_KEY"
            )
    if settings.authorized_query_engine_v1_mode not in {"off", "shadow"}:
        raise RuntimeError(
            "Invalid AUTHORIZED_QUERY_ENGINE_V1_MODE: expected off or shadow"
        )
    if (
        settings.authorized_query_engine_v1_mode == "shadow"
        and not settings.authorized_query_engine_v1_workspace_allowlist
    ):
        raise RuntimeError("Missing AUTHORIZED_QUERY_ENGINE_V1_WORKSPACE_ALLOWLIST")
    for value in settings.authorized_query_engine_v1_workspace_allowlist:
        try:
            UUID(value)
        except ValueError as exc:
            raise RuntimeError(
                "Invalid AUTHORIZED_QUERY_ENGINE_V1_WORKSPACE_ALLOWLIST"
            ) from exc
    if settings.agent_task_planner_v2_mode not in {"disabled", "shadow"}:
        raise RuntimeError(
            "Invalid AGENT_TASK_PLANNER_V2_MODE: expected disabled or shadow"
        )
    if settings.agent_task_planner_v2_mode == "shadow":
        if not settings.agent_task_planner_v2_shadow_workspace_ids:
            raise RuntimeError("Missing AGENT_TASK_PLANNER_V2_SHADOW_WORKSPACE_IDS")
        for value in settings.agent_task_planner_v2_shadow_workspace_ids:
            try:
                UUID(value)
            except ValueError as exc:
                raise RuntimeError(
                    "Invalid AGENT_TASK_PLANNER_V2_SHADOW_WORKSPACE_IDS"
                ) from exc
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
    if settings.agent_event_runtime_enabled:
        if settings.agent_event_runtime_mode not in {"embedded", "redis_worker"}:
            raise RuntimeError(
                "Invalid AGENT_EVENT_RUNTIME_MODE: expected embedded or redis_worker"
            )
        if settings.agent_event_runtime_mode == "redis_worker":
            _validate_agent_runtime_key(settings.agent_runtime_input_key)
        if not 30 <= settings.agent_runtime_input_ttl_seconds <= 900:
            raise RuntimeError(
                "Invalid AGENT_RUNTIME_INPUT_TTL_SECONDS: expected 30..900"
            )
        for value in settings.agent_event_runtime_allowed_workspace_ids:
            try:
                UUID(value)
            except ValueError as exc:
                raise RuntimeError(
                    "Invalid AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS"
                ) from exc
        if settings.environment in PRODUCTION_LIKE_ENVIRONMENTS:
            if settings.agent_event_runtime_mode != "redis_worker":
                raise RuntimeError(
                    "Invalid AGENT_EVENT_RUNTIME_MODE: production-like Stage10 requires redis_worker"
                )
            if not settings.agent_event_runtime_allowed_workspace_ids:
                raise RuntimeError("Missing AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS")
    if settings.environment in PRODUCTION_LIKE_ENVIRONMENTS:
        missing = [
            name for name in REQUIRED_PRODUCTION_LIKE_ENV_VARS if not os.getenv(name)
        ]
        if missing:
            joined_names = ", ".join(missing)
            raise RuntimeError(
                "Missing required runtime environment variables: " f"{joined_names}"
            )
        unsafe = []
        if settings.telegram_send_mode not in {"dry_run", "restricted_test"}:
            unsafe.append("TELEGRAM_SEND_MODE")
        if settings.llm_enabled and settings.agent_workflow_mode != "real_openrouter":
            unsafe.append("LLM_ENABLED")
        if settings.provider_mode != "disabled":
            unsafe.append("PROVIDER_MODE")
        if unsafe:
            joined_names = ", ".join(unsafe)
            raise RuntimeError(
                "Unsafe Stage 03 runtime settings are enabled: " f"{joined_names}"
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


def durable_action_v1_enabled(settings: Settings, workspace_id: UUID) -> bool:
    if settings.durable_action_v1_mode == "active":
        return True
    return (
        settings.durable_action_v1_mode == "isolated"
        and str(workspace_id) in settings.durable_action_v1_workspace_allowlist
    )


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


def _validate_agent_runtime_key(value: str | None) -> None:
    if value is None:
        raise RuntimeError("Missing AGENT_RUNTIME_INPUT_KEY")
    try:
        key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("Invalid AGENT_RUNTIME_INPUT_KEY") from exc
    if len(key) != 32:
        raise RuntimeError("Invalid AGENT_RUNTIME_INPUT_KEY")
