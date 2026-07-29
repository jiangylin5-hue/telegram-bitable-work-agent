# Stage11 Multi-Agent Coordination Implementation Plan

> Status: approved by the user's explicit instruction to execute the previously proposed coordination middleware and add complex Chinese cases.

**Goal:** Complete the durable coordination middleware and prove it with real, complex Chinese multi-table and controlled-action workloads.

**Architecture:** Extend the existing Stage10 run/command/event/checkpoint runtime. Add a versioned capability registry and deterministic Task Gateway planner. Dispatch multiple child commands, let specialists finish independently, and give only Supervisor authority to fan-in and terminate a run. Materialize write-like proposals through existing Stage06/Stage08 draft, ticket, notification and audit services.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/PostgreSQL, Redis Streams, LangGraph/Stage08 collaboration runtime, OpenRouter, pytest, React/Vite browser acceptance.

---

## Task 1: Freeze contracts and registry

**Files:**

- Create: `backend/app/agents/agent_capability_registry.py`
- Create: `backend/app/services/agent_task_gateway.py`
- Modify: `backend/app/schemas/agent_event_runtime.py`
- Test: `backend/tests/unit/test_agent_capability_registry.py`
- Test: `backend/tests/unit/test_agent_task_gateway.py`

1. Write failing tests for the four registered capabilities, allowed command mapping, immutable definitions, action-to-plan mapping and invalid permission expansion.
2. Extend strict schema literals for capabilities, commands, intents and requested actions.
3. Implement immutable registry definitions and deterministic plan creation.
4. Run focused tests and verify old Stage10 read-only request compatibility.

## Task 2: Implement durable fan-out/fan-in

**Files:**

- Modify: `backend/app/services/agent_orchestrator.py`
- Modify: `backend/app/services/agent_event_runtime.py`
- Modify: `backend/app/workers/agent_tabular_runtime.py` or create a generic specialist worker adapter
- Modify: `backend/app/api/routes/agent_runs.py`
- Test: `backend/tests/unit/test_agent_coordination_runtime.py`
- Test: `backend/tests/integration/test_agent_coordination_postgres.py`

1. Write failing tests: batch dispatch creates one command per plan node; first child completion does not finish run; out-of-order completion; duplicate delivery; required failure; optional failure; scope drift.
2. Implement transactional `dispatch_specialist_commands` and idempotent replay.
3. Split child completion from Supervisor terminal fan-in.
4. Implement fan-in decision with required/optional metadata kept in safe control references, not private data.
5. Verify PostgreSQL row locks/version conflicts and Redis Stream recovery.

## Task 3: Implement Specialist handler registry

**Files:**

- Create: `backend/app/agents/agent_specialist_handlers.py`
- Modify: worker runtime and deployment unit definitions
- Test: `backend/tests/unit/test_agent_specialist_handlers.py`

1. Write failing tests for command/capability mismatch, output schema mismatch and forbidden direct write.
2. Adapt the existing Stage08 safe analysis path for tabular, risk and daily handlers.
3. Implement action proposal handler that returns only `ControlledActionProposal`.
4. Persist validated artifacts and specialist terminal events without terminating the run.

## Task 4: Implement controlled Tool Gateway

**Files:**

- Create: `backend/app/schemas/agent_controlled_actions.py`
- Create: `backend/app/services/agent_tool_gateway.py`
- Reuse/modify: Stage06 digital employee and Stage08 execution ticket services only where needed
- Test: `backend/tests/unit/test_agent_tool_gateway.py`
- Test: `backend/tests/integration/test_agent_tool_gateway_postgres.py`

1. Write failing tests for create/update/task/reminder proposals, field permission denial, idempotency, version drift and zero external sends.
2. Implement strict proposal schemas and action-specific adapters.
3. Re-check identity, employee/table/field scope at materialization time.
4. Create pending draft/ticket/notification plus audit in one transaction.
5. Never call confirmation or external send paths.

## Task 5: Add complex evaluation fixture and scorer

**Files:**

- Create: `backend/scripts/stage11_complex_coordination_eval.py`
- Create: `backend/tests/unit/test_stage11_complex_coordination_eval.py`
- Create after execution: Stage11 JSON and Markdown evidence under `project-docs/08-implementation/evidence/`

1. Write 48 truth cases across all categories in the protocol, including eight single-query multi-intent DAG cases.
2. Add offline truth validation so broken fixture/case definitions fail before LLM calls, including objective decomposition and dependency-edge truth.
3. Run cases through the real HTTP/Redis/SSE path and inspect persisted commands/artifacts/drafts/tickets/notifications.
4. Calculate routing, retrieval, join, action, permission, quality, latency and cost metrics.
5. Preserve failures honestly and iterate implementation, not the truth labels.

## Task 6: UI observability and browser acceptance

**Files:**

- Modify only existing conversation components/tests when the backend event payload needs presentation support.
- Test: existing frontend unit/integration suite plus browser acceptance.

1. Display multiple capability steps, running/completed/degraded states and safe action result.
2. Ensure read-only answer still behaves like normal LLM chat.
3. Ensure draft/task/reminder exposes a review action and never claims execution.
4. Test all interactive controls on desktop and Telegram-size viewport.

## Task 7: Full verification, staging deployment and one commit

1. Run focused backend tests, full backend suite, migration-head check and frontend full suite/build.
2. Run real local PostgreSQL/Redis/OpenRouter 40-case evaluation.
3. Deploy to isolated staging, run server API and browser smoke, then verify logs and no external sends.
4. Update Stage11 acceptance, active source-of-truth progress, changed files, skipped tests, risks and cleanup.
5. Audit git diff, secrets, temporary artifacts and documentation consistency.
6. Create one final commit, push the branch and update the existing PR only after all acceptance gates pass.
