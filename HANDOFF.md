# Stage07 Handoff

## 1. Read This First

This handoff is for a new session with no prior context. It records the actual current state of the Stage07 Mini App worktree; it is not a claim that Stage07 is complete.

- Repository worktree: `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui`
- Branch: `codex/stage07-mini-app-ui`
- Latest commit at handoff: `06dada5 fix(stage07): close real postgres builder proof`
- Working tree at handoff: clean.
- User language: Chinese. Keep code, API, database and stable status identifiers in English.
- Current delivery rule: document first; do not implement a new schema/API/permission/technical direction without the user’s explicit approval. A change already described and approved in the relevant Stage07 documents may proceed without another confirmation.

Read these authoritative documents in this order before changing code:

1. `AGENTS.md`
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
3. `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`
4. `project-docs/08-implementation/STAGE_07_SDD.md`
5. `project-docs/08-implementation/STAGE_07_API_DATA_SECURITY_CONTRACT.md`
6. `project-docs/08-implementation/STAGE_07_BDD_AND_ACCEPTANCE.md`
7. `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
8. the relevant substage design/plan before touching that substage.

## 2. What This Project Is

The product is a Telegram-first generic multidimensional-table and no-code workspace platform, with table-bound digital employees. The durable product order is:

```text
workspace -> base -> table -> field schema -> record -> view/form/dashboard-lite
-> permission -> template/import -> digital employee -> draft confirmation -> audit
```

Stage02–Stage05 advertising-agency work is historical implementation evidence and an optional sample/template source only. Do not make it the top-level product model again. Telegram/chat/temporary agent memory are not durable business results unless the workflow persists an authorized platform resource, draft, audit event or controlled action.

## 3. Stage07 Goal And Actual Status

Stage07 is the responsive React/Vite Mini App and desktop browser surface over the Stage06 backend. It must expose platform resources through server-authorized, permission-filtered models without moving authority to the browser.

**Stage07 is not accepted.** It has a verified bounded Package 1/2 vertical path, not a finished product.

### Completed, bounded `implemented-local`

- Server-verified Mini App bootstrap, active membership/workspace navigation, permission-filtered Home/Base/table/view/record reads and protected query-state cleanup.
- Base Canvas with Grid/Kanban/Calendar/Form presentation dispatch, cursor-safe paging, scalar record create and version-aware scalar edit.
- P3 atomic Base/Table Builder:
  - `POST /workspaces/{workspace_id}/base-initializations`
  - `POST /bases/{base_id}/table-initializations`
  - server-generated table keys, blank initial table, one default Grid, safe receipts, idempotency, authorization and audit.
- F1 Independent Field Builder:
  - `POST /tables/{table_id}/field-initializations`
  - approved types only: `text`, `number`, `date`, `status`, `single_select`, `multi_select`, `user`, `checkbox`, `url`, `email`, `phone`.
  - server-generated key/order/default policy, safe schema/receipt projection, explicit saved-view field append, idempotency, audit and choice-aware record create/direct edit.
- F1 browser evidence at `1440`, `1280`, `430`, `390`:
  - duplicate name shows only the fixed local Chinese message, retains the typed name and does not render the server message;
  - pending creation locks create/close/cancel while keeping the drawer/sheet visible;
  - the direct-edit success visual is retained at `project-docs/08-implementation/artifacts/stage07/f1-direct-edit-success-1440.png`.
- Real local PostgreSQL evidence for P3/F1:
  - P3 rollback, same-key concurrency and default-view uniqueness;
  - F1 rollback, same-key replay, distinct-key serialized order and view append;
  - all six passed on 2026-07-11.

### Deliberately not implemented / not accepted

- F2 relation/lookup Builder and V1 additional View Builder.
- Server-recognized filter/sort/group UI behavior.
- Template/import UI.
- Package 3 governance: members, roles, permissions and audit-readback UI.
- Package 4: team Bot contacts, personal assistant, knowledge source selection, memory partitions, draft detail/confirm UI and Telegram deep-link/handoff.
- Real Telegram Mini App identity/deep-link evidence, production/staging release, and full Stage07 visual fidelity/exit acceptance.

The traceability table is authoritative for the remaining scope: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`.

## 4. Most Recent Work And Why It Matters

Commit `06dada5` closed the prior database-evidence gap and fixed a real defect exposed only by PostgreSQL.

### Root cause found

P3 created a Base/Table, then immediately re-read the new object via `Session.get()` in the same transaction. With SQLAlchemy/PostgreSQL, the new object was still pending, so the read returned `None` and the endpoint reported `base_not_found`, then `table_not_found`. The in-memory UoW hid this behavior.

### Minimal repair

`backend/app/services/stage06_platform.py` now calls `self.session.flush()` in:

- `SqlAlchemyStage06PlatformUnitOfWork.add_base`
- `SqlAlchemyStage06PlatformUnitOfWork.add_table`

This is a transaction flush, not a commit. Atomic rollback semantics are still verified by the real database test.

`backend/tests/integration/test_stage06_postgres_security.py` also now imports `UUID` and `IntegrityError`, and includes response bodies in two failure assertions. Those imports were missing and initially masked the default-view database test.

## 5. Evidence And Exact Verification Commands

The disposable local PostgreSQL URL is persisted for the current Windows user as `STAGE06_LOCAL_DATABASE_URL`. A new terminal/Codex process may be needed to inherit it. Do not write the full connection string into tracked files.

