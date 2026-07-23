from app.api.routes import stage08_collaboration as route
from app.core.config import Settings
from app.runtime.stage08_collaboration_contracts import UnavailableAnalysisProvider
from app.services.stage08_openrouter_analysis_provider import (
    OpenRouterStage08AnalysisProvider,
)


def test_real_openrouter_mode_builds_a_bounded_stage08_analysis_dependency() -> None:
    dependencies, runtime_control = route._stage08_runtime_dependencies(
        Settings(
            llm_enabled=True,
            agent_workflow_mode="real_openrouter",
            openrouter_api_key="synthetic-key",
            openrouter_base_url="https://provider.invalid/api/v1",
            openrouter_model="synthetic/model",
        )
    )

    assert type(dependencies.analysis_provider) is OpenRouterStage08AnalysisProvider
    remaining = route.remaining_stage08_runtime_seconds(runtime_control)
    assert 0 < remaining <= 30


def test_non_real_mode_keeps_the_stage08_analysis_provider_unavailable() -> None:
    dependencies, runtime_control = route._stage08_runtime_dependencies(
        Settings(
            llm_enabled=False,
            agent_workflow_mode="fake",
            openrouter_api_key="synthetic-key",
        )
    )

    assert type(dependencies.analysis_provider) is UnavailableAnalysisProvider
    assert 0 < route.remaining_stage08_runtime_seconds(runtime_control) <= 30
