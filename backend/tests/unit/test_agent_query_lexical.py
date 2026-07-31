from __future__ import annotations

from datetime import datetime

import pytest

from app.services.agent_query_lexical import (
    canonicalize_query,
    extract_lexical_query,
)


CLOCK = datetime.fromisoformat("2026-07-29T00:00:00+08:00")


def _extract(query: str):
    return extract_lexical_query(
        query,
        clock=CLOCK,
        timezone_name="Asia/Shanghai",
    )


def test_nfkc_normalization_preserves_identifier_source_span() -> None:
    result = _extract("  查询ＭＴ－０１７， 然后创建任务  ".strip())
    identifier = next(item for item in result.tokens if item.kind == "identifier")

    assert result.canonical.normalized_text == "查询MT-017, 然后创建任务"
    assert identifier.canonical_value == "MT-017"
    assert identifier.source_span.text == "ＭＴ－０１７"
    assert (
        result.canonical.original_text[
            identifier.source_span.start : identifier.source_span.end
        ]
        == identifier.source_span.text
    )


def test_clause_segmentation_keeps_connector_and_half_open_spans() -> None:
    result = _extract("查询 Atlas，同时比较风险；但不要发送。")

    assert tuple(item.text for item in result.clauses) == (
        "查询 Atlas",
        "比较风险",
        "不要发送",
    )
    assert tuple(item.connector_before for item in result.clauses) == (
        None,
        "同时",
        "但",
    )
    assert all(
        result.canonical.original_text[item.source_span.start : item.source_span.end]
        == item.source_span.text
        for item in result.clauses
    )


def test_actions_safety_aggregation_comparison_and_top_n_are_typed() -> None:
    result = _extract("按项目统计数量，列出优先级最高的前三项，只生成草稿，不要发送")
    by_kind = {}
    for token in result.tokens:
        by_kind.setdefault(token.kind, []).append(token.canonical_value)

    assert "count" in by_kind["aggregation"]
    assert "maximum" in by_kind["comparison"]
    assert "3" in by_kind["limit"]
    assert "draft_only" in by_kind["safety"]
    assert "no_external_send" in by_kind["safety"]


def test_tomorrow_before_uses_closed_open_utc_boundary() -> None:
    result = _extract("创建明天之前的评审任务")
    boundary = result.date_ranges[0]

    assert boundary.kind == "before_tomorrow"
    assert boundary.start_utc is None
    assert boundary.end_utc.isoformat() == "2026-07-30T16:00:00+00:00"


def test_today_tomorrow_and_this_week_use_workspace_timezone() -> None:
    today = _extract("汇总今天完成事项").date_ranges[0]
    tomorrow = _extract("明天创建任务").date_ranges[0]
    week = _extract("汇总本周事项").date_ranges[0]

    assert today.start_utc.isoformat() == "2026-07-28T16:00:00+00:00"
    assert today.end_utc.isoformat() == "2026-07-29T16:00:00+00:00"
    assert tomorrow.start_utc.isoformat() == "2026-07-29T16:00:00+00:00"
    assert tomorrow.end_utc.isoformat() == "2026-07-30T16:00:00+00:00"
    assert week.start_utc.isoformat() == "2026-07-26T16:00:00+00:00"
    assert week.end_utc.isoformat() == "2026-08-02T16:00:00+00:00"


@pytest.mark.parametrize(
    "query",
    (
        "列出 high 优先级事项",
        "显示 blocked_reason",
        "创建回滚方案评审任务",
        "查看 blocked 工作项",
    ),
)
def test_value_and_field_markers_do_not_become_risk_intent(query: str) -> None:
    result = _extract(query)

    assert not any(item.kind == "risk_intent" for item in result.tokens)


def test_explicit_risk_language_is_a_risk_intent() -> None:
    result = _extract("比较 Atlas 和 Beacon 的风险并解释原因")

    assert [
        item.canonical_value for item in result.tokens if item.kind == "risk_intent"
    ] == ["risk_analysis"]


@pytest.mark.parametrize(
    ("query", "error"),
    (
        (" leading", "lexical_query_boundary_invalid"),
        ("trailing ", "lexical_query_boundary_invalid"),
        ("bad\x00query", "lexical_query_boundary_invalid"),
        ("x" * 601, "lexical_query_length_invalid"),
    ),
)
def test_invalid_query_boundaries_fail_closed(query: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _extract(query)


def test_invalid_timezone_fails_closed() -> None:
    with pytest.raises(ValueError, match="lexical_timezone_invalid"):
        extract_lexical_query("查询项目", clock=CLOCK, timezone_name="Mars/Base")


def test_canonical_mapping_points_every_character_to_original_source() -> None:
    canonical = canonicalize_query("Ａ  Ｂ，Ｃ")

    assert canonical.normalized_text == "A B,C"
    assert len(canonical.normalized_to_source) == len(canonical.normalized_text)
    assert canonical.normalized_to_source == (0, 1, 3, 4, 5)
