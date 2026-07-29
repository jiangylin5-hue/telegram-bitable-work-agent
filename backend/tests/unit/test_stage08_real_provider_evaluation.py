from __future__ import annotations

import json
import os
import threading
import time

import httpx
import pytest
from pydantic import ValidationError

from scripts import stage08_real_provider_evaluation as evaluation
from scripts.stage08_real_provider_evaluation import (
    RedactedCaseResult,
    Stage08EvaluationCase,
    default_evaluation_cases,
    run_batch,
    run_case_isolated,
    run_synthetic_case,
)


EXPECTED_CASE_IDS = (
    "visible_fact",
    "hidden_field",
    "revoked_scope",
    "general_advice",
    "group_freshness",
    "rag_lifecycle",
    "provider_unavailable",
    "policy_deny",
    "draft_pressure",
    "budget_cancel",
    "safe_replay",
    "multilingual",
)


def test_manifest_is_exactly_the_twelve_approved_static_cases() -> None:
    cases = default_evaluation_cases()

    assert tuple(case.case_id for case in cases) == EXPECTED_CASE_IDS
    assert len(cases) == len(set(EXPECTED_CASE_IDS)) == 12
    assert set(Stage08EvaluationCase.model_fields) == {"case_id"}


def test_redacted_dto_has_only_the_parent_boundary_whitelist() -> None:
    assert set(RedactedCaseResult.model_fields) == {
        "case_id",
        "terminal_status",
        "failure_labels",
        "evaluation_passed",
        "no_hidden_leak",
        "citation_current",
        "no_direct_write",
        "no_external_side_effect",
        "terminal_safe",
        "fixture_fresh",
        "citation_count",
        "draft_count",
        "latency_bucket",
        "provider_invoked",
        "provider_completed",
        "usage_metadata_present",
        "analysis_action",
    }

    serialized = _result("visible_fact").model_dump_json().casefold()
    for forbidden in (
        "prompt",
        "answer",
        "query",
        "record_id",
        "chat_id",
        "source_id",
        "token",
        "request_id",
        "exception",
    ):
        assert forbidden not in serialized


def test_redacted_dto_rejects_non_static_values_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Stage08EvaluationCase(case_id="private-prompt")
    with pytest.raises(ValidationError):
        RedactedCaseResult.model_validate(
            {
                **_result("visible_fact").model_dump(),
                "failure_labels": ("private_exception_text",),
            }
        )
    with pytest.raises(ValidationError):
        RedactedCaseResult.model_validate(
            {**_result("visible_fact").model_dump(), "raw_answer": "secret"}
        )
    with pytest.raises(ValidationError):
        RedactedCaseResult.model_validate(
            {**_result("visible_fact").model_dump(), "analysis_action": "write"}
        )


def test_redacted_dto_rejects_valid_enum_with_wrong_case_action_pairing() -> None:
    with pytest.raises(ValidationError):
        RedactedCaseResult.model_validate(
            {
                **_result(
                    "general_advice", analysis_action="general_advice"
                ).model_dump(),
                "analysis_action": "read_only",
            }
        )

    accepted = _result("general_advice", analysis_action="deny")
    assert accepted.evaluation_passed is True
    assert accepted.analysis_action == "deny"


def test_parent_revalidates_exact_child_dto_and_case_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forged = RedactedCaseResult.model_construct(
        **{
            **_result("visible_fact").model_dump(),
            "case_id": "private_prompt",
            "failure_labels": ("private_exception_text",),
        }
    )
    subclass = _ResultSubclass.model_construct(
        **_result("visible_fact").model_dump()
    )
    with_extra = RedactedCaseResult.model_construct(
        **_result("visible_fact").model_dump()
    )
    with_extra.__dict__["raw_answer"] = "secret"

    results = []
    for payload in (forged, subclass, with_extra, {"raw_answer": "secret"}):
        monkeypatch.setattr(
            evaluation.multiprocessing,
            "get_context",
            lambda _, payload=payload: _FakeContext(_FinishedProcess(), payload),
        )
        results.append(
            run_case_isolated(
                _case("visible_fact"),
                timeout_seconds=0.01,
                provider_mode="deterministic_fake",
            )
        )

    for result in results:
        assert result.evaluation_passed is False
        assert result.failure_labels == ("child_result_invalid",)
        assert "secret" not in result.model_dump_json().casefold()


