import pytest
from pydantic import ValidationError

from app.schemas import stage06_platform


def test_view_initialization_is_private_and_rejects_acl_or_raw_config_fields() -> None:
    request_type = getattr(stage06_platform, "ViewInitializationRequest", None)
    assert request_type is not None

    request = request_type.model_validate(_grid_initialization())
    assert request.view_type == "grid"
    assert request.presentation.view_type == "grid"

    with pytest.raises(ValidationError):
        request_type.model_validate(_grid_initialization(members=[]))
    with pytest.raises(ValidationError):
        request_type.model_validate(_grid_initialization(config={"raw": True}))
    with pytest.raises(ValidationError):
        request_type.model_validate(
            _grid_initialization(
                presentation={
                    "view_type": "calendar",
                    "visible_field_keys": ["title"],
                    "date_field_key": "due_date",
                }
            )
        )


def test_presentation_patch_requires_version_and_forbids_raw_view_state() -> None:
    request_type = getattr(stage06_platform, "ViewPresentationPatchRequest", None)
    assert request_type is not None

    request = request_type.model_validate(
        {
            "expected_version": 1,
            "name": "Mine",
            "presentation": _grid_presentation(),
        }
    )
    assert request.expected_version == 1

    with pytest.raises(ValidationError):
        request_type.model_validate({"presentation": _grid_presentation()})
    with pytest.raises(ValidationError):
        request_type.model_validate(
            {"expected_version": 1, "config": {}, "presentation": _grid_presentation()}
        )
    with pytest.raises(ValidationError):
        request_type.model_validate(
            {
                "expected_version": 1,
                "scope": "restricted",
                "presentation": _grid_presentation(),
            }
        )


def test_typed_v1_query_and_member_commands_enforce_documented_bounds() -> None:
    initialization_type = getattr(stage06_platform, "ViewInitializationRequest", None)
    members_type = getattr(stage06_platform, "ViewMemberReplaceRequest", None)
    assert initialization_type is not None
    assert members_type is not None

    with pytest.raises(ValidationError):
        initialization_type.model_validate(
            _grid_initialization(
                presentation={
                    **_grid_presentation(),
                    "filters": [
                        {"field_key": f"field_{index}", "operator": "equals", "value": "x"}
                        for index in range(13)
                    ],
                }
            )
        )
    with pytest.raises(ValidationError):
        initialization_type.model_validate(
            _grid_initialization(
                presentation={
                    **_grid_presentation(),
                    "sort_rules": [
                        {"field_key": f"field_{index}", "direction": "asc"}
                        for index in range(4)
                    ],
                }
            )
        )
    with pytest.raises(ValidationError):
        initialization_type.model_validate(
            _grid_initialization(
                presentation={**_grid_presentation(), "filter_conjunction": "or"}
            )
        )
    with pytest.raises(ValidationError):
        members_type.model_validate(
            {
                "expected_version": 1,
                "members": [
                    {"user_id": f"member-{index}", "access_level": "viewer"}
                    for index in range(101)
                ],
            }
        )
    with pytest.raises(ValidationError):
        members_type.model_validate(
            {
                "expected_version": 1,
                "members": [{"user_id": "member-1", "access_level": "owner"}],
            }
        )


def test_safe_v1_read_models_forbid_raw_config_policy_and_owner_identity() -> None:
    summary_type = getattr(stage06_platform, "SafeViewSummaryResponse", None)
    assert summary_type is not None

    summary = summary_type.model_validate(
        {
            "id": "view-1",
            "base_id": "base-1",
            "table_id": "table-1",
            "name": "Mine",
            "view_type": "grid",
            "scope": "private",
            "caller_access_level": "owner",
            "status": "active",
            "is_default": False,
        }
    )
    assert summary.scope == "private"

    for forbidden_field in ("config", "permission_policy", "owner_user_id", "audit"):
        with pytest.raises(ValidationError):
            summary_type.model_validate(
                {
                    **summary.model_dump(),
                    forbidden_field: {"secret": True},
                }
            )


def _grid_initialization(**overrides: object) -> dict[str, object]:
    return {
        "name": "Mine",
        "view_type": "grid",
        "presentation": _grid_presentation(),
        **overrides,
    }


def _grid_presentation() -> dict[str, object]:
    return {
        "view_type": "grid",
        "visible_field_keys": ["title"],
        "filter_conjunction": "and",
        "filters": [],
        "sort_rules": [],
        "group_by_field_key": None,
    }
