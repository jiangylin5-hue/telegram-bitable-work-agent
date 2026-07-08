# Stage 05 Local OpenRouter Env Smoke

## Status

- Document status: active local real-LLM smoke runbook
- Scope: Local OpenRouter environment setup and redacted Stage05 router smoke before any further Tencent Cloud staging attempt.
- Current Progress: 2026-07-08 Added after the first real staging OpenRouter AgentRun reached the worker but failed RouterResult validation with `agent_output_invalid`. From this point on, any router prompt/schema compatibility fix must pass deterministic local tests and this local real OpenRouter smoke before redeploying to staging.

## 1. Purpose

This document defines the local, one-shot real OpenRouter smoke test for Stage05.

It is meant to catch model-output/schema mismatches locally before using Tencent Cloud staging. It does not replace unit/integration tests and does not count as final Stage05 acceptance by itself.

The smoke proves:

- The local OpenRouter key can call the configured model.
- `message_intake_router.build_router_request(...)` gives the model enough contract guidance.
- The returned JSON parses through `parse_router_result(...)`.
- The result can be summarized without printing raw prompt, raw response, key, token or raw allowlist values.

## 2. Safety Boundary

Allowed:

- Temporary local process environment variables.
- One real OpenRouter call using the Stage05 router prompt.
- Redacted console output containing model metadata, request-id presence, usage presence, intent types, confidence and manual-review flags.

Forbidden:

- Writing `OPENROUTER_API_KEY` to any `.env`, `.ps1`, `.sh`, Markdown, Python file, shell history paste or git-tracked file.
- Printing the raw OpenRouter key.
- Printing raw LLM response text.
- Printing full prompt text after the call.
- Saving full prompt/response to database, files or docs.
- Setting Telegram send env or provider env for this local smoke.
- Any Telegram send, provider write, funds movement, account production or account replacement action.

The local smoke only calls OpenRouter. It does not touch PostgreSQL, Redis, Telegram, Tencent Cloud or provider systems.

## 3. Required Local Env

Set these only in the current terminal session:

| Variable | Required | Value |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | Enter through secure prompt only |
| `OPENROUTER_MODEL` | no | Defaults to `openrouter/auto`; may be set to the exact staging model for closer reproduction |
| `OPENROUTER_BASE_URL` | no | Defaults to `https://openrouter.ai/api/v1` |

Do not set these for local smoke:

| Variable | Reason |
| --- | --- |
| `LLM_ENABLED` | Not needed; the script calls the adapter directly |
| `AGENT_WORKFLOW_MODE` | Not needed; no worker/runtime service is started |
| `TELEGRAM_BOT_TOKEN` | Telegram is out of scope |
| `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` | Telegram is out of scope |
| `PROVIDER_MODE` | Provider is out of scope |

## 4. Preflight

Run from the repository backend directory:

```powershell
cd "D:\telegram多维表格和工作智能体的开发\backend"
```

Confirm the key is not already present in the shell unless intentionally set for this smoke:

```powershell
if ($env:OPENROUTER_API_KEY) {
  "OPENROUTER_API_KEY_present=yes"
} else {
  "OPENROUTER_API_KEY_present=no"
}

if ($env:OPENROUTER_MODEL) {
  "OPENROUTER_MODEL_present=yes value=$env:OPENROUTER_MODEL"
} else {
  "OPENROUTER_MODEL_present=no default=openrouter/auto"
}
```

Run deterministic local verification first:

```powershell
pytest tests/unit/test_stage05_router_schema.py tests/integration/test_stage05_agent_workflow.py -q
pytest tests -k stage05 -q
pytest tests -q
```

Expected local deterministic result after the router prompt-contract fix:

```text
15 passed
86 passed, 190 deselected
259 passed, 17 skipped
```

The 17 skipped tests are the documented online PostgreSQL smoke tests requiring `STAGE02_ONLINE_DATABASE_URL`.

## 5. Set Key For Current Terminal Only

Use a secure prompt. Do not paste the key into the command itself.

```powershell
$secure = Read-Host "OpenRouter API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:OPENROUTER_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

$env:OPENROUTER_MODEL = "openrouter/auto"
$env:OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
```

If staging uses a specific model, set `OPENROUTER_MODEL` to that exact model instead of `openrouter/auto`. Do not record the key.

## 6. Run Local Real OpenRouter Smoke

This script prints redacted operational evidence only. It does not print raw prompt or raw response.

