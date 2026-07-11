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
| F1 PostgreSQL | field-init rollback, same-key replay, distinct-key order and view visibility | disposable local PostgreSQL only; 2026-07-11 real-local run passed and does not constitute staging/production evidence |

## 2. Required Matrices

- desktop widths: 1280px and 1440px; mobile widths: 390px and 430px;
- roles: owner/admin/builder/operator/viewer plus inactive member;
- views: Grid/Kanban/Calendar/Form;
- states: loading/empty/denied/error/conflict/expired/success;
- Bot classes: team contact and personal assistant;
- write outcomes: confirm/reject/replay/conflict/expired.
- F1 field types: `text`, `number`, `date`, `status`, `single_select`, `multi_select`, `user`, `checkbox`, `url`, `email`, `phone`; relation/lookup/JSON remain negative cases.
- F1 failure states: blank/duplicate name with the allowlisted local feedback only, invalid/missing choices, raw request extras, schema-policy leak, 401/403/404/409/5xx and failed view update rollback.
- F2 relation/lookup: use the separate F2 BDD, SDD and complex-feature index as the exhaustive state source. Required cases include same-Base/permission denial, replay/conflict/rollback, candidate search/cursor/label omission, relation required/self/unreadable-target writes, all fixed aggregates, two-level/cycle failure, whole-lookup fail-closed omission, future delete guards, protected-cache cancellation and four-width UI QA.

## 2.1 F1 Required Evidence

- service tests prove generated keys, default policy, explicit-view append-once, implicit-view no-op and sanitized audit;
- API tests prove `field.manage` and cross-workspace denial before writes, strict request shape, safe receipt/schema projection and idempotency replay/conflict;
- record tests prove configured choice membership and multi-select distinctness while option-less legacy fields remain compatible;
- real PostgreSQL tests prove table-row serialization and all-or-nothing rollback when an approved disposable URL is configured;
- frontend panel/application tests prove drawer/sheet accessibility, retry/409 handling, exact schema reread, stale response rejection and protected-scope cleanup;
- Browser QA compares the retained Workspace Ledger source at 1440/1280/430/390 and records zero relevant console errors.

## 2.2 F2 Required Evidence

- Unit/API cases map one-to-one to F2-I01 through F2-I08 in STAGE_07_F2_RELATION_LOOKUP_COMPLEX_FEATURE_INDEX.md; each behavior begins red and becomes green before the next behavior.
- Disposable PostgreSQL cases prove source-table locking, all-or-nothing relation/lookup initialization, same-key replay, graph/dependency guards and concurrent relation-update integrity. They may not run against development, staging or production.
- Frontend cases prove typed transport redaction, fixed error-code mapping, verified user/workspace candidate keys, cancellation/removal, builder reread, Picker paging/order, relation required validation and direct-edit conflict behavior.
- Browser cases use a disposable fixture only and cover 1440, 1280, 430 and 390 widths; they record Builder, Picker, relation create/edit, nested lookup, aggregation families, denial/invalid state, late scope switch and final console scan. Fixture/server/artifact cleanup is recorded before any F2 completion report.
- Current F2 evidence is incomplete. Local commits are not substitutes for this matrix.

### F1 Automated Current Evidence

- 2026-07-11: direct-record mutation safety repair added red/green application/query-state cases for late `403` after record switch, `401` versus a concurrent PATCH completion, detail-close cancellation, 401/403/404 save/conflict failures and exact 404 cleanup. Fresh Mini App regression: `14` passed test files and `67` passed tests; `npm.cmd run build` passed. This is TD001 cache/race evidence, not backend authorization proof.
- 2026-07-11: fresh full backend regression with the authorised disposable local URL: `440 passed, 17 skipped in 23.10s`. The only skips are 17 historical Stage02 online-PostgreSQL cases requiring `STAGE02_ONLINE_DATABASE_URL`; the five Stage06-local security cases and three F1 disposable-PostgreSQL cases ran and passed.
- 2026-07-11: fresh Mini App regression after the duplicate-feedback refinement: `13 passed` test files and `55 passed` tests; `npm.cmd run build` passed.
- 2026-07-10: `alembic heads` reports only `20260710_0021 (head)`; `alembic upgrade head --sql` exited successfully.

### F2 Automated Current Evidence

