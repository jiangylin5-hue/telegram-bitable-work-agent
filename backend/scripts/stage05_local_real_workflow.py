from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.models.accounts import AccountInventory
from app.services.agent_workflows import (
    InMemoryStage05WorkflowUnitOfWork,
    Stage05AgentWorkflowService,
)
from app.services.telegram_ingestion import IngestedMessage


DEFAULT_ENV_FILE = REPO_ROOT / ".local" / "stage05-real-workflow.env"
DEFAULT_TEST_MESSAGE = (
    "stage05_local_real 请帮客户 act_stage05_test 充值 100 USD，同时看下 "
    "BM invite 能不能处理；如果客户问进度，请回复：我们正在确认账户和资料，稍后同步。"
    "另外客户说 act_stage05_test 可能被风控了，请先标记异常，不要自动换号。"
)


def main() -> int:
    env_file = Path(os.getenv("STAGE05_LOCAL_ENV_FILE", str(DEFAULT_ENV_FILE)))
    loaded_keys = _load_env_file(env_file)
    _apply_safety_defaults()

    missing = [
        name
        for name in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL")
        if not os.getenv(name)
    ]
    if missing:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "env_preflight",
                    "env_file": str(env_file),
                    "missing": missing,
                    "openrouter_key_present": bool(os.getenv("OPENROUTER_API_KEY")),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    if os.getenv("PROVIDER_MODE") != "disabled":
        return _fail_safety("PROVIDER_MODE must stay disabled for local workflow")
    if os.getenv("TELEGRAM_SEND_MODE") != "dry_run":
        return _fail_safety("TELEGRAM_SEND_MODE must stay dry_run for local workflow")
    if _env_bool("AGENT_SAVE_FULL_PROMPT") or _env_bool("AGENT_SAVE_FULL_RESPONSE"):
        return _fail_safety("Full prompt/response persistence must stay disabled")

    customer_id = uuid4()
    message = _local_message(customer_id=customer_id)
    account = AccountInventory(
        id=uuid4(),
        platform="meta",
        external_account_id="act_stage05_test",
        inventory_status="allocated",
        production_batch_id="local-stage05-real-workflow",
        assigned_customer_id=customer_id,
    )
    uow = InMemoryStage05WorkflowUnitOfWork(
        messages=[message],
        inventory_accounts=[account],
    )
    service = Stage05AgentWorkflowService(
        uow=uow,
        llm_client=OpenRouterStructuredLLMClient(),
        model_name=os.getenv("OPENROUTER_MODEL"),
    )

    outcome = service.run_message(str(message.id))
    evidence = _redacted_evidence(
        env_file=env_file,
        loaded_keys=loaded_keys,
        outcome=outcome,
        message=message,
        account=account,
        uow=uow,
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
    return 0 if evidence["ok"] else 1


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


def _fail_safety(message: str) -> int:
    print(
        json.dumps(
            {
                "ok": False,
                "stage": "safety_preflight",
                "error_message_redacted": message,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _local_message(*, customer_id) -> IngestedMessage:
    raw_text = os.getenv("STAGE05_LOCAL_TEST_MESSAGE", DEFAULT_TEST_MESSAGE)
    message = IngestedMessage(
        id=uuid4(),
        telegram_update_id="local-stage05-real-workflow",
        telegram_chat_id="local-redacted-chat",
        telegram_message_id="local-message-stage05-real",
        telegram_user_id="local-redacted-user",
        customer_group_id=None,
        customer_id=customer_id,
        raw_text=raw_text,
        raw_caption=None,
        normalized_text=raw_text,
        message_type="text",
        intent_status="intent_ready",
        intent_type=None,
        ingestion_status="stored",
        trace_id="local:stage05-real-workflow",
        binding_status="bound",
        processing_status="processed",
        outbox_status="processed",
    )
    message.received_at = datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)
    return message


def _redacted_evidence(
    *,
    env_file: Path,
    loaded_keys: list[str],
    outcome,
    message: IngestedMessage,
    account: AccountInventory,
    uow: InMemoryStage05WorkflowUnitOfWork,
) -> dict[str, object]:
    agent_runs = [_agent_run_summary(run) for run in uow.agent_runs]
    return {
        "ok": outcome.status in {"routed", "manual_review"},
        "env_file": str(env_file),
        "loaded_key_names": sorted(
            key
            for key in loaded_keys
            if key not in {"OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN"}
        ),
        "openrouter_key_present": bool(os.getenv("OPENROUTER_API_KEY")),
        "telegram_bot_token_present": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "provider_mode": os.getenv("PROVIDER_MODE"),
        "telegram_send_mode": os.getenv("TELEGRAM_SEND_MODE"),
        "workflow_status": outcome.status,
        "workflow_reason": outcome.reason,
        "selected_agents": outcome.selected_agents,
        "manual_review_reasons": outcome.manual_review_reasons,
        "message_intent_status": message.intent_status,
        "message_last_error_code": message.last_error_code,
        "agent_runs": agent_runs,
        "service_drafts": [_draft_summary(draft) for draft in uow.service_drafts],
        "account_inventory": {
            "external_account_id": account.external_account_id,
            "inventory_status": account.inventory_status,
            "status_reason_present": bool(account.status_reason),
        },
        "account_status_events": [
            {
                "event_type": event.event_type,
                "before_status": event.before_status,
                "after_status": event.after_status,
                "confidence": str(event.confidence) if event.confidence else None,
                "risk_flags": list(event.risk_flags or []),
            }
            for event in uow.status_events
        ],
        "audit_event_types": [
            getattr(event, "event_type", "unknown") for event in uow.audit_events
        ],
        "commits": uow.commits,
    }


def _agent_run_summary(run) -> dict[str, object]:
    output_summary = run.output_summary or {}
    intents = output_summary.get("intents", [])
    return {
        "agent_name": run.agent_name,
        "graph_name": run.graph_name,
        "model_provider": run.model_provider,
        "model_name": run.model_name,
        "prompt_version": run.prompt_version,
        "status": run.status,
        "error_code": run.error_code,
        "error_message_redacted": run.error_message_redacted,
        "redaction_policy": run.redaction_policy,
        "request_id_or_usage_present": bool(run.usage_summary),
        "usage_summary_present": bool(run.usage_summary),
        "intent_types": [
            str(intent.get("intent_type"))
            for intent in intents
            if isinstance(intent, dict) and intent.get("intent_type")
        ],
        "requires_manual_review": output_summary.get("requires_manual_review"),
        "overall_confidence": output_summary.get("overall_confidence"),
        "redacted_summary": output_summary.get("redacted_summary"),
    }


def _draft_summary(draft) -> dict[str, object]:
    payload = dict(draft.payload or {})
    return {
        "draft_type": draft.draft_type,
        "status": draft.status,
        "missing_fields": list(draft.missing_fields or []),
        "risk_flags": list(draft.risk_flags or []),
        "confidence": str(draft.confidence) if draft.confidence else None,
        "payload_summary": draft.payload_summary,
        "provider_execution_allowed": payload.get("provider_execution_allowed"),
        "send_request_created": payload.get("send_request_created"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
