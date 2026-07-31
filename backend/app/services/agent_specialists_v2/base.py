from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from app.schemas.agent_specialist_results import ObjectiveSpecialistInputV1


@dataclass(frozen=True, slots=True)
class SpecialistExecutionContextV2:
    artifact_reader: Callable[..., BaseModel]
    clock: Callable[[], datetime]
    metrics: Callable[[str, int], None]
    authorized_query_gateway: object | None = None
    risk_policy_reader: object | None = None
    model_gateway: object | None = None
    tool_gateway: object | None = None


@dataclass(frozen=True, slots=True)
class SpecialistHandlerResultV2:
    payload: BaseModel
    safe_summary: str
    metrics: Mapping[str, int]


class SpecialistHandler(Protocol):
    capability_id: str
    input_schema_version: str
    output_schema_version: str
    allowed_ports: frozenset[str]

    def execute(
        self,
        command: ObjectiveSpecialistInputV1,
        context: SpecialistExecutionContextV2,
    ) -> SpecialistHandlerResultV2: ...


__all__ = [
    "SpecialistExecutionContextV2",
    "SpecialistHandler",
    "SpecialistHandlerResultV2",
]
