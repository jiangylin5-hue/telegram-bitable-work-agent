from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage07_telegram import Stage07TelegramDeepLink
from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage06_runtime import RecordChangeDraft
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage07_telegram_deep_links import (
    TelegramDeepLinkDestinationInput,
    resolve_telegram_deep_link,
)
from app.services.stage07_telegram_mini_app_identity import (
    ValidatedTelegramMiniAppLaunch,
)


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260712_0025_stage07_telegram_mini_app_deep_links.py"
)
S6_ROUTE = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "api"
    / "routes"
    / "stage07_telegram.py"
)
MINI_APP_ROOT = Path(__file__).resolve().parents[3] / "mini-app" / "src" / "app"


def _deep_link(
    *,
    workspace_id,
    token_hash: str,
    status: str = "active",
    expires_at: datetime = NOW + timedelta(minutes=10),
) -> Stage07TelegramDeepLink:
    return Stage07TelegramDeepLink(
        id=uuid4(),
        token_hash=token_hash,
        workspace_id=workspace_id,
        subject_telegram_user_id="123",
        source_telegram_chat_id="trusted-source-chat",
        destination_kind="base",
        destination_id=uuid4(),
        status=status,
        expires_at=expires_at,
        created_by_type="system",
        created_by_id="test",
    )


def test_deep_link_model_has_only_closed_state_and_token_hash_constraints() -> None:
    names = {constraint.name for constraint in Stage07TelegramDeepLink.__table__.constraints}
    assert {
        "uq_stage07_telegram_deep_links_token_hash",
        "ck_stage07_telegram_deep_links_kind",
        "ck_stage07_telegram_deep_links_status",
    } <= names
    columns = set(Stage07TelegramDeepLink.__table__.columns.keys())
    assert "token" not in columns
    assert "url" not in columns
    assert "target" not in columns


def test_deep_link_uow_lookup_returns_only_active_unexpired_matching_hash() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Telegram", owner_user_id="owner-1")
    active = _deep_link(workspace_id=workspace.id, token_hash="a" * 64)
    revoked = _deep_link(
        workspace_id=workspace.id,
        token_hash="b" * 64,
        status="revoked",
    )
    expired = _deep_link(
        workspace_id=workspace.id,
        token_hash="c" * 64,
        expires_at=NOW,
    )
    uow.add_telegram_deep_link(active)
    uow.add_telegram_deep_link(revoked)
    uow.add_telegram_deep_link(expired)

    assert uow.get_active_telegram_deep_link_by_token_hash("a" * 64, NOW) == active
    assert uow.get_active_telegram_deep_link_by_token_hash("b" * 64, NOW) is None
    assert uow.get_active_telegram_deep_link_by_token_hash("c" * 64, NOW) is None
    assert uow.get_active_telegram_deep_link_by_token_hash("d" * 64, NOW) is None


def test_deep_link_migration_has_only_approved_revision_and_unique_lookup() -> None:
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260712_0025"' in content
    assert 'down_revision = "20260712_0024"' in content
    assert "stage07_telegram_deep_links" in content
    assert "token_hash" in content
    assert "uq_stage07_telegram_deep_links_token_hash" in content
    assert "source_telegram_chat_id" in content
    assert "raw_token" not in content


def _telegram_header(start_param: str) -> dict[str, str]:
    bot_token = "resolver-test-token"
    fields = {
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        "user": '{"id":123,"first_name":"Ada"}',
        "start_param": start_param,
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(
        secret,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(fields)}


def _resolver_fixture(token_hash: str) -> tuple[
    InMemoryStage06PlatformUnitOfWork,
    Stage07TelegramDeepLink,
]:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Resolver", owner_user_id="member-1")
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="Ops")
    table = create_table(uow, base.id, name="Tasks", key="tasks")
    uow.add_telegram_binding(
        Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="chat-1",
            telegram_user_id="123",
            binding_type="member",
            default_base_id=base.id,
            default_digital_employee_id=None,
            scope_policy={},
            status="active",
        )
    )
    link = Stage07TelegramDeepLink(
        id=uuid4(),
        token_hash=token_hash,
        workspace_id=workspace.id,
        subject_telegram_user_id="123",
        source_telegram_chat_id="chat-1",
        destination_kind="base",
        destination_id=base.id,
        status="active",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        created_by_type="system",
        created_by_id="test",
    )
    uow.add_telegram_deep_link(link)
    assert table.base_id == base.id
    return uow, link


