# Stage 04 Intent Placeholder Module

## Status

- Document status: active module design and local implementation note
- Scope: No-LLM intent placeholder state and queue boundary for future Message Intake Router Agent.
- Current Progress: 2026-07-07 No-LLM intent placeholder is implemented locally and verified in staging. Real bound update `184365902` became `intent_ready` in `telegram_inbox`, audit event `telegram.intent_placeholder.ready` was written for message `caec8652-4495-47e5-8345-3d1c7993a15d`, and staging kept `LLM_ENABLED=false`.

## 1. Purpose

Intent Placeholder prepares the system for Stage 05 LLM/Agent intent extraction without enabling OpenRouter or creating business drafts in Stage 04.

## 2. Responsibilities

- Mark bound messages as ready for future intent extraction.
- Reuse the existing `telegram.message_received` outbox event in Stage 04; a separate placeholder outbox event is deferred.
- Expose ready/pending messages in `telegram_intent_queue`.
- Write audit evidence.
- Prove no LLM call and no formal `service_drafts` creation.

## 3. State Semantics

| Status | Meaning |
| --- | --- |
| `intent_ready` | message is bound and eligible for future extraction |
| `intent_pending` | placeholder job boundary is queued |
| `intent_placeholder_recorded` | placeholder processed without LLM |
| `intent_failed` | placeholder failed safely |

These statuses are not business intent classifications.

## 4. Forbidden Behavior

- No OpenRouter call.
- No LangGraph production graph.
- No service draft creation.
- No customer reply.
- No provider execution.

## 5. Acceptance

- Bound message becomes intent-ready.
- Placeholder audit exists.
- `telegram_intent_queue` view shows the message.
- Tests prove no `service_drafts` rows are created.

## 6. Implemented Files

| Layer | File | Responsibility |
| --- | --- | --- |
| Service | `backend/app/services/telegram_intent_placeholder.py` | Applies no-LLM placeholder transition and writes audit |
| Worker | `backend/app/workers/stage03_handlers.py` | Calls placeholder service while handling `telegram.message_received` |
| View | `backend/app/services/bitable_views.py` | Projects `telegram_intent_queue` |
| Tests | `backend/tests/integration/test_stage04_intent_placeholder.py` | Proves bound messages become ready and unbound messages do not |
| Regression tests | `backend/tests/integration/test_stage03_worker_runtime.py` | Proves worker processing still succeeds with new audit event |

## 7. Detailed Runtime Behavior

Stage04 intentionally does not create a new independent placeholder outbox event. Instead, the existing Stage03 worker event is reused:

```text
telegram.message_received
-> load outbox event
-> load message
-> mark processing/outbox as processed
-> if message is bound and unclassified:
     set intent_status = intent_ready
     set intent_type = null
     write telegram.intent_placeholder.ready audit
-> write telegram.message_processed audit
-> commit
```

The design reason is conservative: Stage04 proves the boundary without creating a second asynchronous workflow that would look like production Agent orchestration. A later Stage05 can add a dedicated `agent.intent_extract` event after LLM/LangGraph design is confirmed.

## 8. Transition Matrix

| Input `binding_status` | Input `intent_status` | Output `intent_status` | Audit | Meaning |
| --- | --- | --- | --- | --- |
| `bound` | `unclassified` | `intent_ready` | `telegram.intent_placeholder.ready` | Message is ready for future extraction |
| `bound` | `intent_ready` | `intent_ready` | no duplicate placeholder audit on idempotent rerun | Already prepared |
| `bound` | `needs_review` | `needs_review` | no placeholder audit | Manual state preserved |
| `needs_manual_binding` | `needs_review` | `needs_review` | no placeholder audit | Not eligible until bound |
| `binding_conflict` | `needs_review` | `needs_review` | no placeholder audit | Conflict requires human resolution |
| any | `routed` | `routed` | no placeholder audit | Existing Stage02 mock routing state is preserved |

Only the first row is an active Stage04 transition.

## 9. State Semantics

| Status | Stage04 implementation status | Meaning |
| --- | --- | --- |
| `needs_review` | implemented from Stage03 ingestion | Human binding/review needed |
| `unclassified` | implemented from Stage03 ingestion | Bound but not yet prepared by worker |
| `intent_ready` | implemented in Stage04 | Bound and ready for future intent extraction |
| `intent_pending` | reserved | Future dedicated placeholder/Agent job queued |
| `intent_placeholder_recorded` | reserved | Future dedicated placeholder event processed |
| `intent_failed` | reserved | Future placeholder/Agent boundary failure |

Reserved statuses are documented to avoid future schema churn, but Stage04 local code only sets `intent_ready`.

## 10. No-LLM And No-Draft Guarantees

Stage04 must not:

- Instantiate OpenRouter client for placeholder.
- Call LangGraph production graph.
- Insert `agent_runs` for LLM inference.
- Insert `service_drafts`.
- Set `intent_type` to a business classification such as recharge, bind card, account production or reporting.
- Send any Telegram reply.

The placeholder is not a classifier. It is a durable marker saying:

```text
this message is bound and safe for a later confirmed intent-extraction stage to inspect
```

## 11. Bitable Evidence

`telegram_intent_queue` exposes:

| Field | Expected Stage04 value |
| --- | --- |
| `message_id` | Internal message id |
| `customer_id` | Present for bound messages |
| `binding_status` | Usually `bound` for ready items |
| `intent_status` | `intent_ready` |
| `intent_type` | `null` |
| `processing_status` | `processed` after worker |
| `trace_id` | Original Telegram trace |

`telegram_inbox` also shows the same `intent_status`, so operators can inspect either the inbox or the intent queue.

## 12. Audit Contract

| Event | When | Required fields |
| --- | --- | --- |
| `telegram.intent_placeholder.ready` | Bound unclassified message becomes ready | message id, customer id, binding status, intent status |
| `telegram.message_processed` | Message worker completes | message id, binding status, intent status, processing/outbox status |

Audit must avoid wording that implies completed AI classification.

## 13. Idempotency

If the worker is called again after the message is already processed:

- It returns without changing the message again.
- It does not write another placeholder audit.
- It does not create a service draft.
- It does not call any external service.

This keeps Redis ack/retry edge cases from producing duplicate business state.

## 14. Test Evidence

| Requirement | Automated evidence |
| --- | --- |
| Bound message becomes `intent_ready` | `test_bound_message_becomes_intent_ready_without_service_draft` |
| No service draft is created | same test checks no audit entity is `service_draft`; full suite covers service draft creation separately |
| Unbound message remains `needs_review` | `test_unbound_message_does_not_become_intent_ready` |
| Stage03 worker still processes messages | `tests/integration/test_stage03_worker_runtime.py` |
| View exposes placeholder state | `tests/unit/test_stage04_bitable_views.py` |

Focused command:

```text
cd backend; pytest tests/integration/test_stage04_intent_placeholder.py -v
cd backend; pytest tests/integration/test_stage03_worker_runtime.py -v
cd backend; pytest tests/unit/test_stage04_bitable_views.py -v
```

## 15. Not Implemented In Stage 04

- No dedicated `agent.intent_extract` outbox event.
- No LLM prompt.
- No LangGraph node.
- No vector retrieval.
- No formal business intent result.
- No service draft.
- No customer reply.
