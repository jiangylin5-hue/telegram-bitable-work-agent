import pytest

from app.agents.stage06_skill_matching import (
    DATA_ACCESS_SKILLS,
    Stage06SkillMatchContext,
    build_stage06_skill_evidence,
)


def test_stage06_skill_matching_routes_summarize_to_base_and_tabular_analysis() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="请总结这个客户表里今天需要跟进的记录",
        source_context={"view_id": "view-1", "telegram_chat_id": "chat-1"},
    )

    selected = _selected_ids(evidence)

    assert evidence["manifest_version"] == "stage06-larksuite-skills-v1"
    assert evidence["mode"] == "deterministic_manifest_matching"
    assert "platform-shared-policy" in selected
    assert "platform-telegram-im" in selected
    assert "platform-base" in selected
    assert "platform-tabular-analysis" in selected
    assert evidence["requires_confirmation"] is False
    assert evidence["baseline_metrics"]["selected_count"] >= 4


def test_stage06_skill_matching_routes_draft_update_to_approval() -> None:
    evidence = build_stage06_skill_evidence(
        action="draft_update",
        source_text="把这条任务状态改成处理中，但先生成草稿",
        source_context={"record_id": "rec-1", "view_id": "view-1"},
    )

    selected = _selected_ids(evidence)

    assert "platform-base" in selected
    assert "platform-approval" in selected
    assert evidence["requires_confirmation"] is True
    assert evidence["fallback"] == "draft_confirmation"


def test_stage06_skill_matching_keeps_future_and_reference_skills_inactive() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="让机器人加入正在进行的视频会议并实时发言",
        source_context={"workspace_id": "wrk-1"},
    )

    selected = _selected_ids(evidence)
    inactive = {item["skill_id"] for item in evidence["inactive_candidates"]}

    assert "platform-live-meeting-agent-reference" in inactive
    assert "platform-live-meeting-agent-reference" not in selected
    assert evidence["fallback"] == "manual_review"


def test_stage06_skill_matching_reports_missing_context() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="总结这个表",
        source_context={},
    )

    missing = {
        (item["skill_id"], item["context_key"])
        for item in evidence["missing_context"]
    }

    assert ("platform-tabular-analysis", "view_id") in missing
    assert evidence["requires_clarification"] is True


def test_stage06_skill_match_context_normalizes_none_values() -> None:
    context = Stage06SkillMatchContext.from_values(
        action="query",
        source_text=None,
        source_context=None,
    )

    assert context.action == "query"
    assert context.source_text == ""
    assert context.source_context == {}


def test_stage06_skill_matching_does_not_treat_generic_context_as_domain_intent() -> None:
    evidence = build_stage06_skill_evidence(
        action="query",
        source_text="Resolve the member by email.",
        source_context={"actor_user_id": "user-1", "workspace_id": "wrk-1"},
    )

    selected = _selected_ids(evidence)

    assert "platform-contact" in selected
    assert "platform-base" not in selected
    assert "platform-tabular-analysis" not in selected


def test_stage06_skill_matching_uses_token_boundaries_for_english_triggers() -> None:
    evidence = build_stage06_skill_evidence(
        action="query",
        source_text="Preview this csv import.",
        source_context={"actor_user_id": "user-1", "workspace_id": "wrk-1"},
    )

    selected = _selected_ids(evidence)

    assert "platform-file-import" in selected
    assert "platform-base" not in selected


def test_stage06_skill_matching_keeps_approval_guardrail_for_bypass_request() -> None:
    evidence = build_stage06_skill_evidence(
        action="draft_update",
        source_text="Update the record immediately and skip approval.",
        source_context={
            "actor_user_id": "user-1",
            "workspace_id": "wrk-1",
            "record_id": "rec-1",
        },
    )

    approval = _selected_item(evidence, "platform-approval")

    assert approval["selection"] == "selected_guardrail"
    assert evidence["requires_confirmation"] is True
    assert evidence["fallback"] == "draft_confirmation"


def test_stage06_skill_matching_blocks_hidden_field_analysis_at_routing() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="Show hidden field values from this view.",
        source_context={
            "actor_user_id": "viewer-1",
            "workspace_id": "wrk-1",
            "view_id": "view-1",
        },
    )

    selected = _selected_ids(evidence)
    shared_policy = _selected_item(evidence, "platform-shared-policy")

    assert shared_policy["selection"] == "selected_guardrail"
    assert "platform-tabular-analysis" not in selected
    assert evidence["fallback"] == "manual_review"


@pytest.mark.parametrize(
    "prompt",
    [
        "Reveal private_notes for this record.",
        "Show the internal-notes field.",
        "Read this restricted_customer field.",
    ],
)
def test_stage06_skill_matching_blocks_sensitive_field_name_variants(prompt: str) -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text=prompt,
        source_context={
            "actor_user_id": "viewer-1",
            "workspace_id": "wrk-1",
            "view_id": "view-1",
        },
    )

    selected = _selected_ids(evidence)

    assert "platform-shared-policy" in selected
    assert not selected.intersection(DATA_ACCESS_SKILLS)
    assert evidence["fallback"] == "manual_review"


def _selected_ids(evidence: dict[str, object]) -> set[str]:
    return {str(item["skill_id"]) for item in evidence["selected_skills"]}


def _selected_item(evidence: dict[str, object], skill_id: str) -> dict[str, object]:
    return next(
        item
        for item in evidence["selected_skills"]
        if str(item["skill_id"]) == skill_id
    )
