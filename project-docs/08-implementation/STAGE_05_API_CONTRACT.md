# Stage 05 API Contract

## Status

- Document status: active API contract draft
- Scope: Stage05 Agent workflow, service draft filtering/actions, confirmation, customer reply send and Bitable-like views.
- Current Progress: 2026-07-07 API contract drafted before implementation. Task6 implemented Service Draft API filters/response fields. Task8 implemented confirmation response side-effect fields on the existing confirmation action route for customer reply send-request creation and business no-op evidence. Task9 implemented persisted customer reply send request linkage and reused Stage04 send confirmation/worker API behavior. Task10 implemented Stage05 Bitable-like view definitions and derived evidence fields locally.
- Current Progress Update: 2026-07-08 API/view contracts were exercised in Tencent Cloud staging for Stage05 acceptance: service drafts, pending confirmation, customer reply send requests, account inventory evidence, business no-op confirmation and safety-close readbacks were captured. Additional real Telegram traces generated recharge/BM invite drafts and a manual-review boundary for unsupported reporting/balance query.

## 1. Contract Principles

- API responses must be stable enough for Bitable-like views and later UI/Mini App to consume.
- All mutations require an actor and permission check.
- Agent cannot confirm drafts or send Telegram messages.
- LLM output is never accepted as authority to execute real provider actions.
- Errors use stable `detail` strings where current project patterns already do so.
- Secrets and raw prompts are not returned.

## 2. Agent Workflow API

### `POST /agent-runs/messages/{message_id}/run`

Manual trigger for a single message. Worker trigger may use the same service layer without exposing a public route.

Request:

```json
{
  "actor_type": "user",
  "actor_id": "00000000-0000-4000-8000-000000000001",
  "role": "manager",
  "mode": "real_openrouter",
  "force_retry": false
}
```

Fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `actor_type` | yes | `user`, `system` or internal actor type |
| `actor_id` | yes | Stable actor id |
| `role` | yes | Permission role |
| `mode` | no | `fake` or `real_openrouter`; default from config |
| `force_retry` | no | Allows manual retry from `agent_failed` or `manual_review`; does not bypass idempotency |

Success response:

```json
{
  "message_id": "uuid",
  "trace_id": "tg:184365902",
  "status": "routed",
  "agent_run_ids": ["uuid"],
  "draft_ids": ["uuid", "uuid"],
  "account_status_event_ids": ["uuid"],
  "manual_review_reasons": []
}
```

Errors:

| HTTP | `detail` | Meaning |
| --- | --- | --- |
| 404 | `message_not_found` | No message exists |
| 409 | `message_not_agent_ready` | Message state cannot enter Stage05 |
| 409 | `message_not_bound` | Message has no bound customer |
| 403 | `permission_denied` | Actor cannot run workflow |
| 503 | `openrouter_not_configured` | Real mode requested without server key |

## 3. Agent Run Read API

### `GET /agent-runs`

Filters:

- `trace_id`
- `message_id`
- `status`
- `agent_name`
- `limit`

Response:

```json
{
  "records": [
    {
      "id": "uuid",
      "agent_name": "message_intake_router",
      "graph_name": "stage05_supervisor",
      "model_provider": "openrouter",
      "model_name": "configured-model",
      "prompt_version": "stage05-router-v1",
      "status": "succeeded",
      "trace_id": "tg:184365902",
      "input_summary": {"message_count": 2, "redacted": true},
      "output_summary": {"intents": ["recharge", "customer_reply"]},
      "usage_summary": {"prompt_tokens": 1000, "completion_tokens": 400},
      "cost_summary": {"currency": "USD", "estimated_cost": "0.0000"},
      "latency_ms": 1300,
      "error_code": null,
      "created_entity_refs": [
        {"entity_type": "service_draft", "entity_id": "uuid"}
      ]
    }
  ]
}
```

This route must not return raw OpenRouter API key, full prompt or full raw response.

## 4. Service Draft API

### `GET /service-drafts`

Existing list endpoint is enhanced.

Filters:

- `status`
- `draft_type`
- `customer_id`
- `source_message_id`
- `trace_id`
- `limit`

Response record:

```json
{
  "id": "uuid",
  "draft_type": "recharge",
  "status": "pending_confirmation",
  "customer_id": "uuid",
  "source_message_id": "uuid",
  "created_by_type": "agent",
  "created_by_id": "recharge_draft_agent",
  "trace_id": "tg:184365902",
  "payload": {"account_hint": "act_123", "amount": "100", "currency": "USD"},
  "missing_fields": [],
  "risk_flags": [],
  "confidence": "0.9100",
  "created_at": "2026-07-07T00:00:00Z"
}
```

### `POST /confirmations/service-drafts/{draft_id}/actions`

Request:

```json
{
  "actor_type": "user",
  "actor_id": "00000000-0000-4000-8000-000000000001",
  "role": "manager",
  "action": "confirm",
  "reason": "approved for staging validation"
}
```

Response for `customer_reply`:

```json
{
  "draft_id": "uuid",
  "draft_status": "confirmed",
  "service_record_id": null,
  "execution_ticket_id": null,
  "telegram_send_request_id": "uuid",
  "side_effect": "customer_reply_send_request_created"
}
```

Response for business draft:

```json
{
  "draft_id": "uuid",
  "draft_status": "service_record_created",
  "service_record_id": "uuid",
  "execution_ticket_id": null,
  "telegram_send_request_id": null,
  "side_effect": "noop_service_evidence_created"
}
```

