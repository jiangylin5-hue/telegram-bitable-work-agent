from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    specialist_payload_sha256,
)
from app.services.agent_model_gateway import ProviderGatewayResult
from scripts.stage12_action_provider_benchmark import (
    ActionProviderBenchmarkReportV1,
    get_stage12_action_profile,
    main as benchmark_main,
    run_action_provider_benchmark,
)


NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


def _observation() -> ProviderAttemptObservationV1:
    values = {
        "version": "provider-attempt.v1",
        "role": "action",
        "profile_id": "action.zh.stage12-f.v1",
        "provider": "openrouter-compatible",
        "model_id": "google/gemini-2.5-flash",
        "attempt": 1,
        "status": "completed",
        "failure_code": None,
        "latency_ms": 30,
        "input_tokens": 40,
        "output_tokens": 20,
        "repair": False,
    }
    values["observation_hash"] = specialist_payload_sha256(values)
    return ProviderAttemptObservationV1.model_validate(values)


class _PerfectGateway:
    def invoke(self, **kwargs):
        payload = kwargs["validate"](
            json.dumps(
                {
                    "action_kind": "task.create",
                    "safe_summary": "建议创建一条待确认任务",
                    "assignments": [
                        {"field_key": "title", "value": "合成评审任务"},
                        {"field_key": "status", "value": "待处理"},
                    ],
                    "evidence_ids": ["syn-action-01"],
                    "confirmation_required": True,
                    "execution_status": "not_executed",
                },
                ensure_ascii=False,
            )
        )
        return ProviderGatewayResult(
            status="completed",
            payload=payload,
            failure_code=None,
            observations=(_observation(),),
        )


def test_action_provider_benchmark_is_real_call_ready_and_side_effect_free() -> None:
    report = run_action_provider_benchmark(
        gateway=_PerfectGateway(),
        profile=get_stage12_action_profile(),
        now=lambda: NOW,
    )

    assert isinstance(report, ActionProviderBenchmarkReportV1)
    assert report.provider_call_count == 1
    assert report.pass_count == 1
    assert report.pre_confirmation_record_mutation_count == 0
    assert report.telegram_send_count == 0
    rendered = report.model_dump_json()
    assert "合成任务" not in rendered
    assert "safe_summary" not in rendered
    assert "OPENROUTER_API_KEY" not in rendered


def test_action_provider_cli_writes_only_sanitized_evidence(tmp_path: Path) -> None:
    output = tmp_path / "action-provider.json"

    exit_code = benchmark_main(
        ["--output-json", str(output)],
        gateway_factory=lambda _profile: _PerfectGateway(),
        now=lambda: NOW,
    )

    assert exit_code == 0
    report = ActionProviderBenchmarkReportV1.model_validate_json(
        output.read_text(encoding="utf-8")
    )
    assert report.failure_count == 0
    assert report.telegram_send_count == 0
