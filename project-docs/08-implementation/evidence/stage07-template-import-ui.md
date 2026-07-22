# Stage07 Template/Import UI Evidence

## Status

- Evidence status: local implementation evidence
- Date: 2026-07-12
- Scope: approved existing-contract template shelf/install, Base-to-draft-template save, CSV/XLSX preview, scalar mapping and explicit commit
- Environment: built Mini App + temporary same-origin local proxy + real local FastAPI + disposable local PostgreSQL
- Boundary: this is neither Telegram Mini App identity evidence nor staging/production evidence.

## Implemented Behavior

1. The Mini App uses typed, allowlisted transport for template list/install/save and import create/read/commit. It sends an idempotency key for each retryable mutation and does not retain manifests, raw server-error detail or file data in query keys.
2. The template shelf shows safe card metadata only. Installation clears the exact protected state, rereads authorised Home/Base state, opens only the returned Base found in that reread, and closes the shelf after that transition.
3. The Canvas `更多 Base 操作` menu exposes `保存为模板` and `导入到当前 Base` only behind the existing non-authoritative management hint; the backend remains authoritative.
4. Import accepts one `.csv` (at most 5 MiB) or `.xlsx` (at most 10 MiB), creates a server preview, permits only `text`, `number`, `date`, `checkbox` mappings, and issues a separate explicit commit. It does not add relation/lookup/select/user/formula mapping or a client-side parser.

## Regression Repairs Found During Real PostgreSQL / Browser Use

| Finding | Regression proof | Repair | Result |
| --- | --- | --- | --- |
| An official template containing an example record could fail on SQLAlchemy because the just-created fields were not flushed before record validation. | New disposable PostgreSQL test installs CRM with an example record. It failed with `unknown_field: name` before the repair. | Added the existing Unit of Work `flush()` boundary and flushes fields/views before example records are validated. | The PostgreSQL integration suite passes. |
| Two legitimate installs with different idempotency keys but identical payloads could collide on globally-unique `trace_id`. | The same PostgreSQL test installs CRM twice using distinct keys; the pre-repair path raised `uq_stage06_idempotency_trace_id`. | Replaced ad-hoc trace construction with a bounded hash of operation, request fingerprint and idempotency key in all existing idempotent route paths. | Both receipts persist without changing an API, schema or permission contract. |
| A successful template install opened its Base but left the template shelf visible. | New Mini App lifecycle test required the receipt Base to be open and the dialog absent. It failed before the repair. | The post-reread close check now uses current session/workspace authority rather than the invalidated Canvas request generation. | Focused UI lifecycle test and Browser path pass. |

## Fresh Verification

| Check | Command / observation | Actual result |
| --- | --- | --- |
| Mini App focused tests | `npm.cmd test -- --run` with the 7 template/import test files | `7` files, `14` tests passed |
| Production bundle | `npm.cmd run build` | exit `0`; TypeScript build and Vite bundle completed |
| Backend selected contract tests | five template/import/idempotency/authorization unit files | `22 passed` |
| Real local PostgreSQL integration | `DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL; python -m pytest -q tests/integration/test_stage06_postgres_security.py` | `6 passed` |
| Disposable database migration smoke | `python scripts/stage06_local_postgres_migration_smoke.py` | passed at Alembic head `20260711_0022`; required template/import/idempotency tables present |
| Browser main path | Built client installed official CRM through the shelf against real local FastAPI/PostgreSQL. | CRM Base and its `Customers` grid/example record rendered; the template dialog was absent after authorised reread. |
| Browser in-Base entry | Opened `更多 Base 操作` then `导入到当前 Base`. | The `导入数据表` dialog rendered, documented CSV/XLSX and 5/10 MiB limits, with preview disabled until a file is chosen. Browser console `error`/`warn` scan was `[]`. |

## Deliberate Evidence Limits

- The in-app Browser surface available in this run did not expose a file-selection/upload API. Therefore no browser CSV/XLSX upload, preview or commit is claimed. The file adapter, preview, scalar mapping and explicit commit are covered by the focused component/API tests above.
- The previous plan's `-m postgres` variant selects no cases because this existing integration file is not marked `postgres`; the file was run directly with the documented disposable PostgreSQL URL instead.
- No staging, production, Telegram identity/deep-link, schema migration, permission-model change, new API route, template sharing/versioning/deletion, multi-file import, or non-scalar mapping was implemented.

## 2026-07-16 Browser Focus and Responsive Addendum

- Environment: current local Vite Mini App against local FastAPI and a disposable PostgreSQL fixture containing synthetic data only. This is local implementation evidence, not Telegram, staging, production or identity evidence.
- Regression: closing the in-Base import dialog previously left focus on `body`. The cause was that the import flow did not preserve a stable trigger, unlike the View Builder and other panels.
- Repair: the Base Canvas keeps the durable `更多 Base 操作` button reference, passes it to the existing App import opener, and the existing import close path restores it in a microtask after unmount. No schema, API, permission or external-system behavior changed.

| Check | Reproducible command / observation | Actual result |
| --- | --- | --- |
| Red/green regression | `mini-app: npm.cmd test -- --run src/test/import-flow.test.tsx` | The new full-App focus assertion failed before the repair (`body` received focus) and passed after it. |
| Focused regression | `mini-app: npm.cmd test -- --run src/test/import-flow.test.tsx src/test/base-template-actions.test.tsx` | `2` files, `3` tests passed. |
| Literal Browser path | In the Codex in-app Browser, open a synthetic local Base, `更多 Base 操作` → `导入到当前 Base` → `关闭导入`. | The dialog rendered and focus returned to `BUTTON[aria-label="更多 Base 操作"]`. |
| Four-width Browser path | Repeat the literal path at `1440×900`, `1280×900`, `430×844` and `390×844`. | All four widths rendered exactly one `导入数据表` dialog and returned focus to `更多 Base 操作`. |
| Full client regression | `mini-app: npm.cmd test -- --run` | `63` files, `231` tests passed. |
| Production bundle | `mini-app: npm.cmd run build` | exit `0`; TypeScript and Vite production bundle completed. |

This direct Browser evidence permits only `TI-A08` to move to `evidenced-pending`. It does not satisfy the separate literal file-selection, preview or commit requirements in `TI-A04` or `TI-A06`: the available in-app Browser still exposes no supported local file-upload action.

## Cleanup

Temporary synthetic seed/proxy scripts and local FastAPI/proxy processes are removed after this evidence capture. The disposable migration smoke is the final database reset in this package.
