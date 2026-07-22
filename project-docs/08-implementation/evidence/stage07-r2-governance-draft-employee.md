# Stage07 R2 Governance, Draft and Employee Evidence

## Status

- Status: `partial R2 evidence recorded`; this document does not accept R2 or Stage07 as a whole.
- Scope: existing approved governance, draft, digital-employee management and Team Bot contracts only.
- Date: 2026-07-15.
- External side effects: one user-approved OpenRouter summary request only. No Telegram send, webhook/BotFather mutation, remote deployment, production database write or customer data processing occurred.

## Focused Existing-Contract Regression

| Package | Evidence | Result |
| --- | --- | --- |
| Governance / governance write / draft hub / employee management / Team Bot backend | focused unit tests | `41 passed` |
| Same packages | disposable local PostgreSQL integration tests | `11 passed` |
| Same packages | focused Mini App test files | `20 files / 62 tests passed` |
| Client build | `npm.cmd run build` | passed |
| Team Bot live-smoke preflight plus existing service/API regression | focused tests | `9 passed` |

The current test pass did not expose an approved-contract defect. No production service, route, schema, migration or permission rule was modified in response to the R2 regression run.

## Real OpenRouter Team Bot Safe-Route Smoke

The new reusable smoke harness loads the existing ignored local environment file without emitting its values. It creates one in-memory synthetic workspace/Base/Task/view/active employee, then exercises the existing Mini App API sequence:

```text
Team Bot contacts route
-> Team Bot permitted-context route
-> Team Bot summary route
-> existing live OpenRouter employee service
-> redacted audit receipt
```

The one real result was `passed` with the following non-sensitive assertions:

| Assertion | Result |
| --- | --- |
| contacts route | `200` |
| permitted-context route | `200` |
| summary route | `200` |
| summary kind | `summary` |
| answer | non-empty, never printed or stored in this evidence |
| citations | one safe opaque citation |
| audit receipt and agent run | present |
| model provider/name metadata | present, values omitted |
| synthetic record before/after | unchanged |
| raw prompt/response persistence | false |

The process emitted one `StarletteDeprecationWarning` about `TestClient`/`httpx`; it is a dependency warning, not a functional failure. It did not produce a browser console error or an API failure.

## Test-First Harness Addition

`test_stage07_team_bot_live_openrouter_smoke.py` was added first and failed at collection because the smoke module did not exist. The new harness then made the preflight green, and the combined preflight/Team Bot service/API test set passed `9 passed` before the real provider call.

The harness returns only stable outcome fields and never outputs an API key, raw prompt, model answer, citation ID, table/record ID, identity value or environment-file contents.

## Built Mini App Team Bot UI Observation

This observation is deliberately separated from the real-provider smoke above. A temporary loopback-only fixture served the already-built Mini App with a synthetic permitted workspace, one permitted `Project Risks` view and redacted summary data. It did **not** call OpenRouter, Telegram, a remote deployment or a user browser.

| Check | Observed result |
| --- | --- |
| Default desktop browser flow | The Home page exposed exactly one `团队 Bot` entry; the workbench opened with the no-memory notice and its three-step selection flow. |
| Permission-bounded selection | `Project Progress Assistant` then `Project Risks` became selectable in order; the summary button was one visible button after selection. |
| Summary rendering | The workbench rendered the synthetic permitted summary, synthetic safe citation and synthetic audit receipt, then exposed `打开 Base 继续处理`. It did not present a direct record-write control. |
| Mobile viewport | At `390 x 844`, the Team Bot heading, rendered summary and audit receipt remained present. |
| Browser console | `error`/`warn` entries: `0`. |
| Cleanup | The in-app Browser session was finalized. The local fixture process/source and loopback port are removed after this document update. |

The fixture uses invented safe strings (`safe-citation-r2`, `safe-audit-r2`) solely to prove the rendering branch. They are not production identifiers or a provider result. This observation proves client behavior and responsive visibility only; it cannot be combined with the API-route smoke to claim a literal browser-to-OpenRouter end-to-end run.

## Remaining R2 Boundary

- The real smoke proves the existing safe Team Bot API adapter route to a provider with synthetic non-empty permitted context; the local fixture proves the current Mini App selection/rendering surface. Neither is a user-operated Mini App visual/provider end-to-end acceptance.
- The R2 package still needs only its original residual visual/recovery scope: dedicated management-workbench lifecycle observation, selected governance/draft terminal and denial UI paths, and any matrix rows still explicitly marked `requires-evidence`.
- It adds no Team Bot memory, RAG, file/URL source, record picker, direct record write, customer group behavior, Telegram send, new provider selection, schema/API/action/permission model or browser persistence.

## 2026-07-15 R2 Final Reconciliation Addendum

The former residual list is now closed for the approved R2 contract by the continuous R0-R3 pass. The complete scope boundary and evidence separation is in [Stage07 R0-R3 Final Reconciliation](stage07-r0-r3-final-reconciliation.md).

| Former residual | Added observation or focused proof | Reconciled status |
| --- | --- | --- |
| management-workbench lifecycle | Built Mini App: paused employee -> active read-only configuration -> paused editable configuration, plus management/configuration reachability at `390 x 844`; existing R2 client/PostgreSQL evidence owns grant/version/audit authority | closed |
| governance terminal and denial/recovery UI | Built Mini App governance path rendered a version `409` as fixed copy, reread canonical field policy and omitted the fixture raw detail; focused governance suites own normal/denied/replacement variants | closed |
| draft terminal/recovery UI | Built queue -> field-filtered draft handoff rendered fixed conflict recovery, canonical confirmed state and safe audit receipt; focused draft suites own idempotency/replay/terminal authority | closed |
| personal assistant selected view | `test_stage07_assistant_context_api.py`: `2 passed`; two Mini App tests / `3 passed`; Browser selected the safe assistant then a permitted view and rendered a summary/citation without a write control | closed |
| Team Bot visual/provider evidence | The previously recorded real safe API-route -> OpenRouter smoke remains separate from Browser UI. The combined evidence proves the product path without claiming a literal Browser credential/provider trace. | closed for the approved bounded contract |

The R2 closure does not add customer behavior, generic direct writes, memory/RAG/files, a new provider, a new Telegram send or any schema/API/permission change. The temporary combined fixture was deleted and its port `4181` was closed.
