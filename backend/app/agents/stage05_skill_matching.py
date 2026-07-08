from decimal import Decimal
from typing import Any

from app.agents.schemas import RouterIntent, RouterResult
from app.agents.stage05_skills import (
    STAGE05_SKILL_MANIFEST_VERSION,
    Stage05SkillManifest,
    get_skill_manifest,
)


FOUNDATION_SKILLS = (
    "project-base",
    "project-shared",
    "project-im",
    "project-event",
)

INTENT_SKILL_MAP = {
    "recharge": ("recharge-draft",),
    "customer_reply": ("customer-reply-draft", "project-approval"),
    "bm_invite": ("bm-invite-draft", "project-contact"),
    "card_binding": ("card-binding-draft",),
    "account_assignment": ("manual-review-handoff", "project-task"),
    "account_status_exception": ("account-exception-marking",),
    "spend_query": ("spend-query", "project-tabular-analysis", "manual-review-handoff"),
    "spend_table": ("spend-table", "project-tabular-analysis", "manual-review-handoff"),
    "report_request": (
        "project-daily-operations-workflow",
        "manual-review-handoff",
    ),
    "unknown": ("manual-review-handoff",),
    "irrelevant": ("manual-review-handoff",),
}


def build_skill_evidence(
    *,
    router_result: RouterResult,
    source_text_summary: str,
) -> dict[str, object]:
    selected_ids: list[str] = []
    future_ids: list[str] = []
    rejected: list[dict[str, object]] = []
    missing_entities: list[dict[str, object]] = []

    for skill_id in FOUNDATION_SKILLS:
        _append_unique(selected_ids, skill_id)

    if router_result.requires_manual_review or router_result.manual_review_reasons:
        _append_unique(selected_ids, "manual-review-handoff")

    for intent in router_result.intents:
        for skill_id in INTENT_SKILL_MAP.get(intent.intent_type, ()):
            _append_unique(selected_ids, skill_id)
        _append_required_entity_gaps(
            selected_ids=selected_ids,
            intent=intent,
            missing_entities=missing_entities,
        )

    if _looks_like_report_request(source_text_summary, router_result):
        _append_unique(selected_ids, "project-daily-operations-workflow")
        _append_unique(selected_ids, "manual-review-handoff")
        rejected.append(
            {
                "skill_id": "report-draft",
                "selection": "rejected",
                "reason": "report_draft_not_registered_in_stage05_skills_extension",
                "fallback": "future_scope",
            }
        )

    selected_items = [
        _match_item(
            skill=get_skill_manifest(skill_id),
            router_result=router_result,
            selection=(
                "future_scope"
                if get_skill_manifest(skill_id).execution_mode == "future_scope"
                else "selected"
            ),
        )
        for skill_id in selected_ids
    ]
    for item in selected_items:
        if item["selection"] == "future_scope":
            future_ids.append(str(item["skill_id"]))

    return {
        "manifest_version": STAGE05_SKILL_MANIFEST_VERSION,
        "mode": "sidecar_candidate_logging",
        "source": "router_result_and_redacted_text",
        "candidate_skills": selected_items + rejected,
        "selected_skills": selected_items,
        "rejected_skills": rejected,
        "future_scope_skills": [
            item for item in selected_items if item["skill_id"] in future_ids
        ],
        "missing_entities": missing_entities,
        "fallback": _fallback(selected_items, router_result),
        "baseline_metrics": {
            "candidate_count": len(selected_items) + len(rejected),
            "selected_count": len(selected_items),
            "future_scope_count": len(future_ids),
            "rejected_count": len(rejected),
            "selected_business_skill_ids": [
                str(item["skill_id"])
                for item in selected_items
                if str(item["layer"]).startswith("L3")
            ],
            "selected_platform_skill_ids": [
                str(item["skill_id"])
                for item in selected_items
                if not str(item["layer"]).startswith("L3")
            ],
        },
    }


def _append_required_entity_gaps(
    *,
    selected_ids: list[str],
    intent: RouterIntent,
    missing_entities: list[dict[str, object]],
) -> None:
    for skill_id in INTENT_SKILL_MAP.get(intent.intent_type, ()):
        skill = get_skill_manifest(skill_id)
        for entity in skill.required_entities:
            if entity not in intent.entities and entity not in intent.missing_context:
                missing_entities.append(
                    {
                        "skill_id": skill_id,
                        "entity": entity,
                        "source": "skill_required_entity",
                    }
                )
        for entity in intent.missing_context:
            missing_entities.append(
                {
                    "skill_id": skill_id,
                    "entity": entity,
                    "source": "router_missing_context",
                }
            )
    if intent.missing_context and "manual-review-handoff" in selected_ids:
        for entity in intent.missing_context:
            missing_entities.append(
                {
                    "skill_id": "manual-review-handoff",
                    "entity": entity,
                    "source": "router_missing_context",
                }
            )


def _match_item(
    *,
    skill: Stage05SkillManifest,
    router_result: RouterResult,
    selection: str,
) -> dict[str, object]:
    return {
        "skill_id": skill.skill_id,
        "priority": skill.priority,
        "layer": skill.layer,
        "owning_agent": skill.owning_agent,
        "primary_agent_node": skill.primary_agent_node,
        "primary_endpoint": skill.primary_endpoint,
        "confidence": str(_confidence_for_skill(skill, router_result)),
        "selection": selection,
        "reason": "matched_router_intent_or_stage05_foundation",
        "fallback": skill.fallback,
    }


def _confidence_for_skill(
    skill: Stage05SkillManifest,
    router_result: RouterResult,
) -> Decimal:
    matched: list[Decimal] = []
    mapped_intents = [
        intent_type
        for intent_type, skill_ids in INTENT_SKILL_MAP.items()
        if skill.skill_id in skill_ids
    ]
    for intent in router_result.intents:
        if intent.intent_type in mapped_intents:
            matched.append(intent.confidence)
    if matched:
        return max(matched)
    return router_result.overall_confidence


def _looks_like_report_request(
    source_text_summary: str,
    router_result: RouterResult,
) -> bool:
    lowered = source_text_summary.lower()
    if any(intent.intent_type == "report_request" for intent in router_result.intents):
        return True
    return any(
        token in lowered
        for token in ("daily report", "weekly report", "monthly report", "日报", "周报", "月报")
    )


def _fallback(
    selected_items: list[dict[str, Any]],
    router_result: RouterResult,
) -> str:
    if any(item["selection"] == "future_scope" for item in selected_items):
        return "future_scope"
    if router_result.requires_manual_review:
        return "manual_review"
    return "none"


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


__all__ = ["build_skill_evidence"]
