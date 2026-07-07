# Stage 04 Bitable Views Module

## Status

- Document status: active module design and local implementation note
- Scope: Stage04 Bitable-like view contracts for bindings, send requests, intent queue and updated inbox evidence.
- Current Progress: 2026-07-07 Stage04 views are implemented locally with focused view tests, existing view regression tests and local acceptance evidence for row-level safety. Staging data evidence remains pending.

## 1. Purpose

Bitable views are the product endpoint for Stage04. The backend can expose APIs and workers, but the stage is not considered operational unless each workflow lands in a table/view/status/audit combination that an operator can inspect.

This module documents:

- `telegram_bindings`
- `telegram_send_requests`
- `telegram_intent_queue`
- Updated `telegram_inbox`

It also documents how sensitive Telegram ids and send response summaries are projected or masked.

## 2. Implemented Files

| Layer | File | Responsibility |
| --- | --- | --- |
| View definitions | `backend/app/services/bitable_views.py` | Registers Stage04 view keys, projected fields, aliases and sensitive-field policy |
| View API | `backend/app/api/routes/views.py` | Existing `/views/{view_key}/records` route |
| View schemas | `backend/app/schemas/views.py` | Existing response shape |
| Tests | `backend/tests/unit/test_stage04_bitable_views.py` | Stage04 views, projection, masking and row-level filtering |
| Regression tests | `backend/tests/unit/test_bitable_views.py` | Existing Stage02/03 view behavior |

## 3. View Registry Rules

Every view definition includes:

| Property | Meaning |
| --- | --- |
| `view_key` | Public view key in `/views/{view_key}/records` |
| `table_name` | Source table in SQLAlchemy metadata or in-memory data source |
| `fields` | Stable projected field order |
| `field_aliases` | View field to source field mapping, such as `request_id -> id` |
| `sensitive_fields` | Fields masked from roles that should not inspect them |
| `sensitive_fields_visible_to_global_roles` | Allows `admin`/`manager` to inspect operational identifiers |

Projection rules:

- Unknown fields in the source record are omitted.
- Missing fields are omitted rather than filled with guessed values.
- `id` can be projected as a business view field through aliases.
- Records can be filtered by actor customer scope where a customer id is present.
- Views without customer scope, such as send request rows, are hidden from customer-scoped actors.

## 4. `telegram_bindings` View

Source:

```text
telegram_customer_bindings
```

Fields:

| Field | Source | Sensitive | Meaning |
| --- | --- | --- | --- |
| `binding_id` | `id` | no | Binding record id |
| `customer_id` | `customer_id` | no | Bound customer |
| `binding_scope` | `binding_scope` | no | `chat`, `user`, or `chat_user` |
| `telegram_chat_id` | `telegram_chat_id` | yes | Telegram chat id |
| `telegram_user_id` | `telegram_user_id` | yes | Telegram user id |
| `status` | `status` | no | `active` or `inactive` |
| `label` | `label` | no | Operator-readable label |
| `created_by` | `created_by` | no | Actor id that created row |
| `created_at` | `created_at` | no | Creation timestamp |
| `updated_at` | `updated_at` | no | Last update timestamp |

Visibility:

- `admin` and `manager` can inspect Telegram ids.
- Customer-scoped roles only see rows for their `customer_ids`.
- Customer-scoped roles receive `[masked]` for Telegram ids.
- Unscoped actors without global role cannot use this view as a raw Telegram id lookup.

Operational use:

- Find current active bindings.
- Verify a disable took effect.
- Investigate why a new message should or should not bind.
- Provide audit evidence for Stage04 binding operations.

## 5. `telegram_send_requests` View

Source:

```text
telegram_send_requests
```

Fields:

| Field | Source | Sensitive | Meaning |
| --- | --- | --- | --- |
| `request_id` | `id` | no | Send request id |
| `target_chat_id` | `target_chat_id` | yes | Test chat target |
| `status` | `status` | no | Request/send state |
| `requested_by_actor_id` | `requested_by_actor_id` | no | Requesting actor |
| `confirmed_by_actor_id` | `confirmed_by_actor_id` | no | Confirming actor |
| `telegram_response_summary` | `telegram_response_summary` | yes | Redacted Telegram API summary |
| `last_error_code` | `last_error_code` | no | Safe error code |
| `sent_at` | `sent_at` | no | Success timestamp |
| `trace_id` | `trace_id` | no | End-to-end trace |

Visibility:

