from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from urllib.parse import urlencode

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import Settings, validate_runtime_settings
from app.models.stage06_platform import Stage06TelegramBinding, WorkspaceMember
from app.services.stage06_identity import (
    Stage06IdentityError,
    Stage06RequestIdentity,
)
from app.services.stage07_telegram_mini_app_identity import (
    Stage07TelegramMiniAppIdentityError,
    ValidatedTelegramMiniAppLaunch,
    validate_telegram_mini_app_init_data,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_workspace,
)
from app.services.stage07_telegram_mini_app_identity import (
    resolve_telegram_request_identity,
)
from uuid import uuid4


BOT_TOKEN = "test-token-for-stage07"
NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def _signed_init_data(
    *,
    auth_date: datetime = NOW,
    user: str = '{"id":123,"first_name":"Ada"}',
    start_param: str | None = "opaqueToken_123456",
    chat_type: str | None = "sender",
    chat_instance: str | None = "opaque-chat-instance",
) -> str:
    fields = {
        "auth_date": str(int(auth_date.timestamp())),
        "user": user,
    }
    if start_param is not None:
        fields["start_param"] = start_param
    if chat_type is not None:
        fields["chat_type"] = chat_type
    if chat_instance is not None:
        fields["chat_instance"] = chat_instance
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(
        secret,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(fields)


def _validate(raw: str, *, now: datetime = NOW):
    return validate_telegram_mini_app_init_data(
        raw,
        bot_token=BOT_TOKEN,
        now=now,
        max_age_seconds=300,
    )


def test_validates_minimal_signed_launch_fields() -> None:
    launch = _validate(_signed_init_data())

    assert launch.telegram_user_id == "123"
    assert launch.auth_date == NOW
    assert launch.start_param == "opaqueToken_123456"
    assert launch.chat_type == "sender"
    assert launch.chat_instance == "opaque-chat-instance"
    assert not hasattr(launch, "raw")
    assert not hasattr(launch, "profile")


def test_rejects_duplicate_signed_parameter() -> None:
    raw = _signed_init_data() + "&auth_date=1783944000"

    with pytest.raises(Stage07TelegramMiniAppIdentityError) as denied:
        _validate(raw)

    assert denied.value.code == "telegram_init_data_duplicate_key"


def test_rejects_tampered_signed_value_without_echoing_raw_input() -> None:
    raw = _signed_init_data().replace("Ada", "Mallory")

    with pytest.raises(Stage07TelegramMiniAppIdentityError) as denied:
        _validate(raw)

    assert denied.value.code == "telegram_init_data_signature_invalid"
    assert "Mallory" not in str(denied.value)
    assert BOT_TOKEN not in str(denied.value)


@pytest.mark.parametrize(
    ("auth_date", "expected_code"),
    [
        (NOW - timedelta(seconds=300), None),
        (NOW - timedelta(seconds=301), "telegram_init_data_auth_date_stale"),
        (NOW + timedelta(seconds=60), None),
        (NOW + timedelta(seconds=61), "telegram_init_data_auth_date_future"),
    ],
)
def test_enforces_signed_auth_date_window(
    auth_date: datetime,
    expected_code: str | None,
) -> None:
    raw = _signed_init_data(auth_date=auth_date)

    if expected_code is None:
        assert _validate(raw).auth_date == auth_date
        return

    with pytest.raises(Stage07TelegramMiniAppIdentityError) as denied:
        _validate(raw)
    assert denied.value.code == expected_code


@pytest.mark.parametrize(
    ("raw", "bot_token", "expected_code"),
    [
        ("", BOT_TOKEN, "telegram_init_data_required"),
        (_signed_init_data(), None, "telegram_init_data_bot_token_unavailable"),
        ("auth_date=not-an-integer&hash=abc&user=%7B%7D", BOT_TOKEN, "telegram_init_data_signature_invalid"),
        (_signed_init_data(user="not-json"), BOT_TOKEN, "telegram_init_data_user_invalid"),
        (_signed_init_data(user="{}"), BOT_TOKEN, "telegram_init_data_user_invalid"),
    ],
)
def test_rejects_invalid_identity_inputs(
    raw: str,
    bot_token: str | None,
    expected_code: str,
) -> None:
    with pytest.raises(Stage07TelegramMiniAppIdentityError) as denied:
        validate_telegram_mini_app_init_data(
            raw,
            bot_token=bot_token,
            now=NOW,
            max_age_seconds=300,
        )

    assert denied.value.code == expected_code
    assert BOT_TOKEN not in str(denied.value)


def test_rejects_overlong_raw_launch_data() -> None:
    raw = "x" * 8193

    with pytest.raises(Stage07TelegramMiniAppIdentityError) as denied:
        _validate(raw)

    assert denied.value.code == "telegram_init_data_too_large"


def test_runtime_settings_rejects_telegram_init_age_outside_fixed_boundary() -> None:
    with pytest.raises(RuntimeError, match="TELEGRAM_MINI_APP_INIT_MAX_AGE_SECONDS"):
        validate_runtime_settings(
            Settings(telegram_mini_app_init_max_age_seconds=901),
        )


def _binding_uow(*, member_status: str = "active") -> tuple[
    InMemoryStage06PlatformUnitOfWork,
    WorkspaceMember,
]:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Telegram", owner_user_id="owner-1")
    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id="member-1",
        role="viewer",
        status=member_status,
    )
    uow.add_workspace_member(member)
    return uow, member


