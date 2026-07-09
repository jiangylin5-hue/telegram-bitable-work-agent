from app.agents.stage06_skills import (
    STAGE06_SKILL_MANIFEST_VERSION,
    get_stage06_active_skill_registry,
    get_stage06_skill_manifest,
    get_stage06_skill_registry,
    has_stage06_skill,
)


def test_stage06_skill_registry_preserves_all_27_larksuite_source_skills() -> None:
    registry = get_stage06_skill_registry()

    assert STAGE06_SKILL_MANIFEST_VERSION == "stage06-larksuite-skills-v1"
    assert len(registry) == 27
    assert {skill.source_skill for skill in registry} == {
        "lark-approval",
        "lark-apps",
        "lark-attendance",
        "lark-base",
        "lark-calendar",
        "lark-contact",
        "lark-doc",
        "lark-drive",
        "lark-event",
        "lark-im",
        "lark-mail",
        "lark-markdown",
        "lark-minutes",
        "lark-note",
        "lark-okr",
        "lark-openapi-explorer",
        "lark-shared",
        "lark-sheets",
        "lark-skill-maker",
        "lark-slides",
        "lark-task",
        "lark-vc",
        "lark-vc-agent",
        "lark-whiteboard",
        "lark-wiki",
        "lark-workflow-meeting-summary",
        "lark-workflow-standup-report",
    }


def test_stage06_active_core_skill_subset_is_generic_platform_first() -> None:
    active_ids = {skill.skill_id for skill in get_stage06_active_skill_registry()}

    assert active_ids == {
        "platform-approval",
        "platform-base",
        "platform-contact",
        "platform-event",
        "platform-file-import",
        "platform-shared-policy",
        "platform-skill-maker",
        "platform-tabular-analysis",
        "platform-task",
        "platform-telegram-im",
        "platform-tool-discovery",
    }
    assert "recharge-draft" not in active_ids
    assert "bm-invite-draft" not in active_ids
    assert "card-binding-draft" not in active_ids


def test_stage06_skill_manifest_keeps_project_native_boundaries() -> None:
    base = get_stage06_skill_manifest("platform-base")
    shared = get_stage06_skill_manifest("platform-shared-policy")
    live_meeting = get_stage06_skill_manifest("platform-live-meeting-agent-reference")

    assert base.status == "active"
    assert base.source_skill == "lark-base"
    assert "workspace" in base.required_context
    assert "raw_sql" in base.forbidden_actions
    assert "feishu_api_call" in base.forbidden_actions
    assert shared.confirmation_policy == "required_for_write_send_destructive"
    assert live_meeting.status == "reference_only"
    assert has_stage06_skill("platform-base") is True
    assert has_stage06_skill("recharge-draft") is False