- `admin` and `manager` can inspect operational target id and response summary in staging.
- Customer-scoped actors must not see send request rows because Stage04 test sends are internal operational evidence, not customer data.
- Bot token, webhook secret and raw Telegram API response must never appear.

Status evidence:

| Status | View meaning |
| --- | --- |
| `pending_confirmation` | Request created; no real Telegram send happened |
| `blocked` | Request was blocked by allowlist or safety rule |
| `confirmed` | Human confirmation occurred; outbox event should exist |
| `sending` | Worker started send attempt |
| `sent` | Telegram test chat send succeeded |
| `failed` | Telegram send failed with safe error |

Stage04 currently uses `pending_confirmation`, `blocked`, `confirmed`, `sending`, `sent` and `failed` in code paths. `draft`, `queued` and `cancelled` remain reserved design states unless later implementation adds them.

## 6. `telegram_intent_queue` View

Source:

```text
messages
```

Fields:

| Field | Source | Sensitive | Meaning |
| --- | --- | --- | --- |
| `message_id` | `id` | no | Message record id |
| `customer_id` | `customer_id` | no | Resolved customer |
| `binding_status` | `binding_status` | no | Binding result |
| `intent_status` | `intent_status` | no | Placeholder/intent state |
| `intent_type` | `intent_type` | no | Null in Stage04 placeholder flow |
| `processing_status` | `processing_status` | no | Worker status |
| `received_at` | `received_at` | no | Telegram receive time |
| `trace_id` | `trace_id` | no | Trace |

Purpose:

- Show messages that are ready for future intent extraction.
- Provide evidence that Stage04 did not call LLM but prepared the boundary.
- Keep raw message text out of the placeholder queue view.

Expected rows:

- Bound processed messages can appear with `intent_status=intent_ready`.
- Unbound messages can appear with `needs_review` if the data source includes them, but operators should treat them as manual binding queue rather than AI-ready work.
- `intent_type` remains `null` unless a later stage performs real classification.

## 7. Updated `telegram_inbox`

Stage03 already created `telegram_inbox`. Stage04 relies on it to show:

| Field | Stage04 use |
| --- | --- |
| `customer_id` | Proves new-message binding result |
| `binding_status` | Shows `bound`, `needs_manual_binding`, or `binding_conflict` |
| `processing_status` | Shows worker progress |
| `outbox_status` | Shows outbox processing evidence |
| `intent_status` | Shows placeholder readiness |
| `intent_type` | Remains null for no-LLM placeholder |

Stage04 does not add raw text exposure to unauthorized users.

## 8. Masking And Access Matrix

| Role type | Binding ids | Send target id | Send response summary | Customer-scoped records |
| --- | --- | --- | --- | --- |
| `admin` | visible | visible | visible summary only | all |
| `manager` | visible | visible | visible summary only | all |
| `sales` | masked if record visible | no send rows | no send rows | own `customer_ids` only |
| `customer_service` | masked unless explicitly allowed later | no send rows | no send rows | own `customer_ids` only |
| `agent` | masked/limited | no send rows | no send rows | scoped by allowed customer ids |

Mask value:

```text
[masked]
```

## 9. Error Behavior

| Situation | Behavior |
| --- | --- |
| Unknown view key | 404 `unknown_view` |
| Source table missing in metadata | Empty records, not server error |
| Source field missing | Field omitted |
| Actor cannot view record customer | Record filtered out |
| Field is sensitive and actor lacks global role | Field value becomes `[masked]` |

## 10. Test Evidence

| Requirement | Automated evidence |
| --- | --- |
| Stage04 views project expected fields | `test_stage04_views_project_binding_send_request_and_intent_queue` |
| Telegram ids masked for sales actor | `test_stage04_views_mask_telegram_identifiers_for_sales_actor` |
| Customer-scoped actors cannot see unbound/conflict inbox or send request rows | `test_stage04_views_hide_unbound_conflict_and_send_rows_from_sales_actor` |
| Existing views still work | `tests/unit/test_bitable_views.py` |
| SQLAlchemy data source still reads metadata tables | `tests/unit/test_bitable_views.py::test_sqlalchemy_bitable_data_source_reads_metadata_table_rows` |

Focused command:

```text
cd backend; pytest tests/unit/test_stage04_bitable_views.py -v
cd backend; pytest tests/unit/test_bitable_views.py -v
```

## 11. Not Implemented In Stage 04

- No front-end Bitable UI.
- No saved user-specific view filters.
- No view editing API.
- No export endpoint.
- No production-grade row-level policy engine beyond current actor/customer filtering.
- No customer-facing send request visibility.
