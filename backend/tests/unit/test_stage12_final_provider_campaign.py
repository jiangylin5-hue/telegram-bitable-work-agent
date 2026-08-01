from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    specialist_payload_sha256,
)
from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV3,
    GroundedRenderSlotTextV1,
)
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderInvocationError,
)
from app.schemas.retrieval_v2 import canonical_retrieval_sha256
from scripts.stage12_final_provider_campaign import (
    REPRESENTATIVE_P2_CASE_IDS,
    _round_observation,
    execute_grounded_p2_campaign,
    execute_final_provider_campaign,
    main,
    validate_human_gold_signoff,
    write_grounded_p2_campaign,
    write_final_provider_campaign,
)
from scripts.stage12_isolated_af_runner import IsolatedAFExecutor
from scripts.stage12_quality_evaluation import build_stage12_truth_cases
from scripts.stage12_retrieval_v2_evaluation import (
    Stage12RetrievalEvaluationReportV1,
)


def _approved_cases():
    return tuple(
        case.model_copy(
            update={
                "gold_audit": case.gold_audit.model_copy(
                    update={"status": "human_approved"}
                )
            }
        )
        for case in build_stage12_truth_cases()
    )


def _pending_cases():
    return tuple(
        case.model_copy(
            update={
                "gold_audit": case.gold_audit.model_copy(
                    update={"status": "agent_audited_pending_human_signoff"}
                )
            }
        )
        for case in build_stage12_truth_cases()
    )


def _representative_cases():
    by_id = {item.case_id: item for item in _approved_cases()}
    return tuple(by_id[case_id] for case_id in REPRESENTATIVE_P2_CASE_IDS)


def _valid_grounded_plan(request) -> GroundedAnswerPlanV3:
    claims = {item.claim_handle: item for item in request.claims}
    actions = {item.action_handle: item for item in request.actions}
    outputs = []
    for slot in request.render_slots:
        if slot.statement_kind in {"fact", "analysis", "recommendation"}:
            text = (
                "；".join(
                    f"{claims[handle].subject_label} 的{claims[handle].predicate_label}为 {claims[handle].value_text}"
                    for handle in slot.claim_handles
                )
                + "。"
            )
        elif slot.statement_kind == "action_status":
            text = "；".join(
                actions[handle].safe_summary for handle in slot.action_handles
            )
        else:
            text = "当前存在无法完成或降级的部分，未提供未经验证的结论。"
        outputs.append(
            GroundedRenderSlotTextV1(slot_handle=slot.slot_handle, text=text)
        )
    return GroundedAnswerPlanV3(slot_outputs=tuple(outputs))


class _ValidComposerProvider:
    def __init__(self) -> None:
        self.observations: tuple[ProviderAttemptObservationV1, ...] = ()
        self.call_count = 0

    def __call__(self, request):
        self.call_count += 1
        values = {
            "version": "provider-attempt.v1",
            "role": "composer",
            "profile_id": "composer.zh.grounded.glm-5.2.v4",
            "provider": "openrouter-compatible",
            "model_id": "z-ai/glm-5.2",
            "attempt": 1,
            "status": "completed",
            "failure_code": None,
            "latency_ms": 3,
            "input_tokens": 20,
            "output_tokens": 8,
            "repair": False,
        }
        values["observation_hash"] = specialist_payload_sha256(values)
        self.observations = (ProviderAttemptObservationV1.model_validate(values),)
        return _valid_grounded_plan(request)


class _IntermittentInvalidComposerProvider:
    def __init__(self) -> None:
        self.observations: tuple[ProviderAttemptObservationV1, ...] = ()
        self.call_count = 0

    def __call__(self, request):
        self.call_count += 1
        failure_code = (
            "provider_schema_invalid"
            if self.call_count in {1, 97}
            else "provider_semantic_invalid" if self.call_count == 49 else None
        )
        values = {
            "version": "provider-attempt.v1",
            "role": "composer",
            "profile_id": "composer.zh.grounded.glm-5.2.v4",
            "provider": "openrouter-compatible",
            "model_id": "z-ai/glm-5.2",
            "attempt": 1,
            "status": "failed" if failure_code else "completed",
            "failure_code": failure_code,
            "latency_ms": 3,
            "input_tokens": 20,
            "output_tokens": 8,
            "repair": False,
        }
        values["observation_hash"] = specialist_payload_sha256(values)
        self.observations = (ProviderAttemptObservationV1.model_validate(values),)
        if failure_code is not None:
            raise GroundedAnswerProviderInvocationError(failure_code)
        return _valid_grounded_plan(request)


