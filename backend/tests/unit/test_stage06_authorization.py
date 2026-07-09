from uuid import uuid4

import pytest

from app.models.stage06_platform import WorkspaceMember
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
    workspace_id_for_base,
    workspace_id_for_record,
    workspace_id_for_table,
    workspace_id_for_view,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


def _add_member(
    uow: InMemoryStage06PlatformUnitOfWork,
    workspace_id,
    *,
    user_id: str,
    role: str,
    status: str = "active",
) -> None:
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status=status,
        )
    )


def test_stage06_authorization_resolves_actor_from_active_membership() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    _add_member(uow, workspace.id, user_id="builder-1", role="builder")

    actor = authorize_workspace_action(
        uow,
        Stage06RequestIdentity("builder-1", "development_header"),
        workspace.id,
        "base.create",
    )

    assert actor.actor_type == "user"
    assert actor.actor_id == "builder-1"
    assert actor.role == "builder"


def test_stage06_authorization_denies_missing_membership() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")

    with pytest.raises(Stage06AuthorizationError) as denied:
        authorize_workspace_action(
            uow,
            Stage06RequestIdentity("outsider-1", "development_header"),
            workspace.id,
            "workspace.read",
        )

    assert denied.value.code == "stage06_membership_required"


def test_stage06_authorization_denies_inactive_membership() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    _add_member(
        uow,
        workspace.id,
        user_id="viewer-1",
        role="viewer",
        status="inactive",
    )

    with pytest.raises(Stage06AuthorizationError) as denied:
        authorize_workspace_action(
            uow,
            Stage06RequestIdentity("viewer-1", "development_header"),
            workspace.id,
            "workspace.read",
        )

    assert denied.value.code == "stage06_membership_required"


def test_stage06_authorization_denies_viewer_write_action() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    _add_member(uow, workspace.id, user_id="viewer-1", role="viewer")

    with pytest.raises(Stage06AuthorizationError) as denied:
        authorize_workspace_action(
            uow,
            Stage06RequestIdentity("viewer-1", "development_header"),
            workspace.id,
            "base.create",
        )

    assert denied.value.code == "stage06_action_denied"


def test_stage06_authorization_owner_has_all_stage06_actions() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")

    actor = authorize_workspace_action(
        uow,
        Stage06RequestIdentity("owner-1", "development_header"),
        workspace.id,
        "audit.read",
    )

    assert actor.role == "owner"


def test_stage06_resource_resolvers_map_nested_resources_to_workspace() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    record = create_record(uow, table.id, values={})
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Grid",
        view_type="grid",
        config={},
    )

    assert workspace_id_for_base(uow, base.id) == workspace.id
    assert workspace_id_for_table(uow, table.id) == workspace.id
    assert workspace_id_for_record(uow, record.id) == workspace.id
    assert workspace_id_for_view(uow, view.id) == workspace.id
