# Stage07 TD010 Browser Lifecycle Evidence — 2026-07-16

## Status

- Evidence status: `evidenced-pending` local acceptance evidence for TD010 only.
- Scope: one fresh Codex in-app Browser run against the current Mini App source and a disposable loopback-only fixture.
- Stage decision: `not accepted`. This record may support individual `DEM-A01` through `DEM-A10` rows, but it does not independently accept them or Stage07.
- External boundary: no Telegram, OpenRouter, deployment, production, staging, user Chrome, real database, or real external write was used.

## Method And Safety Boundary

The Mini App was run locally at `127.0.0.1` through Vite. A temporary Python fixture supplied only the closed TD010 response shapes and was restarted during the run to reset synthetic state. Its source file was removed after capture. The observed employee, Base, view and member labels are synthetic acceptance data only.

This browser record is deliberately composed with the existing TD010 unit, Mini App and disposable-PostgreSQL evidence; it does **not** claim that the fixture proves server persistence, row locking, idempotency storage, permission enforcement, audit storage, provider execution, or any external delivery.

## Observations

| Requirement IDs | Direct current observation | Retained evidence |
| --- | --- | --- |
| `DEM-A01`--`DEM-A04` | The manager opened the Base-bound workbench, created one draft employee, selected the only provided table/view, selected only `summarize` and `draft_update`, and never saw runtime/provider/prompt/memory/policy/record controls. The fresh draft remained inactive until configuration and grants were persisted. | `01-manager-draft.png`; `02-manager-active-read-only.png` |
| `DEM-A05`--`DEM-A06` | The manager persisted one `assigned` member. A separate operator rendering of the same Base had zero `数字员工管理` controls while retaining the ordinary `数字员工` entry. The existing service/migration tests remain the authority for grant eligibility and legacy workspace semantics. | `06-member-no-management-entry.png` |
| `DEM-A07`--`DEM-A08` | After server rereads for config and member grants, activation produced an `active` read-only employee. Pausing changed it to an editable `paused` employee without exposing extra controls; a post-conflict reread and reactivation returned it to the same read-only active state. | `02-manager-active-read-only.png`; `04-manager-reactivated.png` |
| `DEM-A09` | The synthetic server returned a `409` for the first paused-to-active retry. The UI rendered only its fixed Chinese reread message and a `重新读取员工配置` action; no raw server detail appeared. After reread, the retry became active. Existing unit/PostgreSQL evidence covers the actual concurrent, stale and idempotency transaction matrix. | `03-manager-conflict-recovery.png`; current DOM observation log |
| `DEM-A10` | Closing the desktop workbench returned focus to the originating `数字员工管理` button. The same focus return was independently observed at `390 × 844`; the mobile active state was also rendered without a hidden management escape hatch. Existing protected-query tests remain the authority for exact cancellation/removal. | `05-manager-mobile-active.png`; `07-manager-mobile-focus-return.png`; current DOM observation log |

## Visual Inspection

Each retained screenshot was inspected after capture. The management surface uses the existing workspace visual language: a safe Base overlay, three bounded columns on desktop and a stacked mobile workbench. The current record establishes functional/visual state evidence only; the separate visual-reference acceptance audit still controls the broader UI-reference decision.

## Current Focused Regression

```text
mini-app: npm.cmd test -- --run src/test/digital-employee-management-api.test.ts src/test/digital-employee-management-app-flow.test.tsx src/test/digital-employee-management-query.test.ts src/test/digital-employee-management-workbench.test.tsx src/test/base-canvas-management.test.tsx
result: 5 files passed, 12 tests passed

mini-app: npm.cmd run build
result: passed
```

No backend/PostgreSQL suite was rerun for this browser-evidence-only update; the existing `DEM-U` and `DEM-PG` evidence remains separately named in the acceptance ledger.

## Retained Artifacts

- [Draft manager workbench](../artifacts/stage07/td010-acceptance-2026-07-16/01-manager-draft.png)
- [Active manager read-only state](../artifacts/stage07/td010-acceptance-2026-07-16/02-manager-active-read-only.png)
- [Fixed conflict and reread state](../artifacts/stage07/td010-acceptance-2026-07-16/03-manager-conflict-recovery.png)
- [Reactivated manager state](../artifacts/stage07/td010-acceptance-2026-07-16/04-manager-reactivated.png)
- [Mobile active state](../artifacts/stage07/td010-acceptance-2026-07-16/05-manager-mobile-active.png)
- [Member Base without the management entry](../artifacts/stage07/td010-acceptance-2026-07-16/06-member-no-management-entry.png)
- [Mobile focus-return state](../artifacts/stage07/td010-acceptance-2026-07-16/07-manager-mobile-focus-return.png)

## Remaining Acceptance Limit

All current observations are local and synthetic. A later independent Task 5 review must reconcile each BDD row with this artifact and its named automated evidence before it can change from `evidenced-pending` to `accepted`. No external operation is authorized by this note.

## Temporary Cleanup

The local fixture process and Vite process were stopped and the temporary fixture source was deleted. One generated non-executable Python bytecode cache remains under `.local/__pycache__` because this environment rejected its deletion; remove that cache before any deployment or commit.
