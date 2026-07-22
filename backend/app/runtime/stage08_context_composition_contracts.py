from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS = 12_000
COMPOSITE_CONTEXT_GROUP_MAX_DIRECT_CHARS = 24_000
COMPOSITE_CONTEXT_MAX_CONTENT_CHARS = 36_000
COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS = 24
COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS = 120

_STRICT_CONFIG = ConfigDict(
    extra="forbid",
    strict=True,
    frozen=True,
    hide_input_in_errors=True,
)


class CompositeContextBudgetUsage(BaseModel):
    model_config = _STRICT_CONFIG

    c1_evidence_items: StrictInt = Field(
        ge=0, le=COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS
    )
    group_window_fragments: StrictInt = Field(
        ge=0, le=COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS
    )
    group_rendered_fragments: StrictInt = Field(
        ge=0, le=COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS
    )
    c1_content_chars: StrictInt = Field(
        ge=0, le=COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS
    )
    group_rendered_chars: StrictInt = Field(
        ge=0, le=COMPOSITE_CONTEXT_GROUP_MAX_DIRECT_CHARS
    )
    total_content_chars: StrictInt = Field(
        ge=0, le=COMPOSITE_CONTEXT_MAX_CONTENT_CHARS
    )

    @model_validator(mode="after")
    def validate_usage(self) -> "CompositeContextBudgetUsage":
        if (
            self.group_rendered_fragments > self.group_window_fragments
            or self.total_content_chars
            != self.c1_content_chars + self.group_rendered_chars
        ):
            raise ValueError("composite_context_usage_invalid")
        return self


class CompositeContextView(BaseModel):
    model_config = _STRICT_CONFIG

    contract_version: Literal["stage08-composite-context.v1"]
    status: Literal[
        "internal_evidence",
        "group_compression_pending",
        "general_advice_only",
        "no_evidence",
    ]
    c1_status: Literal[
        "internal_evidence", "general_advice_only", "no_evidence"
    ]
    group_status: Literal[
        "group_context_unavailable",
        "group_context_partial",
        "group_context_available",
    ]
    group_compression_required: StrictBool
    usage: CompositeContextBudgetUsage

    @model_validator(mode="after")
    def validate_view(self) -> "CompositeContextView":
        is_pending = self.status == "group_compression_pending"
        if is_pending is not self.group_compression_required or (
            is_pending
            and (
                self.usage.group_rendered_fragments != 0
                or self.usage.group_rendered_chars != 0
            )
        ):
            raise ValueError("composite_context_compression_state_invalid")

        if self.c1_status == "internal_evidence":
            if self.usage.c1_evidence_items == 0:
                raise ValueError("composite_context_status_invalid")
        elif (
            self.usage.c1_evidence_items != 0
            or self.usage.c1_content_chars != 0
        ):
            raise ValueError("composite_context_status_invalid")

        group_unavailable = self.group_status == "group_context_unavailable"
        if group_unavailable:
            if (
                self.usage.group_window_fragments != 0
                or self.usage.group_rendered_fragments != 0
                or self.usage.group_rendered_chars != 0
                or self.group_compression_required
            ):
                raise ValueError("composite_context_status_invalid")
        elif self.usage.group_window_fragments == 0:
            raise ValueError("composite_context_status_invalid")
        elif not is_pending and (
            self.usage.group_rendered_fragments == 0
            or self.usage.group_rendered_chars == 0
        ):
            raise ValueError("composite_context_status_invalid")

        if self.status == "internal_evidence":
            if (
                self.usage.c1_evidence_items == 0
                and self.usage.group_rendered_fragments == 0
            ):
                raise ValueError("composite_context_status_invalid")
        elif self.status == "group_compression_pending":
            if group_unavailable:
                raise ValueError("composite_context_status_invalid")
        elif self.status == "general_advice_only":
            if (
                self.c1_status != "general_advice_only"
                or not group_unavailable
                or self.usage.c1_evidence_items != 0
                or self.usage.group_rendered_fragments != 0
                or self.usage.total_content_chars != 0
            ):
                raise ValueError("composite_context_status_invalid")
        elif (
            self.c1_status != "no_evidence"
            or not group_unavailable
            or self.usage.c1_evidence_items != 0
            or self.usage.group_rendered_fragments != 0
            or self.usage.total_content_chars != 0
        ):
            raise ValueError("composite_context_status_invalid")
        return self


def validate_composite_context_view(
    view: CompositeContextView,
) -> CompositeContextView:
    usage_source = _fixed_value(view, "usage")
    usage = CompositeContextBudgetUsage.model_validate(
        {
            "c1_evidence_items": _fixed_value(
                usage_source, "c1_evidence_items"
            ),
            "group_window_fragments": _fixed_value(
                usage_source, "group_window_fragments"
            ),
            "group_rendered_fragments": _fixed_value(
                usage_source, "group_rendered_fragments"
            ),
            "c1_content_chars": _fixed_value(
                usage_source, "c1_content_chars"
            ),
            "group_rendered_chars": _fixed_value(
                usage_source, "group_rendered_chars"
            ),
            "total_content_chars": _fixed_value(
                usage_source, "total_content_chars"
            ),
        }
    )
    return CompositeContextView.model_validate(
        {
            "contract_version": _fixed_value(view, "contract_version"),
            "status": _fixed_value(view, "status"),
            "c1_status": _fixed_value(view, "c1_status"),
            "group_status": _fixed_value(view, "group_status"),
            "group_compression_required": _fixed_value(
                view, "group_compression_required"
            ),
            "usage": usage,
        }
    )


def _fixed_value(source: object, field: str) -> object:
    if isinstance(source, dict):
        return source.get(field)
    return getattr(source, field, None)
