# Stage 04 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Stage 04 Telegram inbox operations: binding management API, restricted Telegram test send, no-LLM intent placeholder, Bitable views and staging evidence.

**Architecture:** Reuse the Stage 03 webhook, outbox, Redis Streams and Bitable view foundation. Add synchronous binding management through service/UOW boundaries, add `telegram_send_requests` for controlled test-send evidence, and extend worker handlers for intent placeholder and allowlisted Telegram send. PostgreSQL remains the fact source; Redis Streams remains delivery/runtime; real sends are limited to allowlisted test chat after human confirmation.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis Streams, Telegram Bot API `sendMessage`, pytest, Docker Compose staging.

## Status

- Document status: completed implementation plan
- Scope: Stage 04 documentation and future code task breakdown.
- Current Progress: 2026-07-07 Tasks 1-10 are complete in the confirmed Stage04 scope. Local backend suite passed with 172 passed / 17 skipped; Tencent Cloud staging ran commit `360d376`, migration reached `20260706_0011`, binding/inbox/intent evidence was recorded for update `184365902`, restricted test send request `05f46883-e4c7-4669-99cb-99a093629f70` reached `sent`, and staging was closed back to dry-run.

## 1. Delivery Shape

```text
04.0 Documentation And Stage Gate
-> 04.1 Binding Management API
-> 04.2 New Message Binding And Views
-> 04.3 Intent Placeholder Boundary
-> 04.4 Restricted Test Send
-> 04.5 Staging Rehearsal And Stage Close
```

## 2. Non-Goals

Stage 04 不做：

- UI / Mini App。
- Telegram command management。
- OpenRouter / real LLM。
- LangGraph production graph。
- Customer group send。
- Customer reply drafts。
- Provider writes。
- Real funds or account operations。
- Historical message replay。
- Production cutover。

## 3. Required Reading Before Code

1. [AGENTS.md](../../AGENTS.md)
2. [Stage 04 Source Of Truth](STAGE_04_SOURCE_OF_TRUTH.md)
3. [Stage 04 SDD](STAGE_04_SDD.md)
4. [Stage 04 BDD](STAGE_04_BDD.md)
5. [Stage 04 API Contract](STAGE_04_API_CONTRACT.md)
6. [Stage 04 Database And Migration Design](STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md)
7. [Stage 04 Security And Permission Design](STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md)
8. [Stage 04 Test Plan](STAGE_04_TEST_PLAN.md)
9. [Stage 03 Final Acceptance Report](STAGE_03_FINAL_ACCEPTANCE_REPORT.md)
10. Stage 04 module docs under `modules/`.

## 4. Proposed Future File Structure

```text
backend/
  app/
    api/routes/
      telegram_bindings.py
      telegram_send_requests.py
    clients/
      telegram_bot.py
    core/
      config.py
    models/
      telegram.py
    schemas/
      telegram_bindings.py
      telegram_send_requests.py
    services/
      telegram_binding_management.py
      telegram_send_requests.py
      telegram_intent_placeholder.py
      bitable_views.py
      permissions.py
      outbox.py
    workers/
      stage03_handlers.py
      runner.py
    tests/
      unit/
        test_stage04_config.py
        test_stage04_bitable_views.py
        test_stage04_telegram_bot_client.py
      integration/
        test_stage04_binding_management.py
        test_stage04_new_message_binding.py
        test_stage04_intent_placeholder.py
        test_stage04_test_send.py
```

If implementation discovers better existing file placement, update this plan/progress before coding.

## 5. Phase 04.0: Documentation And Stage Gate

### Task 0: Stage 04 Documentation Package

**Files:**

- Create: `project-docs/08-implementation/STAGE_04_SOURCE_OF_TRUTH.md`
- Create: `project-docs/08-implementation/STAGE_04_IMPLEMENTATION_PLAN.md`
- Create: `project-docs/08-implementation/STAGE_04_SDD.md`
- Create: `project-docs/08-implementation/STAGE_04_BDD.md`
- Create: `project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md`
- Create: `project-docs/08-implementation/STAGE_04_PROGRESS.md`
- Create: `project-docs/08-implementation/STAGE_04_API_CONTRACT.md`
- Create: `project-docs/08-implementation/STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md`
- Create: `project-docs/08-implementation/STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md`
- Create: `project-docs/08-implementation/STAGE_04_TEST_PLAN.md`
- Create: `project-docs/08-implementation/STAGE_04_OPERATIONS_RUNBOOK.md`
- Create: `project-docs/08-implementation/STAGE_04_RISK_REGISTER.md`
- Create: `project-docs/08-implementation/STAGE_04_MODULE_INDEX.md`
- Update: `project-docs/08-implementation/README.md`
- Update: `project-docs/README.md`