- 2026-07-11: targeted backend F2/unit/API regression previously reported `53 passed`; the dedicated PostgreSQL relation/lookup suite is executable but remains `2 skipped` when the authorised disposable `STAGE06_LOCAL_DATABASE_URL` is absent. A skip is not PostgreSQL acceptance evidence.
- 2026-07-11: the protected candidate transport/Pickers, create/direct-edit relation values, safe Detail/Canvas rendering and F2 Builder now have Mini App component/application coverage. The final fresh command `npm.cmd test -- --run` passed `18` files / `92` tests, and `npm.cmd run build` passed. Fresh targeted F2 backend unit/API verification passed `39`; the subsequent full backend regression passed `463`, skipped `27` after a historical test assertion was aligned to the approved safe relation `{ id, label }` projection.
- Builder coverage includes relation/lookup safe payload shapes, fixed aggregation choices, retry-only idempotency, 409 lock, protected schema prefetch, receipt reread, 403 failure, and delayed prefetch races on close/workspace/table/view replacement. Detail coverage includes ID-only PATCH mapping, lookup read-only behavior and exact candidate-cache cleanup.
- 2026-07-11: a disposable local proxy fixture exercised actual Mini App interactions at 1440px (relation builder, numeric lookup builder, candidate cursor page, record create and direct relation edit), 1280px (Detail/chip/lookup rendering), 430px (full-height F2 builder bounds) and 390px (Relation Picker bounds). A second desktop fixture exercised nested safe lookup output, replay `200` plus reread, `409` Builder lock, allowlisted `lookup_target_incompatible` feedback without the server message, and candidate `403` denied boundary. The final console error/warn query was `[]`; fixture/Vite processes and temporary scripts were removed.
- Still required before an F2 acceptance report: documented negative-state mobile permutations, an authorised disposable PostgreSQL pass (the dedicated suite remains `2 skipped` without `STAGE06_LOCAL_DATABASE_URL`), and the final requirement-by-requirement acceptance audit. Full backend regression is no longer an open F2 evidence item.

### F1 PostgreSQL Current Evidence

- 2026-07-11: after `scripts/stage06_local_postgres_migration_smoke.py` reset and migrated the authorised disposable local database to `20260710_0021`, `python -m pytest -q tests/integration/test_stage07_field_builder_postgres.py` passed all three F1 cases. The combined P3/F1 real-PostgreSQL command passed `6` cases with `2` unrelated cases deselected; it proves the documented local rollback, replay, row-lock ordering, view-append and default-view invariants. It is not staging or production evidence.

### F1 Browser Current Evidence

- 2026-07-10: a disposable local fixture exercised 1440px, 1280px, 430px and 390px. It covered fieldless-to-status, visible header re-read, `multi_select`, allowed-choice record creation, blank-name feedback, same-key 503 retry, 409 lock and 403 denied-state cleanup. The retained Workspace Ledger reference and the 1440px rendered F1 state were reviewed together; all final fixture console warnings/errors were empty.
- The 390px nonempty-table trigger initially exposed a responsive defect: the generic toolbar rule hid the authorised field action. A test was written red, the explicit mobile field/record action override was added, and a fresh 390px fixture run opened the field sheet from its visible `添加字段` trigger.
- 2026-07-11: a corrected disposable fixture handled `PATCH` before its generic record read. It changed a record from `新建` / `[重点客户, 续费关注]` to `跟进中` / `[重点客户]`, reread version `2` into both Grid and Record Detail, emitted an empty error/warning log and retained `artifacts/stage07/f1-direct-edit-success-1440.png` after visual inspection.
- 2026-07-11: a disposable local error fixture exercised the actual transport chain for `422.detail.code = duplicate_field_name` at 1440px, 1280px, 430px and 390px: every run retained `客户阶段`, rendered only `字段名称已存在，请使用其他名称。`, rendered no `field_name` server message and had no warning/error console entries. At the same four widths, a pending field request kept the dialog visible and disabled `创建中…`, `关闭` and `取消`. The application test remains the authoritative scope-switch simulation: it resolves a delayed field receipt only after a workspace replacement and proves the old field does not render. Do not force an impossible background switch through the modal or treat component coverage as browser evidence. This closes the F1 browser state matrix only; it is not real-PostgreSQL proof.

### TD001 Direct-Record Mutation Browser Evidence

- 2026-07-11: a disposable local fixture/proxy used the actual Vite Mini App transport. It opened `客户管理`, edited `Ada Wong`, began a delayed `PATCH`, switched to `产品协作工作区` and waited for the old response. The rendered UI stayed on `需求规划`, did not render `Ada Ltd`, and the final console warning/error query returned `[]`. The fixture, proxy and Vite processes were removed/stopped. This validates the repaired workspace-switch race only; it does not replace the required whole-stage four-width matrix or real Telegram identity evidence.

## 3. Completion Rule

No visual pass substitutes for authorization/contract tests. No mocked UI pass substitutes for the approved Telegram deep-link smoke. Test artifacts must not contain raw hidden fields, prompts, memory or Telegram text.
