"""Deterministic, source-preserving lexical extraction for Planner V2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
import re
from typing import Literal
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas.agent_task_spec_v2 import SourceSpan


LexicalTokenKind = Literal[
    "identifier",
    "action",
    "safety",
    "logical",
    "date",
    "number",
    "limit",
    "aggregation",
    "comparison",
    "risk_intent",
]

_PUNCTUATION = str.maketrans(
    {
        "，": ",",
        "；": ";",
        "。": ".",
        "！": "!",
        "？": "?",
        "、": ",",
    }
)
_IDENTIFIER_RE = re.compile(
    r"(?<![A-Z0-9])(?:[A-Z][A-Z0-9_]{1,31})-[A-Z0-9][A-Z0-9_-]{0,63}(?![A-Z0-9])",
    re.IGNORECASE,
)
_CLAUSE_CONNECTOR_RE = re.compile(r"同时|然后|并且|但|若|[,;.!?]")
_LIMIT_RE = re.compile(r"前\s*([一二三四五六七八九十\d]+)")
_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(frozen=True, slots=True)
class CanonicalQuery:
    original_text: str
    normalized_text: str
    normalized_to_source: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LexicalToken:
    kind: LexicalTokenKind
    canonical_value: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class LexicalClause:
    clause_id: str
    text: str
    connector_before: str | None
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class LexicalDateRange:
    kind: Literal["today", "tomorrow", "before_tomorrow", "this_week"]
    start_utc: datetime | None
    end_utc: datetime
    source_span: SourceSpan


@dataclass(frozen=True, slots=True)
class LexicalQuery:
    canonical: CanonicalQuery
    tokens: tuple[LexicalToken, ...]
    clauses: tuple[LexicalClause, ...]
    date_ranges: tuple[LexicalDateRange, ...]


def canonicalize_query(query: str) -> CanonicalQuery:
    normalized_chars: list[str] = []
    source_indexes: list[int] = []
    previous_space = False
    for index, character in enumerate(query):
        expanded = unicodedata.normalize("NFKC", character).translate(_PUNCTUATION)
        for normalized in expanded:
            if normalized.isspace():
                if previous_space:
                    continue
                normalized = " "
                previous_space = True
            else:
                previous_space = False
            normalized_chars.append(normalized)
            source_indexes.append(index)
    return CanonicalQuery(
        original_text=query,
        normalized_text="".join(normalized_chars),
        normalized_to_source=tuple(source_indexes),
    )


def extract_lexical_query(
    query: str,
    *,
    clock: datetime,
    timezone_name: str,
) -> LexicalQuery:
    _validate_query(query)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("lexical_clock_timezone_required")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("lexical_timezone_invalid") from exc
    canonical = canonicalize_query(query)
    tokens: list[LexicalToken] = []
    for match in _IDENTIFIER_RE.finditer(canonical.normalized_text):
        tokens.append(
            _token(
                canonical,
                match.start(),
                match.end(),
                "identifier",
                match.group().upper(),
            )
        )
    tokens.extend(_pattern_tokens(canonical))
    date_ranges = _extract_date_ranges(canonical, clock=clock, timezone=timezone)
    tokens.extend(
        LexicalToken(
            kind="date",
            canonical_value=item.kind,
            source_span=item.source_span,
        )
        for item in date_ranges
    )
    tokens.extend(_limit_tokens(canonical))
    unique_tokens = {
        (
            item.kind,
            item.canonical_value,
            item.source_span.start,
            item.source_span.end,
        ): item
        for item in tokens
    }
    ordered = tuple(
        sorted(
            unique_tokens.values(),
            key=lambda item: (
                item.source_span.start,
                item.source_span.end,
                item.kind,
                item.canonical_value,
            ),
        )
    )
    return LexicalQuery(
        canonical=canonical,
        tokens=ordered,
        clauses=_segment_clauses(canonical),
        date_ranges=date_ranges,
    )


def _validate_query(query: str) -> None:
    if not query or query != query.strip() or "\x00" in query:
        raise ValueError("lexical_query_boundary_invalid")
    if len(query) > 600:
        raise ValueError("lexical_query_length_invalid")


def _source_span(canonical: CanonicalQuery, start: int, end: int) -> SourceSpan:
    if start < 0 or end <= start or end > len(canonical.normalized_to_source):
        raise ValueError("lexical_source_span_invalid")
    source_start = canonical.normalized_to_source[start]
    source_end = canonical.normalized_to_source[end - 1] + 1
    return SourceSpan(
        start=source_start,
        end=source_end,
        text=canonical.original_text[source_start:source_end],
    )


def _token(
    canonical: CanonicalQuery,
    start: int,
    end: int,
    kind: LexicalTokenKind,
    value: str,
) -> LexicalToken:
    return LexicalToken(
        kind=kind,
        canonical_value=value,
        source_span=_source_span(canonical, start, end),
    )


def _pattern_tokens(canonical: CanonicalQuery) -> list[LexicalToken]:
    patterns: tuple[tuple[LexicalTokenKind, str, str], ...] = (
        (
            "action",
            r"(?<!只)(?<!仅)(?:创建|生成|新增)[^，,;；。]{0,20}?任务",
            "task.create",
        ),
        (
            "action",
            r"(?<!只)(?<!仅)(?:创建|生成|新增)[^，,;；。]{0,20}?提醒|提醒|催办请求",
            "reminder.request",
        ),
        (
            "action",
            r"(?:修改|改为|调整为|补充|(?<!错误)更新)",
            "record.update",
        ),
        ("action", r"(?:新增|创建).{0,32}?(?:记录|事项)", "record.create"),
        ("action", r"(?:发送|通知|催办)", "external.send"),
        ("action", r"删除", "delete"),
        ("action", r"确认", "confirm"),
        (
            "safety",
            r"只生成(?:一个|任务)?草稿|仅生成(?:一个|任务)?草稿",
            "draft_only",
        ),
        (
            "safety",
            r"不要(?:直接)?发送|绝不能直接发送|不得发送|不能群发",
            "no_external_send",
        ),
        ("safety", r"等待确认|需要确认", "confirmation_required"),
        ("aggregation", r"数量|计数|统计|总计", "count"),
        ("aggregation", r"平均", "average"),
        ("aggregation", r"求和|合计", "sum"),
        ("comparison", r"最高|最大", "maximum"),
        ("comparison", r"最低|最小", "minimum"),
        (
            "risk_intent",
            r"(?:比较|评估|分析|解释|说明|判断|识别).{0,24}?风险"
            r"|风险.{0,12}?(?:暴露|评估|分析|解释)"
            r"|潜在.{0,12}?风险",
            "risk_analysis",
        ),
    )
    values: list[LexicalToken] = []
    for kind, pattern, canonical_value in patterns:
        for match in re.finditer(pattern, canonical.normalized_text, re.IGNORECASE):
            values.append(
                _token(
                    canonical,
                    match.start(),
                    match.end(),
                    kind,
                    canonical_value,
                )
            )
    for match in re.finditer(
        r"同时|然后|并且|但|若|只|不要", canonical.normalized_text
    ):
        values.append(
            _token(canonical, match.start(), match.end(), "logical", match.group())
        )
    return values


def _limit_tokens(canonical: CanonicalQuery) -> list[LexicalToken]:
    values: list[LexicalToken] = []
    for match in _LIMIT_RE.finditer(canonical.normalized_text):
        raw = match.group(1)
        number = int(raw) if raw.isdigit() else _CHINESE_NUMBERS.get(raw)
        if number is None or not 1 <= number <= 5000:
            continue
        values.append(
            _token(canonical, match.start(), match.end(), "limit", str(number))
        )
    return values


def _extract_date_ranges(
    canonical: CanonicalQuery,
    *,
    clock: datetime,
    timezone: ZoneInfo,
) -> tuple[LexicalDateRange, ...]:
    local_clock = clock.astimezone(timezone)
    today = datetime.combine(local_clock.date(), time.min, tzinfo=timezone)
    monday = today - timedelta(days=today.weekday())
    patterns: tuple[tuple[str, str, datetime | None, datetime], ...] = (
        ("明天之前", "before_tomorrow", None, today + timedelta(days=2)),
        ("今天", "today", today, today + timedelta(days=1)),
        (
            "明天",
            "tomorrow",
            today + timedelta(days=1),
            today + timedelta(days=2),
        ),
        ("本周", "this_week", monday, monday + timedelta(days=7)),
    )
    occupied: set[int] = set()
    values: list[LexicalDateRange] = []
    for phrase, kind, start_local, end_local in patterns:
        for match in re.finditer(phrase, canonical.normalized_text):
            indexes = set(range(match.start(), match.end()))
            if indexes & occupied:
                continue
            occupied.update(indexes)
            values.append(
                LexicalDateRange(
                    kind=kind,  # type: ignore[arg-type]
                    start_utc=(
                        None if start_local is None else start_local.astimezone(UTC)
                    ),
                    end_utc=end_local.astimezone(UTC),
                    source_span=_source_span(canonical, match.start(), match.end()),
                )
            )
    return tuple(sorted(values, key=lambda item: item.source_span.start))


def _segment_clauses(canonical: CanonicalQuery) -> tuple[LexicalClause, ...]:
    values: list[LexicalClause] = []
    segment_start = 0
    pending_connector: str | None = None

    def append_segment(start: int, end: int) -> None:
        nonlocal pending_connector
        while start < end and canonical.normalized_text[start].isspace():
            start += 1
        while end > start and (
            canonical.normalized_text[end - 1].isspace()
            or canonical.normalized_text[end - 1] in ",;.!?"
        ):
            end -= 1
        if start >= end:
            return
        span = _source_span(canonical, start, end)
        values.append(
            LexicalClause(
                clause_id=f"clause-{len(values) + 1:02d}",
                text=span.text.strip().strip(",;.!?，；。！？"),
                connector_before=pending_connector,
                source_span=span,
            )
        )
        pending_connector = None

    for match in _CLAUSE_CONNECTOR_RE.finditer(canonical.normalized_text):
        connector = match.group()
        append_segment(segment_start, match.start())
        if connector not in ",;.!?":
            pending_connector = connector
        segment_start = match.end()
    append_segment(segment_start, len(canonical.normalized_text))
    return tuple(values)


__all__ = [
    "CanonicalQuery",
    "LexicalClause",
    "LexicalDateRange",
    "LexicalQuery",
    "LexicalToken",
    "canonicalize_query",
    "extract_lexical_query",
]
