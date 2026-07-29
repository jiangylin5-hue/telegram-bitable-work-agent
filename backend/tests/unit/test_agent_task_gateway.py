from uuid import uuid4

import pytest

from app.services.agent_task_gateway import (
    TaskGatewayRequest,
    build_task_plan,
)


def _request(**overrides: object) -> TaskGatewayRequest:
    values: dict[str, object] = {
        "workspace_id": uuid4(),
        "employee_id": uuid4(),
        "actor_user_id": "owner-1",
        "intent": "business_fact",
        "requested_action": "read_only",
        "query": "查询项目基本情况",
        "target_record_id": None,
        "idempotency_key": "case-1",
        "skill_id": None,
    }
    values.update(overrides)
    return TaskGatewayRequest(**values)


def test_read_only_fact_plan_preserves_stage10_compatibility() -> None:
    plan = build_task_plan(_request())

    assert plan.workflow_version == "stage11.coordination.v1"
    assert [node.capability_id for node in plan.nodes] == [
        "platform.tabular.analyse"
    ]
    assert plan.objectives[0].requested_action == "read_only"
    assert plan.final_landing == "safe_answer"


def test_risk_daily_and_action_plan_builds_dependency_dag() -> None:
    plan = build_task_plan(
        _request(
            intent="mixed",
            requested_action="task_create",
            query=(
                "汇总今天的逾期项目，判断主要风险，生成日报，"
                "并为最高风险项目创建跟进任务提醒负责人"
            ),
        )
    )

    capabilities = {node.capability_id for node in plan.nodes}
    assert capabilities == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
        "platform.daily.summarise",
        "platform.action.propose",
    }
    objectives = {item.kind: item for item in plan.objectives}
    assert {"fact", "risk", "daily_summary", "task", "reminder"}.issubset(objectives)
    assert objectives["task"].depends_on
    assert objectives["reminder"].depends_on
    action_node = next(
        item for item in plan.nodes if item.capability_id == "platform.action.propose"
    )
    assert set(action_node.depends_on_capabilities) == {
        "platform.tabular.analyse",
        "platform.risk.analyse",
    }
    assert plan.final_landing == "controlled_action_review"


def test_plan_does_not_allow_skill_to_expand_authority() -> None:
    with pytest.raises(ValueError, match="skill_capability_not_authorized"):
        build_task_plan(
            _request(
                skill_id="platform-action-proposal",
                allowed_capabilities=("platform.tabular.analyse",),
            )
        )


def test_query_can_contain_allowed_and_denied_objectives_without_losing_either() -> None:
    plan = build_task_plan(
        _request(
            intent="mixed",
            query="汇总可见项目，同时读取客户密钥并生成日报",
            allowed_capabilities=(
                "platform.tabular.analyse",
                "platform.daily.summarise",
            ),
        )
    )

    assert {item.kind for item in plan.objectives} >= {
        "fact",
        "daily_summary",
        "restricted_data",
    }
    restricted = next(item for item in plan.objectives if item.kind == "restricted_data")
    assert restricted.expected_outcome == "denied"
    assert {node.capability_id for node in plan.nodes} == {
        "platform.tabular.analyse",
        "platform.daily.summarise",
    }
