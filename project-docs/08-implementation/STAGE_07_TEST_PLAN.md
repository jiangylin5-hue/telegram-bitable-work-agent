# Stage 07 Test Plan

## Status

- Document status: active verification matrix
- Scope: unit, integration, contract, visual and manual Mini App evidence

## 1. Test Layers

| Layer | Focus | Evidence |
| --- | --- | --- |
| unit | view-model mapping, field formatting, state reducers, diff rendering | deterministic component tests |
| integration | route bootstrap, queue destinations, view changes, draft lifecycle | mocked authorized/denied API responses |
| contract | request shape, cursor/version/idempotency handling, proposed endpoint gates | backend/API tests and typed client contract tests |
| security | hidden fields, workspace boundaries, revoked membership, chat/Bot scope | negative tests plus cache-clear assertions |
| visual | selected white design system, desktop/mobile layout and state screens | reviewed screenshots at target viewports |
| manual | Telegram entry/deep link and approved real identity path | sanitized run note only |
| F1 PostgreSQL | field-init rollback, same-key replay, distinct-key order and view visibility | disposable local PostgreSQL only; an unavailable `STAGE06_LOCAL_DATABASE_URL` is an explicit skip/gap |

## 2. Required Matrices

- desktop widths: 1280px and 1440px; mobile widths: 390px and 430px;
- roles: owner/admin/builder/operator/viewer plus inactive member;
- views: Grid/Kanban/Calendar/Form;
- states: loading/empty/denied/error/conflict/expired/success;
- Bot classes: team contact and personal assistant;
- write outcomes: confirm/reject/replay/conflict/expired.
- F1 field types: `text`, `number`, `date`, `status`, `single_select`, `multi_select`, `user`, `checkbox`, `url`, `email`, `phone`; relation/lookup/JSON remain negative cases.
- F1 failure states: blank/duplicate name, invalid/missing choices, raw request extras, schema-policy leak, 401/403/404/409/5xx and failed view update rollback.

## 2.1 F1 Required Evidence

- service tests prove generated keys, default policy, explicit-view append-once, implicit-view no-op and sanitized audit;
- API tests prove `field.manage` and cross-workspace denial before writes, strict request shape, safe receipt/schema projection and idempotency replay/conflict;
- record tests prove configured choice membership and multi-select distinctness while option-less legacy fields remain compatible;
- real PostgreSQL tests prove table-row serialization and all-or-nothing rollback when an approved disposable URL is configured;
- frontend panel/application tests prove drawer/sheet accessibility, retry/409 handling, exact schema reread, stale response rejection and protected-scope cleanup;
- Browser QA compares the retained Workspace Ledger source at 1440/1280/430/390 and records zero relevant console errors.

### F1 PostgreSQL Current Evidence

- 2026-07-10: `python -m pytest -q tests/integration/test_stage07_field_builder_postgres.py` collected the rollback, same-key replay and distinct-key concurrent-order cases, then reported `3 skipped` because `STAGE06_LOCAL_DATABASE_URL` is absent.
- The skipped result is not real PostgreSQL proof. An authorised disposable local URL remains required before F1 can claim database rollback, row-lock ordering or concurrent view-configuration evidence.

## 3. Completion Rule

No visual pass substitutes for authorization/contract tests. No mocked UI pass substitutes for the approved Telegram deep-link smoke. Test artifacts must not contain raw hidden fields, prompts, memory or Telegram text.
