from __future__ import annotations

from collections.abc import Callable, Mapping

from app.agents.agent_capability_registry import (
    AgentCapabilityDefinition,
    registered_capabilities,
)
from app.services.agent_specialists_v2.base import SpecialistHandler


HandlerFactory = Callable[[], SpecialistHandler]


def default_specialist_factories() -> Mapping[str, HandlerFactory]:
    from app.services.agent_specialists_v2.action import ActionSpecialistV2
    from app.services.agent_specialists_v2.daily import DailySpecialistV2
    from app.services.agent_specialists_v2.risk import RiskSpecialistV2
    from app.services.agent_specialists_v2.tabular import TabularSpecialistV2

    return {
        "platform.tabular.analyse": TabularSpecialistV2,
        "platform.risk.analyse": RiskSpecialistV2,
        "platform.daily.summarise": DailySpecialistV2,
        "platform.action.propose": ActionSpecialistV2,
    }


def validate_specialist_readiness(
    factories: Mapping[str, HandlerFactory],
    *,
    registry: Mapping[str, AgentCapabilityDefinition] | None = None,
) -> tuple[SpecialistHandler, ...]:
    definitions = registry or registered_capabilities()
    if set(factories) != set(definitions):
        raise RuntimeError("specialist_handler_factory_missing")
    handlers: list[SpecialistHandler] = []
    for capability_id, definition in definitions.items():
        handler = factories[capability_id]()
        if handler.capability_id != capability_id:
            raise RuntimeError("specialist_handler_identity_mismatch")
        if (
            handler.input_schema_version != definition.input_schema_version
            or handler.output_schema_version != definition.output_schema_version
        ):
            raise RuntimeError("specialist_handler_version_mismatch")
        if handler.allowed_ports != definition.allowed_ports:
            raise RuntimeError("specialist_handler_port_mismatch")
        handlers.append(handler)
    if len({id(item) for item in handlers}) != len(handlers):
        raise RuntimeError("specialist_handler_instance_reused")
    return tuple(handlers)


__all__ = [
    "HandlerFactory",
    "default_specialist_factories",
    "validate_specialist_readiness",
]