def test_resolver_returns_safe_base_pointer_after_current_authorization(
    monkeypatch,
) -> None:
    start_param = "opaqueToken_123456"
    token_hash = hashlib.sha256(start_param.encode("ascii")).hexdigest()
    uow, link = _resolver_fixture(token_hash)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "resolver-test-token")
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[deps.get_stage06_identity_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.post(
            "/mini-app/telegram/deep-links/resolve",
            headers=_telegram_header(start_param),
            json={"start_param": start_param},
        )

    assert response.status_code == 200
    assert response.json() == {
        "outcome": "resolved",
        "destination": {
            "kind": "base",
            "workspace_id": str(link.workspace_id),
            "base_id": str(link.destination_id),
        },
    }


def test_resolver_returns_same_recovery_for_unknown_or_subject_mismatched_link(
    monkeypatch,
) -> None:
    start_param = "opaqueToken_123456"
    token_hash = hashlib.sha256(start_param.encode("ascii")).hexdigest()
    uow, link = _resolver_fixture(token_hash)
    link.subject_telegram_user_id = "different-telegram-user"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "resolver-test-token")
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[deps.get_stage06_identity_uow] = lambda: uow

    with TestClient(app) as client:
        mismatch = client.post(
            "/mini-app/telegram/deep-links/resolve",
            headers=_telegram_header(start_param),
            json={"start_param": start_param},
        )
        unknown = client.post(
            "/mini-app/telegram/deep-links/resolve",
            headers=_telegram_header("differentOpaque_123456"),
            json={"start_param": "differentOpaque_123456"},
        )

    assert mismatch.status_code == unknown.status_code == 200
    assert mismatch.json() == unknown.json() == {"outcome": "recovery"}


def test_resolver_requires_telegram_launch_proof_before_identity_fallback() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mini-app/telegram/deep-links/resolve",
            headers={"X-Stage06-User-Id": "development-user"},
            json={"start_param": "opaqueToken_123456"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "telegram_init_data_required"


def test_resolver_rechecks_all_closed_destination_kinds_without_target_values() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Destination", owner_user_id="member-1")
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="Ops")
    table = create_table(uow, base.id, name="Tasks", key="tasks")
    create_field(uow, table.id, name="Secret title", key="title", field_type="text")
    record = create_record(uow, table.id, values={"title": "must-not-return"})
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Grid",
        view_type="grid",
        config={"fields": ["title"]},
    )
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=record.id,
        draft_type="record_update",
        proposed_values={"title": "also-must-not-return"},
        before_values={"title": "must-not-return"},
        created_by_type="digital_employee",
        created_by_id="employee",
        status="pending_confirmation",
        confirmation_policy={},
        trace_id="private-trace",
        expected_version=record.version,
        version=1,
    )
    uow.add_record_change_draft(draft)
    uow.add_telegram_binding(
        Stage06TelegramBinding(
            id=uuid4(), workspace_id=workspace.id, workspace_member_id=member.id,
            telegram_chat_id="chat-1", telegram_user_id="123", binding_type="member",
            default_base_id=base.id, default_digital_employee_id=None,
            scope_policy={}, status="active",
        )
    )
    identity = Stage06RequestIdentity(
        user_id="member-1", source="telegram_binding", telegram_user_id="123"
    )
    expected = {
        "base": (base.id, {"base_id": base.id}),
        "view": (view.id, {"base_id": base.id, "table_id": table.id, "view_id": view.id}),
        "record": (record.id, {"base_id": base.id, "table_id": table.id, "record_id": record.id}),
        "record_change_draft": (draft.id, {"base_id": base.id, "table_id": table.id, "record_id": record.id, "draft_id": draft.id}),
    }
    for kind, (destination_id, expected_ids) in expected.items():
        start_param = f"opaque_{kind}_123456"
        link = Stage07TelegramDeepLink(
            id=uuid4(), token_hash=hashlib.sha256(start_param.encode()).hexdigest(),
            workspace_id=workspace.id, subject_telegram_user_id="123", source_telegram_chat_id="chat-1",
            destination_kind=kind, destination_id=destination_id, status="active",
            expires_at=NOW + timedelta(minutes=10), created_by_type="system", created_by_id="test",
        )
        uow.add_telegram_deep_link(link)
        destination = resolve_telegram_deep_link(
            uow, identity=identity,
            launch=ValidatedTelegramMiniAppLaunch("123", NOW, start_param, None, None),
            start_param=start_param, now=NOW,
        )
        assert destination is not None
        assert destination.kind == kind
        assert destination.workspace_id == workspace.id
        for field_name, field_value in expected_ids.items():
            assert getattr(destination, field_name) == field_value
        assert "must-not-return" not in repr(destination)
        assert "private-trace" not in repr(destination)


