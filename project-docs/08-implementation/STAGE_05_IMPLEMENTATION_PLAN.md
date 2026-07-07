# Stage 05 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 05 Agent capability loop from real Telegram `intent_ready` messages to OpenRouter-powered multi-intent routing, child-agent draft creation, account inventory risk marking, confirmation, allowlisted customer-reply test send and Bitable-like evidence.

**Architecture:** Reuse Stage 04 Telegram ingestion, binding, Redis Streams, service draft, confirmation, Telegram send request and Bitable view foundations. Add LangGraph-first Supervisor orchestration, a structured OpenRouter Router, focused child draft agents, account inventory exception handling, stronger `agent_runs` evidence and business-first views. PostgreSQL remains the business fact source; Redis remains runtime delivery; OpenRouter and Telegram sends are the only real external calls in Stage 05, both gated and audited.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis Streams, LangGraph, OpenRouter-compatible Chat Completions, Telegram Bot API `sendMessage`, pytest, Docker Compose staging.

## Status

- Document status: active implementation plan draft
- Scope: Stage 05 documentation and future code task breakdown.
- Current Progress: 2026-07-08 Stage05 scope confirmed by user and documentation package created. Phase 05.1 Task 1 and Task 2, Phase 05.2 Task 3 and Task 4, Phase 05.3 Task 5 and Task 6, Phase 05.4 Task 7, Phase 05.5 Tasks 8-9, Phase 05.6 Task10, Task11 and Task12 local readiness have completed local verification. Task12 was explicitly approved by user on `2026-07-08 00:15:10 +08:00`; Step 1 is complete. Real Tencent Cloud deployment, staging migration, real OpenRouter, real Telegram allowlisted receipt, staging no-op/account-exception evidence and safety close remain pending execution. No dependency install, staging env change, OpenRouter call or real Telegram send has been executed yet after approval.

## Global Constraints

- All workflows must terminate in Bitable-like records, statuses, views, audit events or execution evidence.
- Account Inventory Agent does not produce accounts; it only manages distribution, inventory state and exceptions.
- High-confidence account risk/block/disabled events may be automatically marked through backend service and audit; replacement account recommendation/reservation/distribution is out of scope.
- `customer_reply` is the only Stage05 draft type that can lead to a real Telegram send, and only to staging allowlisted private test chat.
- `recharge`, `card_binding`, `bm_invite` and `account_assignment` confirmation must not trigger provider writes.
- Full prompt and raw LLM response must not be exposed in operational views; save structured output plus redacted summary and metadata.
- OpenRouter key, Telegram token, webhook secret, database URL, Redis password and allowlisted chat ids must never be committed.
- UI, Mini App, RAG, production cutover, customer group send and real customer send are out of scope.

## 1. Delivery Shape

```text
05.0 Documentation And Stage Gate
-> 05.1 Runtime Config, Dependency And LLM Evidence Foundation
-> 05.2 Supervisor Graph And Router
-> 05.3 Child Draft Agents And Multi-Draft Persistence
-> 05.4 Account Inventory Exception Handling
-> 05.5 Confirmation, Customer Reply Send And No-Op Evidence
-> 05.6 Bitable Views, Regression And Staging Rehearsal
```

The stage is intentionally broader than a tiny patch, but each subphase has an independently testable deliverable and a clear Bitable endpoint.

## 2. Required Reading Before Code

1. [AGENTS.md](../../AGENTS.md)
2. [Stage 05 Source Of Truth](STAGE_05_SOURCE_OF_TRUTH.md)
3. [Stage 05 SDD](STAGE_05_SDD.md)
4. [Stage 05 BDD](STAGE_05_BDD.md)
5. [Stage 05 API Contract](STAGE_05_API_CONTRACT.md)
6. [Stage 05 Database And Migration Design](STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md)
7. [Stage 05 Security And Permission Design](STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md)
8. [Stage 05 Test Plan](STAGE_05_TEST_PLAN.md)
9. [Stage 05 Module Index](STAGE_05_MODULE_INDEX.md)
10. [Stage 04 Final Acceptance Report](STAGE_04_FINAL_ACCEPTANCE_REPORT.md)

