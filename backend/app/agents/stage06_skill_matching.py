import re
from dataclasses import dataclass
from typing import Any

from app.agents.stage06_skills import (
    STAGE06_SKILL_MANIFEST_VERSION,
    Stage06SkillManifest,
    get_stage06_active_skill_registry,
    get_stage06_skill_registry,
)


WRITE_LIKE_ACTIONS = frozenset({"draft_create", "draft_update", "status_advance"})
NON_DISCRIMINATING_CONTEXT_KEYS = frozenset({"actor_user_id", "workspace_id"})
GUARDRAIL_SKILLS = frozenset({"platform-approval", "platform-shared-policy"})
POLICY_DENIAL_TRIGGERS = (
    "bypass permission",
    "ignore scope",
    "hidden field",
    "hidden from me",
    "restricted field",
    "private records",
    "raw sql",
)
DATA_ACCESS_SKILLS = frozenset(
    {
        "platform-base",
        "platform-contact",
        "platform-file-import",
        "platform-tabular-analysis",
        "platform-task",
        "platform-telegram-im",
    }
)


@dataclass(frozen=True)
class Stage06SkillMatchContext:
    action: str
    source_text: str
    source_context: dict[str, object]

    @classmethod
    def from_values(
        cls,
        *,
        action: str,
        source_text: str | None,
        source_context: dict[str, object] | None,
    ) -> "Stage06SkillMatchContext":
        return cls(
            action=action,
            source_text=source_text or "",
            source_context=dict(source_context or {}),
        )


def build_stage06_skill_evidence(
    *,
    action: str,
    source_text: str | None,
    source_context: dict[str, object] | None = None,
) -> dict[str, object]:
    context = Stage06SkillMatchContext.from_values(
        action=action,
        source_text=source_text,
        source_context=source_context,
    )
    selected: list[dict[str, object]] = []
    inactive: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    missing_context: list[dict[str, object]] = []

    for skill in get_stage06_active_skill_registry():
        if _is_foundation_skill(skill) or _skill_matches_context(skill, context):
            selection = (
                "selected_guardrail"
                if _skill_requires_guardrail(skill, context)
                else "selected"
            )
            _append_unique(selected, _match_item(skill, context, selection))

    for skill in get_stage06_skill_registry():
        if skill.status != "active" and _skill_matches_context(skill, context):
            inactive.append(_match_item(skill, context, skill.status))

    _ensure_action_defaults(selected, context)
    _append_missing_context(selected, context, missing_context)
    _reject_negative_trigger_matches(selected, rejected, context)
    _block_policy_denied_data_routes(selected, rejected, context)

    requires_confirmation = context.action in WRITE_LIKE_ACTIONS or (
        _looks_write_like(context)
        and any(
            str(item["skill_id"]) in {"platform-approval", "platform-telegram-im"}
            for item in selected
        )
    )
    requires_clarification = bool(missing_context)
    requires_manual_review = any(
        item.get("selection") == "selected_guardrail" for item in selected
    )
    fallback = _fallback(
        inactive=inactive,
        requires_confirmation=requires_confirmation,
        requires_clarification=requires_clarification,
        requires_manual_review=requires_manual_review,
    )
    return {
        "manifest_version": STAGE06_SKILL_MANIFEST_VERSION,
        "mode": "deterministic_manifest_matching",
        "source": "action_text_context",
        "candidate_skills": selected + inactive + rejected,
        "selected_skills": selected,
        "inactive_candidates": inactive,
        "rejected_skills": rejected,
        "missing_context": missing_context,
        "requires_confirmation": requires_confirmation,
        "requires_clarification": requires_clarification,
        "fallback": fallback,
        "baseline_metrics": {
            "candidate_count": len(selected) + len(inactive) + len(rejected),
            "selected_count": len(selected),
            "inactive_count": len(inactive),
            "rejected_count": len(rejected),
            "missing_context_count": len(missing_context),
            "selected_skill_ids": [str(item["skill_id"]) for item in selected],
        },
    }


def _is_foundation_skill(skill: Stage06SkillManifest) -> bool:
    return skill.skill_id == "platform-shared-policy"


def _skill_matches_context(
    skill: Stage06SkillManifest,
    context: Stage06SkillMatchContext,
) -> bool:
    text = _lowered_text(context)
    if any(_trigger_matches(trigger, text) for trigger in skill.negative_triggers):
        return False
    if any(_trigger_matches(trigger, text) for trigger in skill.positive_triggers):
        return True
    if any(
        pattern not in NON_DISCRIMINATING_CONTEXT_KEYS
        and pattern in context.source_context
        for pattern in skill.resource_patterns
    ):
        return True
    if skill.skill_id == "platform-telegram-im" and "telegram_chat_id" in context.source_context:
        return True
    return False


def _ensure_action_defaults(
    selected: list[dict[str, object]],
    context: Stage06SkillMatchContext,
) -> None:
    selected_ids = {str(item["skill_id"]) for item in selected}
    active_by_id = {skill.skill_id: skill for skill in get_stage06_active_skill_registry()}
    if context.action == "summarize":
        for skill_id in ("platform-base", "platform-tabular-analysis"):
            if skill_id not in selected_ids:
                skill = active_by_id[skill_id]
                _append_unique(
                    selected,
                    _match_item(
                        skill,
                        context,
                        "selected_guardrail"
                        if _skill_requires_guardrail(skill, context)
                        else "selected",
                    ),
                )
    if context.action in WRITE_LIKE_ACTIONS:
        for skill_id in ("platform-base", "platform-approval"):
            if skill_id not in selected_ids:
                skill = active_by_id[skill_id]
                _append_unique(
                    selected,
                    _match_item(
                        skill,
                        context,
                        "selected_guardrail"
                        if _skill_requires_guardrail(skill, context)
                        else "selected",
                    ),
                )


