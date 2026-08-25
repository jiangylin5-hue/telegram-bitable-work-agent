from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from app.core.config import (
    STAGE12_GROUNDED_PROVIDER_PROFILE,
    STAGE12_RETRIEVAL_ACTIVE_PROFILE,
    Settings,
)


Stage12RuntimeMode = Literal["off", "isolated"]


@dataclass(frozen=True, slots=True)
class Stage12RuntimeProfile:
    mode: Stage12RuntimeMode
    workspace_allowlist: frozenset[UUID]


def build_stage12_runtime_profile(settings: Settings) -> Stage12RuntimeProfile:
    mode = settings.stage12_runtime_mode
    if mode not in {"off", "isolated"}:
        raise RuntimeError("Invalid STAGE12_RUNTIME_MODE: expected off or isolated")
    workspace_allowlist = _parse_workspace_allowlist(
        settings.stage12_runtime_workspace_allowlist
    )
    if mode == "off":
        if workspace_allowlist:
            raise RuntimeError(
                "Invalid STAGE12_RUNTIME_WORKSPACE_ALLOWLIST: off mode requires empty"
            )
        return Stage12RuntimeProfile(mode="off", workspace_allowlist=frozenset())

    if not workspace_allowlist:
        raise RuntimeError("Missing STAGE12_RUNTIME_WORKSPACE_ALLOWLIST")
    if not settings.agent_event_runtime_enabled:
        raise RuntimeError(
            "Invalid AGENT_EVENT_RUNTIME_ENABLED: Stage12 isolated runtime requires true"
        )
    if settings.agent_event_runtime_mode != "redis_worker":
        raise RuntimeError(
            "Invalid AGENT_EVENT_RUNTIME_MODE: Stage12 isolated runtime requires redis_worker"
        )
    event_runtime_workspaces = _parse_uuid_values(
        settings.agent_event_runtime_allowed_workspace_ids,
        error_name="AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS",
    )
    if not workspace_allowlist.issubset(event_runtime_workspaces):
        raise RuntimeError(
            "Invalid AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS: "
            "Stage12 allowlist must be authorized by Agent Event Runtime"
        )
    _validate_private_input_key(settings.agent_runtime_input_key)
    _validate_postgresql_url(settings.database_url)
    _validate_redis_url(settings.redis_url)
    if settings.retrieval_v2_active_profile != STAGE12_RETRIEVAL_ACTIVE_PROFILE:
        raise RuntimeError(
            "Invalid RETRIEVAL_V2_ACTIVE_PROFILE: expected confirmed Stage12 profile"
        )
    if settings.stage12_provider_v2_profile != STAGE12_GROUNDED_PROVIDER_PROFILE:
        raise RuntimeError(
            "Invalid STAGE12_PROVIDER_V2_PROFILE: expected confirmed Grounded Provider profile"
        )
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "Missing required Stage12 runtime environment variable: OPENROUTER_API_KEY"
        )
    return Stage12RuntimeProfile(
        mode="isolated",
        workspace_allowlist=workspace_allowlist,
    )


def stage12_runtime_enabled(
    profile: Stage12RuntimeProfile,
    *,
    workspace_id: UUID,
) -> bool:
    return profile.mode == "isolated" and workspace_id in profile.workspace_allowlist


def _parse_workspace_allowlist(value: str) -> frozenset[UUID]:
    if not isinstance(value, str):
        raise RuntimeError("Invalid STAGE12_RUNTIME_WORKSPACE_ALLOWLIST")
    if not value.strip():
        return frozenset()
    return _parse_uuid_values(
        tuple(part.strip() for part in value.split(",")),
        error_name="STAGE12_RUNTIME_WORKSPACE_ALLOWLIST",
    )


def _parse_uuid_values(
    values: tuple[str, ...],
    *,
    error_name: str,
) -> frozenset[UUID]:
    parsed: set[UUID] = set()
    for value in values:
        if not value or value == "*":
            raise RuntimeError(f"Invalid {error_name}")
        try:
            parsed.add(UUID(value))
        except (AttributeError, ValueError) as exc:
            raise RuntimeError(f"Invalid {error_name}") from exc
    return frozenset(parsed)


def _validate_private_input_key(value: str | None) -> None:
    if value is None:
        raise RuntimeError("Missing AGENT_RUNTIME_INPUT_KEY")
    try:
        key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("Invalid AGENT_RUNTIME_INPUT_KEY") from exc
    if len(key) != 32:
        raise RuntimeError("Invalid AGENT_RUNTIME_INPUT_KEY")


def _validate_postgresql_url(value: str) -> None:
    scheme = urlparse(value).scheme
    if scheme not in {"postgresql", "postgresql+psycopg"}:
        raise RuntimeError(
            "Invalid DATABASE_URL: Stage12 isolated runtime requires PostgreSQL"
        )


def _validate_redis_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme in {"redis", "rediss"}:
        return
    if (
        parsed.scheme == "unix"
        and value.startswith("unix:///")
        and parsed.path.startswith("/")
        and not parsed.netloc
        and not parsed.fragment
    ):
        return
    raise RuntimeError("Invalid REDIS_URL: Stage12 isolated runtime requires Redis")


__all__ = [
    "Stage12RuntimeMode",
    "Stage12RuntimeProfile",
    "build_stage12_runtime_profile",
    "stage12_runtime_enabled",
]