```powershell
@'
import json

from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.agents.message_intake_router import (
    RouterOutputInvalid,
    build_router_request,
    parse_router_result,
)

request = build_router_request(
    trace_id="local-stage05-smoke",
    message_id="local-message-smoke",
    customer_id="local-customer-smoke",
    source_text_summary=(
        "stage05_local_smoke 请帮客户 act_stage05_test 充值 100 USD，"
        "同时看下 BM invite 能不能处理；如果客户问进度，请回复："
        "我们正在确认账户和资料，稍后同步。"
    ),
    context_summary="Local smoke only. Do not execute provider actions.",
)

client = OpenRouterStructuredLLMClient()
result = client.generate_json(request)

try:
    parsed = parse_router_result(result.content)
except RouterOutputInvalid as exc:
    print(json.dumps(
        {
            "ok": False,
            "stage": "parse_router_result",
            "error_code": exc.error_code,
            "error_message_redacted": "Router output schema validation failed",
            "model_provider": result.model_provider,
            "model_name": result.model_name,
            "prompt_version": result.prompt_version,
            "request_id_present": bool(result.request_id),
            "usage_present": bool(result.usage),
            "output_top_level_keys": (
                sorted(result.content.keys())
                if isinstance(result.content, dict)
                else []
            ),
        },
        ensure_ascii=False,
        indent=2,
    ))
    raise SystemExit(1)

print(json.dumps(
    {
        "ok": True,
        "model_provider": result.model_provider,
        "model_name": result.model_name,
        "prompt_version": result.prompt_version,
        "request_id_present": bool(result.request_id),
        "usage_present": bool(result.usage),
        "intent_types": [intent.intent_type for intent in parsed.intents],
        "overall_confidence": str(parsed.overall_confidence),
        "requires_manual_review": parsed.requires_manual_review,
        "manual_review_reasons": parsed.manual_review_reasons,
        "redacted_summary": parsed.redacted_summary,
    },
    ensure_ascii=False,
    indent=2,
))
'@ | python -
```

## 7. Cleanup

Always clear the local key from the current shell after the smoke:

```powershell
Remove-Item Env:\OPENROUTER_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\OPENROUTER_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:\OPENROUTER_BASE_URL -ErrorAction SilentlyContinue

if ($env:OPENROUTER_API_KEY) {
  "OPENROUTER_API_KEY_present=yes"
} else {
  "OPENROUTER_API_KEY_present=no"
}
```

Expected cleanup proof:

```text
OPENROUTER_API_KEY_present=no
```

## 8. Pass Criteria

The local real OpenRouter smoke passes only if:

- Output contains `"ok": true`.
- `model_provider` is `openrouter`.
- `model_name` is present and matches the configured model.
- `prompt_version` is `stage05-router-v1`.
- `request_id_present` is `true` or usage metadata is otherwise present.
- `intent_types` is non-empty and contains only supported Stage05 intent types.
- The output has no raw API key, no raw prompt, no raw LLM response and no raw Telegram/chat allowlist.

For the default mixed Chinese/English smoke message, acceptable model behavior is:

- Preferred: `intent_types` includes `recharge`, `bm_invite` and `customer_reply`.
- Acceptable for a conservative model: `intent_types` includes `recharge` plus either `bm_invite` or `customer_reply`, with `requires_manual_review=true` or meaningful `manual_review_reasons`.
- Not acceptable: unsupported intent types, empty intents, top-level flat `intent_type`, or schema validation failure.

## 9. Failure Handling

If the smoke fails with `agent_output_invalid`:

- Do not redeploy to staging.
- Do not paste raw OpenRouter response into chat or docs.
- Use only `output_top_level_keys`, `error_code`, model metadata and prompt version as evidence.
- Adjust the router prompt/schema locally.
- Re-run deterministic local tests.
- Re-run this local real OpenRouter smoke.

If the smoke fails with authentication or HTTP errors:

- Clear env variables.
- Re-enter the key through secure prompt.
- Verify the model name.
- Do not paste the key, raw headers or raw error payload.

If the smoke times out or rate-limits:

- Stop and record redacted failure type only.
- Do not repeatedly retry without checking cost/rate-limit impact.

## 10. Evidence Format

Allowed local evidence to paste into chat or docs:

```json
{
  "ok": true,
  "model_provider": "openrouter",
  "model_name": "openrouter/auto",
  "prompt_version": "stage05-router-v1",
  "request_id_present": true,
  "usage_present": true,
  "intent_types": ["recharge", "bm_invite", "customer_reply"],
  "overall_confidence": "0.9000",
  "requires_manual_review": false,
  "manual_review_reasons": [],
  "redacted_summary": "Customer asks for recharge, BM invite and reply draft."
}
```

Forbidden evidence:

- Raw OpenRouter API key.
- Raw request headers.
- Raw prompt.
- Raw response text.
- Full customer chat id or Telegram allowlist value.
- Any provider credential, database URL or Redis URL.

## 11. Staging Gate

Before the next Tencent Cloud staging retry, all of these must be true:

- Deterministic local tests passed.
- This local real OpenRouter smoke passed.
- The local key was cleared after the smoke.
- No raw key, raw prompt, raw response or raw allowlist entered git or docs.
- The prompt/schema fix was committed and pushed as a reviewed deployable artifact.

Only then continue with Stage05 Task12 staging redeploy and fresh Telegram test message.