## 3. Proposed File Structure

```text
backend/
  pyproject.toml
  app/
    agents/
      stage05_state.py
      stage05_supervisor.py
      message_intake_router.py
      account_inventory_agent.py
      recharge_draft_agent.py
      card_binding_draft_agent.py
      bm_invite_draft_agent.py
      customer_reply_draft_agent.py
      schemas.py
    adapters/
      llm_openrouter.py
      llm_fake.py
    api/routes/
      agent_runs.py
      service_drafts.py
      views.py
    core/
      config.py
    models/
      agent.py
      service_drafts.py
      service.py
      telegram.py
      accounts.py
    schemas/
      agent_runs.py
      service_drafts.py
    services/
      agent_runs.py
      agent_workflows.py
      service_drafts.py
      confirmation.py
      telegram_send_requests.py
      account_inventory.py
      bitable_views.py
      permissions.py
      outbox.py
    workers/
      stage03_handlers.py
      stage03_runtime.py
  tests/
    unit/
      test_stage05_openrouter_evidence.py
      test_stage05_router_schema.py
      test_stage05_child_agents.py
      test_stage05_account_inventory_agent.py
      test_stage05_bitable_views.py
      test_stage05_config.py
    integration/
      test_stage05_agent_workflow.py
      test_stage05_service_draft_confirmation.py
      test_stage05_customer_reply_send.py
      test_stage05_worker_runtime.py
      test_stage05_staging_contract.py
```

Existing files should be extended only where Stage05 behavior belongs to their established responsibility. Avoid broad refactors that do not directly support Stage05.

## 4. Phase 05.0: Documentation And Stage Gate

### Task 0: Stage 05 Documentation Package

**Files:**

- Create: `project-docs/08-implementation/STAGE_05_SOURCE_OF_TRUTH.md`
- Create: `project-docs/08-implementation/STAGE_05_IMPLEMENTATION_PLAN.md`
- Create: `project-docs/08-implementation/STAGE_05_SDD.md`
- Create: `project-docs/08-implementation/STAGE_05_BDD.md`
- Create: `project-docs/08-implementation/STAGE_05_API_CONTRACT.md`
- Create: `project-docs/08-implementation/STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md`
- Create: `project-docs/08-implementation/STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md`
- Create: `project-docs/08-implementation/STAGE_05_TEST_PLAN.md`
- Create: `project-docs/08-implementation/STAGE_05_ACCEPTANCE_CHECKLIST.md`
- Create: `project-docs/08-implementation/STAGE_05_PROGRESS.md`
- Create: `project-docs/08-implementation/STAGE_05_OPERATIONS_RUNBOOK.md`
- Create: `project-docs/08-implementation/STAGE_05_RISK_REGISTER.md`
- Create: `project-docs/08-implementation/STAGE_05_MODULE_INDEX.md`
- Create: `project-docs/08-implementation/modules/STAGE_05_AGENT_GRAPH_AND_ROUTING.md`
- Create: `project-docs/08-implementation/modules/STAGE_05_AGENT_SKILLS_AND_CAPABILITIES.md` as a post-acceptance reference doc only
- Create: `project-docs/08-implementation/modules/STAGE_05_ACCOUNT_INVENTORY_AGENT.md`
- Create: `project-docs/08-implementation/modules/STAGE_05_DRAFT_AGENTS.md`
- Create: `project-docs/08-implementation/modules/STAGE_05_CONFIRMATION_AND_SEND.md`
- Create: `project-docs/08-implementation/modules/STAGE_05_BITABLE_VIEWS.md`
- Create: `project-docs/08-implementation/modules/STAGE_05_OPENROUTER_EVIDENCE.md`
- Update: `project-docs/08-implementation/README.md`
- Update: `project-docs/README.md`
- Update: `project-docs/04-agents/ACCOUNT_INVENTORY_AGENT.md`
- Update: `project-docs/01-product/scenarios/ACCOUNT_INVENTORY_WORKFLOW.md`

