from pathlib import Path


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


def test_stage04_runtime_services_can_enable_restricted_test_send_mode() -> None:
    compose_path = Path(__file__).parents[3] / "deploy" / "stage03" / "compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "TELEGRAM_SEND_MODE: dry_run" in _service_block(compose_text, "migrate")

    for service_name in ["api", "outbox-bridge", "worker"]:
        assert (
            "TELEGRAM_SEND_MODE: ${TELEGRAM_SEND_MODE:-dry_run}"
            in _service_block(compose_text, service_name)
        )
