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

### S6.2 Local Matrix

- Closed delivery extension/model, exact one-target configuration, server-only create/confirmation and generic-confirmation exclusion use unit tests only; no browser delivery route is permitted.
- Fake Bot client cases exercise the only permitted fixed button payload. Disposable local PostgreSQL exercises successful terminalization, definite rejection, transport uncertainty, sequential reservation replay and pointer revocation.
- The remaining local S6.2 matrix is deliberately limited to simultaneous two-Worker reservation and any future logger sink. Real Bot delivery and Mini App opening are manual, explicitly authorized work only.

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
- S3 Governance Readback: API tests prove independent `member.read` / Base-scoped `audit.read`, closed DTO shapes, denial and opaque cursor behavior; disposable PostgreSQL proves isolation/redaction/paging; frontend tests prove strict parser/key/workbench paths. A Browser run is required for desktop/mobile entry, safe rows/timeline, retry/denial and console scan, but remains external-environment-pending until the in-app Browser can reach the local built client.
- S4 Governance Write: focused route/authorization/redaction and disposable PostgreSQL tests prove fixed role/policy commands, revision/idempotency/row-lock behavior, hidden field omission from schema/presentation/detail and record-update non-escalation. Typed Mini App parser/query/workbench tests and the built-client local pass prove no optimistic role/policy result, restricted-owner V1 grant reuse and `1440/1280/430/390` labelled entry paths. The exhaustive delayed governance-write `401/403/404/409` App-flow matrix and Browser stale/denied/retry/focus-return permutations remain required before full S4 acceptance; see `evidence/stage07-governance-write.md`.

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
- The bounded F2 matrix below is implemented and verified locally. Local commits remain insufficient by themselves: the recorded automated, PostgreSQL and Browser evidence is required, and none of it is Telegram/staging/production evidence.

## 2.3 V1 Saved View Builder Required Evidence

- V1 implementation is user-approved and is `partial-local`. The detailed requirements remain in `docs/superpowers/specs/2026-07-11-stage07-v1-saved-view-builder-design.md` and its BDD/SDD/work-surface/index companions; only the explicitly recorded focused/API/PostgreSQL/client/Browser observations count as evidence.
- Unit/API cases must cover every typed field/operator eligibility branch, four view-type configurations, private/restricted/system-default scope rules, owner/editor/viewer separation, safe response redaction and all fixed error allowlist codes.
- Disposable PostgreSQL cases must prove private initialization rollback, replay, changed-payload conflict, grant replacement rollback, unique recipient grant under concurrency, version conflict, one-default Grid invariant and server filter/sort before pagination.
- Query tests must prove the server evaluates only flat `AND` conditions, applies at most three stable sort rules plus record-ID tie-break, rejects `OR`/nested/arbitrary expressions and does not make the browser reconstruct semantics.
- F2 integration must prove relation filters use only server candidates, numeric lookup filter/sort works only over safe numeric output, and relation/lookup grouping is rejected.
- Frontend cases must prove protected query-key isolation, create/replay/409/401/403/404 behavior, owner/editor/viewer controls, member candidate cleanup, no raw config/policy/member role render and exact authoritative reread after each successful command.
- Browser cases must cover private creation, restricted sharing, editor/viewer separation, Grid filter/sort/group, Kanban group, Calendar date, Form order, invalid/denied/conflict states and console scan at 1440/1280/430/390. Tasks 12--13 observed a partial matrix: four view types at the required widths, owner/editor/viewer UI differences, disabled 13th filter/4th sort, relation/lookup group exclusion, safe F2 relation label, editor save and safe `409` reread with console `[]`. Real-backend authority intersection, numeric-lookup mutation, Record Detail relation edit and complete type-invalid Browser coverage are still outstanding. Every temporary server/fixture was removed before reporting.

### F1 Automated Current Evidence

- 2026-07-11: direct-record mutation safety repair added red/green application/query-state cases for late `403` after record switch, `401` versus a concurrent PATCH completion, detail-close cancellation, 401/403/404 save/conflict failures and exact 404 cleanup. Fresh Mini App regression: `14` passed test files and `67` passed tests; `npm.cmd run build` passed. This is TD001 cache/race evidence, not backend authorization proof.
- 2026-07-11: fresh full backend regression with the authorised disposable local URL: `440 passed, 17 skipped in 23.10s`. The only skips are 17 historical Stage02 online-PostgreSQL cases requiring `STAGE02_ONLINE_DATABASE_URL`; the five Stage06-local security cases and three F1 disposable-PostgreSQL cases ran and passed.
- 2026-07-11: fresh Mini App regression after the duplicate-feedback refinement: `13 passed` test files and `55 passed` tests; `npm.cmd run build` passed.
- 2026-07-10: `alembic heads` reports only `20260710_0021 (head)`; `alembic upgrade head --sql` exited successfully.

