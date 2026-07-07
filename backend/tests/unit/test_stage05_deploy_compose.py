from pathlib import Path
from subprocess import DEVNULL, check_output


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "deploy" / "stage03" / "compose.yml").exists():
            return parent

    return Path(
        check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=DEVNULL,
            text=True,
        ).strip()
    )


def _compose_text() -> str:
    return (_repo_root() / "deploy" / "stage03" / "compose.yml").read_text(
        encoding="utf-8"
    )


def _env_example_text() -> str:
    return (_repo_root() / "deploy" / "stage03" / "env.stage03.example").read_text(
        encoding="utf-8"
    )


def _service_block(compose_text: str, service_name: str) -> str:
    marker = f"  {service_name}:\n"
    start = compose_text.index(marker)
    rest = compose_text[start + len(marker) :]

    for next_service in [
        "  postgres:\n",
        "  redis:\n",
        "  migrate:\n",
        "  api:\n",
        "  outbox-bridge:\n",
        "  worker:\n",
        "  caddy:\n",
    ]:
        index = rest.find(next_service)
        if index > 0:
            return rest[:index]

    return rest


def test_stage05_runtime_services_can_enable_real_openrouter_rehearsal() -> None:
    compose_text = _compose_text()

    migrate_block = _service_block(compose_text, "migrate")
    assert "LLM_ENABLED: \"false\"" in migrate_block
    assert "AGENT_WORKFLOW_MODE: fake" in migrate_block
    assert "PROVIDER_MODE: disabled" in migrate_block

    for service_name in ["api", "outbox-bridge", "worker"]:
        block = _service_block(compose_text, service_name)
        assert 'LLM_ENABLED: "${LLM_ENABLED:-false}"' in block
        assert 'AGENT_WORKFLOW_MODE: "${AGENT_WORKFLOW_MODE:-fake}"' in block
        assert 'OPENROUTER_API_KEY: "${OPENROUTER_API_KEY:-}"' in block
        assert 'OPENROUTER_MODEL: "${OPENROUTER_MODEL:-openrouter/auto}"' in block
        assert (
            'OPENROUTER_BASE_URL: '
            '"${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"'
            in block
        )
        assert 'AGENT_SAVE_FULL_PROMPT: "${AGENT_SAVE_FULL_PROMPT:-false}"' in block
        assert (
            'AGENT_SAVE_FULL_RESPONSE: "${AGENT_SAVE_FULL_RESPONSE:-false}"'
            in block
        )
        assert "PROVIDER_MODE: disabled" in block


def test_stage05_env_example_keeps_safe_defaults_for_real_mode_fields() -> None:
    env_text = _env_example_text()

    assert "LLM_ENABLED=false" in env_text
    assert "AGENT_WORKFLOW_MODE=fake" in env_text
    assert "OPENROUTER_API_KEY=" in env_text
    assert "OPENROUTER_MODEL=openrouter/auto" in env_text
    assert "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1" in env_text
    assert "AGENT_SAVE_FULL_PROMPT=false" in env_text
    assert "AGENT_SAVE_FULL_RESPONSE=false" in env_text
    assert "PROVIDER_MODE=disabled" in env_text
