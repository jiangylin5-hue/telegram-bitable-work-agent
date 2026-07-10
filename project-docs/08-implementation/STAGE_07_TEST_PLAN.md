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
- F1 failure states: blank/duplicate name with the allowlisted local feedback only, invalid/missing choices, raw request extras, schema-policy leak, 401/403/404/409/5xx and failed view update rollback.

## 2.1 F1 Required Evidence

- service tests prove generated keys, default policy, explicit-view append-once, implicit-view no-op and sanitized audit;
- API tests prove `field.manage` and cross-workspace denial before writes, strict request shape, safe receipt/schema projection and idempotency replay/conflict;
- record tests prove configured choice membership and multi-select distinctness while option-less legacy fields remain compatible;
- real PostgreSQL tests prove table-row serialization and all-or-nothing rollback when an approved disposable URL is configured;
- frontend panel/application tests prove drawer/sheet accessibility, retry/409 handling, exact schema reread, stale response rejection and protected-scope cleanup;
- Browser QA compares the retained Workspace Ledger source at 1440/1280/430/390 and records zero relevant console errors.

### F1 Automated Current Evidence

- 2026-07-10: fresh full backend regression: `432 passed, 25 skipped in 13.27s`. The 25 skips comprise 17 historical Stage02 online-PostgreSQL cases, five Stage06 local-PostgreSQL security cases and three F1 disposable-PostgreSQL cases; no skipped test is counted as passed evidence.
- 2026-07-11: fresh Mini App regression after the duplicate-feedback refinement: `13 passed` test files and `55 passed` tests; `npm.cmd run build` passed.
- 2026-07-10: `alembic heads` reports only `20260710_0021 (head)`; `alembic upgrade head --sql` exited successfully.

### F1 PostgreSQL Current Evidence

- 2026-07-10: `python -m pytest -q tests/integration/test_stage07_field_builder_postgres.py` collected the rollback, same-key replay and distinct-key concurrent-order cases, then reported `3 skipped` because `STAGE06_LOCAL_DATABASE_URL` is absent.
- The skipped result is not real PostgreSQL proof. An authorised disposable local URL remains required before F1 can claim database rollback, row-lock ordering or concurrent view-configuration evidence.

### F1 Browser Current Evidence

- 2026-07-10: a disposable local fixture exercised 1440px, 1280px, 430px and 390px. It covered fieldless-to-status, visible header re-read, `multi_select`, allowed-choice record creation, blank-name feedback, same-key 503 retry, 409 lock and 403 denied-state cleanup. The retained Workspace Ledger reference and the 1440px rendered F1 state were reviewed together; all final fixture console warnings/errors were empty.
- The 390px nonempty-table trigger initially exposed a responsive defect: the generic toolbar rule hid the authorised field action. A test was written red, the explicit mobile field/record action override was added, and a fresh 390px fixture run opened the field sheet from its visible `添加字段` trigger.
- 2026-07-11: a corrected disposable fixture handled `PATCH` before its generic record read. It changed a record from `新建` / `[重点客户, 续费关注]` to `跟进中` / `[重点客户]`, reread version `2` into both Grid and Record Detail, emitted an empty error/warning log and retained `artifacts/stage07/f1-direct-edit-success-1440.png` after visual inspection.
- 2026-07-11: a disposable local error fixture exercised the actual transport chain for `422.detail.code = duplicate_field_name` at 1440px, 1280px, 430px and 390px: every run retained `客户阶段`, rendered only `字段名称已存在，请使用其他名称。`, rendered no `field_name` server message and had no warning/error console entries. At the same four widths, a pending field request kept the dialog visible and disabled `创建中…`, `关闭` and `取消`. The application test remains the authoritative scope-switch simulation: it resolves a delayed field receipt only after a workspace replacement and proves the old field does not render. Do not force an impossible background switch through the modal or treat component coverage as browser evidence. This closes the F1 browser state matrix only; it is not real-PostgreSQL proof.

## 3. Completion Rule

No visual pass substitutes for authorization/contract tests. No mocked UI pass substitutes for the approved Telegram deep-link smoke. Test artifacts must not contain raw hidden fields, prompts, memory or Telegram text.