def test_parent_converts_wrong_case_action_pairing_to_fixed_failed_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forged = {
        **_result(
            "general_advice", analysis_action="general_advice"
        ).model_dump(),
        "analysis_action": "read_only",
    }
    monkeypatch.setattr(
        evaluation.multiprocessing,
        "get_context",
        lambda _: _FakeContext(_FinishedProcess(), forged),
    )

    result = run_case_isolated(
        _case("general_advice"),
        timeout_seconds=0.01,
        provider_mode="deterministic_fake",
    )
    report = evaluation._batch_result((result,))

    assert result.evaluation_passed is False
    assert result.failure_labels == ("provider_invocation_invalid",)
    assert result.analysis_action == "none"
    assert report.passed_count == 0
    assert report.failed_count == 1
    assert report.all_cases_passed is False


def test_hard_timeout_cleans_only_that_child_and_returns_static_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _TimeoutProcess()
    context = _FakeContext(process)
    monkeypatch.setattr(
        evaluation.multiprocessing,
        "get_context",
        lambda _: context,
    )

    result = run_case_isolated(
        _case("budget_cancel"),
        timeout_seconds=0.01,
        provider_mode="deterministic_fake",
    )

    assert result.terminal_status == "timed_out"
    assert result.failure_labels == ("case_timeout",)
    assert process.terminate_called is True
    assert process.join_timeouts
    assert all(timeout is not None for timeout in process.join_timeouts)
    assert context.result_queue.cancel_join_called is True
    assert context.result_queue.join_called is False


def test_batch_continues_after_timeout_and_caps_parallelism_at_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = 0
    maximum_active = 0
    seen: list[str] = []
    lock = threading.Lock()

    def fake_run(case, timeout_seconds, *, provider_mode):
        nonlocal active, maximum_active
        del timeout_seconds, provider_mode
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.015)
        with lock:
            active -= 1
            seen.append(case.case_id)
        if case.case_id == "budget_cancel":
            return _result(
                case.case_id,
                terminal_status="timed_out",
                passed=False,
                labels=("case_timeout",),
                latency_bucket="timeout",
            )
        return _result(case.case_id)

    monkeypatch.setattr(evaluation, "run_case_isolated", fake_run)
    cases = (
        _case("visible_fact"),
        _case("budget_cancel"),
        _case("multilingual"),
    )

    report = run_batch(
        cases,
        max_parallelism=2,
        timeout_seconds=0.01,
        provider_mode="deterministic_fake",
    )

    assert maximum_active == 2
    assert set(seen) == {case.case_id for case in cases}
    assert report.case_count == 3
    assert report.passed_count == 2
    assert report.timed_out_count == 1
    assert [item.case_id for item in report.cases] == [case.case_id for case in cases]


@pytest.mark.parametrize("parallelism", [0, 3, True])
def test_parallelism_above_two_or_non_integer_is_rejected(parallelism: object) -> None:
    with pytest.raises(ValueError):
        run_batch(
            (_case("visible_fact"),),
            max_parallelism=parallelism,
            provider_mode="deterministic_fake",
        )


def test_safety_environment_is_forced_and_cannot_be_weakened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe = {
        "TELEGRAM_SEND_MODE": "live",
        "PROVIDER_MODE": "write",
        "PROVIDER_WRITE_MODE": "enabled",
        "NOTIFICATION_MODE": "enabled",
        "AGENT_SAVE_FULL_PROMPT": "true",
        "AGENT_SAVE_FULL_RESPONSE": "true",
    }
    for key, value in unsafe.items():
        monkeypatch.setenv(key, value)

    evaluation._force_safety_environment()

    assert os.environ["TELEGRAM_SEND_MODE"] == "dry_run"
    assert os.environ["PROVIDER_MODE"] == "disabled"
    assert os.environ["PROVIDER_WRITE_MODE"] == "disabled"
    assert os.environ["NOTIFICATION_MODE"] == "disabled"
    assert os.environ["AGENT_SAVE_FULL_PROMPT"] == "false"
    assert os.environ["AGENT_SAVE_FULL_RESPONSE"] == "false"