def _retrieval_report(round_number: int) -> Stage12RetrievalEvaluationReportV1:
    values = {
        "version": "stage12-retrieval-v2-evaluation.v1",
        "profile_name": "stage12.openrouter-bge-m3-v1",
        "model_revision": "baai/bge-m3-20251117",
        "corpus_hash": "a" * 64,
        "requested_rounds": 1,
        "completed_rounds": 1,
        "failed_rounds": 0,
        "case_count": 12,
        "recall_at_20": 1.0,
        "mrr_at_20": 1.0,
        "forbidden_candidate_count": 0,
        "truncated_case_count": 0,
        "p95_latency_ms": float(round_number),
        "provider_call_count": 2,
        "action_expansion_count": 0,
        "record_write_count": 0,
        "external_send_count": 0,
        "passed": True,
    }
    values["report_hash"] = canonical_retrieval_sha256(values)
    return Stage12RetrievalEvaluationReportV1.model_validate(values)


def test_final_campaign_refuses_pending_human_gold_before_any_provider_call() -> None:
    calls = []

    def forbidden_retrieval(_round_number: int):
        calls.append("retrieval")
        raise AssertionError("provider must not run")

    with pytest.raises(ValueError, match="final_campaign_human_gold_not_approved"):
        execute_final_provider_campaign(
            cases=_pending_cases(),
            executor=lambda _request: calls.append("composer"),
            observations={},
            run_retrieval_round=forbidden_retrieval,
        )

    assert calls == []


def test_final_campaign_validates_retrieval_identity_before_composer_calls() -> None:
    calls = []

    def invalid_retrieval(round_number: int):
        calls.append(f"retrieval-{round_number}")
        return _retrieval_report(round_number).model_copy(
            update={"profile_name": "wrong-profile"}
        )

    with pytest.raises(ValueError, match="final_campaign_retrieval_round_invalid"):
        execute_final_provider_campaign(
            cases=_approved_cases(),
            executor=lambda _request: calls.append("composer"),
            observations={},
            run_retrieval_round=invalid_retrieval,
        )

    assert calls == ["retrieval-1", "retrieval-2", "retrieval-3"]


def test_final_campaign_runs_exactly_three_grounded_rounds_with_zero_effects(
    tmp_path,
) -> None:
    cases = _approved_cases()
    provider = _ValidComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)
    retrieval_rounds = []

    def run_retrieval(round_number: int):
        retrieval_rounds.append(round_number)
        return _retrieval_report(round_number)

    bundle = execute_final_provider_campaign(
        cases=cases,
        executor=executor,
        observations=executor.observations,
        run_retrieval_round=run_retrieval,
        now=lambda: datetime(2026, 7, 31, tzinfo=UTC),
    )

    assert retrieval_rounds == [1, 2, 3]
    assert bundle.report.case_count == 48
    assert bundle.report.rounds == 3
    assert len(bundle.report.results) == 144
    assert bundle.summary.human_gold_approved_count == 48
    assert provider.call_count == 144, {
        item.failure_code for item in executor.observations.values()
    }
    assert all(item.attempt_count == 48 for item in bundle.provider_rounds), [
        item.model_dump(mode="json") for item in bundle.provider_rounds
    ]
    assert bundle.summary.release_gate_pass is True, {
        name: metric.model_dump(mode="json")
        for name, metric in bundle.summary.metrics.items()
        if not metric.gate_pass
    }
    assert all(item.required_count == 48 for item in bundle.provider_rounds)
    assert all(item.unavailable_count == 0 for item in bundle.provider_rounds)
    assert all(item.confirmed_action_count == 0 for item in bundle.provider_rounds)
    assert all(item.production_write_count == 0 for item in bundle.provider_rounds)
    assert all(item.telegram_send_count == 0 for item in bundle.provider_rounds)
    assert bundle.content_hash
    json_path, markdown_path = write_final_provider_campaign(
        bundle,
        output_dir=tmp_path,
    )
    combined = json_path.read_text(encoding="utf-8") + markdown_path.read_text(
        encoding="utf-8"
    )
    assert bundle.content_hash in combined
    assert "OPENROUTER_API_KEY" not in combined
    assert not tuple(tmp_path.glob("*.tmp"))


