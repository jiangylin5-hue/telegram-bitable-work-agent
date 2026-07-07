# Stage 05 OpenRouter Evidence

## Status

- Document status: active module design draft
- Scope: Real OpenRouter request/response handling, redaction, AgentRun evidence, usage/cost/latency and failure evidence.
- Current Progress: 2026-07-07 Module design created before implementation.

## 1. Purpose

Stage05 uses real OpenRouter as the main LLM path. This module ensures real model calls are useful for debugging and audit without exposing secrets or full customer context in operational views.

## 2. What To Persist

Persist:

- model provider: `openrouter`
- model name
- prompt version
- request id if returned
- status
- trace id
- input summary
- output structured summary
- redacted summary
- usage tokens if available
- estimated cost if available
- latency ms
- error code
- redacted error message
- created entity refs

Do not persist by default:

- full prompt
- full raw response
- OpenRouter API key
- Authorization headers
- raw sensitive attachments
- raw card/payment data

## 3. Input Summary

Example:

```json
{
  "message_count": 2,
  "roles": ["system", "user"],
  "source": "telegram_message",
  "customer_id_present": true,
  "recent_context_count": 3,
  "redaction_policy": "stage05_summary_only"
}
```

## 4. Output Summary

Example:

```json
{
  "intents": ["recharge", "bm_invite", "customer_reply"],
  "overall_confidence": "0.8800",
  "manual_review": false,
  "draft_types_created": ["recharge", "bm_invite", "customer_reply"],
  "missing_fields": [],
  "risk_flags": []
}
```

## 5. Usage And Cost

OpenRouter may return token usage. Store what is available:

```json
{
  "prompt_tokens": 1200,
  "completion_tokens": 450,
  "total_tokens": 1650
}
```

Cost:

```json
{
  "currency": "USD",
  "estimated_cost": "0.0000",
  "source": "openrouter_usage_or_internal_estimate"
}
```

Stage05 records cost but does not enforce budget limits by user choice.

## 6. Latency

Record:

- client start time.
- client end time.
- total latency in milliseconds.

Latency helps distinguish model/API issues from worker/persistence issues.

## 7. Prompt Versioning

Prompt versions:

- `stage05-router-v1`
- `stage05-recharge-draft-v1` if child agent prompts are used
- `stage05-card-binding-draft-v1`
- `stage05-bm-invite-draft-v1`
- `stage05-customer-reply-draft-v1`
- `stage05-account-inventory-v1`

If child agents do not call LLM separately and only use Router result, their prompt version can be recorded as `derived-from-router-v1`.

## 8. Failure Evidence

Error codes:

- `openrouter_not_configured`
- `openrouter_timeout`
- `openrouter_http_error`
- `openrouter_invalid_json`
- `agent_output_invalid`
- `agent_policy_blocked`

Persist safe error message:

```json
{
  "error_code": "openrouter_invalid_json",
  "error_message_redacted": "Model response was not a JSON object."
}
```

Never persist raw HTTP headers or API keys.

## 9. View Exposure

`agent_runs` internal API may expose operational summaries to manager/admin.

Bitable-like business views should expose only:

- status.
- model provider/name.
- prompt version.
- intent summary.
- error code.
- trace id.
- created entity refs.

They should not expose:

- full prompt.
- full raw model response.
- unredacted sensitive context.

## 10. Tests

Required:

- Fake OpenRouter response records usage and latency.
- Invalid JSON stores failed AgentRun and no draft.
- Missing API key fails closed.
- View response omits raw prompt/raw response.
- Secret scan finds no OpenRouter key.
