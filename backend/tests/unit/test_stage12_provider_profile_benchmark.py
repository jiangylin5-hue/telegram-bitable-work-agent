from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.schemas.agent_specialist_results import ProviderAttemptObservationV1
from app.services.agent_model_gateway import ProviderGatewayResult
from scripts.stage12_provider_profile_benchmark import (
    ProviderProfileBenchmarkReportV1,
    get_stage12_baseline_profiles,
    main as benchmark_main,
    run_provider_profile_benchmark,
)


NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)


def _observation(role: str, attempt: int = 1) -> ProviderAttemptObservationV1:
    values = {
        "version": "provider-attempt.v1",
        "role": role,
        "profile_id": f"{role}.zh.baseline.v1",
        "provider": "openrouter-compatible",
        "model_id": "google/gemini-2.5-flash",
        "attempt": attempt,
        "status": "completed",
        "failure_code": None,
        "latency_ms": 25,
        "input_tokens": 30,
        "output_tokens": 10,
        "repair": attempt > 1,
    }
    from app.schemas.agent_specialist_results import specialist_payload_sha256

    values["observation_hash"] = specialist_payload_sha256(values)
    return ProviderAttemptObservationV1.model_validate(values)


class _Payload:
    def __init__(self, evidence_ids: tuple[str, ...]) -> None:
        self.evidence_ids = evidence_ids


class _PerfectGateway:
    def invoke(self, *, role, **_kwargs):
        return ProviderGatewayResult(
            status="completed",
            payload=_Payload((f"syn-{role}-01",)),
            failure_code=None,
            observations=(_observation(role),),
        )


def test_focused_benchmark_reports_only_sanitized_aggregate_metrics() -> None:
    report = run_provider_profile_benchmark(
        gateway=_PerfectGateway(),
        profiles=get_stage12_baseline_profiles(),
        now=lambda: NOW,
    )

    assert isinstance(report, ProviderProfileBenchmarkReportV1)
    assert report.case_count == 3
    assert report.pass_count == 3
    assert report.failure_count == 0
    assert report.attempt_count == 3
    assert report.input_tokens == 90
    assert report.output_tokens == 30
    assert report.roles == ("risk", "daily", "composer")
    rendered = report.model_dump_json()
    assert "合成风险" not in rendered
    assert "synthetic evidence" not in rendered
    assert "answer" not in rendered


def test_baseline_profiles_freeze_model_and_role_binding() -> None:
    profiles = get_stage12_baseline_profiles()

    assert tuple(profiles) == ("risk", "daily", "composer")
    assert {profile.model_id for profile in profiles.values()} == {
        "google/gemini-2.5-flash"
    }
    assert all(role in profiles[role].allowed_roles for role in profiles)
    assert len({profile.profile_id for profile in profiles.values()}) == 3


def test_cli_writes_sanitized_report_with_injected_gateway(
    tmp_path: Path,
) -> None:
    output = tmp_path / "provider-report.json"

    exit_code = benchmark_main(
        ["--output-json", str(output)],
        gateway_factory=lambda _profiles: _PerfectGateway(),
        now=lambda: NOW,
    )

    assert exit_code == 0
    rendered = output.read_text(encoding="utf-8")
    payload = json.loads(rendered)
    report = ProviderProfileBenchmarkReportV1.model_validate_json(rendered)
    assert report.pass_count == 3
    assert report.failure_counts == {}
    assert "合成" not in rendered