- [x] Step 1: Record confirmed user choices and Account Inventory Agent clarification.
- [x] Step 2: Define Stage05 source, scope, non-goals, Bitable endpoints and exit gates.
- [x] Step 3: Define task breakdown and module ownership.
- [x] Step 4: Create detailed module docs for complex Stage05 areas.
- [x] Step 5: Run documentation consistency scan.
- [x] Step 6: Ask user to review Stage05 docs before code implementation.

Note: Agent skills/capabilities are documented as a later post-acceptance Stage05 extension. Do not add runtime capability registry code or capability tests during the main Stage05 implementation.

## 5. Phase 05.1: Runtime Config, Dependency And LLM Evidence Foundation

### Task 1: Runtime Config And Dependency Gate

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_stage05_config.py`

**Implementation requirements:**

- Add `langgraph` dependency.
- Add Stage05 settings:
  - `LLM_ENABLED`
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`
  - `OPENROUTER_BASE_URL`
  - `AGENT_WORKFLOW_MODE`
  - `AGENT_LLM_TIMEOUT_SECONDS`
  - `AGENT_SAVE_FULL_PROMPT`
  - `AGENT_SAVE_FULL_RESPONSE`
- Fail closed when `AGENT_WORKFLOW_MODE=real_openrouter` but `OPENROUTER_API_KEY` is absent.
- Default `AGENT_SAVE_FULL_PROMPT=false` and `AGENT_SAVE_FULL_RESPONSE=false`.
- Preserve Stage04 `TELEGRAM_SEND_MODE=dry_run` default.

- [x] Step 1: Write failing config tests for real OpenRouter enabled/disabled modes.
- [x] Step 2: Add config fields and validation.
- [x] Step 3: Run `pytest tests/unit/test_stage05_config.py -v`.
- [x] Step 4: Update `.env.example` with placeholders only.
- [x] Step 5: Update `STAGE_05_PROGRESS.md` and checklist.

### Task 2: AgentRun Evidence Model And Service

**Files:**

- Modify: `backend/app/models/agent.py`
- Modify: `backend/app/services/agent_runs.py`
- Create: `backend/app/schemas/agent_runs.py`
- Create: `backend/alembic/versions/20260707_0012_stage05_agent_run_evidence.py`
- Test: `backend/tests/unit/test_stage05_openrouter_evidence.py`

**Implementation requirements:**

- Add or preserve fields for:
  - `input_summary`
  - `output_summary`
  - `tool_calls`
  - `status`
  - `trace_id`
  - `usage_summary`
  - `cost_summary`
  - `latency_ms`
  - `error_code`
  - `error_message_redacted`
  - `created_entity_refs`
- Do not expose full prompt/raw response in views.
- Store redacted summaries only; full raw text is not persisted by default.

- [x] Step 1: Write metadata tests for new fields.
- [x] Step 2: Add model and migration changes.
- [x] Step 3: Update `create_agent_run_record`.
- [x] Step 4: Run `pytest tests/unit/test_stage05_openrouter_evidence.py -v`.
- [x] Step 5: Run `alembic upgrade head --sql`.

## 6. Phase 05.2: Supervisor Graph And Router

### Task 3: Stage05 State And Router Schema

**Files:**

- Create: `backend/app/agents/stage05_state.py`
- Create: `backend/app/agents/schemas.py`
- Create: `backend/app/agents/message_intake_router.py`
- Test: `backend/tests/unit/test_stage05_router_schema.py`

**Technical confirmation gate:**

Task 3 changes the workflow state shape and Router output schema, so it must not begin until the user confirms the technical approach. User confirmed approach A on 2026-07-07. The confirmed approach is:

- Use official LangGraph `StateGraph`-compatible state and routing conventions rather than adding a separate supervisor wrapper package at this step.
- Use Pydantic v2 models for Router output validation and downstream child-agent selection.
- Reuse the existing OpenRouter-compatible structured LLM adapter boundary; Task 3 only builds request construction and response validation, not real network calls.
- Keep the deferred Agent skills/capabilities registry out of the main Stage05 implementation until Stage05 has passed acceptance.

