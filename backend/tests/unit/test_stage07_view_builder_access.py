from uuid import uuid4

import pytest

from app.models.stage06_platform import WorkspaceMember
from app.schemas.stage06_platform import (
    ViewInitializationRequest,
    ViewMemberCommand,
    ViewPresentationPatchRequest,
)
from app.services.permissions import Actor
from app.services import stage06_platform
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_table,
    create_workspace,
)


def test_v1_initialize_is_private_and_replays_same_idempotency_key() -> None:
    uow, table = _workspace_table()
    initialize = getattr(stage06_platform, "initialize_v1_view", None)
    assert initialize is not None

    request = _grid_initialization("Mine")
    first = initialize(
        uow,
        table.id,
        request=request,
        idempotency_key="new-private",
        actor=_actor("owner-1", "owner"),
    )
    replay = initialize(
        uow,
        table.id,
        request=request,
        idempotency_key="new-private",
        actor=_actor("owner-1", "owner"),
    )

    assert first.replayed is False
    assert first.view.scope == "private"
    assert first.view.owner_user_id == "owner-1"
    assert first.view.is_default is False
    assert first.view.version == 1
    assert replay.replayed is True
    assert replay.view.id == first.view.id
    assert len(uow.list_views(table.id)) == 1

    with pytest.raises(PlatformValidationError) as changed_payload:
        initialize(
            uow,
            table.id,
            request=_grid_initialization("Changed"),
            idempotency_key="new-private",
            actor=_actor("owner-1", "owner"),
        )
    assert changed_payload.value.code == "idempotency_conflict"


def test_owner_editor_viewer_and_versioned_grant_state_are_separated() -> None:
    uow, table = _workspace_table()
    _add_member(uow, "editor-1", "builder")
    _add_member(uow, "viewer-1", "viewer")
    initialize = getattr(stage06_platform, "initialize_v1_view", None)
    replace_members = getattr(stage06_platform, "replace_v1_view_members", None)
    patch_presentation = getattr(stage06_platform, "update_v1_view_presentation", None)
    assert initialize is not None
    assert replace_members is not None
    assert patch_presentation is not None

    created = initialize(
        uow,
        table.id,
        request=_grid_initialization("Mine"),
        idempotency_key="acl-private",
        actor=_actor("owner-1", "owner"),
    ).view
    replaced = replace_members(
        uow,
        created.id,
        expected_version=1,
        members=[ViewMemberCommand(user_id="editor-1", access_level="editor")],
        actor=_actor("owner-1", "owner"),
    )

    assert replaced.scope == "restricted"
    assert replaced.version == 2
    assert [(grant.user_id, grant.access_level) for grant in uow.list_view_grants(created.id)] == [
        ("editor-1", "editor")
    ]

    updated = patch_presentation(
        uow,
        created.id,
        request=ViewPresentationPatchRequest(
            expected_version=2,
            presentation=_grid_presentation(),
        ),
        actor=_actor("editor-1", "builder"),
    )
    assert updated.version == 3

    with pytest.raises(PlatformValidationError) as editor_grant_denial:
        replace_members(
            uow,
            created.id,
            expected_version=3,
            members=[],
            actor=_actor("editor-1", "builder"),
        )
    assert editor_grant_denial.value.code == "view_access_denied"

    with pytest.raises(PlatformValidationError) as viewer_patch_denial:
        patch_presentation(
            uow,
            created.id,
            request=ViewPresentationPatchRequest(
                expected_version=3,
                presentation=_grid_presentation(),
            ),
            actor=_actor("viewer-1", "viewer"),
        )
    assert viewer_patch_denial.value.code == "view_access_denied"

    with pytest.raises(PlatformValidationError) as stale_version:
        patch_presentation(
            uow,
            created.id,
            request=ViewPresentationPatchRequest(
                expected_version=2,
                presentation=_grid_presentation(),
            ),
            actor=_actor("editor-1", "builder"),
        )
    assert stale_version.value.code == "view_version_conflict"


