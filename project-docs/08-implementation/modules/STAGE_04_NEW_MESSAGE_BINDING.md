# Stage 04 New Message Binding Module

## Status

- Document status: active module design and local implementation note
- Scope: Future Telegram messages use active customer bindings while historical messages remain unchanged.
- Current Progress: 2026-07-07 New-message binding behavior is covered locally by Stage04 regression tests for `chat_user`, `chat`, `user`, inactive binding and no historical rewrite. Existing Stage03 ingestion implementation already satisfied the Stage04 rules; no production code change was required for Task 4.

## 1. Purpose

New Message Binding is the runtime bridge between binding operations and the Telegram inbox. Binding records are only valuable if future incoming messages use them consistently and safely.

This module proves:

- Active bindings affect future messages.
- Disabled bindings do not affect future messages.
- Historical messages are not rewritten automatically.
- Conflicts do not guess a customer.
- Binding evidence lands in `messages`, `telegram_inbox` and `ops_audit_events`.

It is not a history replay engine, customer identity verification system, or Telegram access-control system.

## 2. Implemented Files

| Layer | File | Responsibility |
| --- | --- | --- |
| Binding resolver | `backend/app/services/customer_binding.py` | Resolves active `chat_user`, `chat`, `user` records with precedence |
| Telegram ingestion | `backend/app/services/telegram_ingestion.py` | Applies resolver result to new `messages` rows and audit |
| Webhook route | `backend/app/api/routes/telegram_webhook.py` | Receives real Telegram updates and uses ingestion service |
| Mock route | `backend/app/api/routes/mock_telegram.py` | Supports local tests without Telegram |
| View service | `backend/app/services/bitable_views.py` | Projects binding status into `telegram_inbox` and `telegram_intent_queue` |
| Tests | `backend/tests/integration/test_stage04_new_message_binding.py` | Covers Stage04 binding rules for future messages |
| Regression tests | `backend/tests/integration/test_stage03_customer_binding.py` | Proves Stage03 resolver behavior remains compatible |

## 3. Input Data

### 3.1 Telegram Update Fields

The resolver relies on fields extracted from an inbound Telegram update:

| Field | Source | Required for binding |
| --- | --- | --- |
| `telegram_chat_id` | Telegram message chat id | Required for `chat` and `chat_user` matching |
| `telegram_user_id` | Telegram sender user id | Required for `user` and `chat_user` matching |
| `telegram_update_id` | Telegram update id | Used for idempotency/evidence |
| `telegram_message_id` | Telegram message id | Used with chat id for uniqueness |
| `text` / `caption` | Telegram message content | Not used for binding decision |

### 3.2 Binding Records

Only these binding rows participate:

```text
telegram_customer_bindings.status = active
```

Rows with `inactive`, malformed ids or missing required ids are ignored by the resolver. The API/schema prevents newly created malformed bindings, but the resolver still treats inactive/non-matching rows safely.

## 4. Resolution Algorithm

Resolution order:

```text
1. active chat_user binding where chat id and user id both match
2. active chat binding where chat id matches
3. active user binding where user id matches
4. legacy customer_group fallback if configured
5. no binding -> needs_manual_binding
```

The first matching precedence level wins. Lower-precedence matches must not override a higher-precedence match.

Conflict rule:

- If multiple active bindings match the same precedence level, the resolver returns `binding_conflict`.
- Conflict means `customer_id` must remain `None`.
- The system must not choose the first row, latest row, or any guessed customer.

## 5. State Outcomes

| Resolver outcome | `messages.customer_id` | `messages.binding_status` | `messages.intent_status` | Audit |
| --- | --- | --- | --- | --- |
| Bound by `chat_user` | matched customer | `bound` | `unclassified` | `telegram.binding.resolved` |
| Bound by `chat` | matched customer | `bound` | `unclassified` | `telegram.binding.resolved` |
| Bound by `user` | matched customer | `bound` | `unclassified` | `telegram.binding.resolved` |
| Legacy customer group fallback | matched customer | `bound` | `unclassified` | binding resolution evidence |
| No active binding | `None` | `needs_manual_binding` | `needs_review` | `telegram.binding.unbound` |
| Same-level active conflict | `None` | `binding_conflict` | `needs_review` | `telegram.binding.conflict` |
| Matching inactive binding only | `None` | `needs_manual_binding` | `needs_review` | `telegram.binding.unbound` |