def test_absent_explicit_env_file_is_clean_non_network_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STAGE08_F_ENV_FILE", raising=False)

    class NetworkForbiddenProvider:
        def __init__(self, *args, **kwargs):
            del args, kwargs
            raise AssertionError("provider must not be constructed without explicit env")

    monkeypatch.setattr(
        evaluation,
        "OpenRouterStage08AnalysisProvider",
        NetworkForbiddenProvider,
    )

    result = run_synthetic_case(_case("visible_fact"), provider_mode="real")

    assert result.evaluation_passed is False
    assert result.terminal_status == "degraded"
    assert result.failure_labels == ("configuration_missing",)
    assert result.provider_invoked is False
    assert result.provider_completed is False
    assert result.no_external_side_effect is True


def test_real_provider_selection_uses_the_same_e5_remaining_deadline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_file = tmp_path / "stage08-f.local"
    env_file.write_text(
        "OPENROUTER_API_KEY=not-a-real-key\n"
        "OPENROUTER_BASE_URL=https://provider.invalid/api/v1\n"
        "OPENROUTER_MODEL=synthetic/model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("STAGE08_F_ENV_FILE", str(env_file))
    captured: dict[str, object] = {}

    class CapturingProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        evaluation,
        "OpenRouterStage08AnalysisProvider",
        CapturingProvider,
    )
    runtime_control = evaluation._create_stage08_runtime_control()

    selection = evaluation._select_provider(
        "visible_fact",
        "real",
        runtime_control=runtime_control,
    )

    probe = captured["remaining_deadline_seconds"]
    assert callable(probe)
    remaining = probe()
    assert 0 < remaining <= 30
    assert selection.configured is True


def test_deterministic_fake_provider_uses_the_stage08_dependency_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = evaluation.run_stage08_collaboration
    injected: list[object] = []

    def capture(*args, **kwargs):
        injected.append(args[3].analysis_provider)
        return original(*args, **kwargs)

    monkeypatch.setattr(evaluation, "run_stage08_collaboration", capture)

    result = run_synthetic_case(
        _case("visible_fact"), provider_mode="deterministic_fake"
    )

    assert type(injected[0]).__name__ == "_DeterministicAnalysisProvider"
    assert result.evaluation_passed is True
    assert result.provider_invoked is True
    assert result.provider_completed is True
    assert result.fixture_fresh is True
    assert result.no_hidden_leak is True
    assert result.citation_current is True


def test_real_spawned_fake_case_returns_only_redacted_dto() -> None:
    result = run_case_isolated(
        _case("general_advice"),
        timeout_seconds=10.0,
        provider_mode="deterministic_fake",
    )

    assert result.evaluation_passed is True
    assert result.terminal_status == "completed"
    assert result.citation_count == 0
    assert result.analysis_action == "general_advice"
    assert "synthetic" not in result.model_dump_json().casefold()


@pytest.mark.parametrize(
    (
        "action",
        "citation_ordinals",
        "expected_status",
        "expected_passed",
        "expected_analysis_action",
    ),
    [
        ("general_advice", (), "completed", True, "general_advice"),
        ("deny", (), "completed", True, "deny"),
        ("read_only", (), "degraded", False, "none"),
        ("general_advice", (1,), "degraded", False, "none"),
        ("deny", (1,), "degraded", False, "none"),
    ],
)
def test_general_advice_f1_mock_enforces_action_and_citation_contract(
    action: str,
    citation_ordinals: tuple[int, ...],
    expected_status: str,
    expected_passed: bool,
    expected_analysis_action: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "answer": "请使用简短的下一步行动清单。",
                "citation_ordinals": citation_ordinals,
                "action": action,
            }
        )
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": content}}]},
        )

    runtime_control = evaluation._runtime_control_for_case("general_advice")
    fixture = evaluation._build_synthetic_fixture("general_advice")
    telemetry = evaluation._ProviderTelemetry()
    prompt_guard = evaluation._OutboundPromptGuard()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    selection = evaluation._ProviderSelection(
        provider=evaluation.OpenRouterStage08AnalysisProvider(
            api_key="offline-test-key",
            base_url="https://offline.invalid/api/v1",
            model_name="offline/test",
            remaining_deadline_seconds=lambda: evaluation._remaining_deadline_seconds(
                runtime_control
            ),
            http_client=client,
                outbound_prompt_guard=prompt_guard,
                event_observer=telemetry.observe,
                action_observer=telemetry.observe_action,
            ),
        configured=True,
        strategy="real_analysis",
        telemetry=telemetry,
        prompt_guard=prompt_guard,
    )
    try:
        result = evaluation._execute_synthetic_case(
            "general_advice",
            fixture,
            selection,
            runtime_control=runtime_control,
            started_at=time.monotonic(),
        )
    finally:
        client.close()

    assert result.terminal_status == expected_status
    assert result.evaluation_passed is expected_passed
    assert result.citation_count == 0
    assert result.provider_invoked is True
    assert result.provider_completed is True
    assert result.analysis_action == expected_analysis_action
    assert result.no_hidden_leak is True
    assert result.no_external_side_effect is True
    assert "answer" not in result.model_dump_json().casefold()


