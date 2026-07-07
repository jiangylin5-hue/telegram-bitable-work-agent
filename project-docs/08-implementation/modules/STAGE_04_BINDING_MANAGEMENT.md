# Stage 04 Binding Management Module

## Status

- Document status: active module design and local implementation note
- Scope: Internal API and service behavior for Telegram customer binding management.
- Current Progress: 2026-07-07 Binding management service/API is implemented locally with 15 focused tests covering permission, schema validation, create/list/disable, customer existence, list filters, inactive replacement, idempotent disable, conflict and audit. Staging verification remains pending.

## 1. Purpose

Binding Management lets internal authorized actors connect Telegram chats/users to customers so future inbound messages can land in customer-scoped Bitable views.

It is not a user management system, tenant model, or Telegram permission system.

## 2. Responsibilities

- Validate actor can manage binding.
- Validate binding scope and Telegram identifiers.
- Create active binding.
- Reject active conflicts.
- Disable binding.
- List bindings for operational review.
- Write audit events.

## 3. Scope Rules

| Scope | Required ids | Match meaning |
| --- | --- | --- |
| `chat` | `telegram_chat_id` | any sender in the chat maps to customer |
| `user` | `telegram_user_id` | user maps to customer when user id is present |
| `chat_user` | both | user maps to customer only inside the chat |

Resolution precedence:

```text
chat_user
-> chat
-> user
-> needs_manual_binding
```

## 4. Audit

Required events:

- `telegram.binding.created`
- `telegram.binding.disabled`
- `telegram.binding.create_conflict`
- `permission_denied`

Audit payload must include binding scope and redacted ids where needed. It must not include secrets.

## 5. Acceptance

- Authorized actor can create/list/disable binding.
- Unauthorized actor cannot create/disable binding.
- Active conflict is rejected.
- Inactive binding is ignored by future message resolution.
- Historical messages are not rewritten.

## 6. Implemented Files

| Layer | File | Responsibility |
| --- | --- | --- |
| API route | `backend/app/api/routes/telegram_bindings.py` | Exposes create/list/disable endpoints and maps stable HTTP errors |
| Service | `backend/app/services/telegram_binding_management.py` | Performs permission checks, customer existence check, conflict detection, state changes and audit writes |
| Schemas | `backend/app/schemas/telegram_bindings.py` | Validates create/list/disable request and response contracts |
| Permissions | `backend/app/services/permissions.py` | Adds `manage_telegram_binding` action for `manager`; `admin` keeps wildcard permission |
| Model | `backend/app/models/telegram.py` | Reuses `TelegramCustomerBinding` from Stage03 |
| App wiring | `backend/app/main.py` | Registers the binding route |
| Tests | `backend/tests/integration/test_stage04_binding_management.py` | Covers permissions, schema validation, create/list/disable, conflict and audit |

## 7. API Behavior

### 7.1 Create Binding

Endpoint:

```text
POST /telegram/bindings
```

Request fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `customer_id` | yes | Existing customer id to bind |
| `binding_scope` | yes | `chat`, `user`, or `chat_user` |
| `telegram_chat_id` | depends | Required for `chat` and `chat_user` |
| `telegram_user_id` | depends | Required for `user` and `chat_user` |
| `label` | no | Operator-readable label |
| `created_by` | no | Optional actor override; defaults to current actor id |

Validation matrix:

| Scope | `telegram_chat_id` | `telegram_user_id` | Valid |
| --- | --- | --- | --- |
| `chat` | present | absent or present | yes; `telegram_chat_id` is the matching key |
| `chat` | absent | any | no |
| `user` | absent or present | present | yes; `telegram_user_id` is the matching key |
| `user` | any | absent | no |
| `chat_user` | present | present | yes; both ids are matching keys |
| `chat_user` | missing | present | no |
| `chat_user` | present | missing | no |

Create flow:

```text
request
-> Pydantic scope/id validation
-> build Actor from internal dependency
-> assert `manage_telegram_binding`
-> verify customer exists
-> check active binding conflict for same scope/key
-> insert `telegram_customer_bindings.status=active`
-> write `telegram.binding.created` audit
-> commit
-> return binding id and status
```

Conflict rules:

- Conflict checks only consider `status=active`.
- `chat` conflicts on active `(binding_scope=chat, telegram_chat_id)`.
- `user` conflicts on active `(binding_scope=user, telegram_user_id)`.
- `chat_user` conflicts on active `(binding_scope=chat_user, telegram_chat_id, telegram_user_id)`.
- A disabled/inactive binding does not block a later new active binding.
- Conflict returns 409 with `telegram_binding_conflict`; it does not overwrite the old binding.
- Conflict writes `telegram.binding.create_conflict` audit.

Permission failures:

- `sales`, `agent`, `customer_service`, `finance` and `production` cannot create bindings unless later docs explicitly change the action allowlist.
- Permission failure writes `permission_denied` audit and returns 403.
- Permission failure must not create any binding row.

Unknown customer behavior:

- A create request for a non-existent `customer_id` returns FastAPI 404 `detail`.
- It does not create a binding row.
- It does not write `telegram.binding.created` or `telegram.binding.create_conflict`
  audit, because no binding state transition or binding conflict occurred.
- Stage 04 does not currently define a custom stable error code for this case.
  If the API contract should expose `telegram_binding_customer_not_found`, that
  must be confirmed as a contract change before implementation.

### 7.2 List Bindings

Endpoint:

```text
GET /telegram/bindings
```

Supported filters:

| Filter | Meaning |
| --- | --- |
| `customer_id` | Return bindings for one customer |
| `telegram_chat_id` | Return bindings involving one chat id |
| `telegram_user_id` | Return bindings involving one user id |
| `status` | `active` or `inactive` |

List behavior:

- Listing is read-only.
- Listing requires `manage_telegram_binding`, because it exposes operational Telegram identifiers.
- Successful listing does not write audit.
- Unauthorized listing writes `permission_denied` audit and returns 403.
- Results expose operational identifiers through the internal API; Bitable view masking still applies for non-global actors.
- Empty result is a successful `bindings: []`, not an error.

### 7.3 Disable Binding

Endpoint:

```text
POST /telegram/bindings/{binding_id}/disable
```

Disable flow:

```text
request
-> assert `manage_telegram_binding`
-> load binding by id
-> set `status=inactive`
-> update timestamp
-> write `telegram.binding.disabled` audit
-> commit
-> return disabled status
```

Disable behavior:

- Disable only affects future message resolution.
- It does not rewrite historical `messages.customer_id` or `messages.binding_status`.
- Disabling an already inactive row is allowed by the current service as an idempotent state set; if stricter behavior is required later, it must be documented as a state-machine change first.
- Missing binding returns stable not-found error.

## 8. Resolution Behavior For New Messages

Binding resolution itself remains in the Stage03 ingestion path, but Stage04 depends on the following rules:

```text
active chat_user exact match
-> active chat match
-> active user match
-> legacy customer_group fallback if present
-> needs_manual_binding
```

Important cases:

| Case | Expected result |
| --- | --- |
| Exact `chat_user` and broader `chat` both match | `chat_user` wins |
| Only `chat` matches | message is bound to chat customer |
| Only `user` matches | message is bound to user customer |
| Matching binding is `inactive` | ignored; message remains unbound or uses another active match |
| Multiple active records match same precedence | `binding_conflict`; no customer is guessed |
| Binding is created after old message | old message remains unchanged |
| New message after binding | new message resolves with current active binding |

## 9. Bitable Endpoints

| Workflow | Endpoint evidence |
| --- | --- |
| Binding created | `/views/telegram_bindings/records` shows active row |
| Binding disabled | `/views/telegram_bindings/records` shows inactive row |
| Future message bound | `/views/telegram_inbox/records` shows `binding_status=bound` and `customer_id` |
| Conflict | `/views/telegram_inbox/records` shows `binding_status=binding_conflict` |

Sensitive fields:

- `telegram_chat_id` and `telegram_user_id` are operational identifiers.
- `admin` and `manager` may inspect them for operations.
- Customer-scoped roles see masked values through Bitable views.

## 10. Audit Contract

| Event | When | Required evidence |
| --- | --- | --- |
| `telegram.binding.created` | Active binding created | binding id, customer id, scope, status |
| `telegram.binding.disabled` | Binding disabled | before/after status and reason if supplied |
| `telegram.binding.create_conflict` | Active conflict rejected | attempted customer, scope and Telegram id shape |
| `permission_denied` | Actor lacks `manage_telegram_binding` | action, role and actor type |

Audit must not include:

- Bot token.
- Webhook secret.
- Database URL.
- Redis URL.
- Any payment credential.

## 11. Test Evidence

| Requirement | Automated evidence |
| --- | --- |
| Manager has binding permission | `test_manager_can_manage_telegram_bindings_and_test_sends` |
| Sales lacks binding permission | `test_sales_cannot_manage_telegram_bindings_or_test_sends` |
| Schema validates scope/id requirements | `test_binding_create_schema_requires_chat_id_for_chat_scope`; `test_binding_create_schema_rejects_missing_scope_identifier` |
| Manager create/list/disable works | `test_binding_api_manager_can_create_list_and_disable_binding` |
| Unauthorized create is blocked and audited | `test_binding_api_sales_create_is_forbidden_and_audited` |
| Unknown customer is rejected before create | `test_binding_api_unknown_customer_is_rejected_before_create` |
| Unauthorized list is blocked and audited | `test_binding_api_sales_list_is_forbidden_and_audited` |
| List filters by Telegram ids and empty result is successful | `test_binding_api_list_filters_by_telegram_ids_and_empty_result` |
| Invalid list status filter is rejected | `test_binding_api_list_rejects_invalid_status_filter` |
| Unauthorized disable is blocked and audited | `test_binding_api_sales_disable_is_forbidden_and_audited` |
| Missing binding disable returns stable error | `test_binding_api_disable_missing_binding_returns_stable_error` |
| Inactive binding does not block new active binding | `test_binding_api_inactive_binding_does_not_block_new_active_binding` |
| Disable inactive binding is current idempotent state set | `test_binding_api_disable_inactive_binding_is_idempotent_state_set` |
| Active conflict is rejected | `test_binding_api_rejects_active_conflict` |
| New messages use active bindings | `tests/integration/test_stage04_new_message_binding.py` |
| Stage03 binding behavior still works | `tests/integration/test_stage03_customer_binding.py` |

Focused command:

```text
cd backend; pytest tests/integration/test_stage04_binding_management.py -v
cd backend; pytest tests/integration/test_stage04_new_message_binding.py -v
cd backend; pytest tests/integration/test_stage03_customer_binding.py -v
```

## 12. Not Implemented In Stage 04

- No UI for binding management.
- No Telegram command to create binding.
- No bulk import of bindings.
- No historical replay/recompute of old unbound messages.
- No customer-facing notification.
- No automatic customer identity proofing from Telegram profile alone.