- [x] Step 1: Record confirmed user choices.
- [x] Step 2: Define source, Bitable endpoints, out-of-scope and exit gates.
- [x] Step 3: Define implementation task breakdown.
- [x] Step 4: Run documentation consistency scan.
- [x] Step 5: Ask user to review Stage 04 docs before code.

## 6. Phase 04.1: Binding Management API

### Task 1: Permission Actions And Schemas

**Files:**

- Modify: `backend/app/services/permissions.py`
- Create: `backend/app/schemas/telegram_bindings.py`
- Test: `backend/tests/integration/test_stage04_binding_management.py`

- [x] Step 1: Write failing tests for authorized/unauthorized binding-management permissions and create schema validation.
- [x] Step 2: Add actions `manage_telegram_binding`, `request_test_telegram_send`, `confirm_test_telegram_send`.
- [x] Step 3: Add Pydantic schemas for create/list/disable binding.
- [x] Step 4: Run `pytest tests/integration/test_stage04_binding_management.py -v`.
- [x] Step 5: Update Stage 04 progress and acceptance checklist.

### Task 2: Binding Management Service And API

**Files:**

- Create: `backend/app/services/telegram_binding_management.py`
- Create: `backend/app/api/routes/telegram_bindings.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_stage04_binding_management.py`

- [x] Step 1: Write failing tests for create, list, disable and conflict.
- [x] Step 2: Implement service validation for `chat`, `user`, `chat_user`.
- [x] Step 3: Implement active conflict checks and audit events.
- [x] Step 4: Implement route and register router.
- [x] Step 5: Run binding management tests.
- [x] Step 6: Update docs evidence.

## 7. Phase 04.2: New Message Binding And Views

### Task 3: Bitable Views For Bindings And Intent Queue

**Files:**

- Modify: `backend/app/services/bitable_views.py`
- Test: `backend/tests/unit/test_stage04_bitable_views.py`

- [x] Step 1: Write failing view tests for `telegram_bindings`, `telegram_intent_queue` and `telegram_send_requests`.
- [x] Step 2: Add view definitions and safe fields.
- [x] Step 3: Ensure sensitive fields are masked for non-admin/manager actors.
- [x] Step 4: Run `pytest tests/unit/test_stage04_bitable_views.py -v`.

### Task 4: New Message Binding Regression

**Files:**

- Modify: `backend/app/services/customer_binding.py` if needed
- Modify: `backend/app/services/telegram_ingestion.py` if needed
- Test: `backend/tests/integration/test_stage04_new_message_binding.py`

- [x] Step 1: Write tests proving `chat_user`, `chat`, `user` precedence on new messages.
- [x] Step 2: Write test proving inactive binding is ignored.
- [x] Step 3: Write test proving historical messages are not rewritten.
- [x] Step 4: Implement minimal fixes only if current behavior fails.
- [x] Step 5: Run new-message binding tests and Stage 03 binding tests.

## 8. Phase 04.3: Intent Placeholder Boundary

### Task 5: Intent Placeholder Service

**Files:**

- Create: `backend/app/services/telegram_intent_placeholder.py`
- Modify: `backend/app/workers/stage03_handlers.py`
- Test: `backend/tests/integration/test_stage04_intent_placeholder.py`

- [x] Step 1: Write failing test proving bound message becomes `intent_ready` without LLM.
- [x] Step 2: Write failing test proving no `service_drafts` row is created.
- [x] Step 3: Implement placeholder status update and audit.
- [x] Step 4: Wire placeholder into existing `telegram.message_received` handler; no separate outbox handler needed.
- [x] Step 5: Run intent placeholder tests.

## 9. Phase 04.4: Restricted Test Send

### Task 6: Runtime Config For Restricted Test Send

**Files:**

- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_stage04_config.py`
- Modify: `deploy/stage03/env.stage03.example`

- [x] Step 1: Write tests proving `restricted_test` requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`.
- [x] Step 2: Write tests proving unrestricted send modes are rejected.
- [x] Step 3: Implement settings fields and validation.
- [x] Step 4: Update env example with placeholders only.
- [x] Step 5: Run Stage 03 and Stage 04 config tests.

