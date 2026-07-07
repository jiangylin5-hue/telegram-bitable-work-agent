# Stage 05 Draft Agents

## Status

- Document status: active module design draft
- Scope: Recharge, card binding, BM invite, customer reply and account assignment draft generation.
- Current Progress: 2026-07-07 Task 5 Draft Agent and `service_drafts` metadata implementation completed locally after user confirmed approach A. Four deterministic child agents, Stage05 draft candidate schema, additive service_drafts metadata migration and workflow multi-draft persistence are implemented and covered by local tests. Account inventory, confirmation/send, provider writes and staging calls remain out of scope for Task 5.

## 1. Purpose

Draft Agents convert Router intents into structured, reviewable `service_drafts`. They are not execution agents. They prepare business records for human confirmation and later controlled execution stages.

## 2. Shared Draft Contract

Every draft candidate contains:

```text
draft_type
status
intent_type
intent_index
payload
payload_summary
missing_fields
risk_flags
confidence
source_message_id
source_agent_run_id
created_by_type = agent
created_by_id = <child agent name>
trace_id
idempotency_key
```

Status rules:

- `pending_confirmation`: enough required fields and no blocking risk.
- `needs_more_info`: intent clear but required fields missing.
- `manual_review`: risk/ambiguity too high.

Idempotency:

```text
draft:{message_id}:{draft_type}:{intent_index}
```

## 2.1 Confirmed Task 5 Implementation

Task 5 changed the draft Agent contract and the `service_drafts` persistence shape, so it required explicit user confirmation before code or migration changes. The user confirmed approach A on 2026-07-07.

Implemented approach A:

- Keep Stage02/Stage04 `DraftCandidate` and mock router compatibility intact.
- Add a Stage05-specific draft candidate schema for child Agent outputs.
- Implement the four Task 5 child Agents as deterministic pure functions:
  - `recharge_draft_agent`
  - `card_binding_draft_agent`
  - `bm_invite_draft_agent`
  - `customer_reply_draft_agent`
- Add an additive Alembic migration for nullable `service_drafts` metadata:
  - `source_agent_run_id`
  - `intent_index`
  - `payload_summary`
  - `review_reason`
  - `confirmed_at`
- Do not add a first-class `intent_type` column in Task 5. Keep `intent_type` in the candidate contract and in redacted summary/audit metadata unless the user explicitly requests a database column.
- Integrate Stage05 workflow so selected child Agents create one or more service drafts with idempotency key `draft:{message_id}:{draft_type}:{intent_index}`.
- Keep `account_assignment` and `account_status_exception` for 05.4 Account Inventory Agent.
- Do not confirm drafts, create Telegram send requests, call providers, allocate accounts, send customer messages or perform staging calls.

Implemented files:

- `backend/app/agents/recharge_draft_agent.py`
- `backend/app/agents/card_binding_draft_agent.py`
- `backend/app/agents/bm_invite_draft_agent.py`
- `backend/app/agents/customer_reply_draft_agent.py`
- `backend/app/agents/schemas.py`
- `backend/app/services/service_drafts.py`
- `backend/app/services/agent_workflows.py`
- `backend/app/models/service_drafts.py`
- `backend/alembic/versions/20260707_0013_stage05_service_draft_metadata.py`

Local verification:

- RED: `pytest tests\unit\test_stage05_child_agents.py tests\integration\test_stage05_agent_workflow.py::test_workflow_routes_bound_intent_ready_message_and_records_agent_run -v` failed 8/8 before implementation.
- GREEN: the same command passed 8/8 after implementation.
- Workflow/worker regression: `pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v` passed 9/9.
- Old draft compatibility: `pytest tests\unit\test_mock_router_agent.py tests\unit\test_service_drafts_api.py tests\unit\test_service_draft_state_machine.py -v` passed 16/16.

Compatibility constraints from current code:

- `service_drafts` already has `draft_type`, `status`, `customer_id`, `source_message_id`, `payload`, `missing_fields`, `risk_flags`, `confidence`, `trace_id` and unique `idempotency_key`.
- Existing unit tests expect `/service-drafts?status=...` to keep returning the current basic record shape.
- Existing confirmation tests expect `pending_confirmation` drafts to confirm/reject/request-more-info/escalate without requiring Stage05 metadata.
- Existing mock router tests expect old idempotency key shape and `created_by_id="mock_router"` to keep working.

## 3. Recharge Draft Agent

### Required fields

- account hint or resolved account id.
- amount.
- currency.

### Optional fields

- requested payment profile hint.
- customer note.
- urgency.

### Payload example

```json
{
  "account_hint": "act_123",
  "amount": "100",
  "currency": "USD",
  "customer_message_summary": "Customer requested recharge.",
  "provider_execution_allowed": false
}
```

### Edge cases

| Case | Handling |
| --- | --- |
| Missing amount | `needs_more_info`, missing `amount`, `currency` if absent |
| Account ambiguous | `manual_review` or `needs_more_info` depending evidence |
| Currency unsupported | `manual_review` |
| Account marked blocked | `manual_review` and risk flag |
| Customer not bound | no draft from Stage05 |

## 4. Card Binding Draft Agent

### Required fields

- account hint or account id.
- tokenized card/payment profile reference or safe card resource hint.

### Forbidden fields

- raw card number.
- CVV.
- full card image.
- unmasked payment credentials.

### Payload example

```json
{
  "account_hint": "act_123",
  "payment_profile_hint": "profile_label_or_tokenized_ref",
  "one_card_one_account_policy": true,
  "provider_execution_allowed": false
}
```

### Edge cases

| Case | Handling |
| --- | --- |
| Raw card data detected | `manual_review`; do not persist raw sensitive field |
| Missing account | `needs_more_info` |
| Missing payment profile | `needs_more_info` |
| Account blocked | `manual_review` |

## 5. BM Invite Draft Agent

### Required fields

- BM hint or id.
- invitee/contact hint.
- customer id.

### Payload example

```json
{
  "bm_hint": "bm_abc",
  "invitee_hint": "user@example.com",
  "customer_id": "uuid",
  "provider_execution_allowed": false
}
```

### Edge cases

| Case | Handling |
| --- | --- |
| Missing invitee | `needs_more_info` |
| Missing BM hint | `needs_more_info` |
| Invite target ambiguous | `manual_review` |
| Message asks to execute immediately | Still draft only; no provider call |

## 6. Customer Reply Draft Agent

### Required fields

- reply text.
- source message.
- target context.

### Payload example

```json
{
  "reply_text": "我们正在确认账户和资料，稍后同步进度。",
  "reply_language": "zh",
  "source_summary": "Customer asked for recharge and BM invite.",
  "send_allowed_scope": "staging_allowlisted_test_chat_only"
}
```

### Safety rules

- Reply text must not promise completed actions unless there is evidence.
- Reply text must not expose internal errors or secrets.
- Reply text must not be sent without human confirmation.
- Stage05 send goes only to allowlisted private test chat.

## 7. Account Assignment Draft

Owned by Account Inventory Agent but persisted as a draft.

Required:

- customer id.
- request type.
- candidate account ids only if safely selected for human review.

Forbidden:

- direct allocation.
- direct activation.
- replacement recommendation after automatic block.

## 8. Manual Review Policy

Draft Agents should choose manual review when:

- Router confidence is low.
- Multiple account/customer candidates conflict.
- Sensitive data appears.
- Action would exceed Stage05 scope.
- Provider execution is requested by the customer.
- Account replacement would be needed after block.

Manual review must include reason codes in payload or risk flags.

## 9. Audit Events

For each created draft:

- `agent.draft_created`
- entity type `service_draft`
- entity id draft id
- draft type/status
- missing fields
- risk flags
- source message id
- child agent name

For each skipped/blocked draft:

- `agent.manual_review_requested`
- reason.

## 10. Tests

Required:

- Each agent creates correct draft on complete input.
- Each agent creates `needs_more_info` on missing required fields.
- Sensitive card data is not persisted.
- Customer reply does not create send request until confirmation.
- Multiple intents create multiple drafts with distinct idempotency keys.
