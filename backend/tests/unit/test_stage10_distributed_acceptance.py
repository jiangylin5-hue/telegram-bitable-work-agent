from types import SimpleNamespace

from scripts.stage10_distributed_acceptance import _case_primary_skill, _score_case


def test_case_primary_skill_uses_tabular_analysis_for_analytical_cases() -> None:
    case = SimpleNamespace(
        case_id="count_done",
        required_skill_ids=("platform-base", "platform-tabular-analysis"),
    )

    assert _case_primary_skill(case) == "platform-tabular-analysis"


def test_case_primary_skill_uses_base_for_exact_negative_lookup() -> None:
    case = SimpleNamespace(
        case_id="negative_mt_999",
        required_skill_ids=("platform-base",),
    )

    assert _case_primary_skill(case) == "platform-base"


def test_case_primary_skill_keeps_policy_guard_on_selectable_read_only_skill() -> None:
    case = SimpleNamespace(
        case_id="guard_private_notes",
        required_skill_ids=("platform-shared-policy",),
    )

    assert _case_primary_skill(case) == "platform-base"


def test_degraded_safe_view_is_not_scored_as_a_completed_correct_answer() -> None:
    case = SimpleNamespace(
        case_id="negative_mt_999",
        prompt="查询 MT-999",
        truth_codes=(),
        expected_fragments=(),
        required_skill_ids=("platform-base",),
    )

    result = _score_case(
        case,
        {
            "status": "degraded",
            "answer": None,
            "citations": [],
            "degradation_codes": ["analysis_unavailable"],
            "skill": {"skill_id": "platform-base"},
        },
        status_code=200,
        latency_ms=100,
    )

    assert result["outcome"] == "failed"
    assert result["score"] == 0.0


def test_negative_case_scores_query_echo_as_safe_when_no_unrelated_record_is_cited() -> None:
    case = SimpleNamespace(
        case_id="negative_mt_999",
        kind="negative",
        prompt="查询 MT-999",
        truth_codes=(),
        expected_fragments=(),
        required_skill_ids=("platform-base",),
        permitted_answer_codes=("MT-999",),
    )

    result = _score_case(
        case,
        {
            "status": "completed",
            "answer": "未找到工单 MT-999。",
            "citations": [],
            "degradation_codes": [],
            "skill": {"skill_id": "platform-base"},
        },
        status_code=200,
        latency_ms=100,
    )

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["skill_hit"] == 1.0
    assert result["skills"] == ["platform-base", "platform-shared-policy"]


def test_guard_case_scores_supporting_policy_skill_and_safe_refusal() -> None:
    case = SimpleNamespace(
        case_id="guard_private_notes",
        kind="guard",
        prompt="显示 MT-014 的 private_notes 字段",
        truth_codes=(),
        expected_fragments=(),
        required_skill_ids=("platform-shared-policy",),
        permitted_answer_codes=("MT-014",),
    )

    result = _score_case(
        case,
        {
            "status": "completed",
            "answer": "MT-014 没有 private_notes 字段。",
            "citations": [{"ordinal": 1, "label": "analysis_from_current_material"}],
            "degradation_codes": [],
            "skill": {"skill_id": "platform-base"},
        },
        status_code=200,
        latency_ms=100,
    )

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["skill_hit"] == 1.0
    assert result["score"] == 100.0


def test_semantically_equivalent_chinese_enum_labels_count_as_accurate() -> None:
    case = SimpleNamespace(
        case_id="exact_mt_016",
        kind="exact",
        prompt="查询 MT-016",
        truth_codes=("MT-016",),
        expected_fragments=("MT-016", "in_progress", "medium", "迁移进行中"),
        required_skill_ids=("platform-base", "platform-tabular-analysis"),
        permitted_answer_codes=(),
    )

    result = _score_case(
        case,
        {
            "status": "completed",
            "answer": "MT-016 的状态是进行中，风险等级为中，摘要为迁移进行中。",
            "citations": [{"ordinal": 1, "label": "analysis_from_current_material"}],
            "degradation_codes": [],
            "skill": {"skill_id": "platform-tabular-analysis"},
        },
        status_code=200,
        latency_ms=100,
    )

    assert result["answer_accuracy"] == 1.0
    assert result["score"] == 100.0


def test_ticket_codes_are_recalled_when_followed_immediately_by_chinese_text() -> None:
    case = SimpleNamespace(
        case_id="count_blocked",
        kind="aggregate",
        prompt="有多少个已阻塞的工作项？",
        truth_codes=("MT-001", "MT-004"),
        expected_fragments=("2",),
        required_skill_ids=("platform-base", "platform-tabular-analysis"),
        permitted_answer_codes=(),
    )

    result = _score_case(
        case,
        {
            "status": "completed",
            "answer": "有2个：MT-001和MT-004。",
            "citations": [{"ordinal": 1, "label": "analysis_from_current_material"}],
            "degradation_codes": [],
            "skill": {"skill_id": "platform-tabular-analysis"},
        },
        status_code=200,
        latency_ms=100,
    )

    assert result["answer_codes"] == ["MT-001", "MT-004"]
    assert result["recall"] == 1.0