### Task 7: `telegram_send_requests` Model And Migration

**Files:**

- Modify: `backend/app/models/telegram.py`
- Create: `backend/alembic/versions/<next>_stage04_telegram_send_requests.py`
- Test: `backend/tests/unit/test_model_metadata.py` or new metadata test
- Test: `backend/tests/integration/test_stage04_test_send.py`

- [x] Step 1: Write metadata/migration tests for `telegram_send_requests`.
- [x] Step 2: Add SQLAlchemy model.
- [x] Step 3: Add Alembic migration.
- [x] Step 4: Run `alembic upgrade head --sql`.
- [x] Step 5: Run affected tests.

### Task 8: Test Send Request Service And API

**Files:**

- Create: `backend/app/schemas/telegram_send_requests.py`
- Create: `backend/app/services/telegram_send_requests.py`
- Create: `backend/app/api/routes/telegram_send_requests.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_stage04_test_send.py`

- [x] Step 1: Write failing tests for request, confirm, blocked non-allowlisted target and invalid state.
- [x] Step 2: Implement request creation with `pending_confirmation`.
- [x] Step 3: Implement confirm with allowlist check and outbox event.
- [x] Step 4: Implement route and register router.
- [x] Step 5: Run test send API tests.

### Task 9: Telegram Bot Client And Worker Handler

**Files:**

- Create: `backend/app/clients/telegram_bot.py`
- Modify: `backend/app/workers/stage03_handlers.py`
- Test: `backend/tests/unit/test_stage04_telegram_bot_client.py`
- Test: `backend/tests/integration/test_stage04_test_send.py`

- [x] Step 1: Write unit tests for client request construction and response redaction using fake HTTP client.
- [x] Step 2: Write worker tests proving allowlist re-check and idempotency.
- [x] Step 3: Implement Telegram Bot `sendMessage` client behind interface.
- [x] Step 4: Implement worker handler for `telegram.test_send_requested`.
- [x] Step 5: Run client and worker tests.

## 10. Phase 04.5: Staging Rehearsal And Stage Close

### Task 10: Staging Rehearsal

**Files:**

- Update: `project-docs/08-implementation/STAGE_04_ACCEPTANCE_CHECKLIST.md`
- Update: `project-docs/08-implementation/STAGE_04_PROGRESS.md`
- Update: `project-docs/08-implementation/STAGE_04_OPERATIONS_RUNBOOK.md`
- Update: `project-docs/08-implementation/STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md`

- [x] Step 1: Confirm with user before any staging env change or real Telegram send.
- [x] Step 2: Deploy Stage 04 code to Tencent Cloud staging.
- [x] Step 3: Run migration.
- [x] Step 4: Configure `TELEGRAM_SEND_MODE=restricted_test` and test chat allowlist server-side only.
- [x] Step 5: Create binding through API.
- [x] Step 6: Send new real Telegram message and verify bound inbox evidence.
- [x] Step 7: Create and confirm test send request.
- [x] Step 8: Verify allowlisted test chat receives message.
- [x] Step 9: Record redacted evidence.
- [x] Step 10: Run full backend suite or record latest unchanged-code evidence.

Task 10 evidence: staging ran commit `360d376`; migration current/head was `20260706_0011`; `/views/telegram_bindings/records` showed binding `76413f27-7de9-4bb4-8e51-ca0ded8f46eb`; `/views/telegram_inbox/records` showed update `184365902` as `bound`, `processed`, `intent_ready`; `/views/telegram_send_requests/records` showed request `05f46883-e4c7-4669-99cb-99a093629f70` as `sent`; outbox and audit records confirmed processing; staging was returned to `TELEGRAM_SEND_MODE=dry_run` with allowlist cleared.

## 11. Final Stage 04 Acceptance

Stage 04 can be accepted only when:

- All Stage 04 focused automated tests pass.
- Existing Stage 02 and Stage 03 regression tests pass.
- Alembic offline SQL reaches Stage 04 migration.
- Binding management staging evidence exists.
- Test send staging evidence exists and target is allowlisted test chat only.
- Intent placeholder evidence exists without LLM call.
- No customer group send, provider write, LLM call or funds movement occurred.