def test_member_replacement_rejects_role_bypasses_even_if_schema_is_constructed() -> None:
    uow, table = _workspace_table()
    _add_member(uow, "member-1", "viewer")
    initialize = getattr(stage06_platform, "initialize_v1_view", None)
    replace_members = getattr(stage06_platform, "replace_v1_view_members", None)
    assert initialize is not None
    assert replace_members is not None
    view = initialize(
        uow,
        table.id,
        request=_grid_initialization("Mine"),
        idempotency_key="member-role",
        actor=_actor("owner-1", "owner"),
    ).view

    with pytest.raises(PlatformValidationError) as exc:
        replace_members(
            uow,
            view.id,
            expected_version=1,
            members=[ViewMemberCommand.model_construct(user_id="member-1", access_level="owner")],
            actor=_actor("owner-1", "owner"),
        )

    assert exc.value.code == "view_member_invalid"


def test_inactive_v1_view_rejects_owner_presentation_mutation() -> None:
    uow, table = _workspace_table()
    initialize = getattr(stage06_platform, "initialize_v1_view", None)
    patch_presentation = getattr(stage06_platform, "update_v1_view_presentation", None)
    assert initialize is not None
    assert patch_presentation is not None
    view = initialize(
        uow,
        table.id,
        request=_grid_initialization("Mine"),
        idempotency_key="inactive-view",
        actor=_actor("owner-1", "owner"),
    ).view
    view.status = "inactive"

    with pytest.raises(PlatformValidationError) as exc:
        patch_presentation(
            uow,
            view.id,
            request=ViewPresentationPatchRequest(
                expected_version=1,
                presentation=_grid_presentation(),
            ),
            actor=_actor("owner-1", "owner"),
        )

    assert exc.value.code == "view_access_denied"


def test_effective_view_access_intersects_active_membership_and_grant_role() -> None:
    uow, table = _workspace_table()
    _add_member(uow, "editor-1", "builder")
    _add_member(uow, "viewer-1", "viewer")
    initialize = getattr(stage06_platform, "initialize_v1_view", None)
    replace_members = getattr(stage06_platform, "replace_v1_view_members", None)
    resolve_access = getattr(stage06_platform, "resolve_v1_view_access", None)
    assert initialize is not None
    assert replace_members is not None
    assert resolve_access is not None
    view = initialize(
        uow,
        table.id,
        request=_grid_initialization("Mine"),
        idempotency_key="access-view",
        actor=_actor("owner-1", "owner"),
    ).view
    replace_members(
        uow,
        view.id,
        expected_version=1,
        members=[
            ViewMemberCommand(user_id="editor-1", access_level="editor"),
            ViewMemberCommand(user_id="viewer-1", access_level="viewer"),
        ],
        actor=_actor("owner-1", "owner"),
    )

    owner = resolve_access(uow, view, actor=_actor("owner-1", "owner"))
    editor = resolve_access(uow, view, actor=_actor("editor-1", "builder"))
    viewer = resolve_access(uow, view, actor=_actor("viewer-1", "viewer"))

    assert (owner.role, owner.can_edit_presentation, owner.can_replace_members) == (
        "owner",
        True,
        True,
    )
    assert (editor.role, editor.can_edit_presentation, editor.can_replace_members) == (
        "editor",
        True,
        False,
    )
    assert (viewer.role, viewer.can_edit_presentation, viewer.can_replace_members) == (
        "viewer",
        False,
        False,
    )


def _workspace_table() -> tuple[InMemoryStage06PlatformUnitOfWork, object]:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Title", key="title", field_type="text")
    return uow, table


def _add_member(
    uow: InMemoryStage06PlatformUnitOfWork,
    user_id: str,
    role: str,
) -> None:
    workspace = uow.workspaces[0]
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user_id,
            role=role,
            status="active",
        )
    )


def _actor(user_id: str, role: str) -> Actor:
    return Actor(actor_type="user", actor_id=user_id, role=role)


def _grid_initialization(name: str) -> ViewInitializationRequest:
    return ViewInitializationRequest(
        name=name,
        view_type="grid",
        presentation=_grid_presentation(),
    )


def _grid_presentation() -> dict[str, object]:
    return {
        "view_type": "grid",
        "visible_field_keys": ["title"],
        "filters": [],
        "sort_rules": [],
        "group_by_field_key": None,
    }
