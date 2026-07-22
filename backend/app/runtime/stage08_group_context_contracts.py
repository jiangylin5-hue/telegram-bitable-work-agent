from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


GROUP_CONTEXT_RETENTION_DAYS = 30
GROUP_CONTEXT_MAX_FRAGMENTS = 120
GROUP_CONTEXT_MAX_FRAGMENT_CHARS = 500
GROUP_CONTEXT_MAX_RAW_CHARS = 60_000
GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT = 24
GROUP_CONTEXT_LATEST_RAW_CHARS = 12_000
GROUP_CONTEXT_HISTORY_HALF_LIFE_DAYS = 7
GROUP_CONTEXT_COMPRESSION_THRESHOLD_CHARS = 24_000

_STRICT_CONFIG = ConfigDict(extra="forbid", strict=True, frozen=True)


class GroupContextBudgetUsage(BaseModel):
    model_config = _STRICT_CONFIG

    considered_fragments: StrictInt = Field(ge=0)
    selected_fragments: StrictInt = Field(ge=0, le=GROUP_CONTEXT_MAX_FRAGMENTS)
    latest_selected_fragments: StrictInt = Field(
        ge=0, le=GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT
    )
    history_selected_fragments: StrictInt = Field(
        ge=0, le=GROUP_CONTEXT_MAX_FRAGMENTS - GROUP_CONTEXT_LATEST_FRAGMENT_LIMIT
    )
    raw_selected_chars: StrictInt = Field(ge=0, le=GROUP_CONTEXT_MAX_RAW_CHARS)

    @model_validator(mode="after")
    def validate_usage(self) -> "GroupContextBudgetUsage":
        if (
            self.selected_fragments > self.considered_fragments
            or self.latest_selected_fragments + self.history_selected_fragments
            != self.selected_fragments
            or self.raw_selected_chars
            > self.selected_fragments * GROUP_CONTEXT_MAX_FRAGMENT_CHARS
        ):
            raise ValueError("group_context_usage_invalid")
        return self


class GroupContextOmissionCounts(BaseModel):
    model_config = _STRICT_CONFIG

    expired: StrictInt = Field(ge=0)
    latest_band_limit: StrictInt = Field(ge=0)
    fragment_limit: StrictInt = Field(ge=0)
    character_limit: StrictInt = Field(ge=0)

    @property
    def total(self) -> int:
        return (
            self.expired
            + self.latest_band_limit
            + self.fragment_limit
            + self.character_limit
        )


class GroupContextWindowView(BaseModel):
    model_config = _STRICT_CONFIG

    contract_version: Literal["stage08-group-context-window.v1"]
    status: Literal[
        "group_context_unavailable",
        "group_context_partial",
        "group_context_available",
    ]
    usage: GroupContextBudgetUsage
    omissions: GroupContextOmissionCounts
    compression_required: StrictBool

    @model_validator(mode="after")
    def validate_window(self) -> "GroupContextWindowView":
        expected_compression = (
            self.usage.raw_selected_chars
            > GROUP_CONTEXT_COMPRESSION_THRESHOLD_CHARS
        )
        if self.compression_required is not expected_compression:
            raise ValueError("group_context_compression_flag_invalid")
        if self.status == "group_context_available" and (
            self.usage.selected_fragments == 0 or self.omissions.total != 0
        ):
            raise ValueError("group_context_status_invalid")
        if self.status == "group_context_partial" and (
            self.usage.selected_fragments == 0 or self.omissions.total == 0
        ):
            raise ValueError("group_context_status_invalid")
        if self.status == "group_context_unavailable" and (
            self.usage.selected_fragments != 0
            or self.usage.raw_selected_chars != 0
        ):
            raise ValueError("group_context_status_invalid")
        return self


class GroupContextPurgeResult(BaseModel):
    model_config = _STRICT_CONFIG

    contract_version: Literal["stage08-group-context-purge.v1"]
    purged_count: StrictInt = Field(ge=0)


def validate_group_context_window_view(
    view: GroupContextWindowView,
) -> GroupContextWindowView:
    usage_source = getattr(view, "usage", None)
    omission_source = getattr(view, "omissions", None)
    usage = GroupContextBudgetUsage.model_validate(
        {
            "considered_fragments": _fixed_value(
                usage_source, "considered_fragments"
            ),
            "selected_fragments": _fixed_value(
                usage_source, "selected_fragments"
            ),
            "latest_selected_fragments": _fixed_value(
                usage_source, "latest_selected_fragments"
            ),
            "history_selected_fragments": _fixed_value(
                usage_source, "history_selected_fragments"
            ),
            "raw_selected_chars": _fixed_value(
                usage_source, "raw_selected_chars"
            ),
        }
    )
    omissions = GroupContextOmissionCounts.model_validate(
        {
            "expired": _fixed_value(omission_source, "expired"),
            "latest_band_limit": _fixed_value(
                omission_source, "latest_band_limit"
            ),
            "fragment_limit": _fixed_value(omission_source, "fragment_limit"),
            "character_limit": _fixed_value(
                omission_source, "character_limit"
            ),
        }
    )
    return GroupContextWindowView.model_validate(
        {
            "contract_version": getattr(view, "contract_version", None),
            "status": getattr(view, "status", None),
            "usage": usage,
            "omissions": omissions,
            "compression_required": getattr(
                view, "compression_required", None
            ),
        }
    )


def validate_group_context_purge_result(
    result: GroupContextPurgeResult,
) -> GroupContextPurgeResult:
    return GroupContextPurgeResult.model_validate(
        {
            "contract_version": result.contract_version,
            "purged_count": result.purged_count,
        }
    )


def _fixed_value(source: object, field: str) -> object:
    if isinstance(source, dict):
        return source.get(field)
    return getattr(source, field, None)
