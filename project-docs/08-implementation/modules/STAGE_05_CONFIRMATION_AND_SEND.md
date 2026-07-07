# Stage 05 Confirmation And Send

## Status

- Document status: active module design draft
- Scope: Service draft confirmation, customer reply allowlisted send, business no-op evidence, idempotency and audit.
- Current Progress: 2026-07-07 Module design created before implementation. Task8 Confirmation Branches implemented locally. Task9 Customer Reply Send Request implemented locally: send requests now persist `source_service_draft_id`, `send_purpose` and `message_text_summary`; send confirmation checks the current allowlist; the existing Stage04 worker re-checks allowlist and records customer-reply-specific sent/failed audit events.

## 1. Purpose

This module turns Stage05 drafts into confirmed evidence. It deliberately separates:

- customer reply draft confirmation, which may create an allowlisted Telegram send request;
- business draft confirmation, which may create service/no-op evidence only;
- real provider execution, which remains out of scope.

## 2. Confirmation Matrix

| Draft type | Confirm result | Real external call |
| --- | --- | --- |
| `customer_reply` | `telegram_send_requests` row created or reused by `reply-send:{draft_id}` trace; persisted draft FK remains Task9 | Telegram only after allowlisted confirmation |
| `recharge` | `service_records` + no-op `execution_logs` | none |
| `card_binding` | `service_records` + no-op `execution_logs` | none |
| `bm_invite` | `service_records` + no-op `execution_logs` | none |
| `account_assignment` | `service_records` + no-op `execution_logs`; no automatic inventory assignment confirmation | none |
| `account_status_review` | manual review; no direct confirmation side effect unless designed in service | none |

## 3. Confirmable States

Confirm allowed:

- `pending_confirmation`

Confirm blocked:

- `needs_more_info`
- `manual_review`
- `confirmed`
- `service_record_created`
- `rejected`
- `blocked`

Missing fields always block confirmation.

## 4. Customer Reply Send Flow

```text
customer_reply draft pending_confirmation
-> human confirm
-> draft confirmed
-> telegram_send_requests row created/linked
-> explicit send confirmation
-> allowlist check
-> outbox event
-> worker allowlist re-check
-> Telegram Bot sendMessage
-> sent/failed status + audit
```

Stage05 may combine draft confirmation and send-request creation, but Telegram send still requires Stage04-style explicit send confirmation and allowlist checks.

## 5. Business Draft No-Op Flow

```text
business draft pending_confirmation
-> human confirm
-> service_records row
-> execution_logs provider=noop, execution_status=skipped
-> draft status service_record_created
-> audit
```

No provider adapter is called. The no-op log exists to prove that a human-confirmed business request was recorded but not executed.

## 6. Idempotency

| Operation | Key |
| --- | --- |
| Customer reply send request | `reply-send:{draft_id}` |
| Service record | `service:{draft_id}` |
| No-op execution log | `noop-execution:{service_record_id}` |

Repeated confirmation must not:

- create duplicate send requests;
- create duplicate service records;
- create duplicate no-op logs;
- re-send Telegram messages.

Stable conflict is acceptable for repeated confirm after terminal state.

Task9 persists `source_service_draft_id`, `send_purpose` and `message_text_summary` on `telegram_send_requests`. `reply-send:{draft_id}` remains the service-level reuse key, and `source_service_draft_id` is the Bitable/query linkage.

## 7. Permission Rules

Confirm:

- manager/admin only.

Reject:

- sales/manager/admin depending scope.

Request more info:

- sales/manager/admin depending scope.

Send customer reply:

- manager/admin only.
- staging allowlist only.

Agent:

- cannot confirm.
- cannot send.
- cannot create real execution ticket.

## 8. Error Cases

| Case | Handling |
| --- | --- |
| Draft missing | 404 |
| Draft wrong status | 409 |
| Draft has missing fields | 409 |
| Actor lacks permission | 403 + audit permission denied |
| Customer reply target not allowlisted | send request blocked; no Telegram call |
| Telegram API failure | request failed; safe error code |
| Provider path accidentally requested | blocked; no provider call |

## 9. Audit Events

Required:

- `draft_confirmed`
- `draft_rejected`
- `draft_more_info_requested`
- `draft_escalated`
- `customer_reply_send_requested`
- `customer_reply_send_confirmed`
- `customer_reply_send_sent`
- `customer_reply_send_failed`
- `business_noop_evidence_created`

Audit must include actor, role, trace id, entity id and safe before/after state.

## 10. Tests

Required:

- `customer_reply` confirmation creates linked send request. Completed locally by `test_customer_reply_confirmation_creates_send_request_without_ticket_or_outbox`.
- non-allowlisted target blocks send request creation and later send-confirm/worker paths. Completed locally by `test_customer_reply_confirmation_blocks_non_allowlisted_target_without_outbox`, `test_customer_reply_send_confirm_blocks_allowlist_drift_without_outbox` and `test_customer_reply_worker_rechecks_allowlist_before_send`.
- customer reply send confirmation and fake worker send pass through the reused Stage04 send worker. Completed locally by `test_customer_reply_draft_to_confirmed_send_request_to_fake_worker_send`.
- business draft confirmation creates service/no-op evidence. Completed locally by `test_stage05_business_confirmation_creates_noop_evidence_without_ticket`.
- wrong state confirmation fails. Completed locally by `test_stage05_confirmation_wrong_states_return_stable_conflict_without_side_effects`.
- agent actor cannot confirm. Completed locally by `test_agent_cannot_confirm_stage05_draft_and_denial_is_audited`.
- duplicate confirmation does not duplicate side effects. Completed locally by `test_stage05_business_confirmation_repeated_call_does_not_duplicate_side_effects`.
- Stage04 send request tests still pass. Completed locally by `pytest tests\integration\test_stage04_test_send.py -v`.
