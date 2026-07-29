from types import MappingProxyType

import pytest

from app.agents.agent_capability_registry import (
    STAGE11_REGISTRY_VERSION,
    get_capability,
    registered_capabilities,
    validate_capability_command,
)


def test_stage11_registry_is_versioned_complete_and_immutable() -> None:
    registry = registered_capabilities()

    assert STAGE11_REGISTRY_VERSION == "stage11.registry.v1"
    assert isinstance(registry, MappingProxyType)
    assert set(registry) == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
        "platform.daily.summarise",
        "platform.action.propose",
    }
    assert registry["platform.action.propose"].can_propose_write is True
    assert registry["platform.action.propose"].can_execute_write is False
    assert all(not item.can_execute_write for item in registry.values())
    assert registry["platform.tabular.analyse"].execution_skill_id == (
        "platform-tabular-analysis"
    )
    assert registry["platform.risk.analyse"].execution_skill_id == (
        "platform-tabular-analysis"
    )
    assert registry["platform.daily.summarise"].execution_skill_id == (
        "platform-tabular-analysis"
    )
    assert registry["platform.action.propose"].execution_skill_id == "platform-task"

    with pytest.raises(TypeError):
        registry["unsafe.sql"] = registry["platform.tabular.analyse"]  # type: ignore[index]


def test_registry_rejects_command_capability_mismatch() -> None:
    validate_capability_command(
        "platform.risk.analyse",
        "analyse_visible_risks",
    )

    with pytest.raises(ValueError, match="command_type_not_registered"):
        validate_capability_command(
            "platform.risk.analyse",
            "analyse_visible_records",
        )

    with pytest.raises(KeyError, match="capability_not_registered"):
        get_capability("unsafe.sql")