def _launch() -> ValidatedTelegramMiniAppLaunch:
    return ValidatedTelegramMiniAppLaunch(
        telegram_user_id="123",
        auth_date=NOW,
        start_param=None,
        chat_type=None,
        chat_instance="must-not-be-used-as-chat-id",
    )


def _add_binding(
    uow: InMemoryStage06PlatformUnitOfWork,
    member: WorkspaceMember,
    *,
    status: str = "active",
) -> None:
    uow.add_telegram_binding(
        Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=member.workspace_id,
            workspace_member_id=member.id,
            telegram_chat_id="real-chat-id",
            telegram_user_id="123",
            binding_type="member",
            default_base_id=None,
            default_digital_employee_id=None,
            scope_policy={},
            status=status,
        )
    )


def test_binding_identity_allows_multiple_active_bindings_for_same_member() -> None:
    uow, member = _binding_uow()
    _add_binding(uow, member)
    _add_binding(uow, member)

    identity = resolve_telegram_request_identity(uow, _launch())

    assert identity == Stage06RequestIdentity(
        user_id="member-1",
        source="telegram_binding",
        telegram_user_id="123",
    )


@pytest.mark.parametrize(
    ("seed", "expected_code"),
    [
        ("none", "telegram_binding_not_found"),
        ("inactive_member", "telegram_binding_member_inactive"),
        ("ambiguous", "telegram_binding_ambiguous"),
    ],
)
def test_binding_identity_fails_closed_for_missing_inactive_or_ambiguous_binding(
    seed: str,
    expected_code: str,
) -> None:
    uow, member = _binding_uow(member_status="inactive" if seed == "inactive_member" else "active")
    if seed != "none":
        _add_binding(uow, member)
    if seed == "ambiguous":
        other_member = WorkspaceMember(
            id=uuid4(),
            workspace_id=member.workspace_id,
            user_id="member-2",
            role="viewer",
            status="active",
        )
        uow.add_workspace_member(other_member)
        _add_binding(uow, other_member)

    with pytest.raises(Stage06IdentityError) as denied:
        resolve_telegram_request_identity(uow, _launch())

    assert denied.value.code == expected_code
    assert denied.value.status_code == 403


def test_identity_dependency_prefers_verified_telegram_proof_over_development_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    uow, member = _binding_uow()
    _add_binding(uow, member)
    app = FastAPI()

    @app.get("/identity")
    def read_identity(
        identity: Stage06RequestIdentity = Depends(deps.get_stage06_request_identity),
    ) -> dict[str, str | None]:
        return {
            "user_id": identity.user_id,
            "source": identity.source,
            "telegram_user_id": identity.telegram_user_id,
        }

    app.dependency_overrides[deps.get_stage06_identity_uow] = lambda: uow
    raw = _signed_init_data(auth_date=datetime.now(UTC))
    with TestClient(app) as client:
        response = client.get(
            "/identity",
            headers={
                "X-Stage06-User-Id": "spoofed-owner",
                "X-Telegram-Init-Data": raw,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "member-1",
        "source": "telegram_binding",
        "telegram_user_id": "123",
    }
