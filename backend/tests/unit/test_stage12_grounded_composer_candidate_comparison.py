from __future__ import annotations

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    specialist_payload_sha256,
)
from scripts.stage12_grounded_composer_candidate_comparison import (
    CANDIDATE_MODEL_IDS,
    REPRESENTATIVE_CASE_IDS,
    build_candidate_profile,
    compare_candidate_runs,
    run_candidate_model,
    write_candidate_comparison,
)
from scripts.stage12_quality_evaluation import build_stage12_truth_cases
from tests.unit.test_stage12_final_provider_campaign import _valid_grounded_plan


def _cases():
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    return tuple(
        by_id[case_id].model_copy(
            update={
                "gold_audit": by_id[case_id].gold_audit.model_copy(
                    update={"status": "human_approved"}
                )
            }
        )
        for case_id in REPRESENTATIVE_CASE_IDS
    )


class _Provider:
    def __init__(self, *, model_id: str, latency_ms: int) -> None:
        self.model_id = model_id
        self.latency_ms = latency_ms
        self.observations: tuple[ProviderAttemptObservationV1, ...] = ()

    def __call__(self, request):
        values = {
            "version": "provider-attempt.v1",
            "role": "composer",
            "profile_id": f"candidate.{self.model_id.replace('/', '.')}",
            "provider": "openrouter-compatible",
            "model_id": self.model_id,
            "attempt": 1,
            "status": "completed",
            "failure_code": None,
            "latency_ms": self.latency_ms,
            "input_tokens": 100,
            "output_tokens": 20,
            "repair": False,
        }
        values["observation_hash"] = specialist_payload_sha256(values)
        self.observations = (ProviderAttemptObservationV1.model_validate(values),)
        return _valid_grounded_plan(request)


def test_candidate_quality_profile_retains_one_bounded_repair() -> None:
    profile = build_candidate_profile(CANDIDATE_MODEL_IDS[0])

    assert profile.max_attempts == 2
    assert profile.model_id == CANDIDATE_MODEL_IDS[0]


def test_candidate_run_uses_exact_representative_cases_and_real_answers() -> None:
    model_id = CANDIDATE_MODEL_IDS[0]

    result = run_candidate_model(
        model_id=model_id,
        cases=_cases(),
        provider=_Provider(model_id=model_id, latency_ms=5),
    )

    assert tuple(item.case_id for item in result.cases) == REPRESENTATIVE_CASE_IDS
    assert result.case_count == 12
    assert result.real_provider_count == 12
    assert result.final_answer_gate_pass_count == 12
    assert result.fallback_count == 0
    assert result.failure_counts == {}
    assert result.unauthorized_effect_count == 0
    assert result.production_write_count == 0
    assert result.telegram_send_count == 0


def test_equal_quality_candidates_use_provider_latency_as_tie_breaker() -> None:
    seed_id, glm_id = CANDIDATE_MODEL_IDS
    cases = _cases()
    seed = run_candidate_model(
        model_id=seed_id,
        cases=cases,
        provider=_Provider(model_id=seed_id, latency_ms=5),
    )
    glm = run_candidate_model(
        model_id=glm_id,
        cases=cases,
        provider=_Provider(model_id=glm_id, latency_ms=8),
    )

    comparison = compare_candidate_runs((seed, glm))

    assert comparison.selection_status == "winner"
    assert comparison.winner_model_id == seed_id
    assert comparison.selection_basis == "quality_then_reliability_then_latency"


def test_candidate_evidence_contains_no_query_answer_or_gold_payload(tmp_path) -> None:
    runs = tuple(
        run_candidate_model(
            model_id=model_id,
            cases=_cases(),
            provider=_Provider(model_id=model_id, latency_ms=index + 5),
        )
        for index, model_id in enumerate(CANDIDATE_MODEL_IDS)
    )
    comparison = compare_candidate_runs(runs)

    json_path, markdown_path = write_candidate_comparison(
        comparison,
        output_dir=tmp_path / "comparison",
    )

    encoded = json_path.read_text(encoding="utf-8") + markdown_path.read_text(
        encoding="utf-8"
    )
    assert comparison.content_hash in encoded
    for forbidden in (
        "rendered_answer",
        "expected_answer",
        "gold_truth",
        "OPENROUTER_API_KEY",
        "列出 Atlas",
    ):
        assert forbidden not in encoded
