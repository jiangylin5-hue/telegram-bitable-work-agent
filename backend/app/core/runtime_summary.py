import json
from typing import Any

from app.core.config import Settings, get_settings, validate_runtime_settings


def build_redacted_runtime_summary(settings: Settings) -> dict[str, Any]:
    validation_error: str | None = None
    try:
        validate_runtime_settings(settings)
    except RuntimeError as exc:
        validation_error = str(exc)

    return {
        "app_env": settings.environment,
        "llm_enabled": settings.llm_enabled,
        "agent_workflow_mode": settings.agent_workflow_mode,
        "openrouter_key_present": settings.openrouter_api_key is not None,
        "openrouter_model_present": bool(settings.openrouter_model),
        "agent_save_full_prompt": settings.agent_save_full_prompt,
        "agent_save_full_response": settings.agent_save_full_response,
        "telegram_send_mode": settings.telegram_send_mode,
        "telegram_bot_token_present": settings.telegram_bot_token is not None,
        "telegram_test_send_allowlist_present": bool(
            settings.telegram_test_send_allowed_chat_ids
        ),
        "provider_mode": settings.provider_mode,
        "runtime_settings_valid": validation_error is None,
        "validation_error": validation_error,
    }


def main() -> int:
    summary = build_redacted_runtime_summary(get_settings())
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
