# Stage09 UI Recovery Local Audit — 2026-07-27

## Status

- Status: `partial-local-pass; authorized-browser-acceptance-pending`
- Scope: Stage09 I3 non-auth failure recovery, recovery-control affordance, compiled UI artifact inspection, and a bounded active-button static audit.
- Not a claim: production deployment, Telegram identity, real authorized Home/Base navigation, spreadsheet import/commit, record mutation, provider/LLM invocation, or a populated-table visual acceptance.
- Source worktree: `codex/stage09-ai-conversation-sse` at `6ed5666051339b0b877591bc6a3b42f5adc06e37` plus uncommitted Stage09 work.

## Reason For This Audit

The previous terminal error surface rendered only the fixed text `暂时无法加载工作区，请稍后重试。`. A user could not recover from either of these safe, non-auth failures:

1. the initial `GET /mini-app/bootstrap` request failed before a workspace was available;
2. a later safe Home reload failed after bootstrap had already selected an authorized workspace.

The global `state.status = 'error'` branch intentionally clears potentially stale panel state. That is safe, but without a Home-bound re-entry it made a failed click look inert and forced a manual browser reload. The remedy is deliberately a read/reload action only. It must not repeat a failed record write, import commit, draft confirmation, provider request, or other mutation.

## Implemented Recovery Contract

```text
non-401/403 bootstrap failure
-> network-recovery surface
-> retry bootstrap only
-> ordinary verified bootstrap/Home path

non-401/403 failure after workspace selection
-> network-recovery surface
-> reuse only current safe bootstrap membership + last workspace id
-> reload Home only

401/403
-> existing denied boundary
-> no retry and no identity fallback
```

The action is disabled while bootstrap is refetching or the session was invalidated. The recovery panel uses a compact 360px-or-viewport-width message stack, an explicit blue primary button, hover feedback, keyboard focus indication and a waiting cursor. It does not reveal raw transport errors.

## Verification Matrix

| Layer | Case | Evidence | Result |
| --- | --- | --- | --- |
| Red regression | Bootstrap network failure had no `重新加载工作区` button before implementation | focused test failed on the absent control | PASS: failure observed before code change |
| Unit/integration | First bootstrap failure → click retry → second bootstrap response → Home | `browser-session-recovery.test.tsx` | PASS |
| Unit/integration | Valid bootstrap → first Home failure → click retry → same workspace Home | `browser-session-recovery.test.tsx` | PASS |
| Safety regression | Bootstrap `401` has no recovery control | `browser-session-recovery.test.tsx` | PASS |
| Mini App suite | Existing and new interaction regressions | `npm.cmd run test:run` | PASS: 77 files, 400 passed, 2 historical skips |
| Production bundle | TypeScript build and Vite asset graph | `npm.cmd run build` | PASS; JS chunk warning recorded below |
| Browser DOM | Unavailable local API renders one recovery button; clicking it makes a retry request and returns to the same safe error page because the API remains unavailable | local Vite browser check | PASS, bounded negative-path evidence |
| Static button audit | `143` authored buttons scanned; `12` without `onClick` are either `type=submit` form controls or intentionally disabled upcoming actions | source audit, no active unbound button found | PASS |
| PostgreSQL backend suite | Full suite began but all PostgreSQL integration fixtures failed before their first test body; focused `-x` diagnosis isolated the common migration prerequisite | `python -m pytest tests/integration/test_stage06_postgres_security.py -x -vv` | BLOCKED: local role cannot create `vector` extension |

## UI And Build Follow-up — 2026-07-27

