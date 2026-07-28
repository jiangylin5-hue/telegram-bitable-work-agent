"""Bounded deterministic retrieval over an already permission-filtered view."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


_IDENTIFIER_RE = re.compile(r"\b[A-Z][A-Z0-9]*-\d{3,}\b", re.IGNORECASE)


@dataclass(frozen=True)
class TableQueryIntent:
    mode: Literal["records", "count"]
    filters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TableQueryResult:
    mode: Literal["records", "count"]
    records: tuple[dict[str, Any], ...]
    record_ids: tuple[str, ...]
    aggregate_value: int | None


def parse_supported_table_query(
    prompt: str | None,
    visible_records: list[dict[str, Any]],
) -> TableQueryIntent | None:
    text = _normalize_supported_query_text(prompt or "")
    if not text or _looks_sensitive(text):
        return None
    identifier = _IDENTIFIER_RE.search(prompt or "")
    visible_fields = _visible_scalar_values(visible_records)
    if identifier is not None and "ticket_code" in visible_fields:
        return TableQueryIntent("records", (("ticket_code", identifier.group(0).upper()),))
    filters = tuple(
        (field_key, value)
        for field_key, values in visible_fields.items()
        for value in values
        if _visible_value_mentioned(value, text)
        and not _value_is_qualified_for_another_field(text, field_key, value)
    )
    if not filters:
        return None
    if "how many" in text or "count" in text:
        return TableQueryIntent("count", filters)
    if any(token in text for token in ("list", "show", "find")):
        return TableQueryIntent("records", filters)
    return None


def execute_visible_table_query(
    intent: TableQueryIntent | None,
    visible_records: list[dict[str, Any]],
) -> TableQueryResult:
    if intent is None:
        raise ValueError("table_query_intent_required")
    matches = tuple(
        record
        for record in visible_records
        if isinstance(record.get("id"), str)
        and isinstance(record.get("fields"), dict)
        and all(record["fields"].get(key) == value for key, value in intent.filters)
    )
    record_ids = tuple(str(record["id"]) for record in matches)
    return TableQueryResult(
        mode=intent.mode,
        records=matches,
        record_ids=record_ids,
        aggregate_value=len(matches) if intent.mode == "count" else None,
    )


def answer_covers_result_ticket_codes(
    answer: str,
    records: list[dict[str, Any]],
) -> bool:
    """Require a record-mode explanation to name every deterministic ticket code."""

    required_codes = {
        value.casefold()
        for record in records
        if isinstance(record.get("fields"), dict)
        and isinstance((value := record["fields"].get("ticket_code")), str)
    }
    return all(code in answer.casefold() for code in required_codes)


def _visible_scalar_values(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for record in records:
        fields = record.get("fields")
        if not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            if isinstance(key, str) and isinstance(value, str) and value:
                values.setdefault(key, set()).add(value)
    return values


def _looks_sensitive(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "private_notes",
            "private-notes",
            "private notes",
            "internal_notes",
            "internal-notes",
            "internal notes",
            "restricted_",
            "restricted-",
        )
    )


def _value_is_qualified_for_another_field(
    text: str,
    field_key: str,
    value: str,
) -> bool:
    """Keep a shared scalar value bound to the field named by the prompt.

    Values such as ``high`` are intentionally not globally unique: it can mean a
    high risk level or a high priority.  The supported-language parser only
    accepts an unambiguous field-qualified phrase, rather than silently adding
    both predicates and lowering recall.
    """

    escaped_value = re.escape(value.casefold())
    risk_phrase = rf"\b{escaped_value}\s+risk\b"
    priority_phrase = rf"\b{escaped_value}\s+priority\b"
    if field_key != "risk_level" and re.search(risk_phrase, text):
        return True
    if field_key != "priority" and re.search(priority_phrase, text):
        return True
    return False


def _visible_value_mentioned(value: str, text: str) -> bool:
    """Match a visible scalar as words while accepting separator spelling variants."""

    normalized_value = re.sub(r"[_\-\s]+", " ", value.casefold()).strip()
    normalized_text = re.sub(r"[_\-\s]+", " ", text.casefold()).strip()
    if not normalized_value:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_value)}(?!\w)", normalized_text) is not None


def _normalize_supported_query_text(value: str) -> str:
    """Normalize only the documented English/Chinese bounded query vocabulary."""

    normalized = value.casefold()
    replacements = (
        ("高优先级", "high priority"),
        ("高风险", "high risk"),
        ("进行中", "in_progress"),
        ("已完成", "done"),
        ("已阻塞", "blocked"),
        ("计划中", "planned"),
        ("多少", "how many"),
        ("几个", "how many"),
        ("列出", "list"),
        ("显示", "show"),
        ("查询", "find"),
        ("查找", "find"),
        ("阻塞", "blocked"),
    )
    for source, replacement in replacements:
        normalized = normalized.replace(source, f" {replacement} ")
    return normalized
