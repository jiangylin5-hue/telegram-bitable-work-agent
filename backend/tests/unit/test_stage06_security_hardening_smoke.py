import json

from scripts.stage06_security_hardening_smoke import (
    build_security_hardening_evidence,
)


def test_security_hardening_artifact_contains_no_secret_or_raw_value_keys() -> None:
    payload = build_security_hardening_evidence(
        {
            "migration_head": "20260710_0020",
            "checks": [
                {
                    "case_id": "stage06_unit_security",
                    "status": "passed",
                    "passed_count": 125,
                    "skipped_count": 0,
                    "database_url": "postgresql://user:secret@localhost/stage06",
                    "token": "secret-token",
                    "record_values": {"secret": "must-not-leak"},
                    "prompt": "private prompt",
                    "response_body": "private response",
                }
            ],
        }
    )

    serialized = json.dumps(payload, sort_keys=True)
    for forbidden in (
        "database_url",
        "token",
        "raw_text",
        "record_values",
        "prompt",
        "response_body",
        "must-not-leak",
    ):
        assert forbidden not in serialized.lower()
    assert payload["status"] == "passed"
    assert payload["checks"] == [
        {
            "case_id": "stage06_unit_security",
            "status": "passed",
            "passed_count": 125,
            "skipped_count": 0,
        }
    ]


def test_security_hardening_artifact_is_blocked_when_required_check_is_blocked() -> None:
    payload = build_security_hardening_evidence(
        {
            "migration_head": "20260710_0020",
            "checks": [
                {
                    "case_id": "stage06_postgres_security",
                    "status": "blocked",
                    "safe_error_code": "postgres_env_missing",
                }
            ],
        }
    )

    assert payload["status"] == "blocked"
    assert payload["checks"][0]["safe_error_code"] == "postgres_env_missing"
