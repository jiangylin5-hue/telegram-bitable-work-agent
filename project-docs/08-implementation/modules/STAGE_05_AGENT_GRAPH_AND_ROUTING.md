# Stage 05 Agent Graph And Routing

## Status

- Document status: active module design draft
- Scope: Stage05 Supervisor graph, Message Intake Router, worker trigger, graph state, routing policy and persistence boundary.
- Current Progress: 2026-07-07 Module design created before implementation. User confirmed Phase 05.2 technical approach A, and Task 3 StateGraph-compatible state/router schema plus Task 4 Supervisor Graph/workflow service/worker delegation completed local TDD verification.

## 1. Purpose

This module upgrades Stage04 `intent_ready` from a placeholder status into a real Agent workflow. It receives a bound Telegram message, calls the Message Intake Router through OpenRouter, selects child agents, coordinates their outputs and persists the final results.

The module is the orchestration layer only. It does not own business state transitions directly; it calls services that own `service_drafts`, `account_inventory`, `agent_runs`, `messages` and audit.

## 2. Non-Goals

This module does not:

- Execute provider operations.
- Confirm drafts.
- Send Telegram messages.
- Produce accounts.
- Replace accounts.
- Store full prompt/raw response in operational views.
- Implement RAG or pgvector retrieval.

## 3. Inputs

Required:

- `message_id`
- `trace_id`
- bound `customer_id`
- message text/caption summary
- Stage04 binding status

Optional context:

- recent messages for the same customer/chat
- open service drafts for the same customer
- existing customer account inventory summary
- known account status for account hints

Context must be minimal and redacted. The graph must not include secrets or raw sensitive payment details.

## 4. Outputs

Possible outputs:

- One or more `service_drafts`
- One or more `account_status_events`
- Message state transition to `routed`, `manual_review` or `agent_failed`
- `agent_runs` evidence
- `ops_audit_events`
- Viewable records through `service_drafts`, `agent_review_queue`, `pending_confirmation`, `telegram_inbox`

## 5. Graph State

```text
Stage05WorkflowState
- trace_id
- message_id
- customer_id
- source_text_summary
- context_summary
- router_result
- selected_agents
- draft_candidates
- account_status_actions
- manual_review_reasons
- agent_run_ids
- created_entity_refs
- status
- errors
```

Rules:

- `source_text_summary` is a redacted summary or normalized text reference; do not duplicate full sensitive payload unnecessarily.
- `router_result` must be schema-validated before any child Agent runs.
- `created_entity_refs` records persisted ids after service calls.
- Graph state is not the business source of truth; PostgreSQL is.

## 5.1 Confirmed Task 3 Technical Approach

User confirmed approach A on 2026-07-07. The Task 3 implementation approach is intentionally conservative and aligned with official LangGraph patterns:

- Represent Stage05 workflow state as a LangGraph `StateGraph`-compatible typed state object.
- Keep Router result validation in Pydantic v2 schemas before any child Agent runs.
- Reuse the existing OpenRouter adapter boundary for structured LLM calls instead of binding business code to a specific model.
- Do not introduce `langgraph-supervisor-py` in Task 3 unless a later confirmed requirement needs the extra abstraction.
- Do not implement the deferred Agent skills/capabilities runtime registry in Task 3.

Task 3 implemented the confirmed schema and router boundary in `stage05_state.py`, `schemas.py` and `message_intake_router.py`. Supervisor execution, child Agent execution, persistence and worker integration remain later tasks.

## 5.2 Confirmed Task 4 Supervisor Graph Implementation

Task 4 connects the Task 3 schema/router boundary into workflow execution. User confirmed the approach on 2026-07-07.

The proposed approach is:

- Use official LangGraph `StateGraph` with `Stage05WorkflowState`.
- Keep graph nodes narrow and testable instead of embedding database writes directly inside model/router code.
- Inject router/LLM and persistence services so local tests use fakes and never require real OpenRouter, Redis, Telegram or provider calls.
- Let `agent_workflows.py` own message state transitions, AgentRun evidence and future persistence calls.
- Let `stage05_supervisor.py` own node order and workflow status mapping.
- Let `stage03_handlers.py` only detect the existing `bound + intent_ready` transition and delegate to the workflow service.
- Limit Task 4 to workflow execution evidence, `agent_running` / `routed` / `manual_review` / `agent_failed` status mapping and duplicate trigger handling. Child draft generation, account inventory mutation, confirmation/send and staging remain later tasks.

Implemented Task 4 behavior:

- `stage05_supervisor.py` builds an official LangGraph `StateGraph` with `mark_running`, `route_message`, `apply_policy` and `finalize_message` nodes.
- `agent_workflows.py` owns Stage05 message status transitions and AgentRun evidence for Router calls.
- `stage03_handlers.py` accepts an optional `stage05_workflow` trigger and delegates only when a message is `bound`, has a customer id and is `intent_ready`.
- Local tests cover happy path, manual review, invalid Router output, LLM runtime failure, duplicate workflow trigger and Stage04 placeholder preservation.

Not implemented in Task 4:

