from pathlib import Path
from uuid import UUID, uuid4

from app.models import stage06_platform
from app.models.stage06_platform import PlatformView, ViewMemberGrant
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260711_0022_stage07_saved_view_builder.py"
)


def test_platform_view_declares_v1_owner_scope_and_version() -> None:
    assert hasattr(stage06_platform, "ViewMemberGrant")

    columns = stage06_platform.PlatformView.__table__.c
    assert {"owner_user_id", "scope", "version"} <= set(columns.keys())
    assert columns.owner_user_id.nullable is True
    assert columns.scope.nullable is False
    assert columns.version.nullable is False


def test_view_member_grants_have_narrow_durable_identity_and_unique_pair() -> None:
    grant = stage06_platform.ViewMemberGrant

    assert grant.__tablename__ == "view_member_grants"
    assert {"view_id", "user_id", "access_level", "status"} <= set(
        grant.__table__.c.keys()
    )
    assert "uq_view_member_grants_view_user" in {
        constraint.name for constraint in grant.__table__.constraints
    }


def test_stage07_saved_view_builder_migration_is_additive_after_builder_defaults() -> None:
    assert MIGRATION.is_file()
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260711_0022"' in source
    assert 'down_revision = "20260710_0021"' in source
    assert "view_member_grants" in source
    assert 'server_default="system_default"' in source
    assert 'server_default="1"' in source
    assert "uq_views_one_default_per_table" not in source
    assert "ix_view_member_grants_user_status" not in source
    assert "ix_views_table_scope_status" not in source


def test_in_memory_uow_replaces_grants_and_lists_only_data_accessible_views() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    base_id = uuid4()
    table_id = uuid4()
    default_view = _view(
        base_id=base_id,
        table_id=table_id,
        scope="system_default",
        owner_user_id=None,
    )
    owned_view = _view(
        base_id=base_id,
        table_id=table_id,
        scope="private",
        owner_user_id="owner-1",
    )
    shared_view = _view(
        base_id=base_id,
        table_id=table_id,
        scope="restricted",
        owner_user_id="owner-2",
    )
    hidden_view = _view(
        base_id=base_id,
        table_id=table_id,
        scope="private",
        owner_user_id="owner-2",
    )
    for view in (default_view, owned_view, shared_view, hidden_view):
        uow.add_view(view)

    grant = ViewMemberGrant(
        id=uuid4(),
        view_id=shared_view.id,
        user_id="owner-1",
        access_level="viewer",
        status="active",
    )
    uow.replace_view_grants(shared_view.id, [grant])

    assert uow.lock_view_for_mutation(shared_view.id) is shared_view
    assert uow.list_view_grants(shared_view.id) == [grant]
    assert {view.id for view in uow.list_views_accessible_to_user(table_id, "owner-1")} == {
        default_view.id,
        owned_view.id,
        shared_view.id,
    }


def _view(
    *,
    base_id: UUID,
    table_id: UUID,
    scope: str,
    owner_user_id: str | None,
) -> PlatformView:
    return PlatformView(
        id=uuid4(),
        base_id=base_id,
        table_id=table_id,
        name="View",
        view_type="grid",
        config={},
        permission_policy={},
        is_default=scope == "system_default",
        status="active",
        owner_user_id=owner_user_id,
        scope=scope,
        version=1,
    )
