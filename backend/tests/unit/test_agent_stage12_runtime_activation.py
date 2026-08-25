from __future__ import annotations

import base64
from dataclasses import replace
from uuid import UUID

import pytest

from app.core.config import Settings, validate_runtime_settings
from app.services.agent_stage12_runtime_activation import (
    build_stage12_runtime_profile,
    stage12_runtime_enabled,
)


WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000001")
OTHER_WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000002")
GROUNDED_PROFILE = "composer.zh.grounded.glm-5.2.v4"
RETRIEVAL_PROFILE = "stage12.openrouter-bge-m3-v1"
def _runtime_key() -> str:
    return base64.urlsafe_b64encode(b"k" * 32).decode("ascii")


def _valid_isolated_settings(**overrides: object) -> Settings:
    settings = Settings(
        stage12_runtime_mode="isolated",
        stage12_runtime_workspace_allowlist=str(WORKSPACE_ID),
        agent_event_runtime_enabled=True,
        agent_event_runtime_mode="redis_worker",
        agent_event_runtime_allowed_workspace_ids=(str(WORKSPACE_ID),),
        agent_runtime_input_key=_runtime_key(),
        retrieval_v2_active_profile=RETRIEVAL_PROFILE,
        stage12_provider_v2_profile=GROUNDED_PROFILE,
        openrouter_api_key="test-provider-key",
    )
    return replace(settings, **overrides)


def test_default_off_profile_never_enables_a_workspace() -> None:
    profile = build_stage12_runtime_profile(Settings())

    assert profile.mode == "off"
    assert profile.workspace_allowlist == frozenset()
    assert not stage12_runtime_enabled(profile, workspace_id=WORKSPACE_ID)


def test_off_mode_rejects_a_non_empty_allowlist() -> None:
    settings = Settings(stage12_runtime_workspace_allowlist=str(WORKSPACE_ID))

    with pytest.raises(RuntimeError, match="STAGE12_RUNTIME_WORKSPACE_ALLOWLIST"):
        build_stage12_runtime_profile(settings)


def test_runtime_rejects_any_mode_other_than_off_or_isolated() -> None:
    settings = _valid_isolated_settings(stage12_runtime_mode="global")

    with pytest.raises(RuntimeError, match="STAGE12_RUNTIME_MODE"):
        build_stage12_runtime_profile(settings)


@pytest.mark.parametrize(
    "allowlist",
    ["", "not-a-uuid", "*", "10000000-0000-4000-8000-000000000001,*"],
)
def test_isolated_mode_rejects_empty_invalid_or_wildcard_allowlist(
    allowlist: str,
) -> None:
    settings = _valid_isolated_settings(
        stage12_runtime_workspace_allowlist=allowlist,
    )

    with pytest.raises(RuntimeError, match="STAGE12_RUNTIME_WORKSPACE_ALLOWLIST"):
        build_stage12_runtime_profile(settings)


def test_isolated_profile_normalizes_duplicates_and_matches_only_exact_uuid() -> None:
    settings = _valid_isolated_settings(
        stage12_runtime_workspace_allowlist=(
            f" {WORKSPACE_ID}, {WORKSPACE_ID} "
        ),
    )

    profile = build_stage12_runtime_profile(settings)

    assert profile.workspace_allowlist == frozenset({WORKSPACE_ID})
    assert stage12_runtime_enabled(profile, workspace_id=WORKSPACE_ID)
    assert not stage12_runtime_enabled(profile, workspace_id=OTHER_WORKSPACE_ID)


def test_isolated_profile_accepts_native_redis_unix_socket() -> None:
    settings = _valid_isolated_settings(
        redis_url="unix:///run/stage09-p1/redis.sock?db=0",
    )

    profile = build_stage12_runtime_profile(settings)

    assert profile.workspace_allowlist == frozenset({WORKSPACE_ID})


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"agent_event_runtime_enabled": False}, "AGENT_EVENT_RUNTIME_ENABLED"),
        ({"agent_event_runtime_mode": "embedded"}, "AGENT_EVENT_RUNTIME_MODE"),
        (
            {"agent_event_runtime_allowed_workspace_ids": (str(OTHER_WORKSPACE_ID),)},
            "AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS",
        ),
        ({"agent_runtime_input_key": None}, "AGENT_RUNTIME_INPUT_KEY"),
        ({"database_url": "sqlite:///test.db"}, "DATABASE_URL"),
        ({"redis_url": "memory://redis"}, "REDIS_URL"),
        ({"redis_url": "unix://relative/redis.sock"}, "REDIS_URL"),
        ({"retrieval_v2_active_profile": None}, "RETRIEVAL_V2_ACTIVE_PROFILE"),
        (
            {"stage12_provider_v2_profile": "stage12.openrouter-gemini-2.5-flash-v1"},
            "STAGE12_PROVIDER_V2_PROFILE",
        ),
        ({"openrouter_api_key": None}, "OPENROUTER_API_KEY"),
    ],
)
def test_isolated_profile_fails_closed_when_a_runtime_prerequisite_is_missing(
    overrides: dict[str, object],
    error: str,
) -> None:
    settings = _valid_isolated_settings(**overrides)

    with pytest.raises(RuntimeError, match=error):
        build_stage12_runtime_profile(settings)


def test_component_shadow_flags_do_not_activate_stage12_answer_authority() -> None:
    settings = Settings(
        agent_task_planner_v2_mode="shadow",
        agent_task_planner_v2_shadow_workspace_ids=(str(WORKSPACE_ID),),
        authorized_query_engine_v1_mode="shadow",
        authorized_query_engine_v1_workspace_allowlist=(str(WORKSPACE_ID),),
        retrieval_v2_mode="shadow",
        retrieval_v2_workspace_allowlist=(str(WORKSPACE_ID),),
        retrieval_v2_active_profile=RETRIEVAL_PROFILE,
        typed_specialists_v2_mode="shadow",
        typed_specialists_v2_workspace_allowlist=(str(WORKSPACE_ID),),
        stage12_provider_v2_profile=GROUNDED_PROFILE,
        openrouter_api_key="test-provider-key",
    )

    profile = build_stage12_runtime_profile(settings)

    assert profile.mode == "off"
    assert not stage12_runtime_enabled(profile, workspace_id=WORKSPACE_ID)


def test_global_runtime_validation_includes_stage12_isolated_contract() -> None:
    validate_runtime_settings(_valid_isolated_settings())

    with pytest.raises(RuntimeError, match="STAGE12_RUNTIME_WORKSPACE_ALLOWLIST"):
        validate_runtime_settings(
            _valid_isolated_settings(stage12_runtime_workspace_allowlist="")
        )