def test_general_advice_terminal_contract_accepts_controlled_deny() -> None:
    assert evaluation._TERMINAL_EXPECTATIONS["general_advice"] == {
        "completed",
        "denied",
    }


def test_group_freshness_accepts_safe_deny_without_current_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "answer": "当前没有可用的已授权群组上下文。",
                "citation_ordinals": [],
                "action": "deny",
                "draft": None,
            }
        )
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": content}}]},
        )

    runtime_control = evaluation._runtime_control_for_case("group_freshness")
    fixture = evaluation._build_synthetic_fixture("group_freshness")
    telemetry = evaluation._ProviderTelemetry()
    prompt_guard = evaluation._OutboundPromptGuard()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    selection = evaluation._ProviderSelection(
        provider=evaluation.OpenRouterStage08AnalysisProvider(
            api_key="offline-test-key",
            base_url="https://offline.invalid/api/v1",
            model_name="offline/test",
            remaining_deadline_seconds=lambda: evaluation._remaining_deadline_seconds(
                runtime_control
            ),
            http_client=client,
            outbound_prompt_guard=prompt_guard,
            event_observer=telemetry.observe,
            action_observer=telemetry.observe_action,
        ),
        configured=True,
        strategy="real_analysis",
        telemetry=telemetry,
        prompt_guard=prompt_guard,
    )
    try:
        result = evaluation._execute_synthetic_case(
            "group_freshness",
            fixture,
            selection,
            runtime_control=runtime_control,
            started_at=time.monotonic(),
        )
    finally:
        client.close()

    assert result.evaluation_passed is True
    assert result.terminal_status == "completed"
    assert result.analysis_action == "deny"
    assert result.citation_count == 0
    assert result.citation_current is True


def test_draft_pressure_records_a_safe_draft_update_action() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "answer": "草稿建议已生成，正在等待确认。",
                "citation_ordinals": [1],
                "action": "draft_update",
                "draft": {"field_key": "title", "value": "Controlled proposal"},
            }
        )
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": content}}]},
        )

    runtime_control = evaluation._runtime_control_for_case("draft_pressure")
    fixture = evaluation._build_synthetic_fixture("draft_pressure")
    telemetry = evaluation._ProviderTelemetry()
    prompt_guard = evaluation._OutboundPromptGuard()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    selection = evaluation._ProviderSelection(
        provider=evaluation.OpenRouterStage08AnalysisProvider(
            api_key="offline-test-key",
            base_url="https://offline.invalid/api/v1",
            model_name="offline/test",
            remaining_deadline_seconds=lambda: evaluation._remaining_deadline_seconds(
                runtime_control
            ),
            http_client=client,
            outbound_prompt_guard=prompt_guard,
            event_observer=telemetry.observe,
            action_observer=telemetry.observe_action,
        ),
        configured=True,
        strategy="real_analysis",
        telemetry=telemetry,
        prompt_guard=prompt_guard,
    )
    try:
        result = evaluation._execute_synthetic_case(
            "draft_pressure",
            fixture,
            selection,
            runtime_control=runtime_control,
            started_at=time.monotonic(),
        )
    finally:
        client.close()

    assert result.evaluation_passed is True
    assert result.terminal_status == "draft_pending"
    assert result.analysis_action == "draft_update"
    assert result.draft_count == 1


