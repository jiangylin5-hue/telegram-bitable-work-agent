from app.models.stage06_platform import PlatformField, WorkspaceMember
from app.services.stage06_authorization import action_allowed_for_role


def test_governance_actions_are_owner_admin_only() -> None:
    assert action_allowed_for_role("owner", "member.manage") is True
    assert action_allowed_for_role("admin", "member.manage") is True
    assert action_allowed_for_role("owner", "field.permission.manage") is True
    assert action_allowed_for_role("admin", "field.permission.manage") is True
    assert action_allowed_for_role("builder", "member.manage") is False
    assert action_allowed_for_role("builder", "field.permission.manage") is False
    assert action_allowed_for_role("viewer", "field.permission.manage") is False


def test_governance_models_start_with_revision_one() -> None:
    assert WorkspaceMember.__table__.c.version.default.arg == 1
    assert PlatformField.__table__.c.permission_version.default.arg == 1
