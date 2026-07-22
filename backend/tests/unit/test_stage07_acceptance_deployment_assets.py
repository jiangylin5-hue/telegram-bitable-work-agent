from pathlib import Path


def test_caddy_template_routes_only_explicit_static_paths_to_web() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    template = (
        repository_root
        / "deploy"
        / "stage07-acceptance"
        / "Caddyfile.stage07-host"
    ).read_text(encoding="utf-8")

    assert "@static path / /index.html /assets/* /favicon.ico" in template
    assert "handle @static {\n        reverse_proxy stage07-web:80" in template
    assert "handle {\n        reverse_proxy stage07-api:8000" in template
    assert "@api path" not in template