**Implementation requirements:**

- Define `Stage05WorkflowState` with:
  - `trace_id`
  - `message_id`
  - `customer_id`
  - `source_text_summary`
  - `router_result`
  - `selected_agents`
  - `draft_candidates`
  - `account_status_actions`
  - `manual_review_reasons`
  - `agent_run_ids`
  - `status`
  - `errors`
- Define Router output schema with:
  - `intents[]`
  - `entities`
  - `confidence`
  - `risk_flags`
  - `missing_context`
  - `requires_manual_review`
- Supported intent types:
  - `recharge`
  - `card_binding`
  - `bm_invite`
  - `customer_reply`
  - `account_assignment`
  - `account_status_exception`
  - `irrelevant`
  - `unknown`
- Do not implement the deferred Agent skills/capabilities registry in this task. Keep current Stage05 focused on Router schema, child Agent outputs, service policy checks and Bitable endpoints.

- [x] Step 1: Write schema validation tests for multi-intent output.
- [x] Step 2: Implement Pydantic/dataclass schema.
- [x] Step 3: Implement Router request construction.
- [x] Step 4: Implement invalid JSON failure mapping to `agent_failed`.
- [x] Step 5: Run router schema tests.

### Task 4: Supervisor Graph

**Files:**

- Create: `backend/app/agents/stage05_supervisor.py`
- Create: `backend/app/services/agent_workflows.py`
- Modify: `backend/app/workers/stage03_handlers.py`
- Test: `backend/tests/integration/test_stage05_agent_workflow.py`
- Test: `backend/tests/integration/test_stage05_worker_runtime.py`

**Implementation requirements:**

**Technical confirmation gate:**

Task 4 introduces the real workflow execution boundary, creates `stage05_supervisor.py`, creates `agent_workflows.py` and modifies the Stage03 worker path. User confirmed this approach on 2026-07-07. The confirmed approach is:

- Use official LangGraph `StateGraph` with the Task 3 `Stage05WorkflowState`, not a custom workflow engine.
- Keep graph nodes thin and deterministic: context loading, running mark, router call, child selection, policy decision and final status mapping.
- Use service injection so tests can run with fake LLM/router services and without real OpenRouter, Redis, Telegram or provider calls.
- Put database/message-state ownership in `backend/app/services/agent_workflows.py`; keep `stage05_supervisor.py` as orchestration.
- Modify `stage03_handlers.py` only at the `bound + intent_ready` trigger boundary, preserving Stage03/Stage04 behavior for all other events.
- In Task 4, create workflow evidence and status transitions only; do not implement child draft generation, account inventory mutations, confirmation/send, provider writes or staging calls.

- Trigger only bound messages with `intent_status=intent_ready`.
- Mark message `agent_running` before graph execution.
- Call Router, select one or more child agents.
- Persist `agent_runs`.
- Mark message `routed` when at least one result is persisted.
- Mark message `manual_review` when Router returns low confidence/high risk without usable child output.
- Mark message `agent_failed` on LLM/runtime failure.
- Use idempotency so repeated worker delivery does not create duplicate drafts.

- [x] Step 1: Write tests for happy path, manual review, invalid output and duplicate trigger.
- [x] Step 2: Implement workflow service.
- [x] Step 3: Wire worker handler while preserving Stage04 behavior.
- [x] Step 4: Run Stage05 workflow tests and Stage04 intent placeholder regression.

## 7. Phase 05.3: Child Draft Agents And Multi-Draft Persistence

### Task 5: Draft Agents

**Files:**

- Create: `backend/app/agents/recharge_draft_agent.py`
- Create: `backend/app/agents/card_binding_draft_agent.py`
- Create: `backend/app/agents/bm_invite_draft_agent.py`
- Create: `backend/app/agents/customer_reply_draft_agent.py`
- Modify: `backend/app/services/service_drafts.py`
- Create: `backend/alembic/versions/20260707_0013_stage05_service_draft_metadata.py`
- Test: `backend/tests/unit/test_stage05_child_agents.py`
- Test: `backend/tests/integration/test_stage05_agent_workflow.py`