| Layer | Case | Evidence | Result |
| --- | --- | --- | --- |
| Build cache partition | Stable React, Query and icon dependencies are emitted separately from Mini App code | focused `vite-local-api-proxy.test.ts`; `npm.cmd run build` | PASS: application `291.47 kB`, React `181.79 kB`, Query `24.09 kB`, icons `16.09 kB`; no Vite oversized-chunk advisory |
| Initial AI focus | Composer receives focus even if an animation frame never runs | `collaboration-workbench.test.tsx` deterministic regression | PASS: old deferred-focus implementation failed; layout-phase focus passes |
| Focus stability | Existing workbench interaction coverage repeatedly executes after the fix | focused workbench test run five times | PASS: each run `20` passed, `2` historical skips |
| Local desktop UI | Local Vite page renders a meaningful error-recovery state, has one enabled retry action, and produces no relevant console errors/warnings | in-app browser at `http://127.0.0.1:4173/` | PASS: actual click reattempts loading and safely returns to the unavailable-API state |
| Local Telegram-width UI | `390 × 844` error-recovery state remains within the viewport and preserves the same retry action | in-app browser DOM and screenshot | PASS: message `350px`, `scrollWidth=390`, `clientWidth=390`, no relevant console errors/warnings |
| Public HTTP reachability | Root and health endpoints remain reachable without a browser identity | `curl.exe` read-only probes | PASS: `/` `200` in `0.84s`; `/health` `200` in `1.31s` |
| Public visual browser check | In-app browser navigation to the public domain | two fresh read-only browser attempts | BLOCKED: browser navigation timed out before a DOM/screenshot could be obtained; this is distinct from the successful HTTP probes |

## Final Regression Rerun — 2026-07-27

The following commands were rerun against the current dirty worktree after the static-artifact and Stage08 evaluator compatibility changes. They are current local evidence, not a deployment claim.

| Command | Result | Boundary |
| --- | --- | --- |
| `npm.cmd run test:run` in `mini-app/` | PASS: `77` files, `402` passed, `2` historical skips, `230.41s` | Serial Mini App regression; no backend or Telegram identity required. |
| `python -m pytest tests/unit` in `backend/` | PASS: `1370` passed, `1` skipped, `122.91s` | The sole skip is the existing POSIX-only server-shell verification; this is not the PostgreSQL integration suite. |
| `npm.cmd run build` in `mini-app/` | PASS | Explicit Rolldown vendor partitioning removes the prior oversized-chunk advisory. |
| `deploy/stage09-native/scripts/test-release-assets.sh` | PASS | Includes native service, rendered Nginx SSE transport and public-ingress static checks; local `nginx -t` remains explicitly skipped because Nginx is not installed on this Windows host. |
| `deploy/stage09-native/scripts/test-static-artifact-parity.sh` | PASS | Exercises valid and invalid fixed-path source/venv/static artifact fixtures. |
| `deploy/stage09-native/scripts/verify-release-assets.sh` | PASS | Read-only sealed-release asset/validator wiring check. |
| `git diff --check b57b152` | PASS | Only repository CRLF conversion advisories were printed; no whitespace error was reported. |

### Active Browser Recheck

The in-app browser opened the local Vite preview at `127.0.0.1:4173` with no backend service behind it. The safe negative path is now re-proven by live DOM inspection:

1. the page exposes exactly one `main` region named `网络错误`, one explanatory paragraph and one enabled `重新加载工作区` button;
2. the desktop DOM reports a `360px` recovery-message width, a `224px` paragraph width and a `111px` button width, matching the CSS contract rather than a collapsed narrow layout;
3. clicking the sole button re-initiates the load and safely returns to the same network-error state while the local API remains unavailable; no browser-console error was captured.

The browser screenshot service again produced an invalid image where the Chinese content was scaled to roughly one third of its inspected DOM position while the canvas remained full size. The saved desktop screenshot is therefore rejected as visual evidence, not used to claim a visual pass. At `390 × 844`, the browser could re-identify the same semantic error page after reload, but repeated layout reads timed out; the temporary viewport override was reset before closing the browser session. This preserves the earlier conclusion: responsive populated-workspace acceptance is still pending a stable, authorized browser surface.

## Browser Evidence Boundaries

