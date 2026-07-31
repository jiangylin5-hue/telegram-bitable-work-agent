from uuid import UUID

from app.core.config import Settings
from app.services.agent_specialist_shadow_v2 import (
    SpecialistShadowMetricsV1,
    run_typed_specialists_shadow,
    typed_specialists_shadow_enabled,
)


WORKSPACE = UUID("10000000-0000-0000-0000-000000000001")
PROFILE = "stage12.openrouter-gemini-2.5-flash-v1"


def _settings(*, allowlisted: bool = True, key: str | None = "test-key") -> Settings:
    return Settings(
        openrouter_api_key=key,
        stage12_provider_v2_profile=PROFILE,
        typed_specialists_v2_mode="shadow",
        typed_specialists_v2_workspace_allowlist=(
            (str(WORKSPACE),) if allowlisted else ()
        ),
    )


def test_shadow_never_invokes_pipeline_outside_exact_gate() -> None:
    calls = 0

    def execute():
        nonlocal calls
        calls += 1
        raise AssertionError("must_not_execute")

    assert typed_specialists_shadow_enabled(Settings(), WORKSPACE) is False
    assert (
        typed_specialists_shadow_enabled(_settings(allowlisted=False), WORKSPACE)
        is False
    )
    assert typed_specialists_shadow_enabled(_settings(key=None), WORKSPACE) is False
    assert (
        run_typed_specialists_shadow(
            settings=Settings(), workspace_id=WORKSPACE, execute_pipeline=execute
        )
        is None
    )
    assert calls == 0


def test_shadow_reports_only_sanitized_counts_hashes_and_zero_side_effects() -> None:
    observation = run_typed_specialists_shadow(
        settings=_settings(),
        workspace_id=WORKSPACE,
        execute_pipeline=lambda: SpecialistShadowMetricsV1(
            handler_count=4,
            typed_artifact_count=6,
            claim_count=3,
            valid_evidence_count=2,
            provider_attempt_count=1,
            provider_failure_count=0,
            action_proposal_count=1,
            write_count=0,
            send_count=0,
            comparison_hash="a" * 64,
        ),
    )

    assert observation is not None
    assert observation.status == "observed"
    assert observation.write_count == 0
    assert observation.send_count == 0
    rendered = observation.model_dump_json()
    for forbidden in ("query", "evidence_id", "candidate", "prompt", "field_value"):
        assert forbidden not in rendered


def test_shadow_provider_failure_isolated_to_stable_class() -> None:
    class Failure(RuntimeError):
        code = "provider_timeout"

    observation = run_typed_specialists_shadow(
        settings=_settings(),
        workspace_id=WORKSPACE,
        execute_pipeline=lambda: (_ for _ in ()).throw(Failure("secret output")),
    )

    assert observation is not None
    assert observation.status == "shadow_failed"
    assert observation.failure_code == "provider_timeout"
    assert "secret" not in observation.model_dump_json()
