from __future__ import annotations

from typing import get_args, get_origin

from pydantic import ValidationError
import pytest

from app.runtime.stage08_context_composition_contracts import (
    COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS,
    COMPOSITE_CONTEXT_GROUP_MAX_DIRECT_CHARS,
    COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS,
    COMPOSITE_CONTEXT_MAX_CONTENT_CHARS,
    COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS,
    CompositeContextBudgetUsage,
    CompositeContextView,
    validate_composite_context_view,
)


_SECRET = "task1-secret-86b5ed34-36dd-4975-9735-90bb02c9bce8"


def _usage(**overrides: object) -> CompositeContextBudgetUsage:
    values: dict[str, object] = {
        "c1_evidence_items": 1,
        "group_window_fragments": 2,
        "group_rendered_fragments": 2,
        "c1_content_chars": 100,
        "group_rendered_chars": 200,
        "total_content_chars": 300,
    }
    values.update(overrides)
    return CompositeContextBudgetUsage.model_validate(values)


def _view(**overrides: object) -> CompositeContextView:
    values: dict[str, object] = {
        "contract_version": "stage08-composite-context.v1",
        "status": "internal_evidence",
        "c1_status": "internal_evidence",
        "group_status": "group_context_available",
        "group_compression_required": False,
        "usage": _usage(),
    }
    values.update(overrides)
    return CompositeContextView.model_validate(values)


def _empty_usage() -> CompositeContextBudgetUsage:
    return _usage(
        c1_evidence_items=0,
        group_window_fragments=0,
        group_rendered_fragments=0,
        c1_content_chars=0,
        group_rendered_chars=0,
        total_content_chars=0,
    )


def test_contract_uses_exact_fixed_content_and_item_budgets() -> None:
    assert (
        COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS,
        COMPOSITE_CONTEXT_GROUP_MAX_DIRECT_CHARS,
        COMPOSITE_CONTEXT_MAX_CONTENT_CHARS,
        COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS,
        COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS,
    ) == (12_000, 24_000, 36_000, 24, 120)


def test_valid_direct_pending_general_and_no_evidence_shapes() -> None:
    direct = _view()
    pending = _view(
        status="group_compression_pending",
        group_compression_required=True,
        usage=_usage(
            group_rendered_fragments=0,
            group_rendered_chars=0,
            total_content_chars=100,
        ),
    )
    general = _view(
        status="general_advice_only",
        c1_status="general_advice_only",
        group_status="group_context_unavailable",
        usage=_empty_usage(),
    )
    no_evidence = _view(
        status="no_evidence",
        c1_status="no_evidence",
        group_status="group_context_unavailable",
        usage=_empty_usage(),
    )

    assert direct.status == "internal_evidence"
    assert pending.status == "group_compression_pending"
    assert general.status == "general_advice_only"
    assert no_evidence.status == "no_evidence"


def test_general_advice_marker_is_removed_when_direct_group_is_usable() -> None:
    view = _view(
        c1_status="general_advice_only",
        usage=_usage(
            c1_evidence_items=0,
            c1_content_chars=0,
            total_content_chars=200,
        ),
    )

    assert view.status == "internal_evidence"
    assert view.c1_status == "general_advice_only"
    assert view.usage.c1_evidence_items == 0
    assert view.usage.c1_content_chars == 0
    assert view.usage.group_rendered_fragments == 2


def test_exact_36_000_budget_is_valid_and_every_cap_is_enforced() -> None:
    exact = _usage(
        c1_evidence_items=24,
        group_window_fragments=120,
        group_rendered_fragments=120,
        c1_content_chars=12_000,
        group_rendered_chars=24_000,
        total_content_chars=36_000,
    )
    assert exact.total_content_chars == 36_000

    invalid_overrides = (
        {"c1_evidence_items": 25},
        {"group_window_fragments": 121},
        {"group_rendered_fragments": 121},
        {"c1_content_chars": 12_001, "total_content_chars": 12_201},
        {"group_rendered_chars": 24_001, "total_content_chars": 24_101},
        {
            "c1_content_chars": 12_000,
            "group_rendered_chars": 24_000,
            "total_content_chars": 36_001,
        },
    )
    for overrides in invalid_overrides:
        values = _usage().model_dump(mode="python")
        values.update(overrides)
        with pytest.raises(ValidationError):
            CompositeContextBudgetUsage.model_validate(values)


def test_usage_rejects_false_arithmetic_and_more_rendered_than_window() -> None:
    for overrides in (
        {"total_content_chars": 299},
        {"group_window_fragments": 1, "group_rendered_fragments": 2},
    ):
        values = _usage().model_dump(mode="python")
        values.update(overrides)
        with pytest.raises(ValidationError, match="composite_context_usage_invalid"):
            CompositeContextBudgetUsage.model_validate(values)


@pytest.mark.parametrize(
    ("usage_overrides", "flag"),
    [
        ({"group_rendered_fragments": 1, "group_rendered_chars": 0}, True),
        ({"group_rendered_fragments": 0, "group_rendered_chars": 1}, True),
        ({"group_rendered_fragments": 0, "group_rendered_chars": 0}, False),
    ],
)
def test_pending_requires_true_flag_and_contains_no_rendered_group_body(
    usage_overrides: dict[str, int], flag: bool
) -> None:
    values = _usage().model_dump(mode="python")
    values.update(usage_overrides)
    values["total_content_chars"] = (
        values["c1_content_chars"] + values["group_rendered_chars"]
    )
    with pytest.raises(
        ValidationError, match="composite_context_compression_state_invalid"
    ):
        _view(
            status="group_compression_pending",
            group_compression_required=flag,
            usage=CompositeContextBudgetUsage.model_validate(values),
        )


