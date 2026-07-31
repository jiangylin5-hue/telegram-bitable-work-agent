from __future__ import annotations

import json

import pytest

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV2,
    GroundedAnswerSectionV2,
    GroundedAnswerStatementV2,
    ProviderResponseFingerprintV1,
)
from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderInvocationError,
)
from scripts.stage12_grounded_answer_preflight import (
    build_grounded_answer_preflight_requests,
    run_grounded_answer_preflight,
    write_grounded_answer_preflight,
)


def _valid_plan(request):
    return GroundedAnswerPlanV2(
        sections=(
            GroundedAnswerSectionV2(
                section_kind="answer",
                heading="结论",
                statements=tuple(
                    GroundedAnswerStatementV2(
                        statement_kind="fact",
                        text=(
                            f"{claim.subject_label} 的 {claim.predicate_label}为"
                            f" {claim.value_text}。"
                        ),
                        claim_handles=(claim.claim_handle,),
                        evidence_handles=claim.evidence_handles,
                        action_handles=(),
                    )
                    for claim in request.claims
                ),
            ),
        )
    )


class _ValidProvider:
    def __init__(self) -> None:
        self.requests = []
        self.observations = ()
        self.diagnostics = ()
        self.transport_diagnostics = ()

    def __call__(self, request):
        self.requests.append(request)
        return _valid_plan(request)


def _capabilities():
    return {
        "model_id": "deepseek/deepseek-v3.2",
        "supported_parameters": (
            "reasoning",
            "response_format",
            "structured_outputs",
        ),
    }


def test_preflight_freezes_four_shapes_for_three_rounds() -> None:
    requests = build_grounded_answer_preflight_requests()

    assert len(requests) == 12
    assert tuple(len(item.claims) for item in requests) == (1, 2, 4, 7) * 3
    assert len({item.content_hash for item in requests}) == 12


def test_preflight_aborts_before_call_when_capability_is_missing() -> None:
    provider = _ValidProvider()

    with pytest.raises(RuntimeError, match="grounded_preflight_capability_missing"):
        run_grounded_answer_preflight(
            provider=provider,
            load_capabilities=lambda: {
                "model_id": "google/gemini-2.5-flash",
                "supported_parameters": ("response_format",),
            },
        )

    assert provider.requests == []


def test_preflight_executes_exactly_twelve_zero_fallback_invocations() -> None:
    provider = _ValidProvider()

    report = run_grounded_answer_preflight(
        provider=provider,
        load_capabilities=_capabilities,
    )

    assert len(provider.requests) == 12
    assert report.required_count == 12
    assert report.http_completed == 12
    assert report.schema_valid == 12
    assert report.grounding_valid == 12
    assert report.answer_source_real_provider == 12
    assert report.fallback_count == 0
    assert report.raw_output_retained == 0
    assert report.gate_pass is True
    payload = report.model_dump(mode="json")

    def keys(value):
        if isinstance(value, dict):
            return set(value) | {key for item in value.values() for key in keys(item)}
        if isinstance(value, list):
            return {key for item in value for key in keys(item)}
        return set()

    serialized_keys = keys(payload)
    for forbidden in (
        "raw_prompt",
        "raw_output",
        "previous_output",
        "expected_answer",
        "gold_truth",
        "case_id",
    ):
        assert forbidden not in serialized_keys


def test_preflight_records_failure_without_selective_retry() -> None:
    class _OneFailureProvider(_ValidProvider):
        def __call__(self, request):
            self.requests.append(request)
            if len(self.requests) == 5:
                raise GroundedAnswerProviderInvocationError("provider_schema_invalid")
            return _valid_plan(request)

    provider = _OneFailureProvider()
    report = run_grounded_answer_preflight(
        provider=provider,
        load_capabilities=_capabilities,
    )

    assert len(provider.requests) == 12
    assert report.schema_valid == 11
    assert report.answer_source_real_provider == 11
    assert report.fallback_count == 0
    assert report.gate_pass is False
    assert report.failure_counts == {"provider_schema_invalid": 1}


def test_preflight_retains_only_sanitized_transport_diagnostics() -> None:
    class _TransportFailureProvider(_ValidProvider):
        def __call__(self, request):
            self.requests.append(request)
            values = {
                "version": "provider-transport-fingerprint.v1",
                "attempt": 1,
                "transport_kind": "http_response",
                "http_status": 400,
                "response_bytes": 120,
                "response_sha256": "a" * 64,
                "provider_name": "provider-safe-name",
                "provider_error_code": "400",
                "provider_error_status": "INVALID_ARGUMENT",
                "error_category": "schema_state_limit",
            }
            values["content_hash"] = specialist_payload_sha256(values)
            self.transport_diagnostics = (
                values,
            )
            raise GroundedAnswerProviderInvocationError("provider_http_error")

    report = run_grounded_answer_preflight(
        provider=_TransportFailureProvider(),
        load_capabilities=_capabilities,
    )

    assert len(report.results) == 12
    assert all(len(item.transport_diagnostics) == 1 for item in report.results)
    encoded = report.model_dump_json()
    assert "schema_state_limit" in encoded
    assert '"raw":' not in encoded
    assert '"message":' not in encoded


def test_preflight_retains_sanitized_response_shape_and_validation_path() -> None:
    class _SchemaFailureProvider(_ValidProvider):
        def __call__(self, request):
            self.requests.append(request)
            values = {
                "version": "provider-response-fingerprint.v1",
                "attempt": 1,
                "top_level_type": "invalid_json",
                "top_level_keys": (),
                "section_count": 0,
                "statement_count": 0,
                "response_bytes": 1600,
                "response_sha256": "c" * 64,
                "validation_error_types": ("json_invalid",),
                "validation_paths": ("$",),
                "repair": False,
            }
            values["content_hash"] = specialist_payload_sha256(values)
            self.diagnostics = (ProviderResponseFingerprintV1.model_validate(values),)
            raise GroundedAnswerProviderInvocationError("provider_schema_invalid")

    report = run_grounded_answer_preflight(
        provider=_SchemaFailureProvider(),
        load_capabilities=_capabilities,
    )

    assert all(len(item.response_diagnostics) == 1 for item in report.results)
    fingerprint = report.results[0].response_diagnostics[0]
    assert fingerprint.top_level_type == "invalid_json"
    assert fingerprint.validation_error_types == ("json_invalid",)
    encoded = report.model_dump_json()
    assert '"raw_output":' not in encoded
    assert '"previous_output":' not in encoded


def test_preflight_writes_only_to_a_previously_absent_output_directory(
    tmp_path,
) -> None:
    report = run_grounded_answer_preflight(
        provider=_ValidProvider(),
        load_capabilities=_capabilities,
    )
    output_dir = tmp_path / "p1"

    json_path, markdown_path = write_grounded_answer_preflight(
        report, output_dir=output_dir
    )

    assert json.loads(json_path.read_text(encoding="utf-8"))["gate_pass"] is True
    assert "12/12" in markdown_path.read_text(encoding="utf-8")
    assert not tuple(output_dir.glob("*.tmp"))
    with pytest.raises(FileExistsError, match="grounded_preflight_output_exists"):
        write_grounded_answer_preflight(report, output_dir=output_dir)
