from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from scripts.stage12_deployed_provider_campaign import (
    DeployedCampaignConfig,
    DeployedCampaignSideEffectSnapshot,
    DeployedRunObservation,
    REPRESENTATIVE_P2_CASE_IDS,
    _default_client_factory,
    _validate_campaign,
    evaluate_public_answer_quality,
    run_deployed_provider_campaign,
)
from scripts.stage12_quality_evaluation import build_stage12_truth_cases


class _Response:
    def __init__(self, status_code: int, *, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")


class _PublicClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.run_ids: list[UUID] = []
        self.streams: dict[UUID, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def get(self, path: str, **kwargs):
        self.calls.append(("GET", path, kwargs))
        if path == "/health":
            return _Response(200, payload={"status": "ok"})
        run_id = UUID(path.split("/")[-2])
        if run_id in self.streams:
            return _Response(200, text=self.streams[run_id])
        sequence = 3
        safe_view = {
            "status": "completed",
            "answer": "这是经过授权数据核验的中文回答，未执行任何写入。",
            "citations": [],
            "degradation_codes": [],
            "draft_id": None,
            "skill": None,
            "answer_source": "real_provider",
            "provider_result_status": "completed",
        }
        result = {
            "run_id": str(run_id),
            "event_id": str(uuid4()),
            "sequence": sequence,
            "event": "result",
            "artifact_ref": str(uuid4()),
            "safe_view": safe_view,
        }
        done = {
            "run_id": str(run_id),
            "event_id": str(uuid4()),
            "sequence": sequence + 1,
            "event": "done",
            "status": "completed",
        }
        stream = "\n".join(
            f"data: {json.dumps(item, ensure_ascii=False)}" for item in (result, done)
        )
        self.streams[run_id] = stream
        return _Response(200, text=stream)

    def post(self, path: str, **kwargs):
        self.calls.append(("POST", path, kwargs))
        run_id = uuid4()
        self.run_ids.append(run_id)
        return _Response(
            202,
            payload={"run_id": str(run_id), "status": "queued", "replayed": False},
        )


class _Observer:
    def __init__(self) -> None:
        self.baseline_calls = 0
        self.observed: list[UUID] = []

    def snapshot(self, _config):
        self.baseline_calls += 1
        return DeployedCampaignSideEffectSnapshot(
            record_state_hash="a" * 64,
            record_count=42,
            telegram_send_count=0,
            notification_request_count=0,
        )

    def observe_run(self, run_id: UUID) -> DeployedRunObservation:
        self.observed.append(run_id)
        return DeployedRunObservation(provider_call_count=1)

    def action_effect_count(self, _run_ids: tuple[UUID, ...]) -> int:
        return 0


def _config(output_dir: Path, *, case_ids=REPRESENTATIVE_P2_CASE_IDS, rounds=3):
    return DeployedCampaignConfig(
        base_url="https://stage12.example.invalid",
        workspace_id=uuid4(),
        employee_id=uuid4(),
        rounds=rounds,
        case_ids=case_ids,
        output_dir=output_dir,
    )


def test_preexisting_output_refuses_before_http_or_observer(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    client_factory_called = False
    observer = _Observer()

    def client_factory(_config):
        nonlocal client_factory_called
        client_factory_called = True
        return _PublicClient()

    with pytest.raises(FileExistsError, match="stage12_deployed_output_exists"):
        run_deployed_provider_campaign(
            _config(output),
            client_factory=client_factory,
            observer=observer,
            quality_evaluator=lambda _case, _view, _events: (True, ()),
        )

    assert client_factory_called is False
    assert observer.baseline_calls == 0


def test_default_public_client_uses_existing_stage06_identity_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STAGE12_DEPLOYED_USER_ID", "stage12-eval-owner")

    client = _default_client_factory(_config(tmp_path / "auth"))
    try:
        assert client.headers["X-Stage06-User-Id"] == "stage12-eval-owner"
    finally:
        client.close()


def test_p2_uses_only_health_post_sse_and_replay_and_writes_sanitized_report(
    tmp_path: Path,
) -> None:
    client = _PublicClient()
    observer = _Observer()
    output = tmp_path / "p2"
    config = _config(output)

    report = run_deployed_provider_campaign(
        config,
        client_factory=lambda _config: client,
        observer=observer,
        quality_evaluator=lambda _case, _view, _events: (True, ()),
    )

    assert report.campaign_kind == "p2"
    assert report.execution_count == 36
    assert report.real_provider_count == 36
    assert report.fallback_count == 0
    assert report.quality_pass_count == 36
    assert report.replay_identity_count == 36
    assert report.provider_call_count_before_replay == 36
    assert report.provider_call_count_after_replay == 36
    assert report.business_write_count == 0
    assert report.confirmed_action_count == 0
    assert report.telegram_send_count == 0
    assert report.gate_pass is True
    assert observer.baseline_calls == 2
    assert len(observer.observed) == 72

    assert client.calls[0][:2] == ("GET", "/health")
    assert sum(method == "POST" for method, _path, _kwargs in client.calls) == 36
    assert all(
        path == "/health"
        or path == "/api/stage10/agent-runs"
        or path.endswith("/events")
        for _method, path, _kwargs in client.calls
    )
    replay_calls = [
        kwargs
        for method, path, kwargs in client.calls
        if method == "GET"
        and path.endswith("/events")
        and kwargs.get("headers", {}).get("Last-Event-ID")
    ]
    assert len(replay_calls) == 36

    payload = (output / "stage12-deployed-provider-campaign.json").read_text(
        encoding="utf-8"
    )
    assert json.loads(payload)["gate_pass"] is True
    assert "这是经过授权" not in payload
    assert "列出 Atlas" not in payload
    assert str(config.workspace_id) not in payload
    assert not any(
        key in payload
        for key in ("query", 'answer"', "citation_id", "prompt", "response")
    )


@pytest.mark.parametrize(
    ("case_ids", "rounds"),
    [
        (REPRESENTATIVE_P2_CASE_IDS[:-1], 3),
        (REPRESENTATIVE_P2_CASE_IDS, 2),
    ],
)
def test_invalid_campaign_dimensions_fail_before_http(
    tmp_path: Path, case_ids: tuple[str, ...], rounds: int
) -> None:
    called = False

    def client_factory(_config):
        nonlocal called
        called = True
        return _PublicClient()

    with pytest.raises(
        ValueError, match="stage12_deployed_campaign_dimensions_invalid"
    ):
        run_deployed_provider_campaign(
            _config(tmp_path / "invalid", case_ids=case_ids, rounds=rounds),
            client_factory=client_factory,
            observer=_Observer(),
            quality_evaluator=lambda _case, _view, _events: (True, ()),
        )
    assert called is False


def test_exact_full_human_gold_set_is_the_only_p3_shape(tmp_path: Path) -> None:
    all_case_ids = tuple(item.case_id for item in build_stage12_truth_cases())

    kind, cases = _validate_campaign(
        _config(tmp_path / "p3", case_ids=all_case_ids, rounds=3)
    )

    assert kind == "p3"
    assert len(cases) == 48
    assert all(item.gold_audit.status == "human_approved" for item in cases)


def test_p3_requires_a_verified_passing_p2_report_before_http(tmp_path: Path) -> None:
    all_case_ids = tuple(item.case_id for item in build_stage12_truth_cases())
    called = False

    def client_factory(_config):
        nonlocal called
        called = True
        return _PublicClient()

    with pytest.raises(RuntimeError, match="stage12_deployed_p2_pass_required"):
        run_deployed_provider_campaign(
            _config(tmp_path / "p3", case_ids=all_case_ids, rounds=3),
            client_factory=client_factory,
            observer=_Observer(),
            quality_evaluator=lambda _case, _view, _events: (True, ()),
        )

    assert called is False


def test_public_answer_quality_checks_gold_results_citations_and_internal_ids() -> None:
    case = next(
        item for item in build_stage12_truth_cases() if item.case_id == "join_01"
    )
    safe_view = {
        "answer": "Atlas 结果包括 MT-001、MT-002、RISK-001 和 RISK-002。",
        "citations": [{"ordinal": 1, "label": "business_data"}],
    }

    passed, reasons = evaluate_public_answer_quality(case, safe_view, ())
    leaked, leak_reasons = evaluate_public_answer_quality(
        case,
        {
            **safe_view,
            "answer": safe_view["answer"]
            + " internal record: 8ec13b24-3c27-4c48-817f-cea18af0cf55",
        },
        (),
    )

    assert passed is True
    assert reasons == ()
    assert leaked is False
    assert "internal_reference_exposed" in leak_reasons


def test_fallback_and_replay_provider_delta_fail_the_gate(tmp_path: Path) -> None:
    client = _PublicClient()
    observer = _Observer()
    observation_counts: dict[UUID, int] = {}

    def observe_run(run_id: UUID) -> DeployedRunObservation:
        observation_counts[run_id] = observation_counts.get(run_id, 0) + 1
        return DeployedRunObservation(provider_call_count=observation_counts[run_id])

    observer.observe_run = observe_run  # type: ignore[method-assign]
    original_get = client.get

    def fallback_get(path: str, **kwargs):
        response = original_get(path, **kwargs)
        if path.endswith("/events"):
            response.text = response.text.replace(
                '"answer_source": "real_provider", "provider_result_status": "completed"',
                '"answer_source": "deterministic_fallback", "provider_result_status": "schema_failed"',
            )
        return response

    client.get = fallback_get  # type: ignore[method-assign]

    report = run_deployed_provider_campaign(
        _config(tmp_path / "failed"),
        client_factory=lambda _config: client,
        observer=observer,
        quality_evaluator=lambda _case, _view, _events: (True, ()),
    )

    assert report.fallback_count == 36
    assert (
        report.provider_call_count_after_replay
        > report.provider_call_count_before_replay
    )
    assert report.gate_pass is False