Errors:

| HTTP | `detail` | Meaning |
| --- | --- | --- |
| 404 | `service_draft_not_found` | Missing draft |
| 400 | `confirmation_required` | Request did not set `confirm=true` |
| 403 | `permission_denied` | Actor cannot confirm |
| 409 | `draft_not_confirmable` | Wrong status, missing fields, manual review or already terminal |
| 409 | `provider_execution_disabled` | Business draft tried to execute provider path |

### `POST /service-drafts/{draft_id}/reject`

Request:

```json
{
  "actor_type": "user",
  "actor_id": "uuid",
  "role": "manager",
  "reason": "duplicate customer request"
}
```

Response:

```json
{"draft_id": "uuid", "draft_status": "rejected"}
```

### `POST /service-drafts/{draft_id}/request-more-info`

Request:

```json
{
  "actor_type": "user",
  "actor_id": "uuid",
  "role": "sales",
  "missing_fields": ["amount", "currency"],
  "reason": "customer did not provide amount"
}
```

Response:

```json
{"draft_id": "uuid", "draft_status": "needs_more_info", "missing_fields": ["amount", "currency"]}
```

### `POST /service-drafts/{draft_id}/escalate`

Request:

```json
{
  "actor_type": "user",
  "actor_id": "uuid",
  "role": "sales",
  "reason": "account risk signal is ambiguous"
}
```

Response:

```json
{"draft_id": "uuid", "draft_status": "manual_review"}
```

## 5. Account Inventory Stage05 API

Stage05 should prefer using existing account inventory service boundaries. If HTTP APIs are added, they must remain internal authenticated routes.

### `POST /account-inventory/{account_id}/status-events`

Used by service layer or internal route to record explicit account status events.

Request:

```json
{
  "actor_type": "agent",
  "actor_id": "account_inventory_agent",
  "role": "agent",
  "event_type": "risk_controlled",
  "after_status": "risk_controlled",
  "reason": "customer message clearly reports account risk-control",
  "source_entity_type": "message",
  "source_entity_id": "uuid",
  "confidence": "0.9400"
}
```

Rules:

- Agent may use only allowed high-confidence abnormal statuses.
- API/service must reject automatic transitions to `reserved`, `allocated`, `activated`, `recycled` or `archived`.
- Replacement recommendation/reservation/distribution is not part of Stage05.

## 6. Customer Reply Send

Stage05 reuses Stage04 send request route. The visible Stage05 contract is through draft confirmation and views.

If `telegram_send_requests` gains `source_service_draft_id`, response records include it:

```json
{
  "request_id": "uuid",
  "source_service_draft_id": "uuid",
  "send_purpose": "customer_reply_rehearsal",
  "status": "pending_confirmation",
  "target_chat_id": "[masked]",
  "trace_id": "tg-send:uuid"
}
```

Send confirmation still follows Stage04 rules:

- Must be allowlisted at request/confirm/worker time.
- Must be explicitly confirmed.
- Worker must re-check allowlist.
- Result writes request status, Telegram response summary and audit.

## 7. Bitable-like Views

### `GET /views/service_drafts/records`

Fields:

- `draft_id`
- `draft_type`
- `status`
- `customer_id`
- `source_message_id`
- `created_by_type`
- `created_by_id`
- `confidence`
- `missing_fields`
- `risk_flags`
- `payload_summary`
- `trace_id`
- `created_at`

### `GET /views/agent_review_queue/records`

Fields:

- `review_id`
- `review_source`
- `customer_id`
- `message_id`
- `draft_id`
- `agent_run_id`
- `reason`
- `risk_flags`
- `last_error_code`
- `trace_id`
- `created_at`

### `GET /views/pending_confirmation/records`

Fields:

- `draft_id`
- `draft_type`
- `customer_id`
- `source_message_id`
- `confidence`
- `risk_flags`
- `confirm_action`
- `trace_id`
- `created_at`

### `GET /views/customer_reply_send_requests/records`

Fields:

- `request_id`
- `source_service_draft_id`
- `status`
- `requested_by_actor_id`
- `confirmed_by_actor_id`
- `telegram_response_summary`
- `last_error_code`
- `sent_at`
- `trace_id`

### Enhanced `telegram_inbox`

Stage05 may add or rely on:

- `intent_status`
- `intent_type`
- `agent_status`
- `draft_count`
- `agent_last_error_code`

### Enhanced `account_inventory`

Fields:

- `platform`
- `external_account_id`
- `inventory_status`
- `assigned_customer_id`
- `assigned_at`
- `status_reason`
- `last_risk_signal_at`
- `last_risk_source`
- `trace_id`

Rules:

- Manager/admin can see `external_account_id` for operational inventory handling.
- Customer-scoped actors can see only authorized customer rows and receive masked `external_account_id`.

## 8. Error Contract

Stable error detail names should be used in tests:

| Detail | Meaning |
| --- | --- |
| `message_not_found` | Agent target message missing |
| `message_not_agent_ready` | Wrong intent state |
| `message_not_bound` | No bound customer |
| `openrouter_not_configured` | Real LLM mode cannot run |
| `agent_output_invalid` | LLM output failed schema |
| `service_draft_not_found` | Draft missing |
| `draft_not_confirmable` | Wrong state or missing fields |
| `telegram_target_not_allowlisted` | Send target blocked |
| `account_status_transition_not_allowed` | Stage05 tried forbidden inventory transition |
| `permission_denied` | Role/action blocked |