**Implementation requirements:**

**Technical confirmation gate:**

Task 5 introduces child Agent output contracts, `service_drafts` persistence metadata, a new Alembic migration and workflow integration. It must not begin until the user confirms the technical approach. The proposed approach is:

User confirmed approach A on 2026-07-07. The implemented local scope is:

- Add a Stage05-specific Pydantic draft candidate schema in `backend/app/agents/schemas.py` instead of changing the existing Stage02 `DraftCandidate` dataclass used by `mock_router`.
- Implement child agents as deterministic pure functions in `recharge_draft_agent.py`, `card_binding_draft_agent.py`, `bm_invite_draft_agent.py` and `customer_reply_draft_agent.py`; they consume validated Router intents and compact context, and return draft candidates only.
- Add additive nullable `service_drafts` metadata columns from the Stage05 database design: `source_agent_run_id`, `intent_index`, `payload_summary`, `review_reason` and `confirmed_at`.
- Keep `intent_type` as a candidate/output contract and in `payload_summary`/audit for Task 5; do not add a first-class database column unless separately confirmed.
- Preserve existing `create_service_draft_from_candidate`, service draft API status filtering, Stage02/Stage04 mock router tests and confirmation state machine behavior.
- Extend Stage05 workflow persistence to create one draft per supported child-agent result using idempotency key `draft:{message_id}:{draft_type}:{intent_index}`.
- Keep `account_assignment` and `account_status_exception` persistence for 05.4 Account Inventory Agent, not Task 5.
- Do not send Telegram messages, confirm drafts, call providers, allocate accounts or perform staging calls in Task 5.

- Each child agent consumes Router intent and structured context.
- Each child agent returns draft candidates with:
  - `draft_type`
  - `status`
  - `payload`
  - `missing_fields`
  - `risk_flags`
  - `confidence`
  - `intent_index`
  - `agent_name`
- Create multiple drafts for one message.
- Use idempotency key `draft:{message_id}:{draft_type}:{intent_index}`.
- `needs_more_info` drafts preserve missing fields and suggested follow-up text.

- [x] Step 1: Write unit tests for each child agent.
- [x] Step 2: Extend draft candidate model and persistence.
- [x] Step 3: Add integration test for one mixed-language message producing multiple drafts.
- [x] Step 4: Run child agent and workflow tests.

### Task 6: Service Draft API Enhancements

**Files:**

- Modify: `backend/app/api/routes/service_drafts.py`
- Modify: `backend/app/schemas/service_drafts.py`
- Modify: `backend/app/services/service_drafts.py`
- Test: `backend/tests/unit/test_service_drafts_api.py`

Note: the original Stage05 draft named `test_stage05_service_draft_confirmation.py`, but current repository ownership keeps `/service-drafts` list route tests in `tests/unit/test_service_drafts_api.py`. Confirmation branch tests remain owned by Phase 05.5.

**Implementation requirements:**

- Support filters:
  - `status`
  - `draft_type`
  - `customer_id`
  - `source_message_id`
  - `trace_id`
- Response includes:
  - `risk_flags`
  - `confidence`
  - `created_by_type`
  - `created_by_id`
  - `source_message_id`
  - `created_at`
- Do not expose hidden LLM raw prompt/response.

- [x] Step 1: Write filtering and response-shape tests.
- [x] Step 2: Implement query and schema changes.
- [x] Step 3: Run service draft API tests.

## 8. Phase 05.4: Account Inventory Exception Handling

### Task 7: Account Inventory Agent

**Files:**

- Create: `backend/app/agents/account_inventory_agent.py`
- Modify: `backend/app/services/account_inventory.py`
- Modify: `backend/app/services/permissions.py`
- Create: `backend/alembic/versions/20260707_0015_stage05_account_status_event_metadata.py`
- Test: `backend/tests/unit/test_stage05_account_inventory_agent.py`

**Implementation requirements:**

**Technical confirmation gate:**

