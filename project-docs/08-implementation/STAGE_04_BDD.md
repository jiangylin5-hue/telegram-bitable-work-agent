# Stage 04 Behavior Driven Development

## Status

- Document status: active BDD
- Scope: Stage 04 可验收行为、测试映射和业务证据。
- Current Progress: 2026-07-07 Local automated evidence has been mapped to implemented Stage04 behavior, including binding filters, customer existence, inactive binding semantics, restricted test-send confirm boundaries, outbox `request_id` projection and failed-send state. Manual staging evidence for real webhook binding and allowlisted Telegram test send remains pending.

## 1. Feature: Telegram Binding Management API

### Scenario 1.1: Authorized manager creates chat binding

Given:

- Actor role is `manager` or `admin`.
- Customer `C1` exists.
- No active chat binding exists for `telegram_chat_id = 1001`.

When:

- Actor posts `POST /telegram/bindings` with `binding_scope = chat`, `telegram_chat_id = 1001`, `customer_id = C1`.

Then:

- One `telegram_customer_bindings` row exists.
- `status = active`.
- `telegram_bindings` view shows the binding.
- `ops_audit_events` includes `telegram.binding.created`.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_manager_can_create_list_and_disable_binding`

### Scenario 1.2: Unauthorized actor cannot create binding

Given:

- Actor role is `sales`.
- Customer `C1` exists.

When:

- Actor posts `POST /telegram/bindings`.

Then:

- API returns 403.
- No binding row is created.
- `ops_audit_events` includes `permission_denied`.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_sales_create_is_forbidden_and_audited`

### Scenario 1.3: Active binding conflict is rejected

Given:

- Active chat binding for `telegram_chat_id = 1001` already points to customer `C1`.

When:

- Actor attempts to create another active chat binding for `telegram_chat_id = 1001` and customer `C2`.

Then:

- API returns 409 `telegram_binding_conflict`.
- Existing binding remains unchanged.
- Audit records conflict evidence.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_rejects_active_conflict`

### Scenario 1.4: Unknown customer cannot be bound

Given:

- Actor role is `manager` or `admin`.
- Customer `C-missing` does not exist.

When:

- Actor posts `POST /telegram/bindings` with `customer_id = C-missing`.

Then:

- API returns 404 FastAPI `detail`.
- No binding row is created.
- No binding-created or conflict audit is written.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_unknown_customer_is_rejected_before_create`

### Scenario 1.5: Binding can be disabled

Given:

- Active binding `B1` exists.
- Actor has `manage_telegram_binding`.

When:

- Actor posts `POST /telegram/bindings/{B1}/disable`.

Then:

- Binding status becomes `inactive`.
- `telegram_bindings` view shows inactive status.
- Audit includes `telegram.binding.disabled`.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_manager_can_create_list_and_disable_binding`

### Scenario 1.6: Unauthorized actor cannot list or disable bindings

Given:

- Actor role is `sales`.
- A binding may or may not exist.

When:

- Actor queries `GET /telegram/bindings`, or posts `POST /telegram/bindings/{binding_id}/disable`.

Then:

- API returns 403.
- Binding state is not changed.
- `ops_audit_events` includes `permission_denied`.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_sales_list_is_forbidden_and_audited`
- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_sales_disable_is_forbidden_and_audited`

### Scenario 1.7: Binding list filters are applied safely

Given:

- Actor has `manage_telegram_binding`.
- Multiple bindings exist with different Telegram chat/user ids.

When:

- Actor queries `GET /telegram/bindings` with `telegram_chat_id`,
  `telegram_user_id` and `status = active`.

Then:

- API returns only matching rows.
- Empty result is `{"bindings": []}` with HTTP 200.
- Successful listing does not write audit or commit a mutation.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_list_filters_by_telegram_ids_and_empty_result`

### Scenario 1.8: Invalid binding list status is rejected

Given:

- Actor has `manage_telegram_binding`.

When:

- Actor queries `GET /telegram/bindings?status=archived`.

Then:

- API returns FastAPI/Pydantic 422.
- No audit or mutation commit occurs.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_list_rejects_invalid_status_filter`

### Scenario 1.9: Missing binding disable returns stable not-found error

Given:

- Actor has `manage_telegram_binding`.
- Binding id does not exist.

When:

- Actor posts `POST /telegram/bindings/{binding_id}/disable`.

Then:

- API returns 404 `telegram_binding_not_found`.
- No binding row is changed.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_disable_missing_binding_returns_stable_error`

### Scenario 1.10: Inactive binding does not block replacement binding

Given:

- An inactive `chat_user` binding exists for chat `1001` and user `2002`.
- Actor has `manage_telegram_binding`.

When:

- Actor creates a new binding with the same chat/user/customer shape.

Then:

- API creates a new active binding.
- The old binding remains inactive.
- No active-conflict error is returned.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_inactive_binding_does_not_block_new_active_binding`

### Scenario 1.11: Re-disable inactive binding keeps inactive state

Given:

- Binding `B1` already has `status = inactive`.
- Actor has `manage_telegram_binding`.

When:

- Actor posts `POST /telegram/bindings/{B1}/disable`.

Then:

- API returns disabled status.
- Binding remains `inactive`.
- Audit records before and after states as inactive.

Evidence:

- Automated: `tests/integration/test_stage04_binding_management.py::test_binding_api_disable_inactive_binding_is_idempotent_state_set`

## 2. Feature: New Message Uses Binding

### Scenario 2.1: New message after binding resolves customer

Given:

- Active `chat_user` binding links chat `1001`, user `2002` to customer `C1`.
- Telegram webhook secret is valid.

When:

- A new Telegram update arrives from chat `1001`, user `2002`.

Then:

- Message has `customer_id = C1`.
- `binding_status = bound`.
- `telegram_inbox` shows bound customer.
- Audit includes `telegram.binding.resolved`.

Evidence:

- Automated: `tests/integration/test_stage04_new_message_binding.py::test_stage04_chat_user_binding_takes_precedence_for_new_messages`
- Automated: `tests/integration/test_stage04_new_message_binding.py::test_stage04_chat_binding_resolves_new_messages`
- Automated: `tests/integration/test_stage04_new_message_binding.py::test_stage04_user_binding_resolves_new_messages`

### Scenario 2.2: Disabled binding is ignored for new messages

Given:

- A matching binding exists with `status = inactive`.

When:

- A new Telegram update arrives.

Then:

- Message has no `customer_id`.
- `binding_status = needs_manual_binding`.
- Audit includes `telegram.binding.unbound`.

Evidence:

- Automated: `tests/integration/test_stage04_new_message_binding.py::test_stage04_inactive_binding_is_ignored_for_new_messages`

### Scenario 2.3: Binding changes do not rewrite historical messages

Given:

- Historical message `M1` is `needs_manual_binding`.
- Actor creates a new binding for `M1`'s chat.

When:

- No replay or manual recompute is requested.

Then:

- Historical message `M1` remains unchanged.
- A later message from the same chat is bound.

Evidence:

- Automated: `tests/integration/test_stage04_new_message_binding.py::test_stage04_new_binding_does_not_rewrite_historical_messages`

## 3. Feature: Intent Placeholder Without LLM

### Scenario 3.1: Bound message becomes intent ready

Given:

- Incoming message is bound to a customer.
- `LLM_ENABLED=false`.

When:

- Worker processes `telegram.message_received`.

Then:

- Message processing succeeds.
- Message `intent_status` becomes `intent_ready` or `intent_pending`.
- `telegram_intent_queue` view shows the message.
- Audit includes `telegram.intent_placeholder.ready`.
- No `agent_runs` row for OpenRouter call is created.
- No `service_drafts` row is created.

Evidence:

- Automated: `tests/integration/test_stage04_intent_placeholder.py::test_bound_message_becomes_intent_ready_without_service_draft`

### Scenario 3.2: Existing worker records placeholder boundary without creating draft

Given:

- `telegram.message_received` outbox event exists for a bound message.

When:

- Worker handles the existing message-received event.

Then:

- Event is processed.
- Audit includes `telegram.intent_placeholder.ready`.
- No OpenRouter call occurs.
- No formal business draft is created.

Evidence:

- Automated: `tests/integration/test_stage04_intent_placeholder.py::test_bound_message_becomes_intent_ready_without_service_draft`
- Automated: `tests/integration/test_stage04_intent_placeholder.py::test_unbound_message_does_not_become_intent_ready`

## 4. Feature: Restricted Telegram Test Send

### Scenario 4.1: Test send request requires confirmation

Given:

- Actor has permission to request a test send.
- `target_chat_id` is allowlisted.

When:

- Actor posts `POST /telegram/send-requests`.

Then:

- A `telegram_send_requests` row exists.
- `status = pending_confirmation`.
- No Telegram API call occurs yet.
- Audit includes `telegram.test_send.requested`.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_api_creates_pending_confirmation_without_outbox`

### Scenario 4.2: Confirmed test send to allowlisted chat is sent

Given:

- A pending send request targets an allowlisted test chat.
- Confirming actor is `manager` or `admin`.
- `TELEGRAM_SEND_MODE=restricted_test`.
- `TELEGRAM_BOT_TOKEN` is configured in staging only.

When:

- Actor confirms the send request.
- Worker processes the send outbox event.

Then:

- Send request status becomes `sent`.
- Telegram response summary is recorded.
- Audit includes `telegram.test_send.sent`.
- `telegram_send_requests` view shows sent result.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_confirm_queues_outbox_event`
- Automated: `tests/integration/test_stage04_test_send.py::test_send_worker_sends_allowlisted_confirmed_request_once`
- Manual staging: record real Telegram test chat evidence in `STAGE_04_ACCEPTANCE_CHECKLIST.md`.

### Scenario 4.3: Confirmation must be explicit

Given:

- A pending send request exists.
- Actor has `confirm_test_telegram_send`.

When:

- Actor posts `POST /telegram/send-requests/{request_id}/confirm` with `confirm = false`.

Then:

- API returns 400.
- Request remains `pending_confirmation`.
- No outbox event is created.
- No confirmation or blocked audit is written.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_confirm_false_is_rejected_without_side_effects`

### Scenario 4.4: Non-allowlisted target is blocked at request time

Given:

- A send request targets a chat id not in `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`.

When:

- Actor posts `POST /telegram/send-requests`.

Then:

- Request status becomes `blocked`.
- `last_error_code` is `telegram_test_send_target_not_allowlisted`.
- No outbox event is created.
- No Telegram API call occurs.
- Audit includes `telegram.test_send.requested` with `target_allowed=false`.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_non_allowlisted_target_is_blocked`

### Scenario 4.4A: Previously allowed target is blocked before send

Given:

- A send request was created as `pending_confirmation` or confirmed while allowlisted.
- The target is no longer in the current server-side allowlist.

When:

- Actor attempts to confirm, or worker attempts to send.

Then:

- Request status becomes `blocked`.
- No Telegram API call occurs.
- Audit includes `telegram.test_send.blocked`.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_confirm_blocks_when_allowlist_changes`
- Automated: `tests/integration/test_stage04_test_send.py::test_send_worker_rechecks_allowlist_before_sending`

### Scenario 4.5: Unauthorized actor cannot request or confirm test send

Given:

- Actor role is `sales`.

When:

- Actor posts `POST /telegram/send-requests`, or posts `POST /telegram/send-requests/{request_id}/confirm`.

Then:

- API returns 403.
- No send request is created by unauthorized request.
- No outbox event is created by unauthorized confirmation.
- `ops_audit_events` includes `permission_denied`.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_sales_create_is_forbidden_and_audited`
- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_sales_confirm_is_forbidden_and_audited`

### Scenario 4.6: Missing send request returns stable not-found error

Given:

- Actor has `confirm_test_telegram_send`.
- Send request id does not exist.

When:

- Actor posts `POST /telegram/send-requests/{request_id}/confirm`.

Then:

- API returns 404 `telegram_send_request_not_found`.
- No outbox event is created.

Evidence:

- Automated: `tests/integration/test_stage04_test_send.py::test_send_request_confirm_missing_request_returns_stable_error`

### Scenario 4.7: Customer group send is out of scope

Given:

- A customer group chat id exists.
- The chat id is not in the test-send allowlist.

When:

- Actor attempts to use it as a test send target.

Then:

- Request is blocked.
- Audit records safe reason.
- No customer group receives a message.

Evidence:

- Automated invariant: `tests/integration/test_stage04_test_send.py::test_send_request_non_allowlisted_target_is_blocked` blocks any target not in `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`, including customer group ids.
- Manual staging: record that no customer group send occurred.

## 5. Feature: Bitable Views

### Scenario 5.1: Telegram bindings view exposes safe fields

Given:

- One active and one inactive binding exist.

When:

- Actor queries `/views/telegram_bindings/records`.

Then:

- Response includes binding id, customer id, scope, status, label and timestamps.
- Response does not include secrets.
- Permission filtering applies.

Evidence:

- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_project_binding_send_request_and_intent_queue`
- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_mask_telegram_identifiers_for_sales_actor`
- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_hide_unbound_conflict_and_send_rows_from_sales_actor`

### Scenario 5.2: Telegram send requests view exposes status evidence

Given:

- Send requests exist in pending, sent and blocked states.

When:

- Actor queries `/views/telegram_send_requests/records`.

Then:

- Response includes status, target chat id masked as needed, safe response summary and error code.
- Bot token is not present.

Evidence:

- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_project_binding_send_request_and_intent_queue`
- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_mask_telegram_identifiers_for_sales_actor`
- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_hide_unbound_conflict_and_send_rows_from_sales_actor`

### Scenario 5.3: Telegram intent queue view exposes placeholder state

Given:

- Messages exist with `intent_ready`, `intent_pending` and `needs_review`.

When:

- Actor queries `/views/telegram_intent_queue/records`.

Then:

- Response includes message id, customer id, intent status, binding status and trace id.
- Raw text is not exposed to unauthorized actors.

Evidence:

- Automated: `tests/unit/test_stage04_bitable_views.py::test_stage04_views_project_binding_send_request_and_intent_queue`

## 6. Stage 04 BDD Acceptance

Stage 04 BDD is accepted only when:

- Every automated scenario above maps to a test before implementation is called complete.
- Manual staging scenario includes timestamp, redacted endpoint, target test chat policy and observed send request/audit evidence.
- No scenario requires customer group send, OpenRouter call, provider write or funds movement.
- Every workflow ends in Bitable view/status/audit evidence.
