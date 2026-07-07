from pathlib import Path


def test_stage04_runtime_services_can_enable_restricted_test_send_mode() -> None:
    compose_path = Path(__file__).parents[3] / "deploy" / "stage03" / "compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert compose_text.count("TELEGRAM_SEND_MODE: dry_run") == 1
    assert (
        compose_text.count("TELEGRAM_SEND_MODE: ${TELEGRAM_SEND_MODE:-dry_run}") == 3
    )
