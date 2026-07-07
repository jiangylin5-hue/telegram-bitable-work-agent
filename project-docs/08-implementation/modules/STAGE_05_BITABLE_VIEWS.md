# Stage 05 Bitable Views

## Status

- Document status: active module design draft
- Scope: Stage05 Bitable-like operational views for draft handling, manual review, pending confirmation, customer reply sends, inbox and account inventory.
- Current Progress: 2026-07-07 Module design implemented locally in Task10. `service_drafts`, `agent_review_queue`, `pending_confirmation` and `customer_reply_send_requests` views now exist; `telegram_inbox` and `account_inventory` include Stage05 evidence fields where derivable. Focused view tests and Stage05 tests passed locally. Staging view evidence remains pending.

## 1. Purpose

Stage05 continues the project constitution: Agent work is complete only when it lands in table records, states and views. Since Stage05 does not implement UI, Bitable-like views are the operational surface for humans and tests.

## 2. View Set

| View | Purpose |
| --- | --- |
| `service_drafts` | All Stage05 drafts and their handling status |
| `agent_review_queue` | Messages/drafts/runs that need human review |
| `pending_confirmation` | Confirmable drafts |
| `customer_reply_send_requests` | Reply send request status |
| enhanced `telegram_inbox` | Message Agent state and draft count |
| enhanced `account_inventory` | Inventory state, abnormal accounts and assignment context |

## 3. `service_drafts` View

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

Sensitive handling:

- Payload details are summarized.
- Account external ids may be masked for non-global roles.
- Raw prompt/response never appears.

## 4. `agent_review_queue` View

Sources:

- `messages.intent_status = manual_review`
- `messages.intent_status = agent_failed`
- `service_drafts.status = manual_review`
- `agent_runs.status = failed`
- account status review events requiring human follow-up

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

Rules:

- A review row should link to the most actionable entity.
- Manager/admin can see cross-customer review queue.
- Sales/customer-scoped actors see only authorized customer records.

## 5. `pending_confirmation` View

Sources:

- `service_drafts.status = pending_confirmation`

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

Confirm action examples:

- `create_customer_reply_send_request`
- `create_noop_service_evidence`
- `confirm_account_assignment_draft`

Design note:

- `pending_confirmation` is an action queue, not a full detail view. It therefore follows the API contract and omits `payload_summary`; operators can open the same `draft_id` in the `service_drafts` view for the summarized payload.

## 6. `customer_reply_send_requests` View

Sources:

- `telegram_send_requests` rows with `send_purpose = customer_reply_rehearsal` or linked `source_service_draft_id`.

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

Sensitive:

- The Stage05-specific `customer_reply_send_requests` view does not project `target_chat_id`; target chat inspection remains limited to the generic Stage04 `telegram_send_requests` operational view where manager/admin can see it and scoped actors are masked or hidden.
- Telegram response summary masked or summarized for scoped users.

## 7. Enhanced `telegram_inbox`

Stage05 should make inbox show:

- `intent_status`
- `intent_type`
- `agent_status` if derived
- `draft_count`
- `agent_last_error_code`
- `trace_id`

This helps prove a Telegram message reached the Agent workflow.

## 8. Enhanced `account_inventory`

Fields useful for Stage05:

- `platform`
- `external_account_id` visible to manager/admin and masked for customer-scoped roles.
- `inventory_status`
- `assigned_customer_id`
- `assigned_at`
- `status_reason`
- `last_risk_signal_at` if implemented.
- `last_risk_source` if implemented.

Rows with `blocked`, `disabled`, `risk_controlled` should be easy to filter.

## 9. Row-Level Security

Views use existing application-level row filtering:

- Global roles can see all records.
- Customer-scoped roles can see rows linked to their customer.
- Unbound or conflict rows are hidden from customer-scoped roles unless explicitly authorized.

## 10. Tests

Required:

- Each Stage05 view exists.
- Fields match contract.
- Sensitive fields mask for scoped actor.
- Manager/admin sees operational evidence.
- `pending_confirmation` excludes non-confirmable drafts.
- `agent_review_queue` includes failed run/manual review rows.
- Existing Stage04 views still pass.

Implemented local test evidence:

- RED: `pytest tests\unit\test_stage05_bitable_views.py -v` failed 4/4 before implementation for missing Stage05 views/enhanced fields.
- GREEN: `pytest tests\unit\test_stage05_bitable_views.py -v` passed 5/5 after implementation.
- View regression: `pytest tests\unit\test_bitable_views.py tests\unit\test_stage03_telegram_inbox_view.py tests\unit\test_stage04_bitable_views.py tests\unit\test_stage05_bitable_views.py -v` passed 22/22.
- Stage05 regression at Task10 completion: `pytest tests -k stage05 -v` passed 68/68 selected tests.
- Latest Stage05 regression after Task12 local staging-contract preflight, scope guard, deployment config gate and redacted runtime summary command: `pytest tests -k stage05 -v` passed 82/82 selected tests.