def test_resolver_recovers_when_link_is_revoked_or_source_member_loses_access() -> None:
    start_param = "opaqueToken_123456"
    uow, link = _resolver_fixture(hashlib.sha256(start_param.encode()).hexdigest())
    identity = Stage06RequestIdentity("member-1", "telegram_binding", "123")
    launch = ValidatedTelegramMiniAppLaunch("123", NOW, start_param, None, None)
    link.status = "revoked"
    assert resolve_telegram_deep_link(uow, identity=identity, launch=launch, start_param=start_param, now=NOW) is None
    link.status = "active"
    uow.list_workspace_members(link.workspace_id)[0].status = "inactive"
    assert resolve_telegram_deep_link(uow, identity=identity, launch=launch, start_param=start_param, now=NOW) is None


def test_resolver_locks_active_link_before_rechecking_authorization() -> None:
    start_param = "opaqueToken_123456"
    uow, _link = _resolver_fixture(hashlib.sha256(start_param.encode()).hexdigest())
    now = datetime.now(UTC)
    original_lookup = uow.get_active_telegram_deep_link_by_token_hash
    lookup_options: list[bool] = []

    def tracked_lookup(token_hash: str, now: datetime, *, for_update: bool = False):
        lookup_options.append(for_update)
        return original_lookup(token_hash, now)

    uow.get_active_telegram_deep_link_by_token_hash = tracked_lookup  # type: ignore[method-assign]

    destination = resolve_telegram_deep_link(
        uow,
        identity=Stage06RequestIdentity("member-1", "telegram_binding", "123"),
        launch=ValidatedTelegramMiniAppLaunch("123", now, start_param, None, None),
        start_param=start_param,
        now=now,
    )

    assert destination is not None
    assert lookup_options == [True]


def test_resolver_mismatch_never_looks_up_a_token_or_writes_resolution_audit() -> None:
    start_param = "opaqueToken_123456"
    uow, _link = _resolver_fixture(hashlib.sha256(start_param.encode()).hexdigest())
    lookup_calls = 0

    def forbidden_lookup(*_args, **_kwargs):
        nonlocal lookup_calls
        lookup_calls += 1
        raise AssertionError("mismatched start parameter must not query a token")

    uow.get_active_telegram_deep_link_by_token_hash = forbidden_lookup  # type: ignore[method-assign]

    destination = resolve_telegram_deep_link(
        uow,
        identity=Stage06RequestIdentity("member-1", "telegram_binding", "123"),
        launch=ValidatedTelegramMiniAppLaunch("123", NOW, "otherOpaque_123456", None, None),
        start_param=start_param,
        now=NOW,
    )

    assert destination is None
    assert lookup_calls == 0
    assert not [
        event
        for event in uow.audit_events
        if event.event_type == "stage07.telegram_deep_link_resolved"
    ]


def test_resolver_audit_retains_only_closed_destination_metadata() -> None:
    start_param = "opaqueToken_123456"
    uow, link = _resolver_fixture(hashlib.sha256(start_param.encode()).hexdigest())
    now = datetime.now(UTC)
    raw_init_data = "auth_date=secret&user=%7B%22first_name%22%3A%22Ada%22%7D"

    destination = resolve_telegram_deep_link(
        uow,
        identity=Stage06RequestIdentity("member-1", "telegram_binding", "123"),
        launch=ValidatedTelegramMiniAppLaunch("123", now, start_param, "private", "opaque-chat"),
        start_param=start_param,
        now=now,
    )

    assert destination is not None
    event = next(
        item
        for item in uow.audit_events
        if item.event_type == "stage07.telegram_deep_link_resolved"
    )
    assert event.after_state == {
        "outcome": "resolved",
        "destination_kind": "base",
        "destination_id": str(link.destination_id),
    }
    serialized = repr(event)
    for forbidden in (start_param, raw_init_data, "Ada", "opaque-chat", "private"):
        assert forbidden not in serialized


def test_s6_public_surface_has_no_mint_send_or_browser_persistence_entry() -> None:
    route_source = S6_ROUTE.read_text(encoding="utf-8")
    assert route_source.count("@router.post(") == 1
    assert '"/mini-app/telegram/deep-links/resolve"' in route_source
    for forbidden in ("mint_telegram_deep_link", "TelegramBotClient", "send_message", "sendMessage"):
        assert forbidden not in route_source

    frontend_sources = "\n".join(
        (MINI_APP_ROOT / name).read_text(encoding="utf-8")
        for name in ("App.tsx", "api.ts", "telegram-mini-app.ts", "protectedQuery.ts")
    )
    for forbidden in (
        "sendData",
        "answerWebAppQuery",
        "localStorage",
        "sessionStorage",
        "persistQueryClient",
    ):
        assert forbidden not in frontend_sources
