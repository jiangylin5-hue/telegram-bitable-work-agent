from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from app.models.stage06_platform import Stage06TelegramBinding
from app.services.stage06_identity import (
    Stage06IdentityError,
    Stage06RequestIdentity,
)
from app.services.stage06_platform import Stage06PlatformUnitOfWork


class Stage07TelegramMiniAppIdentityError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ValidatedTelegramMiniAppLaunch:
    telegram_user_id: str
    auth_date: datetime
    start_param: str | None
    chat_type: str | None
    chat_instance: str | None


def validate_telegram_mini_app_init_data(
    raw: str,
    *,
    bot_token: str | None,
    now: datetime,
    max_age_seconds: int,
) -> ValidatedTelegramMiniAppLaunch:
    if not raw:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_required")
    if len(raw.encode("utf-8")) > 8192:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_too_large")

    values = _parse_unique_query_values(raw)
    supplied_hash = values.pop("hash", None)
    if supplied_hash is None or not supplied_hash:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_signature_invalid")
    if not bot_token:
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_bot_token_unavailable"
        )

    secret = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    data_check_string = "\n".join(
        f"{key}={values[key]}" for key in sorted(values)
    )
    expected_hash = hmac.new(
        secret,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash):
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_signature_invalid"
        )

    auth_date = _validated_auth_date(
        values.get("auth_date"),
        now=now,
        max_age_seconds=max_age_seconds,
    )
    telegram_user_id = _validated_telegram_user_id(values.get("user"))
    return ValidatedTelegramMiniAppLaunch(
        telegram_user_id=telegram_user_id,
        auth_date=auth_date,
        start_param=_optional_nonblank(values.get("start_param")),
        chat_type=_optional_nonblank(values.get("chat_type")),
        chat_instance=_optional_nonblank(values.get("chat_instance")),
    )


def _parse_unique_query_values(raw: str) -> dict[str, str]:
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_malformed"
        ) from exc
    values: dict[str, str] = {}
    for key, value in pairs:
        if not key:
            raise Stage07TelegramMiniAppIdentityError(
                "telegram_init_data_malformed"
            )
        if key in values:
            raise Stage07TelegramMiniAppIdentityError(
                "telegram_init_data_duplicate_key"
            )
        values[key] = value
    return values


def _validated_auth_date(
    value: str | None,
    *,
    now: datetime,
    max_age_seconds: int,
) -> datetime:
    try:
        timestamp = int(value or "")
    except ValueError as exc:
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_auth_date_invalid"
        ) from exc
    auth_date = datetime.fromtimestamp(timestamp, UTC)
    reference_now = now.astimezone(UTC)
    age_seconds = (reference_now - auth_date).total_seconds()
    if age_seconds > max_age_seconds:
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_auth_date_stale"
        )
    if age_seconds < -60:
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_auth_date_future"
        )
    return auth_date


def _validated_telegram_user_id(value: str | None) -> str:
    try:
        payload = json.loads(value or "")
    except (json.JSONDecodeError, TypeError) as exc:
        raise Stage07TelegramMiniAppIdentityError(
            "telegram_init_data_user_invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_user_invalid")
    user_id = payload.get("id")
    if isinstance(user_id, bool) or user_id is None:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_user_invalid")
    normalized = str(user_id).strip()
    if not normalized:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_user_invalid")
    return normalized


def _optional_nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def resolve_telegram_request_identity(
    uow: Stage06PlatformUnitOfWork,
    launch: ValidatedTelegramMiniAppLaunch,
) -> Stage06RequestIdentity:
    bindings = [
        binding
        for binding in uow.list_telegram_bindings()
        if _is_active_binding_for_user(binding, launch.telegram_user_id)
    ]
    if not bindings:
        raise Stage06IdentityError(
            "telegram_binding_not_found",
            status_code=403,
        )

    user_ids: set[str] = set()
    for binding in bindings:
        member = (
            None
            if binding.workspace_member_id is None
            else uow.get_workspace_member(binding.workspace_member_id)
        )
        if (
            member is None
            or member.status != "active"
            or member.workspace_id != binding.workspace_id
        ):
            raise Stage06IdentityError(
                "telegram_binding_member_inactive",
                status_code=403,
            )
        user_ids.add(member.user_id)
    if len(user_ids) != 1:
        raise Stage06IdentityError(
            "telegram_binding_ambiguous",
            status_code=403,
        )
    return Stage06RequestIdentity(
        user_id=user_ids.pop(),
        source="telegram_binding",
        telegram_user_id=launch.telegram_user_id,
    )


def _is_active_binding_for_user(
    binding: Stage06TelegramBinding,
    telegram_user_id: str,
) -> bool:
    return (
        binding.status == "active"
        and binding.telegram_user_id == telegram_user_id
    )