The local browser used `STAGE07_LOCAL_ACCEPTANCE_USER_ID=stage09-ui-recovery-owner` only for client launch testing. There was no local FastAPI/PostgreSQL service available behind the Vite proxy, so the real click could prove request initiation and failure recovery but could not prove successful Home rendering against a live backend.

The existing Chrome profile was checked read-only. It contained only terminal/new-tab pages, no Telegram or workbench-authenticated tab. A direct online workbench tab was opened, but browser-side page inspection timed out twice after the lightweight Chrome connection succeeded. No credentials, cookies, raw Telegram `initData`, identity fallback, remote config change, test-user bootstrap, spreadsheet upload or business write was attempted. The current machine also has no reusable SSH host alias or project-local SSH key/configuration from which a native-host read-only probe can be safely targeted. These facts are not counted as a passing online UI or server test.

An authorized acceptance still needs a real Telegram Mini App/browser handoff session and a deliberately approved non-sensitive acceptance spreadsheet. The exact next matrix is:

1. verified Telegram launch → bootstrap → Home;
2. Home → Base → Grid; verify navigation/back/focus and error recovery;
3. template/import → file preview → mapping → confirmation; this creates an acceptance Base and must retain its opaque identifiers and audit receipt;
4. open the new Base, verify the inferred `status` / selection fields and responsive table state;
5. record only redacted screenshots, timestamps and opaque receipts; do not retain launch credentials or spreadsheet contents outside the approved fixture.

## Release And Artifact Finding

The active native source/venv release is `stage09-p1-20260726-r56-authoritative-answer`. It is a backend-only release under the existing split delivery model. The public static pointer deliberately remains on `stage09-p1-20260725-r39`; r56 contains the required `browser-handoff.html` source marker, not a new complete static UI candidate.

Therefore the locally tested Mini App source is **not** represented as public UI yet. Before any release of this change, build the exact worktree, create the complete external `mini-app/dist` static artifact, record hashes/manifest, and run `deploy/stage09-native/scripts/verify-static-artifact-parity.sh <artifact-id>` before switching pointers. The verifier is fixture-tested and is required by the sealed release layout/asset validators; it checks exact source/venv/static candidate paths, static ID marker, complete relative-file hash manifest and local Vite asset references. A source-only activation is disallowed when `mini-app/**` changed.

## Remaining Risks

- The public host answers HTTP requests, but the available in-app browser timed out before it could read a public DOM or screenshot. An authenticated Telegram/browser UI acceptance remains outstanding; HTTP `200` is transport evidence only.
- The test suite has `2` pre-existing skipped cases. They are not reclassified as passing evidence.
- The complete backend suite could not be accepted locally: its disposable-schema fixture reruns Alembic from zero, and migration `20260720_0032_stage08_knowledge_indexing.py` executes `CREATE EXTENSION IF NOT EXISTS vector`. The configured local PostgreSQL role returned `InsufficientPrivilege` (only a superuser can create the extension) before any Stage06/07/08/09 test body ran. The broad run was stopped after the identical fixture error propagated through PostgreSQL modules; the focused `-x` run produced the recorded root cause. A database administrator must preinstall `pgvector` in the dedicated disposable test database, or provide a dedicated test role permitted to create that extension. Do not weaken the migration or switch the production contract to a non-vector fallback merely to make local tests green.
- No valid authorized browser session was available, so the result is not a whole-product click acceptance and must not be promoted to production acceptance.

## Cleanup

- The local Vite server remains running with its browser tab retained as an in-app handoff at `http://127.0.0.1:4173/`; it serves only the local source and has no backend behind it. It must be stopped before final cleanup or deployment.
- The corresponding local-only logs and rejected screenshots remain under `%LOCALAPPDATA%\\Temp\\stage09-ui-recovery-audit` because the execution environment rejected the requested recursive cleanup. They contain no credentials, API payloads or production records and are not part of the repository or release artifact.
- No production/static/server pointer, database, Telegram state, LLM/provider state, import, record, draft, or workspace was changed.