def _append_missing_context(
    selected: list[dict[str, object]],
    context: Stage06SkillMatchContext,
    missing_context: list[dict[str, object]],
) -> None:
    context_keys = set(context.source_context)
    for item in selected:
        required = item.get("required_context", ())
        if not isinstance(required, tuple):
            continue
        for key in required:
            if _context_key_satisfied(key, context_keys):
                continue
            missing_context.append({"skill_id": item["skill_id"], "context_key": key})


def _context_key_satisfied(key: str, context_keys: set[str]) -> bool:
    if key == "workspace":
        return bool(
            {"workspace", "workspace_id", "base_id", "table_id", "view_id", "record_id"}
            & context_keys
        )
    return key in context_keys


def _reject_negative_trigger_matches(
    selected: list[dict[str, object]],
    rejected: list[dict[str, object]],
    context: Stage06SkillMatchContext,
) -> None:
    active_by_id = {skill.skill_id: skill for skill in get_stage06_active_skill_registry()}
    text = _lowered_text(context)
    for item in list(selected):
        skill = active_by_id.get(str(item["skill_id"]))
        if (
            skill
            and item.get("selection") != "selected_guardrail"
            and any(_trigger_matches(trigger, text) for trigger in skill.negative_triggers)
        ):
            selected.remove(item)
            rejected.append({**item, "selection": "rejected_by_negative_trigger"})


def _skill_requires_guardrail(
    skill: Stage06SkillManifest,
    context: Stage06SkillMatchContext,
) -> bool:
    text = _lowered_text(context)
    if skill.skill_id == "platform-shared-policy":
        return _has_policy_denial_intent(context) or any(
            _trigger_matches(trigger, text)
            for active_skill in get_stage06_active_skill_registry()
            for trigger in active_skill.negative_triggers
        )
    return skill.skill_id in GUARDRAIL_SKILLS and any(
        _trigger_matches(trigger, text) for trigger in skill.negative_triggers
    )


def _block_policy_denied_data_routes(
    selected: list[dict[str, object]],
    rejected: list[dict[str, object]],
    context: Stage06SkillMatchContext,
) -> None:
    if not _has_policy_denial_intent(context):
        return
    for item in list(selected):
        if str(item["skill_id"]) not in DATA_ACCESS_SKILLS:
            continue
        selected.remove(item)
        rejected.append({**item, "selection": "rejected_by_policy_guardrail"})


def _has_policy_denial_intent(context: Stage06SkillMatchContext) -> bool:
    text = _lowered_text(context)
    return any(trigger in text for trigger in POLICY_DENIAL_TRIGGERS)


def _looks_write_like(context: Stage06SkillMatchContext) -> bool:
    text = _lowered_text(context)
    return any(token in text for token in ("send", "发送", "update", "改成", "确认", "approve"))


def _match_item(
    skill: Stage06SkillManifest,
    context: Stage06SkillMatchContext,
    selection: str,
) -> dict[str, object]:
    return {
        "skill_id": skill.skill_id,
        "source_skill": skill.source_skill,
        "status": skill.status,
        "layer": skill.layer,
        "confidence": _confidence(skill, context),
        "selection": selection,
        "reason": "matched_stage06_manifest_triggers_or_context",
        "fallback": skill.fallback,
        "required_context": skill.required_context,
        "confirmation_policy": skill.confirmation_policy,
        "output_contract": skill.output_contract,
    }


def _confidence(skill: Stage06SkillManifest, context: Stage06SkillMatchContext) -> str:
    text = _lowered_text(context)
    if any(_trigger_matches(trigger, text) for trigger in skill.positive_triggers):
        return "0.90"
    if any(pattern in context.source_context for pattern in skill.resource_patterns):
        return "0.80"
    if _is_foundation_skill(skill):
        return "0.75"
    return "0.65"


def _fallback(
    *,
    inactive: list[dict[str, object]],
    requires_confirmation: bool,
    requires_clarification: bool,
    requires_manual_review: bool,
) -> str:
    if any(item["selection"] == "reference_only" for item in inactive):
        return "manual_review"
    if requires_confirmation:
        return "draft_confirmation"
    if requires_manual_review:
        return "manual_review"
    if requires_clarification:
        return "ask_for_missing_context"
    return "none"


def _append_unique(items: list[dict[str, object]], item: dict[str, object]) -> None:
    if str(item["skill_id"]) not in {str(existing["skill_id"]) for existing in items}:
        items.append(item)


def _lowered_text(context: Stage06SkillMatchContext) -> str:
    return f"{context.action} {context.source_text}".lower()


def _trigger_matches(trigger: str, text: str) -> bool:
    normalized = trigger.strip().lower()
    if not normalized:
        return False
    if normalized.isascii() and any(character.isalnum() for character in normalized):
        optional_plural = (
            r"(?:s|es)?" if re.fullmatch(r"[a-z0-9_]+", normalized) else ""
        )
        pattern = (
            rf"(?<![a-z0-9_]){re.escape(normalized)}"
            rf"{optional_plural}(?![a-z0-9_])"
        )
        return re.search(pattern, text) is not None
    return normalized in text


__all__ = ["Stage06SkillMatchContext", "build_stage06_skill_evidence"]
