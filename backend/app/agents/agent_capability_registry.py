from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


STAGE11_REGISTRY_VERSION = "stage11.registry.v1"


@dataclass(frozen=True, slots=True)
class AgentCapabilityDefinition:
    capability_id: str
    command_type: str
    handler_version: str
    execution_skill_id: str
    output_kind: str
    risk_level: Literal["low", "medium", "high"]
    allowed_actions: frozenset[str]
    allowed_tools: frozenset[str]
    can_propose_write: bool = False
    can_execute_write: bool = False
    input_schema_version: str = "agent-specialist-input.v1"
    output_schema_version: str = "agent-specialist-output.v1"
    deadline_seconds: int = 90
    retry_limit: int = 2
    allowed_ports: frozenset[str] = frozenset()
    required_upstream_artifact_kinds: frozenset[str] = frozenset()
    max_provider_calls: int = 0
    max_input_tokens: int = 0
    failure_policy: Literal["required", "optional"] = "required"


_REGISTRY: Mapping[str, AgentCapabilityDefinition] = MappingProxyType(
    {
        "platform.tabular.analyse": AgentCapabilityDefinition(
            capability_id="platform.tabular.analyse",
            command_type="analyse_visible_records",
            handler_version="stage12.tabular.v2",
            execution_skill_id="platform-tabular-analysis",
            output_kind="assistant_safe_view",
            risk_level="low",
            allowed_actions=frozenset({"read_only"}),
            allowed_tools=frozenset(
                {"records.read_authorized", "views.read_authorized"}
            ),
            input_schema_version="objective-specialist-input.v1",
            output_schema_version="structured-fact-set.v1",
            allowed_ports=frozenset(
                {"artifact_reader", "authorized_query_gateway", "clock", "metrics"}
            ),
            required_upstream_artifact_kinds=frozenset({"structured_query_artifact"}),
            max_input_tokens=8192,
        ),
        "platform.risk.analyse": AgentCapabilityDefinition(
            capability_id="platform.risk.analyse",
            command_type="analyse_visible_risks",
            handler_version="stage12.risk.v2",
            execution_skill_id="platform-tabular-analysis",
            output_kind="risk_safe_view",
            risk_level="low",
            allowed_actions=frozenset({"read_only"}),
            allowed_tools=frozenset(
                {"records.read_authorized", "links.traverse_authorized"}
            ),
            input_schema_version="objective-specialist-input.v1",
            output_schema_version="risk-assessment-set.v1",
            allowed_ports=frozenset(
                {
                    "artifact_reader",
                    "risk_policy_reader",
                    "model_gateway",
                    "clock",
                    "metrics",
                }
            ),
            required_upstream_artifact_kinds=frozenset({"structured_fact_set"}),
            max_provider_calls=2,
            max_input_tokens=8192,
            failure_policy="optional",
        ),
        "platform.daily.summarise": AgentCapabilityDefinition(
            capability_id="platform.daily.summarise",
            command_type="summarise_visible_operations",
            handler_version="stage12.daily.v2",
            execution_skill_id="platform-tabular-analysis",
            output_kind="daily_safe_view",
            risk_level="low",
            allowed_actions=frozenset({"read_only"}),
            allowed_tools=frozenset(
                {"records.read_authorized", "records.aggregate_authorized"}
            ),
            input_schema_version="objective-specialist-input.v1",
            output_schema_version="daily-brief.v1",
            allowed_ports=frozenset(
                {"artifact_reader", "model_gateway", "clock", "metrics"}
            ),
            required_upstream_artifact_kinds=frozenset({"structured_fact_set"}),
            max_provider_calls=2,
            max_input_tokens=12288,
            failure_policy="optional",
        ),
        "platform.action.propose": AgentCapabilityDefinition(
            capability_id="platform.action.propose",
            command_type="propose_controlled_action",
            handler_version="stage12.action.v2",
            execution_skill_id="platform-task",
            output_kind="controlled_action_proposal",
            risk_level="medium",
            allowed_actions=frozenset(
                {"draft_create", "draft_update", "task_create", "reminder_request"}
            ),
            allowed_tools=frozenset({"proposals.create"}),
            can_propose_write=True,
            input_schema_version="objective-specialist-input.v1",
            output_schema_version="controlled-action-proposal.v1",
            allowed_ports=frozenset(
                {"artifact_reader", "model_gateway", "tool_gateway", "clock", "metrics"}
            ),
            required_upstream_artifact_kinds=frozenset(
                {"authorized_candidate_set", "evidence_bundle"}
            ),
            max_provider_calls=2,
            max_input_tokens=8192,
        ),
    }
)


def registered_capabilities() -> Mapping[str, AgentCapabilityDefinition]:
    return _REGISTRY


def get_capability(capability_id: str) -> AgentCapabilityDefinition:
    try:
        return _REGISTRY[capability_id]
    except KeyError as exc:
        raise KeyError("capability_not_registered") from exc


def validate_capability_command(
    capability_id: str,
    command_type: str,
) -> AgentCapabilityDefinition:
    definition = get_capability(capability_id)
    if definition.command_type != command_type:
        raise ValueError("command_type_not_registered")
    return definition


__all__ = [
    "AgentCapabilityDefinition",
    "STAGE11_REGISTRY_VERSION",
    "get_capability",
    "registered_capabilities",
    "validate_capability_command",
]