Task 7 introduces a narrowly allowed automatic account inventory mutation. It must not begin until the user confirms the technical approach because it changes account status mutation policy, permission checks and account status event evidence. User confirmed the existing documented plan on 2026-07-07 and clarified that only future changes or conflicts with the established plan require fresh confirmation.

Implemented approach A:

- Implement `backend/app/agents/account_inventory_agent.py` as deterministic policy logic, not a new LLM caller. It consumes validated Router intent data plus resolved inventory context and returns either:
  - `account_assignment` draft candidate for human review,
  - high-confidence `auto_mark_account_exception` action,
  - or manual review reason.
- Add service-level `mark_account_exception_from_agent(...)` or equivalent in `backend/app/services/account_inventory.py` that performs the actual mutation. The Agent module must not mutate models directly.
- Add a narrow permission guard for `auto_mark_account_exception`:
  - allowed for manager/admin,
  - allowed for `actor_type="agent"` only when `actor_id="account_inventory_agent"`,
  - denied for other child Agents even if their role is `agent`.
- Allow automatic transition only to `blocked`, `disabled` and `risk_controlled`.
- Require resolved existing `account_inventory_id`, high confidence and allowed risk flag before mutation.
- Write both `account_status_events` and audit event `account.exception_marked` for successful mutation.
- Add additive nullable metadata to `account_status_events` through `20260707_0015_stage05_account_status_event_metadata.py`:
  - `confidence`
  - `risk_flags`
- Do not add provider readback, account production, replacement recommendation, replacement reservation, automatic assignment or account recycling in Task 7.
- Extend Stage05 workflow only as needed to persist `account_status_exception` outcomes and `account_assignment` draft candidates to Bitable endpoints. If workflow integration requires touching `backend/app/services/agent_workflows.py`, keep the change scoped to `account_inventory_agent` routing and evidence.
- Keep confirmation of `account_assignment` for Phase 05.5.

- The Agent does not create production accounts.
- It may read unused/reserved/allocated/activated/blocked/disabled inventory.
- It may generate `account_assignment` draft only; confirmation is separate.
- It may automatically mark high-confidence exceptions:
  - `blocked`
  - `disabled`
  - `risk_controlled`
- It must write `account_status_events` and audit for automatic high-risk status change.
- It must not recommend replacement, reserve replacement, or redistribute replacement account in Stage05.
- Unclear risk or conflicting evidence goes to manual review.

- [x] Step 1: Write tests proving no production account path is used by the agent.
- [x] Step 2: Write tests for high-confidence block/disabled auto-mark.
- [x] Step 3: Write tests for uncertain risk entering manual review.
- [x] Step 4: Implement service guard and agent logic.
- [x] Step 5: Run account inventory tests and existing inventory tests.

## 9. Phase 05.5: Confirmation, Customer Reply Send And No-Op Evidence

### Task 8: Confirmation Branches

**Files:**

