from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    confirm_notification_request,
    create_notification_request,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_workspace,
)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    return uow, workspace, base, actor


def _create(
    *,
    server_mode: str,
    server_allowlist: tuple[str, ...],
    send_policy: dict | None = None,
    chat_id: str = "chat-1",
):
    uow, workspace, base, actor = _fixture()
    request = create_notification_request(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        source_record_id=None,
        channel="telegram",
        target={"telegram_chat_id": chat_id},
        message_payload={"text": "hello"},
        send_policy=send_policy or {},
        actor=actor,
        server_mode=server_mode,
        server_allowlist=server_allowlist,
    )
    return uow, request, actor


def test_stage06_notification_is_blocked_when_server_disabled() -> None:
    _uow, request, _actor = _create(
        server_mode="disabled",
        server_allowlist=(),
    )

    assert request.status == "blocked"


def test_stage06_notification_restricted_mode_requires_server_allowlist() -> None:
    _uow, request, _actor = _create(
        server_mode="restricted_test",
        server_allowlist=(),
    )

    assert request.status == "blocked"


def test_stage06_request_allowlist_cannot_broaden_server_allowlist() -> None:
    _uow, request, _actor = _create(
        server_mode="restricted_test",
        server_allowlist=("chat-2",),
        send_policy={"allowlist": ["chat-1"]},
        chat_id="chat-1",
    )

    assert request.status == "blocked"


def test_stage06_notification_can_wait_for_confirmation_when_server_allows() -> None:
    _uow, request, _actor = _create(
        server_mode="restricted_test",
        server_allowlist=("chat-1",),
        send_policy={"confirmation": "required"},
    )

    assert request.status == "pending_confirmation"


def test_stage06_confirmation_cannot_bypass_disabled_server() -> None:
    uow, request, actor = _create(
        server_mode="restricted_test",
        server_allowlist=("chat-1",),
        send_policy={"confirmation": "required"},
    )

    confirmed = confirm_notification_request(
        uow,
        request.id,
        actor=actor,
        server_mode="disabled",
        server_allowlist=("chat-1",),
    )

    assert confirmed.status == "blocked"