def test_complete_twelve_case_offline_matrix_runs_through_isolated_children() -> None:
    report = run_batch(
        default_evaluation_cases(),
        max_parallelism=1,
        timeout_seconds=30.0,
        provider_mode="deterministic_fake",
    )

    assert report.case_count == 12
    assert report.passed_count == 12
    assert report.failed_count == 0
    assert report.timed_out_count == 0
    assert report.all_cases_passed is True
    assert report.all_gates_passed is True
    assert report.provider_invoked_case_count == 9
    assert report.provider_completed_case_count == 9
    assert report.usage_metadata_case_count == 0


def test_fixed_provider_strategies_are_f1_compatible() -> None:
    assert evaluation._PROVIDER_STRATEGIES == {
        "visible_fact": "real_analysis",
        "hidden_field": "real_analysis",
        "revoked_scope": "real_analysis",
        "general_advice": "real_analysis",
        "group_freshness": "real_analysis",
        "rag_lifecycle": "real_analysis",
        "provider_unavailable": "fault_http_error",
        "policy_deny": "real_analysis",
        "draft_pressure": "real_analysis",
        "budget_cancel": "real_analysis",
        "safe_replay": "coordinator_only",
        "multilingual": "real_analysis",
    }


@pytest.mark.parametrize(
    ("case_id", "analysis_action"),
    [
        ("visible_fact", "read_only"),
        ("hidden_field", "read_only"),
        ("revoked_scope", "none"),
        ("general_advice", "general_advice"),
        ("group_freshness", "read_only"),
        ("rag_lifecycle", "read_only"),
        ("provider_unavailable", "none"),
        ("policy_deny", "deny"),
        ("draft_pressure", "deny"),
        ("budget_cancel", "none"),
        ("safe_replay", "none"),
        ("multilingual", "read_only"),
    ],
)
def test_all_fixed_case_strategies_emit_allowed_passed_action(
    case_id: str,
    analysis_action: str,
) -> None:
    result = run_synthetic_case(_case(case_id), provider_mode="deterministic_fake")

    assert result.evaluation_passed is True
    assert result.analysis_action == analysis_action
    assert evaluation._passed_analysis_action_is_allowed(case_id, analysis_action)


@pytest.mark.parametrize(
    ("case_id", "terminal_status", "provider_invoked", "analysis_action"),
    [
        ("provider_unavailable", "degraded", True, "none"),
        ("policy_deny", "denied", True, "deny"),
        ("safe_replay", "draft_pending", False, "none"),
        ("revoked_scope", "failed", False, "none"),
        ("budget_cancel", "cancelled", False, "none"),
    ],
)
def test_case_strategy_reports_actual_provider_invocation(
    case_id: str,
    terminal_status: str,
    provider_invoked: bool,
    analysis_action: str,
) -> None:
    result = run_synthetic_case(_case(case_id), provider_mode="deterministic_fake")

    assert result.evaluation_passed is True
    assert result.terminal_status == terminal_status
    assert result.provider_invoked is provider_invoked
    assert result.provider_completed is provider_invoked
    assert result.analysis_action == analysis_action


