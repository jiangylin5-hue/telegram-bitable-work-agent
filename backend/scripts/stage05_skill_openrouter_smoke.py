from __future__ import annotations

import json
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.agents.message_intake_router import build_router_request, parse_router_result
from app.agents.stage05_skill_matching import build_skill_evidence


DEFAULT_ENV_FILE = REPO_ROOT / ".local" / "stage05-real-workflow.env"

SMOKE_CASES = [
    {
        "case_id": "recharge_and_customer_reply",
        "source_text_summary": (
            "Customer asks to recharge act_1001 with 200 USDT and asks us to reply "
            "that the request was received."
        ),
        "expected_any": {"recharge-draft", "customer-reply-draft"},
    },
    {
        "case_id": "bm_invite",
        "source_text_summary": "Please invite buyer@example.com to BM-APAC-01.",
        "expected_any": {"bm-invite-draft"},
    },
    {
        "case_id": "spend_balance_query",
        "source_text_summary": (
            "How much did act_1001 spend today and what balance remains?"
        ),
        "expected_any": {"spend-query", "spend-table", "manual-review-handoff"},
    },
    {
        "case_id": "card_binding",
        "source_text_summary": "Bind payment profile card_profile_alpha to act_2002.",
        "expected_any": {"card-binding-draft"},
    },
    {
        "case_id": "account_exception",
        "source_text_summary": "act_stage05_001 is blocked and under risk control.",
        "expected_any": {"account-exception-marking"},
    },
]


def main() -> int:
    env_file = Path(os.getenv("STAGE05_LOCAL_ENV_FILE", str(DEFAULT_ENV_FILE)))
    loaded_keys = _load_env_file(env_file)
    _apply_safety_defaults()
    _preflight_env(env_file)

    client = OpenRouterStructuredLLMClient()
    summaries: list[dict[str, object]] = []

    for index, case in enumerate(SMOKE_CASES):
        request = build_router_request(
            trace_id=f"local-skill-smoke-{index}",
            message_id=f"local-skill-smoke-message-{index}",
            customer_id="customer-redacted",
            source_text_summary=str(case["source_text_summary"]),
            context_summary="Local redacted skill smoke. Do not execute external actions.",
        )
        result = client.generate_json(request)
        router_result = parse_router_result(result.content)
        evidence = build_skill_evidence(
            router_result=router_result,
            source_text_summary=str(case["source_text_summary"]),
        )
        selected = {
            str(item["skill_id"]) for item in evidence["selected_skills"]  # type: ignore[index]
        }
        expected_any = set(case["expected_any"])
        if not selected.intersection(expected_any):
            raise AssertionError(
                f"{case['case_id']} selected {sorted(selected)}; "
                f"expected one of {sorted(expected_any)}"
            )
        summaries.append(
            {
                "case_id": case["case_id"],
                "model_provider": result.model_provider,
                "model_name": result.model_name,
                "selected_skills": sorted(selected),
                "future_scope_skills": [
                    item["skill_id"] for item in evidence["future_scope_skills"]  # type: ignore[index]
                ],
                "fallback": evidence["fallback"],
                "usage": result.usage or {},
            }
        )

    print(
        json.dumps(
            {
                "ok": True,
                "env_file": str(env_file),
                "loaded_key_names": sorted(
                    key
                    for key in loaded_keys
                    if key not in {"OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN"}
                ),
                "openrouter_key_present": bool(os.getenv("OPENROUTER_API_KEY")),
                "provider_mode": os.getenv("PROVIDER_MODE"),
                "telegram_send_mode": os.getenv("TELEGRAM_SEND_MODE"),
                "case_count": len(summaries),
                "cases": summaries,
            },
            indent=2,
        )
    )
    return 0


def _load_env_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing local env file: {path}. Create it from the project template."
        )
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ[key] = _unquote(value.strip())
        loaded.append(key)
    return loaded


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _apply_safety_defaults() -> None:
    defaults = {
        "LLM_ENABLED": "true",
        "AGENT_WORKFLOW_MODE": "real_openrouter",
        "AGENT_SAVE_FULL_PROMPT": "false",
        "AGENT_SAVE_FULL_RESPONSE": "false",
        "TELEGRAM_SEND_MODE": "dry_run",
        "PROVIDER_MODE": "disabled",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENROUTER_MODEL": "openrouter/auto",
    }
    for key, value in defaults.items():
        if not os.getenv(key):
            os.environ[key] = value


def _preflight_env(env_file: Path) -> None:
    missing = [
        name
        for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(f"Missing local OpenRouter env in {env_file}: {missing}")
    if os.getenv("PROVIDER_MODE") != "disabled":
        raise RuntimeError("PROVIDER_MODE must stay disabled for skill smoke")
    if os.getenv("TELEGRAM_SEND_MODE") != "dry_run":
        raise RuntimeError("TELEGRAM_SEND_MODE must stay dry_run for skill smoke")
    if _env_bool("AGENT_SAVE_FULL_PROMPT") or _env_bool("AGENT_SAVE_FULL_RESPONSE"):
        raise RuntimeError("Full prompt/response persistence must stay disabled")


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