### F2 Automated Current Evidence

- 2026-07-11: the protected candidate transport/Pickers, create/direct-edit relation values, safe Detail/Canvas rendering and F2 Builder have Mini App component/application coverage. The fresh final command `npm.cmd test -- --run` passed `18` files / `93` tests, including the regression that removes the current same-table record from the relation Picker candidate page. `npm.cmd run build` passed.
- 2026-07-11: the authorised disposable `STAGE06_LOCAL_DATABASE_URL` was reset/migrated by the documented smoke script before `python -m pytest -q tests/integration/test_stage07_relation_lookup_postgres.py` passed `6` tests. They prove relation initialization rollback, concurrent ordering, same-key replay, lookup initialization rollback, record/field dependency guards and a real-PostgreSQL safe view projection for all fixed aggregations (`values`, `count`, `count_distinct`, `sum`, `average`, `min`, `max`).
- 2026-07-11: fresh full backend `python -m pytest -q` passed `477` and skipped `17`. Every skip is a historical Stage02 online-PostgreSQL smoke case gated by absent `STAGE02_ONLINE_DATABASE_URL`; the F2 PostgreSQL suite did not skip.
- Builder coverage includes relation/lookup safe payload shapes, fixed aggregation choices, retry-only idempotency, 409 lock, protected schema prefetch, receipt reread, 403 failure, and delayed prefetch races on close/workspace/table/view replacement. Detail coverage includes ID-only PATCH mapping, lookup read-only behavior and exact candidate-cache cleanup.
- 2026-07-11: a disposable local proxy fixture exercised actual Mini App interactions at 1440px (relation builder, numeric lookup builder, candidate cursor page, record create and direct relation edit), 1280px (Detail/chip/lookup rendering), 430px (full-height F2 builder bounds) and 390px (Relation Picker bounds). A second desktop fixture exercised nested safe lookup output, replay `200` plus reread, `409` Builder lock, allowlisted `lookup_target_incompatible` feedback without the server message, and candidate `403` denied boundary. A later mobile fixture run observed the 430px conflict-locked Builder controls, a replay-shaped `200` that closed the Builder only after authoritative schema/presentation/record/create-form rereads rendered `Replay relation`, the 390px create-flow candidate `403` global-denied boundary, and the 390px `422 lookup_target_incompatible` fixed text `目标字段与聚合方式不兼容。` with no server-detail disclosure. Its `127.0.0.1` console error/warn scan was `[]`. Fixture/Vite processes and temporary scripts are removed after the run.
- 2026-07-11: a final disposable local F2 fixture rendered all seven aggregation outputs at 1440px (`["alpha","beta"]`, `73`, `59`, `107`, `13.5`, `2`, `97`) without an opaque target ID. In Record Detail edit mode, a same-table candidate response intentionally contained both the active record and a permitted target; the UI exposed only the permitted `Other record` candidate. The exact 1440px and 390px assertions were `Current record = 0`, `Other record = 1`, selected `Other record × = 1`; remove/reselect behavior completed without a local UI error. The fixture's local-origin console error/warn scan was `[]`.
- The bounded F2 requirement-by-requirement audit is reconciled in `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md` and the F2 BDD acceptance matrix. Remaining Stage07 work is outside F2: V1 views, imports/templates, Package 3/4, real Telegram identity/deep-link proof and production readiness.

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

## 4. Template/Import Package Actual Run (2026-07-12)

| Layer | Command / method | Result |
| --- | --- | --- |
| Mini App focused | `npm.cmd test -- --run` with 7 template/import files | `7 files / 14 tests passed` |
| Mini App build | `npm.cmd run build` | passed |
| Backend focused | five template/import/idempotency/authorization unit files | `22 passed` |
| Disposable PostgreSQL | `DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL; python -m pytest -q tests/integration/test_stage06_postgres_security.py` | `6 passed` |
| Migration smoke | `python scripts/stage06_local_postgres_migration_smoke.py` | passed at `20260711_0022` |
| Browser | built client + temporary same-origin proxy + real local FastAPI/PostgreSQL | CRM install/reread/close and in-Base import entry observed; console error/warn `[]` |

The existing integration file has no `postgres` marker, so the direct file command above is the valid PostgreSQL command; `-m postgres` would deselect it. The Browser cannot choose a local file in this environment. Do not record a Browser upload/preview/commit pass; component/API tests are the actual coverage for that flow.
