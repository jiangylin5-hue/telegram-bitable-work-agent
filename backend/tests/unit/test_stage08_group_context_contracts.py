from pydantic import ValidationError
import pytest

from app.runtime.stage08_group_context_contracts import (
    GROUP_CONTEXT_COMPRESSION_THRESHOLD_CHARS,
    GROUP_CONTEXT_HISTORY_HALF_LIFE_DAYS,
    GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT,
    GROUP_CONTEXT_LATEST_RAW_CHARS,
    GROUP_CONTEXT_MAX_FRAGMENT_CHARS,
    GROUP_CONTEXT_MAX_FRAGMENTS,
    GROUP_CONTEXT_MAX_RAW_CHARS,
    GROUP_CONTEXT_RETENTION_DAYS,
    GroupContextBudgetUsage,
    GroupContextOmissionCounts,
    GroupContextWindowView,
    validate_group_context_window_view,
)


def _view(**overrides) -> GroupContextWindowView:
    values = {
        "contract_version": "stage08-group-context-window.v1",
        "status": "group_context_available",
        "usage": GroupContextBudgetUsage(
            considered_fragments=1,
            selected_fragments=1,
            latest_selected_fragments=1,
            history_selected_fragments=0,
            raw_selected_chars=500,
        ),
        "omissions": GroupContextOmissionCounts(
            expired=0,
            latest_band_limit=0,
            fragment_limit=0,
            character_limit=0,
        ),
        "compression_required": False,
    }
    values.update(overrides)
    return GroupContextWindowView(**values)


def test_group_context_contract_uses_exact_fixed_budgets() -> None:
    assert (
        GROUP_CONTEXT_RETENTION_DAYS,
        GROUP_CONTEXT_MAX_FRAGMENTS,
        GROUP_CONTEXT_MAX_FRAGMENT_CHARS,
        GROUP_CONTEXT_MAX_RAW_CHARS,
        GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT,
        GROUP_CONTEXT_LATEST_RAW_CHARS,
        GROUP_CONTEXT_HISTORY_HALF_LIFE_DAYS,
        GROUP_CONTEXT_COMPRESSION_THRESHOLD_CHARS,
    ) == (30, 120, 500, 60_000, 24, 12_000, 7, 24_000)


def test_window_view_is_strict_count_only_and_revalidated() -> None:
    view = validate_group_context_window_view(_view())
    payload = view.model_dump(mode="python")
    assert set(payload) == {
        "contract_version",
        "status",
        "usage",
        "omissions",
        "compression_required",
    }
    nested_keys = set(payload) | set(payload["usage"]) | set(payload["omissions"])
    for forbidden in (
        "text",
        "content",
        "uuid",
        "telegram",
        "binding",
        "mapping",
        "source_id",
        "token",
        "permission",
        "workspace_id",
        "customer_id",
        "project_id",
    ):
        assert forbidden not in nested_keys

    crafted = GroupContextWindowView.model_construct(
        contract_version="wrong",
        status="group_context_available",
        usage={"selected_fragments": 999},
        omissions={},
        compression_required=False,
    )
    with pytest.raises(ValidationError):
        validate_group_context_window_view(crafted)


def test_window_view_deeply_rebuilds_nested_models_and_rejects_constructed_counts() -> None:
    class CraftedUsage(GroupContextBudgetUsage):
        leaked_text: str

    crafted_usage = CraftedUsage(
        considered_fragments=1,
        selected_fragments=1,
        latest_selected_fragments=1,
        history_selected_fragments=0,
        raw_selected_chars=2,
        leaked_text="must not survive",
    )
    crafted = GroupContextWindowView.model_construct(
        contract_version="stage08-group-context-window.v1",
        status="group_context_available",
        usage=crafted_usage,
        omissions=GroupContextOmissionCounts(
            expired=0,
            latest_band_limit=0,
            fragment_limit=0,
            character_limit=0,
        ),
        compression_required=False,
    )
    safe = validate_group_context_window_view(crafted)
    assert type(safe.usage) is GroupContextBudgetUsage
    assert "leaked_text" not in safe.model_dump(mode="python")["usage"]

    negative_usage = GroupContextBudgetUsage.model_construct(
        considered_fragments=1,
        selected_fragments=-1,
        latest_selected_fragments=-1,
        history_selected_fragments=0,
        raw_selected_chars=-1,
    )
    negative_omissions = GroupContextOmissionCounts.model_construct(
        expired=-1,
        latest_band_limit=0,
        fragment_limit=0,
        character_limit=0,
    )
    for usage, omissions in (
        (negative_usage, crafted.omissions),
        (crafted_usage, negative_omissions),
    ):
        malicious = GroupContextWindowView.model_construct(
            contract_version="stage08-group-context-window.v1",
            status="group_context_available",
            usage=usage,
            omissions=omissions,
            compression_required=False,
        )
        with pytest.raises(ValidationError):
            validate_group_context_window_view(malicious)


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "available"},
        {"text": "forbidden"},
        {"source_refs": ["forbidden"]},
        {"compression_summary": "forbidden"},
    ],
)
def test_window_view_rejects_invalid_status_and_any_content_carrier(payload) -> None:
    data = _view().model_dump(mode="python")
    data.update(payload)
    with pytest.raises(ValidationError):
        GroupContextWindowView.model_validate(data)


def test_usage_rejects_501st_code_point_121st_fragment_and_wrong_compression_flag() -> None:
    with pytest.raises(ValidationError):
        GroupContextBudgetUsage(
            considered_fragments=121,
            selected_fragments=121,
            latest_selected_fragments=24,
            history_selected_fragments=97,
            raw_selected_chars=501 * 121,
        )
    with pytest.raises(ValidationError):
        _view(
            usage=GroupContextBudgetUsage(
                considered_fragments=1,
                selected_fragments=1,
                latest_selected_fragments=1,
                history_selected_fragments=0,
                raw_selected_chars=501,
            )
        )
    with pytest.raises(ValidationError):
        _view(
            usage=GroupContextBudgetUsage(
                considered_fragments=49,
                selected_fragments=49,
                latest_selected_fragments=24,
                history_selected_fragments=25,
                raw_selected_chars=24_001,
            ),
            compression_required=False,
        )


def test_partial_status_requires_selected_fragment_and_omission() -> None:
    omissions = GroupContextOmissionCounts(
        expired=1,
        latest_band_limit=0,
        fragment_limit=0,
        character_limit=0,
    )
    with pytest.raises(ValidationError):
        _view(omissions=omissions)
    with pytest.raises(ValidationError):
        _view(
            status="group_context_partial",
            usage=GroupContextBudgetUsage(
                considered_fragments=1,
                selected_fragments=0,
                latest_selected_fragments=0,
                history_selected_fragments=0,
                raw_selected_chars=0,
            ),
            omissions=omissions,
        )
    partial = _view(status="group_context_partial", omissions=omissions)
    assert partial.usage.selected_fragments == 1
    assert partial.omissions.total == 1