def test_final_campaign_keeps_144_traces_but_fails_provider_availability() -> None:
    cases = _approved_cases()
    provider = _IntermittentInvalidComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)

    bundle = execute_final_provider_campaign(
        cases=cases,
        executor=executor,
        observations=executor.observations,
        run_retrieval_round=_retrieval_report,
        now=lambda: datetime(2026, 7, 31, tzinfo=UTC),
    )

    assert provider.call_count == 144
    assert len(bundle.report.results) == 144
    assert [item.unavailable_count for item in bundle.provider_rounds] == [1, 1, 1]
    failed_answers = tuple(
        item for item in bundle.report.results if not item.score.final_answer.gate_pass
    )
    assert len(failed_answers) == 3
    assert all(
        item.score.final_answer.real_provider_origin is False
        and "real_provider_origin_failed" in item.score.final_answer.reason_codes
        for item in failed_answers
    )
    assert bundle.summary.metrics["provider_unavailable_rate"].gate_pass is False
    assert bundle.summary.release_gate_pass is False
    assert all(item.confirmed_action_count == 0 for item in bundle.provider_rounds)
    assert all(item.production_write_count == 0 for item in bundle.provider_rounds)
    assert all(item.telegram_send_count == 0 for item in bundle.provider_rounds)


def test_grounded_p2_runs_exact_12_cases_for_three_real_provider_rounds(
    tmp_path,
) -> None:
    provider = _ValidComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)

    campaign = execute_grounded_p2_campaign(
        cases=_representative_cases(),
        executor=executor,
        observations=executor.observations,
        now=lambda: datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert campaign.case_ids == REPRESENTATIVE_P2_CASE_IDS
    assert campaign.case_count == 12
    assert campaign.rounds == 3
    assert len(campaign.results) == 36
    assert provider.call_count == 36
    assert campaign.real_provider_count == 36
    assert campaign.final_answer_gate_pass_count == 36
    assert campaign.fallback_count == 0
    assert campaign.unauthorized_effect_count == 0
    assert campaign.production_write_count == 0
    assert campaign.telegram_send_count == 0
    assert campaign.gate_pass is True

    json_path, markdown_path = write_grounded_p2_campaign(
        campaign,
        output_dir=tmp_path / "p2",
    )
    encoded = json_path.read_text(encoding="utf-8") + markdown_path.read_text(
        encoding="utf-8"
    )
    assert campaign.content_hash in encoded
    for forbidden in (
        "rendered_answer",
        "expected_answer",
        "gold_truth",
        "OPENROUTER_API_KEY",
    ):
        assert forbidden not in encoded


def test_grounded_p2_retains_one_provider_failure_and_fails_gate() -> None:
    provider = _IntermittentInvalidComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)

    campaign = execute_grounded_p2_campaign(
        cases=_representative_cases(),
        executor=executor,
        observations=executor.observations,
        now=lambda: datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert provider.call_count == 36
    assert len(campaign.results) == 36
    assert campaign.real_provider_count == 35
    assert campaign.final_answer_gate_pass_count == 35
    assert campaign.fallback_count == 1
    assert campaign.gate_pass is False


def test_human_gold_validator_requires_exactly_48_unique_approved_cases() -> None:
    cases = _approved_cases()

    approval_hash = validate_human_gold_signoff(cases)

    assert len(approval_hash) == 64
    with pytest.raises(ValueError, match="final_campaign_human_gold_shape_invalid"):
        validate_human_gold_signoff(cases[:-1])


def test_provider_round_observation_rejects_missing_or_duplicate_case_traces() -> None:
    provider = _ValidComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)
    cases = _approved_cases()

    execute_final_provider_campaign(
        cases=cases,
        executor=executor,
        observations=executor.observations,
        run_retrieval_round=_retrieval_report,
        now=lambda: datetime(2026, 7, 31, tzinfo=UTC),
    )
    first_round = tuple(
        item for item in executor.observations.values() if item.round_id == "round-01"
    )

    with pytest.raises(
        RuntimeError, match="final_campaign_provider_observation_count_invalid"
    ):
        _round_observation(
            round_id="round-01",
            required_count=48,
            observations=first_round[:-1],
        )
    with pytest.raises(
        RuntimeError, match="final_campaign_provider_observation_identity_invalid"
    ):
        _round_observation(
            round_id="round-01",
            required_count=48,
            observations=first_round[:-1] + (first_round[0],),
        )

    failed = first_round[0].model_copy(
        update={
            "status": "failed",
            "failure_code": "specialist_render_receipt_value_duplicate",
        }
    )
    observed = _round_observation(
        round_id="round-01",
        required_count=48,
        observations=(failed,) + first_round[1:],
    )
    assert observed.failure_counts["specialist_render_receipt_value_duplicate"] == 1


def test_final_cli_checks_environment_after_human_gold_without_network(
    tmp_path, monkeypatch
) -> None:
    calls = []
    monkeypatch.setattr(
        "scripts.stage12_final_provider_campaign._default_retrieval_round",
        lambda _round_number: calls.append("network"),
    )

    with pytest.raises(RuntimeError, match="final_campaign_env_file_missing"):
        main(
            [
                "--env-file",
                str(tmp_path / "missing.env"),
                "--output-dir",
                str(tmp_path / "output"),
            ]
        )

    assert calls == []