Stage04 intent placeholder later changes bound messages from `unclassified` to `intent_ready` when the worker processes the message. That is a separate module and does not change the binding decision.

## 6. Historical Message Rule

Binding changes are prospective only:

```text
old message arrives unbound
-> binding is created
-> old message remains unbound
-> next matching message becomes bound
```

Stage04 intentionally does not:

- Recompute old `messages.customer_id`.
- Rewrite old `messages.binding_status`.
- Backfill old audit events.
- Re-enqueue old messages.
- Create service drafts from old messages.

If a future stage needs manual replay, it must define a separate replay API, permission, audit event, idempotency rule and Bitable endpoint.

## 7. Bitable Evidence

The binding outcome must appear in `/views/telegram_inbox/records`:

| Field | Meaning |
| --- | --- |
| `message_id` | Internal message record id |
| `telegram_chat_id` | Source chat id, masked by role if required |
| `telegram_user_id` | Source sender id, masked by role if required |
| `customer_id` | Resolved customer, or null |
| `binding_status` | `bound`, `needs_manual_binding`, or `binding_conflict` |
| `processing_status` | Worker processing state |
| `intent_status` | Placeholder/intent state |
| `trace_id` | End-to-end trace |

The binding source itself appears in `/views/telegram_bindings/records`.

## 8. Audit Contract

| Event | When | Required evidence |
| --- | --- | --- |
| `message_ingested` | Message record is stored | message id, binding status, intent status |
| `telegram.binding.resolved` | Binding maps message to customer | customer id and binding status |
| `telegram.binding.unbound` | No active match exists | source ids and manual binding status |
| `telegram.binding.conflict` | Same-level active conflict | conflict status and no guessed customer |
| `telegram.message_processed` | Worker finishes message | final binding/processing/outbox state |

Audit must not treat a Telegram username or profile field as proof of customer identity.

## 9. Edge Cases

| Case | Required behavior |
| --- | --- |
| Missing `telegram_user_id` | `chat` matching can still work; `user` and `chat_user` cannot match |
| Missing `telegram_chat_id` | Real Telegram message should not reach this state; fail safe if parser rejects it |
| Same chat, different users | `chat` binding maps all users in that chat unless a more specific `chat_user` binding exists |
| Same user in multiple chats | `user` binding maps user across chats unless a `chat_user` or `chat` binding has higher precedence |
| Disabled exact binding and active broad binding | disabled exact is ignored; active broad can match |
| Active exact binding and active broad binding | exact `chat_user` wins |
| Multiple active exact bindings | conflict; no customer guessed |
| Binding created while message is already queued | Existing queued message keeps its stored `customer_id` and `binding_status` |

## 10. Test Evidence

| Requirement | Automated evidence |
| --- | --- |
| `chat_user` precedence | `test_stage04_chat_user_binding_takes_precedence_for_new_messages` |
| `chat` binding | `test_stage04_chat_binding_resolves_new_messages` |
| `user` binding | `test_stage04_user_binding_resolves_new_messages` |
| inactive ignored | `test_stage04_inactive_binding_is_ignored_for_new_messages` |
| no historical rewrite | `test_stage04_new_binding_does_not_rewrite_historical_messages` |
| Stage03 binding still compatible | `tests/integration/test_stage03_customer_binding.py` |

Focused command:

```text
cd backend; pytest tests/integration/test_stage04_new_message_binding.py -v
cd backend; pytest tests/integration/test_stage03_customer_binding.py -v
```

## 11. Not Implemented In Stage 04

- No history replay.
- No binding approval workflow beyond manager/admin permission.
- No customer-facing claim/verification flow.
- No Telegram command-based binding.
- No UI for resolving conflicts.
- No automatic creation of customers from Telegram senders.
