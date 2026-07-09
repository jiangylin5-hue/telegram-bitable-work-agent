from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
EVIDENCE_PATH = (
    PROJECT_ROOT
    / "project-docs"
    / "08-implementation"
    / "evidence"
    / "STAGE_06_SECURITY_HARDENING_EVIDENCE.json"
)
EXPECTED_HEAD = "20260710_0020"
_SAFE_ERROR_CODE = re.compile(r"^[a-z0-9_]{1,80}$")


def build_security_hardening_evidence(
    results: Mapping[str, object],
) -> dict[str, object]:
    checks = [
        _safe_check(check)
        for check in results.get("checks", [])
        if isinstance(check, Mapping)
    ]
    statuses = {str(check["status"]) for check in checks}
    if "failed" in statuses:
        status = "failed"
    elif "blocked" in statuses:
        status = "blocked"
    elif checks and statuses == {"passed"}:
        status = "passed"
    else:
        status = "failed"
    migration_head = str(results.get("migration_head", ""))
    if not re.fullmatch(r"[0-9_]{8,32}", migration_head):
        migration_head = "unknown"
        status = "failed"
    return {
        "schema_version": "stage06-security-evidence-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "migration_head": migration_head,
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed_count": sum(check["status"] == "passed" for check in checks),
            "blocked_count": sum(check["status"] == "blocked" for check in checks),
            "failed_count": sum(check["status"] == "failed" for check in checks),
        },
    }


def main() -> int:
    _load_default_stage06_env()
    unit_check = _pytest_check(
        "stage06_unit_security",
        ["tests/unit", "-k", "stage06"],
    )
    head, head_check = _alembic_head_check()
    postgres_checks = _postgres_checks()
    payload = build_security_hardening_evidence(
        {
            "migration_head": head,
            "checks": [unit_check, head_check, *postgres_checks],
        }
    )
    if payload["status"] == "passed":
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["status"] == "passed":
        return 0
    if payload["status"] == "blocked":
        return 2
    return 1


def _safe_check(check: Mapping[str, object]) -> dict[str, object]:
    case_id = str(check.get("case_id", "unknown"))
    if not re.fullmatch(r"[a-z0-9_]{1,100}", case_id):
        case_id = "invalid_case_id"
    status = str(check.get("status", "failed"))
    if status not in {"passed", "blocked", "failed"}:
        status = "failed"
    safe: dict[str, object] = {"case_id": case_id, "status": status}
    for key in ("passed_count", "skipped_count"):
        value = check.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            safe[key] = value
    error_code = check.get("safe_error_code")
    if isinstance(error_code, str) and _SAFE_ERROR_CODE.fullmatch(error_code):
        safe["safe_error_code"] = error_code
    return safe


def _pytest_check(case_id: str, arguments: Sequence[str]) -> dict[str, object]:
    result = _run([sys.executable, "-m", "pytest", "-q", *arguments])
    combined = f"{result.stdout}\n{result.stderr}"
    check: dict[str, object] = {
        "case_id": case_id,
        "status": "passed" if result.returncode == 0 else "failed",
        "passed_count": _summary_count(combined, "passed"),
        "skipped_count": _summary_count(combined, "skipped"),
    }
    if result.returncode != 0:
        check["safe_error_code"] = "pytest_failed"
    return check


def _alembic_head_check() -> tuple[str, dict[str, object]]:
    result = _run([sys.executable, "-m", "alembic", "heads"])
    match = re.search(r"([0-9_]+)\s+\(head\)", result.stdout)
    head = match.group(1) if match else "unknown"
    passed = result.returncode == 0 and head == EXPECTED_HEAD
    check: dict[str, object] = {
        "case_id": "stage06_alembic_head",
        "status": "passed" if passed else "failed",
        "passed_count": 1 if passed else 0,
        "skipped_count": 0,
    }
    if not passed:
        check["safe_error_code"] = "alembic_head_mismatch"
    return head, check


def _postgres_checks() -> list[dict[str, object]]:
    if not os.getenv("STAGE06_LOCAL_DATABASE_URL"):
        return [
            {
                "case_id": "stage06_postgres_migration",
                "status": "blocked",
                "passed_count": 0,
                "skipped_count": 1,
                "safe_error_code": "postgres_env_missing",
            },
            {
                "case_id": "stage06_postgres_security",
                "status": "blocked",
                "passed_count": 0,
                "skipped_count": 2,
                "safe_error_code": "postgres_env_missing",
            },
        ]
    migration = _run(
        [sys.executable, "scripts/stage06_local_postgres_migration_smoke.py"]
    )
    migration_passed = migration.returncode == 0
    migration_check: dict[str, object] = {
        "case_id": "stage06_postgres_migration",
        "status": "passed" if migration_passed else "failed",
        "passed_count": 1 if migration_passed else 0,
        "skipped_count": 0,
    }
    if not migration_passed:
        migration_check["safe_error_code"] = "postgres_migration_failed"
        return [
            migration_check,
            {
                "case_id": "stage06_postgres_security",
                "status": "blocked",
                "passed_count": 0,
                "skipped_count": 2,
                "safe_error_code": "postgres_migration_required",
            },
        ]
    return [
        migration_check,
        _pytest_check(
            "stage06_postgres_security",
            ["tests/integration/test_stage06_postgres_security.py"],
        ),
    ]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _summary_count(output: str, label: str) -> int:
    matches = re.findall(rf"(\d+)\s+{re.escape(label)}", output)
    return int(matches[-1]) if matches else 0


def _load_default_stage06_env() -> None:
    env_path = Path(os.getenv("STAGE06_ENV_FILE", str(BACKEND_ROOT / ".env")))
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and not os.environ.get(key):
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