- Child Agent draft generation.
- Service draft persistence.
- Account inventory mutations.
- Confirmation/send behavior.
- Real OpenRouter, Redis runtime, Telegram send or staging calls.

Compatibility notes from the current codebase:

- `stage03_handlers.py` already uses a unit-of-work boundary with in-memory and SQLAlchemy implementations, which is compatible with service injection for Stage05 workflow tests.
- `handle_telegram_message_received` currently calls `apply_telegram_intent_placeholder` and records `telegram.message_processed`; Task 4 must preserve that Stage04 behavior for messages that do not enter Stage05 workflow execution.
- Existing Stage04 tests require a bound unclassified message to become `intent_ready` without creating `service_draft` records. Task 4 may trigger Stage05 after `intent_ready`, but must not turn Stage04 placeholder into immediate business draft persistence.
- `agent_runs.py` already exposes success and failure evidence helpers; Task 4 should reuse these helpers rather than creating a parallel evidence model.
- Worker retry/dead-letter behavior is already centralized in Stage03 runtime tests. Task 4 should fit that path and avoid introducing separate retry semantics in the worker handler.

## 6. Node Design

### `load_context`

Responsibilities:

- Load message.
- Verify `binding_status = bound`.
- Verify `customer_id` exists.
- Verify `intent_status = intent_ready` unless manual retry rules apply.
- Load compact context.

Failure:

- message missing -> stable not found.
- unbound -> manual review/no-op.
- wrong state -> conflict/no-op.

### `mark_running`

Responsibilities:

- Set `messages.intent_status = agent_running`.
- Write `agent.workflow_started`.

This happens before OpenRouter call so stuck/failed runs are visible.

### `route_message`

Responsibilities:

- Build Router LLM request.
- Call OpenRouter or fake client.
- Validate JSON.
- Persist Router `agent_runs`.

Failure:

- OpenRouter missing config -> `agent_failed`.
- timeout/network -> `agent_failed`.
- invalid JSON -> `agent_failed`.

### `select_child_agents`

Mapping:

| Intent | Child agent |
| --- | --- |
| `recharge` | Recharge Draft Agent |
| `card_binding` | Card Binding Draft Agent |
| `bm_invite` | BM Invite Draft Agent |
| `customer_reply` | Customer Reply Draft Agent |
| `account_assignment` | Account Inventory Agent |
| `account_status_exception` | Account Inventory Agent |
| `irrelevant` | no child agent; mark ignored/manual depending policy |
| `unknown` | manual review |

### `run_child_agents`

Responsibilities:

- Run selected child agents.
- Collect draft candidates, account status actions and review reasons.
- Preserve intent index for idempotency.

Child agents may return no output if their intent is invalid or unsupported. That must become manual review, not silent success.

### `apply_policy`

Rules:

- Any high-risk output without allowed automatic status action enters manual review.
- Missing required draft fields -> `needs_more_info`.
- Complete and safe draft -> `pending_confirmation`.
- High-confidence account exception -> allowed automatic status action.
- Replacement/reallocation suggestions are discarded and converted to manual review because Stage05 forbids them.

### `persist_results`

Responsibilities:

- Create drafts with idempotency keys.
- Create account status events through Account Inventory service.
- Persist AgentRun created entity refs.
- Write audit events.

### `finalize_message`

Rules:

- If drafts or account status events were created, message becomes `routed`.
- If no safe output but review is required, message becomes `manual_review`.
- If an execution failure occurred, message becomes `agent_failed`.

## 7. Router Prompt Contract

The Router prompt must instruct the model:

- Return JSON only.
- Identify multiple intents when present.
- Do not invent account ids, customer ids, payment profiles or statuses.
- Mark missing fields explicitly.
- Use `unknown` if evidence is insufficient.
- Preserve account hints as strings, not confirmed records.
- Do not claim provider actions succeeded.

Output must include:

- `intents`
- `overall_confidence`
- `requires_manual_review`
- `manual_review_reasons`
- `redacted_summary`

## 8. Idempotency

The workflow must tolerate:

- duplicate outbox/Redis delivery
- manual retry after transient failure
- worker restart

Rules:

- Existing successful draft idempotency keys prevent duplicate drafts.
- A retry from `agent_failed` may create a new `agent_runs` row but must not duplicate previously persisted drafts.
- Account status event idempotency prevents duplicate high-risk status events for same message/account/status.

## 9. Audit Events

Required events:

- `agent.workflow_started`
- `agent.router_completed`
- `agent.router_failed`
- `agent.child_agent_completed`
- `agent.draft_created`
- `agent.manual_review_requested`
- `agent.workflow_completed`
- `agent.workflow_failed`

Each event includes:

- `trace_id`
- actor type/id
- entity type/id
- before/after state where applicable
- safe summary
- permission snapshot if a permission check was involved

## 10. Tests

Unit:

- Router schema validation.
- Intent-to-agent selection.
- Policy mapping.

Integration:

- bound message happy path.
- duplicate delivery.
- invalid JSON.
- OpenRouter failure.
- low confidence manual review.
- multiple child agents.

Regression:

- Stage04 `intent_placeholder` still produces `intent_ready`.
- Stage03 worker runtime still handles previous events.
