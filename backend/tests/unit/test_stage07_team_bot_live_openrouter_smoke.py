from scripts.stage07_team_bot_live_openrouter_smoke import build_team_bot_smoke_preflight


def test_team_bot_live_smoke_preflight_is_closed_and_does_not_echo_key() -> None:
    blocked = build_team_bot_smoke_preflight({})

    assert blocked == {
        "ok": False,
        "status": "blocked",
        "missing": ["OPENROUTER_API_KEY"],
        "openrouter_key_present": False,
    }

    ready = build_team_bot_smoke_preflight(
        {
            "OPENROUTER_API_KEY": "must-not-be-returned",
            "OPENROUTER_MODEL": "openrouter/auto",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        }
    )

    assert ready == {
        "ok": True,
        "status": "ready",
        "missing": [],
        "openrouter_key_present": True,
        "model_configured": True,
        "base_url_configured": True,
    }
    assert "must-not-be-returned" not in str(ready)