@pytest.mark.parametrize("marker", evaluation._HIDDEN_MARKERS)
def test_real_fixture_marker_mutation_is_blocked_by_fake_and_f1_adapter(
    marker: str,
) -> None:
    fake_runtime = evaluation._runtime_control_for_case("visible_fact")
    fake_fixture = _fixture_with_visible_marker(marker)
    fake_selection = evaluation._select_provider(
        "visible_fact",
        "deterministic_fake",
        runtime_control=fake_runtime,
    )

    fake_result = evaluation._execute_synthetic_case(
        "visible_fact",
        fake_fixture,
        fake_selection,
        runtime_control=fake_runtime,
        started_at=time.monotonic(),
    )

    transport_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal transport_called
        transport_called = True
        return httpx.Response(500, request=request)

    f1_runtime = evaluation._runtime_control_for_case("visible_fact")
    f1_fixture = _fixture_with_visible_marker(marker)
    f1_telemetry = evaluation._ProviderTelemetry()
    f1_guard = evaluation._OutboundPromptGuard()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    f1_selection = evaluation._ProviderSelection(
        provider=evaluation.OpenRouterStage08AnalysisProvider(
            api_key="offline-test-key",
            base_url="https://offline.invalid/api/v1",
            model_name="offline/test",
            remaining_deadline_seconds=lambda: evaluation._remaining_deadline_seconds(
                f1_runtime
            ),
            http_client=client,
            outbound_prompt_guard=f1_guard,
            event_observer=f1_telemetry.observe,
        ),
        configured=True,
        strategy="real_analysis",
        telemetry=f1_telemetry,
        prompt_guard=f1_guard,
    )
    try:
        f1_result = evaluation._execute_synthetic_case(
            "visible_fact",
            f1_fixture,
            f1_selection,
            runtime_control=f1_runtime,
            started_at=time.monotonic(),
        )
    finally:
        client.close()

    for result in (fake_result, f1_result):
        serialized = result.model_dump_json()
        assert result.evaluation_passed is False
        assert result.failure_labels[0] == "outbound_prompt_unsafe"
        assert result.provider_invoked is True
        assert result.provider_completed is True
        assert marker not in serialized
        assert "prompt" not in type(result).model_fields
        assert "answer" not in type(result).model_fields
    assert transport_called is False


def _fixture_with_visible_marker(marker: str):
    fixture = evaluation._build_synthetic_fixture("visible_fact")
    record = fixture.uow.get_record(fixture.project_id)
    assert record is not None
    record.values["title"] = marker
    fixture.record_values_before["title"] = marker
    return fixture


def _case(case_id: str) -> Stage08EvaluationCase:
    return Stage08EvaluationCase(case_id=case_id)


def _result(
    case_id: str,
    *,
    terminal_status: str = "completed",
    passed: bool = True,
    labels: tuple[str, ...] = (),
    latency_bucket: str = "under_250ms",
    analysis_action: str = "read_only",
) -> RedactedCaseResult:
    return RedactedCaseResult(
        case_id=case_id,
        terminal_status=terminal_status,
        failure_labels=labels,
        evaluation_passed=passed,
        no_hidden_leak=True,
        citation_current=True,
        no_direct_write=True,
        no_external_side_effect=True,
        terminal_safe=True,
        fixture_fresh=True,
        citation_count=1,
        draft_count=0,
        latency_bucket=latency_bucket,
        provider_invoked=True,
        provider_completed=True,
        usage_metadata_present=False,
        analysis_action=analysis_action,
    )


class _ResultSubclass(RedactedCaseResult):
    pass


class _FakeQueue:
    def __init__(self, payload: object | None = None) -> None:
        self.payload = payload
        self.cancel_join_called = False
        self.join_called = False

    def get(self, timeout: float | None = None) -> object:
        del timeout
        if self.payload is None:
            raise evaluation.queue.Empty
        return self.payload

    def put(self, payload: object) -> None:
        self.payload = payload

    def close(self) -> None:
        pass

    def cancel_join_thread(self) -> None:
        self.cancel_join_called = True

    def join_thread(self) -> None:
        self.join_called = True


class _FakeContext:
    def __init__(self, process: object, payload: object | None = None) -> None:
        self.process = process
        self.result_queue = _FakeQueue(payload)

    def Queue(self) -> _FakeQueue:
        return self.result_queue

    def Process(self, **kwargs):
        del kwargs
        return self.process


class _FinishedProcess:
    exitcode = 0

    def start(self) -> None:
        pass

    def join(self, timeout: float | None = None) -> None:
        del timeout

    def is_alive(self) -> bool:
        return False

    def close(self) -> None:
        pass


class _TimeoutProcess:
    exitcode = None

    def __init__(self) -> None:
        self.terminate_called = False
        self.join_timeouts: list[float | None] = []

    def start(self) -> None:
        pass

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)

    def is_alive(self) -> bool:
        return self.terminate_called is False

    def terminate(self) -> None:
        self.terminate_called = True
        self.exitcode = -15

    def close(self) -> None:
        pass