The target is intentionally local and disposable. The test fixture resets the PostgreSQL `public` schema before migrations. Never point this variable at a development, staging or production database.

Run from `backend`:

```powershell
# Verify the configured local target, reset it and run Alembic migrations.
python scripts/stage06_local_postgres_migration_smoke.py

# P3 + F1 real-PostgreSQL proof.
python -m pytest -q tests/integration/test_stage07_field_builder_postgres.py tests/integration/test_stage06_postgres_security.py -k "stage07 or field_initialization or default_view"

# Full backend regression with local PostgreSQL evidence enabled.
python -m pytest -q

# Migration checks.
alembic heads
alembic upgrade head --sql
```

Latest verified results:

| Check | Result | Limit |
| --- | --- | --- |
| Disposable migration smoke | passed, Alembic `20260710_0021` | local database only |
| P3/F1 real PostgreSQL matrix | `6 passed, 2 deselected` | local database only |
| Full backend | `440 passed, 17 skipped` | skips are the 17 historical Stage02 online-PostgreSQL tests without `STAGE02_ONLINE_DATABASE_URL` |
| Mini App tests | 13 files / 55 tests passed | mocked transport; not backend authorization proof |
| Mini App production build | passed | compilation/build only |

Run from `mini-app` when frontend code changes:

```powershell
npm.cmd test -- --run
npm.cmd run build
```

When a UI path changes, use the in-app Browser, inspect the actual rendered state at the required desktop/mobile widths, inspect console warnings/errors, then remove any disposable fixture/server. Do not cite a component test as browser evidence.

## 6. Immediate Next Step: Discussion, Not Code

P3 and F1 are closed bounded substages. The next safe work is to discuss **F2 and V1**, before writing code:

- **F2 relation/lookup:** safe target Base/table/field selection, field-level read permissions, relation write semantics, lookup read-only/refresh semantics, delete/rename behavior, safe request and receipt models, browser error boundaries and audit.
- **V1 additional views:** Grid/Kanban/Calendar/Form creation/configuration, grouping/date/form-field choices, saved filter/sort semantics, default-view switching, field visibility, permission model, browser/mobile interaction and audit.

These decisions alter API/data/permission/interaction contracts. Prepare a concise options-and-tradeoffs proposal for the user and obtain explicit confirmation. Do not infer approval from existing Stage06 primitive endpoints: their raw config/policy shapes are not safe client contracts.

After F2/V1 are approved, write the detailed design, BDD/SDD/API-security updates and implementation plan first, then use test-first implementation and perform real UI QA. Import/template should be a separate later decision unless the user explicitly combines it.

## 7. Non-Negotiable Safety And Product Boundaries

- Never send raw policies, technical keys, arbitrary field options, raw saved-view configuration, hidden field values, draft before/proposed values, audit bodies, provider keys or database credentials to the browser.
- The browser must not reconstruct permissions, derive policy, create client-only filter/sort/group semantics or claim an action succeeded before an authorized persisted receipt/re-read.
- Digital employees cannot bypass authorization, confirmation, audit or backend service boundaries. Agent writes default to `record_change_draft` then explicit confirmation.
- No direct AI write, self-confirmation, audit bypass, broad Telegram send, provider write, funds movement or production account operation.
- Keep the selected visual grammar: true white, cool gray, restrained azure, compact dense table UI and 8px radii. Do not introduce dark AI dashboards, decorative gradients, glows or generic card walls.
- Do not push unless the user asks. Commit coherent scoped changes; inspect a dirty worktree before staging.

## 8. Pitfalls That Must Not Be Repeated

1. **Do not accept in-memory tests as transaction proof.** The P3 flush defect passed in memory and failed on PostgreSQL. Any atomic, concurrent, unique-index or rollback claim needs the disposable real PostgreSQL suite.
2. **Do not point Stage06 smoke/tests at a real database.** The fixture drops and recreates the `public` schema. The target must be local and disposable; its database name must satisfy the Stage06 `stage06`/`test`/`smoke` safety classification.
3. **Do not count a skipped test as passed evidence.** Before the local DB was configured, the same six tests were skips. Evidence status must say exactly pass/fail/skip.
4. **Do not force an impossible workspace/view switch during a pending modal request.** The UI correctly disables close/cancel while pending. Prove delayed old-scope protection with the application-level scope-isolation test instead.
5. **Do not leak backend error details.** The frontend may map only `422.detail.code === "duplicate_field_name"` to the fixed local Chinese message. Ignore `detail.message` and all unrecognized/malformed codes; keep generic safe feedback.
6. **Do not begin F2/V1 merely because F1 is complete.** F2/V1 need user-approved safe API/permission/interaction contracts first.
7. **Do not edit Stage06/Stage07 truth documents casually.** Stage06 is the backend baseline; Stage07 documents record bounded local evidence, not production readiness.
8. **Do not retain disposable UI fixture imports, preview servers or test artifacts.** Verify they are removed before commit.

## 9. Completion Standard

Do not claim Stage07 complete until the source-of-truth BDD, visual QA, responsive flows, permission denial/revocation behavior, controlled draft lifecycle, Telegram identity/deep-link evidence and all Package 2–4 acceptance rows are implemented and verified against approved contracts.

Before any completion statement, run fresh evidence commands, read the full output, update the traceability/acceptance documents and clearly list remaining gaps. Production readiness is a separate later gate.
