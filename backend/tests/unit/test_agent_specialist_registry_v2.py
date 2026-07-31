from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.agents.agent_capability_registry import registered_capabilities
from app.services.agent_specialist_registry_v2 import (
    default_specialist_factories,
    validate_specialist_readiness,
)


@dataclass(frozen=True)
class _Handler:
    capability_id: str
    input_schema_version: str
    output_schema_version: str
    allowed_ports: frozenset[str]

    def execute(self, command, context):
        raise AssertionError("readiness_must_not_execute")


def _factories():
    return {
        capability_id: (
            lambda definition=definition: _Handler(
                capability_id=definition.capability_id,
                input_schema_version=definition.input_schema_version,
                output_schema_version=definition.output_schema_version,
                allowed_ports=definition.allowed_ports,
            )
        )
        for capability_id, definition in registered_capabilities().items()
    }


def test_registry_requires_one_distinct_factory_per_capability() -> None:
    factories = _factories()
    handlers = validate_specialist_readiness(factories)
    assert {item.capability_id for item in handlers} == set(factories)
    assert len({id(item) for item in handlers}) == 4

    factories.pop("platform.risk.analyse")
    with pytest.raises(RuntimeError, match="specialist_handler_factory_missing"):
        validate_specialist_readiness(factories)


def test_registry_rejects_version_or_capability_fallback() -> None:
    factories = _factories()
    risk = registered_capabilities()["platform.risk.analyse"]
    factories["platform.risk.analyse"] = lambda: _Handler(
        capability_id="platform.tabular.analyse",
        input_schema_version=risk.input_schema_version,
        output_schema_version=risk.output_schema_version,
        allowed_ports=risk.allowed_ports,
    )
    with pytest.raises(RuntimeError, match="specialist_handler_identity_mismatch"):
        validate_specialist_readiness(factories)

    factories = _factories()
    factories["platform.daily.summarise"] = lambda: _Handler(
        capability_id="platform.daily.summarise",
        input_schema_version="agent-specialist-input.v1",
        output_schema_version="daily-brief.v1",
        allowed_ports=frozenset(),
    )
    with pytest.raises(RuntimeError, match="specialist_handler_version_mismatch"):
        validate_specialist_readiness(factories)


def test_registry_ports_prevent_rescan_and_write_authority() -> None:
    registry = registered_capabilities()
    assert (
        "authorized_query_gateway"
        not in registry["platform.risk.analyse"].allowed_ports
    )
    assert (
        "authorized_query_gateway"
        not in registry["platform.daily.summarise"].allowed_ports
    )
    assert "tool_gateway" not in registry["platform.tabular.analyse"].allowed_ports
    assert "tool_gateway" not in registry["platform.risk.analyse"].allowed_ports
    assert "tool_gateway" not in registry["platform.daily.summarise"].allowed_ports
    assert "tool_gateway" in registry["platform.action.propose"].allowed_ports
    assert all(not definition.can_execute_write for definition in registry.values())


def test_handler_context_does_not_expose_infrastructure_handles() -> None:
    from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2

    assert "session" not in SpecialistExecutionContextV2.__dataclass_fields__
    assert "redis" not in SpecialistExecutionContextV2.__dataclass_fields__
    assert "provider_key" not in SpecialistExecutionContextV2.__dataclass_fields__


def test_default_registry_uses_four_real_distinct_handler_types() -> None:
    handlers = validate_specialist_readiness(default_specialist_factories())
    assert [type(item).__name__ for item in handlers] == [
        "TabularSpecialistV2",
        "RiskSpecialistV2",
        "DailySpecialistV2",
        "ActionSpecialistV2",
    ]
