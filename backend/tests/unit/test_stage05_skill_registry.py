def test_stage05_skill_registry_contains_confirmed_platform_and_business_skills() -> None:
    from app.agents.stage05_skills import get_stage05_skill_registry

    registry = get_stage05_skill_registry()
    skill_ids = {skill.skill_id for skill in registry}

    assert {
        "project-base",
        "project-shared",
        "project-im",
        "project-event",
        "project-skill-maker",
        "project-task",
        "project-contact",
        "project-approval",
        "project-tabular-analysis",
        "project-tool-discovery",
        "project-daily-operations-workflow",
        "project-period-summary-workflow",
        "recharge-draft",
        "customer-reply-draft",
        "bm-invite-draft",
        "card-binding-draft",
        "account-exception-marking",
        "manual-review-handoff",
        "spend-query",
        "spend-table",
    }.issubset(skill_ids)
    assert "report-draft" not in skill_ids


def test_stage05_skill_registry_entries_have_required_boundaries() -> None:
    from app.agents.stage05_skills import get_stage05_skill_registry

    for skill in get_stage05_skill_registry():
        assert skill.skill_id
        assert skill.priority in {"P0", "P1"}
        assert skill.layer.startswith("L")
        assert skill.owning_agent
        assert skill.primary_endpoint
        assert skill.source_skill
        assert skill.description.startswith("Use when")
        assert skill.positive_triggers
        assert skill.forbidden_actions
        assert skill.execution_mode in {"sidecar", "draft", "manual_review", "future_scope"}


def test_stage05_skill_registry_keeps_reporting_as_future_workflow_only() -> None:
    from app.agents.stage05_skills import get_skill_manifest

    daily = get_skill_manifest("project-daily-operations-workflow")
    period = get_skill_manifest("project-period-summary-workflow")

    assert daily.execution_mode == "future_scope"
    assert period.execution_mode == "future_scope"
    assert daily.fallback in {"manual_review", "future_scope"}
    assert period.fallback in {"manual_review", "future_scope"}