- Modify: `backend/app/services/confirmation.py`
- Modify: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/schemas/service_drafts.py`
- Reuse: `backend/app/models/service.py` existing `ServiceRecord` and `ExecutionLog` tables for no-op evidence; no migration is required in Task 8.
- Test: `backend/tests/integration/test_stage05_service_draft_confirmation.py`

**Implementation requirements:**

- `customer_reply` confirmation creates or reuses a `telegram_send_requests` row.
- `recharge`, `card_binding`, `bm_invite`, `account_assignment` confirmation creates service/no-op evidence only.
- Stage05 business draft confirmation does not create a provider execution job.
- Confirming `needs_more_info`, `manual_review`, `rejected`, `confirmed` or already processed drafts returns stable error.
- Repeated confirmation is idempotent or returns stable conflict without duplicate side effects.

- [x] Step 1: Write confirmation state tests.
- [x] Step 2: Implement branch-specific confirmation service.
- [x] Step 3: Add audit events.
- [x] Step 4: Run confirmation tests and Stage02 confirmation regression.

Task 8 implementation note: the original draft listed `service_drafts.py` as the route file, but current repository ownership keeps mutation actions under `backend/app/api/routes/confirmations.py`. Task 8 therefore updated `confirmations.py` and the shared `ConfirmationActionResponse` schema. Task 9 still owns persisted `source_service_draft_id` / `send_purpose` reply-send linkage and must continue from current Alembic head `20260707_0015`.

### Task 9: Customer Reply Send Request

**Files:**

- Modify: `backend/app/services/telegram_send_requests.py`
- Modify: `backend/app/models/telegram.py`
- Create: `backend/alembic/versions/20260707_0016_stage05_reply_send_link.py`
- Test: `backend/tests/integration/test_stage05_customer_reply_send.py`

**Implementation requirements:**

- Link `telegram_send_requests` to `customer_reply` draft through `source_service_draft_id` or equivalent persisted evidence.
- Confirm route checks current allowlist at confirm time.
- Worker re-checks allowlist before send.
- Sent/failed result updates request and audit.
- It must be impossible to send to non-allowlisted customer chat in Stage05.

- [x] Step 1: Write tests for reply draft -> send request -> confirm -> fake send.
- [x] Step 2: Write non-allowlisted rejection tests.
- [x] Step 3: Add model/migration link if needed.
- [x] Step 4: Implement service changes.
- [x] Step 5: Run customer reply send tests and Stage04 send tests.

Task 9 implementation note: the original placeholder migration name used `0014`, but current Stage05 head was already `20260707_0015` after Task7. The implemented migration is therefore `20260707_0016_stage05_reply_send_link.py` with `down_revision = "20260707_0015"` to avoid a second Alembic head.

## 10. Phase 05.6: Views, Regression And Staging Rehearsal

### Task 10: Bitable Views

**Files:**

- Modify: `backend/app/services/bitable_views.py`
- Test: `backend/tests/unit/test_stage05_bitable_views.py`

**Implementation requirements:**

- Add/extend:
  - `service_drafts`
  - `agent_review_queue`
  - `pending_confirmation`
  - `customer_reply_send_requests`
  - `account_inventory`
  - `telegram_inbox`
- Views must protect sensitive fields and preserve row-level customer scope rules.
- Manager/admin can inspect operational evidence; customer-scoped roles see only allowed records and masked sensitive fields.

- [x] Step 1: Write view field and row-level tests.
- [x] Step 2: Implement view definitions.
- [x] Step 3: Run Stage05 and existing view tests.

Implementation notes:

- Added Stage05 view tests in `tests/unit/test_stage05_bitable_views.py` and observed RED failures for unknown views / missing enhanced fields before implementation.
- Added `service_drafts`, `agent_review_queue`, `pending_confirmation` and `customer_reply_send_requests` view definitions.
- Enhanced `telegram_inbox` with derived `agent_status`, `draft_count` and `agent_last_error_code` when related AgentRun/draft evidence exists.
- Enhanced `account_inventory` with latest risk signal fields from `account_status_events`.
- `pending_confirmation` intentionally includes only action-queue fields from the API contract; full draft detail and `payload_summary` remain available through the `service_drafts` view.
- Manager/admin can inspect account external ids in `account_inventory`; customer-scoped roles see only authorized customer rows and masked external ids.

### Task 11: Local Acceptance Audit

**Files:**

- Create/Update: `project-docs/08-implementation/STAGE_05_LOCAL_ACCEPTANCE_AUDIT.md`
- Update: `project-docs/08-implementation/STAGE_05_ACCEPTANCE_CHECKLIST.md`
- Update: `project-docs/08-implementation/STAGE_05_PROGRESS.md`

- [x] Step 1: Run focused Stage05 tests.
- [x] Step 2: Run Stage03/Stage04 regressions.
- [x] Step 3: Run `cd backend; pytest tests -q`.
- [x] Step 4: Run `cd backend; alembic upgrade head --sql`.
- [x] Step 5: Run secret scan over `backend`, `deploy`, `project-docs`.
- [x] Step 6: Record results and skipped tests.

Task11 initial local acceptance snapshot:

These values were captured before Task12 local staging-contract preflight and the later scope guard. The latest local counts are recorded in the Task12 local preflight/scope-guard notes below, the acceptance checklist and the traceability audit.

- Focused Stage05: `pytest tests -k stage05 -v` passed 68 selected tests.
- Stage03/Stage04 regression: planned regression command passed 33 tests.
- Full backend suite: `pytest tests -q` passed 241 tests with 17 online PostgreSQL smoke tests skipped because `STAGE02_ONLINE_DATABASE_URL` is not configured.
- Alembic offline SQL reaches `20260707_0016`.
- Secret scan found only config names, placeholders, documented scan patterns and fake test values.
- `git diff --check` reported no whitespace errors; only Windows LF-to-CRLF warnings.

### Task 12: Tencent Cloud Staging Rehearsal

**Files:**

- Update: `project-docs/08-implementation/STAGE_05_ACCEPTANCE_CHECKLIST.md`
- Update: `project-docs/08-implementation/STAGE_05_PROGRESS.md`
- Update: `project-docs/08-implementation/STAGE_05_OPERATIONS_RUNBOOK.md`
- Create/Update: `project-docs/08-implementation/STAGE_05_FINAL_ACCEPTANCE_REPORT.md`

- [x] Step 1: Ask user for explicit approval against `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` before staging env change, real OpenRouter call or real Telegram send.
- [ ] Step 2: Deploy Stage05 commit to Tencent Cloud staging.
- [ ] Step 3: Run Alembic migration.
- [ ] Step 4: Enable real OpenRouter with server-only key.
- [ ] Step 5: Temporarily enable restricted Telegram test send allowlist.
- [ ] Step 6: Send mixed Chinese/English Telegram test message.
- [ ] Step 7: Verify `agent_runs`, multiple `service_drafts`, views and audit.
- [ ] Step 8: Confirm `customer_reply` and verify allowlisted test chat receives it.
- [ ] Step 9: Confirm business draft and verify service/no-op evidence without provider write.
- [ ] Step 10: Verify account risk branch with staging fixture or clearly documented test message evidence.
- [ ] Step 11: Restore staging safety configuration.
- [ ] Step 12: Record redacted final evidence.

Local preflight and scope-guard work completed before Step 1:

- Added `tests/integration/test_stage05_staging_contract.py` as a local, no-external-call contract check for the Task12 env assumptions listed in the runbook and test plan.
- `pytest tests\integration\test_stage05_staging_contract.py -v` passed 5 tests.
- Added `tests/unit/test_stage05_scope_guards.py` as a local, no-external-call source guard for Stage05 out-of-scope runtime boundaries.
- `pytest tests\unit\test_stage05_scope_guards.py -v` passed 4 tests.
- Added `tests/unit/test_stage05_runtime_summary.py` and `backend/app/core/runtime_summary.py` as a local, no-external-call redacted runtime proof command for Task12 container settings evidence.
- `pytest tests\unit\test_stage05_runtime_summary.py -v` passed 3 tests.
- Latest local Stage05 focused regression after the scope guard, deployment config gate and redacted runtime summary command: `pytest tests -k stage05 -v` passed 82 selected tests.
- Latest full backend suite after the redacted runtime summary command: `pytest tests -q` passed 255 tests with 17 online PostgreSQL smoke tests skipped because `STAGE02_ONLINE_DATABASE_URL` is not configured.
- This does not satisfy Step 1 or any real staging step. Explicit approval is still required before staging env changes, real OpenRouter calls or real Telegram sends.

## 11. Final Stage 05 Acceptance

Stage 05 can be accepted only when:

- Documentation package is complete and linked from indexes.
- All Stage05 focused tests pass.
- Existing Stage03 and Stage04 regression tests pass.
- Alembic offline SQL reaches Stage05 head.
- Staging has real OpenRouter evidence.
- Staging has allowlisted Telegram customer-reply test send evidence.
- Multiple draft candidates are created from one mixed-language message.
- Account Inventory Agent exception boundary is tested and documented.
- No true provider write, customer chat send, customer group send, funds movement, account production or automatic replacement distribution occurred.