def test_true_compression_flag_requires_pending_status() -> None:
    with pytest.raises(
        ValidationError, match="composite_context_compression_state_invalid"
    ):
        _view(group_compression_required=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "status": "internal_evidence",
            "c1_status": "no_evidence",
            "group_status": "group_context_unavailable",
            "usage": _empty_usage(),
        },
        {
            "status": "internal_evidence",
            "c1_status": "general_advice_only",
            "usage": _usage(),
        },
        {
            "status": "general_advice_only",
            "c1_status": "internal_evidence",
            "group_status": "group_context_unavailable",
            "usage": _empty_usage(),
        },
        {
            "status": "general_advice_only",
            "c1_status": "general_advice_only",
            "usage": _usage(
                c1_evidence_items=0,
                c1_content_chars=0,
                total_content_chars=200,
            ),
        },
        {
            "status": "no_evidence",
            "c1_status": "no_evidence",
            "group_status": "group_context_unavailable",
            "usage": _usage(
                group_window_fragments=0,
                group_rendered_fragments=0,
                group_rendered_chars=0,
                total_content_chars=100,
            ),
        },
    ],
)
def test_invalid_status_c1_and_group_combinations_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="composite_context_status_invalid"):
        _view(**overrides)


@pytest.mark.parametrize(
    "carrier",
    [
        "content",
        "renderer",
        "digest",
        "actor",
        "plan",
        "scope",
        "chat_id",
        "message_id",
        "source_ref",
        "uuid",
    ],
)
def test_safe_view_rejects_every_body_identity_and_execution_carrier(
    carrier: str,
) -> None:
    payload = _view().model_dump(mode="python")
    payload[carrier] = _SECRET
    with pytest.raises(ValidationError) as exc_info:
        CompositeContextView.model_validate(payload)
    assert _SECRET not in str(exc_info.value)
    assert "86b5ed34-36dd-4975-9735-90bb02c9bce8" not in repr(exc_info.value)


def test_models_are_strict_frozen_and_expose_only_the_fixed_safe_fields() -> None:
    assert set(CompositeContextBudgetUsage.model_fields) == {
        "c1_evidence_items",
        "group_window_fragments",
        "group_rendered_fragments",
        "c1_content_chars",
        "group_rendered_chars",
        "total_content_chars",
    }
    assert set(CompositeContextView.model_fields) == {
        "contract_version",
        "status",
        "c1_status",
        "group_status",
        "group_compression_required",
        "usage",
    }
    for model in (CompositeContextBudgetUsage, CompositeContextView):
        for field in model.model_fields.values():
            assert "UUID" not in _annotation_names(field.annotation)

    with pytest.raises(ValidationError):
        CompositeContextBudgetUsage.model_validate(
            {
                **_usage().model_dump(mode="python"),
                "c1_evidence_items": True,
            }
        )
    with pytest.raises(ValidationError):
        CompositeContextView.model_validate(
            {**_view().model_dump(mode="python"), "group_compression_required": 0}
        )
    with pytest.raises(ValidationError):
        _view().status = "no_evidence"


def test_validator_rebuilds_nested_usage_and_blocks_construct_and_subclass_bypasses() -> None:
    class CarrierUsage(CompositeContextBudgetUsage):
        content: str

    carrier = CarrierUsage(
        **_usage().model_dump(mode="python"),
        content=_SECRET,
    )
    crafted = CompositeContextView.model_construct(
        contract_version="stage08-composite-context.v1",
        status="internal_evidence",
        c1_status="internal_evidence",
        group_status="group_context_available",
        group_compression_required=False,
        usage=carrier,
    )
    safe = validate_composite_context_view(crafted)
    assert type(safe) is CompositeContextView
    assert type(safe.usage) is CompositeContextBudgetUsage
    assert _SECRET not in safe.model_dump_json()
    assert _SECRET not in repr(safe)

    invalid_usage = CompositeContextBudgetUsage.model_construct(
        c1_evidence_items=1,
        group_window_fragments=1,
        group_rendered_fragments=2,
        c1_content_chars=1,
        group_rendered_chars=1,
        total_content_chars=2,
    )
    invalid = CompositeContextView.model_construct(
        contract_version="stage08-composite-context.v1",
        status="internal_evidence",
        c1_status="internal_evidence",
        group_status="group_context_available",
        group_compression_required=False,
        usage=invalid_usage,
    )
    with pytest.raises(ValidationError, match="composite_context_usage_invalid"):
        validate_composite_context_view(invalid)


def test_validator_rebuilds_usage_dict_without_copying_unknown_nested_values() -> None:
    crafted = CompositeContextView.model_construct(
        contract_version="stage08-composite-context.v1",
        status="internal_evidence",
        c1_status="internal_evidence",
        group_status="group_context_available",
        group_compression_required=False,
        usage={**_usage().model_dump(mode="python"), "renderer": _SECRET},
    )
    safe = validate_composite_context_view(crafted)
    dumped = safe.model_dump(mode="json")
    assert _SECRET not in str(dumped)
    assert _SECRET not in repr(safe)


def _annotation_names(annotation: object) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", repr(annotation))
    return " ".join(_annotation_names(argument) for argument in get_args(annotation))
