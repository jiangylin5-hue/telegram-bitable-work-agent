# Stage09 UI 可恢复错误与静态工件一致性实施计划

## Status

- Status: approved implementation scope under Stage09 Interaction and Import Closure I3.
- Scope: Mini App 对非鉴权网络/服务失败的可恢复入口，以及含 Mini App 变更的 source/venv/static 发布一致性门禁。
- Non-goals: 改变 Telegram verified identity、权限模型、API contract、导入写入语义、LLM/Provider 配置或线上业务数据。
- Current Progress: 2026-07-27 root-cause audit and local implementation completed. The current global `error` state previously replaced an already ready workspace after several non-401/403 failures, leaving only text and no recovery action. Red tests, focused recovery tests, the serial Mini App suite (77 files / 402 passed / 2 historical skips), the backend unit suite (1370 passed / 1 POSIX-only skip) and `npm.cmd run build` now pass. Build output is partitioned into cacheable React/Query/icon chunks with no oversized-chunk advisory. Browser verification confirms one recovery button and a real click initiates a retry on both desktop and 390px width; the local API is intentionally unavailable, and public in-app-browser navigation times out even though read-only public HTTP probes return 200, so a populated authorized browser flow is still not accepted. The source/venv/static parity policy is now enforced by `verify-static-artifact-parity.sh`, its fixture test and sealed-release validator wiring; their static test commands pass. A PostgreSQL integration-suite attempt is environment-blocked before test bodies because the configured local PostgreSQL role may not create the required `vector` extension; details are recorded in the linked audit evidence. Source/static releases are intentionally separate artifacts; r56 source-only deployment is not itself a packaging defect, but the current uncommitted UI work must be deployed as a new static artifact with its matching candidate. A user-supplied public screenshot and a read-only SSH probe now reject the live visual acceptance: `/var/www/stage09-p1/current` resolves to `stage09-p1-20260725-r39`, whose static bundle still opens the legacy three-column `AssistantContextWorkbench` for the `AI 对话` route. This is a deployment-artifact drift, not a supported target state; the current source maps every visible `AI 对话` entry to `CollaborationWorkbench`, while the legacy panel remains limited to `智能汇总` and business-context inspection.

## Problem And Root Cause

`App.tsx` currently has two failure families:

1. `bootstrapQuery.isError`: startup request fails before a workspace is loaded. The page says “请稍后重试” but exposes no control that invokes `bootstrapQuery.refetch()`.
2. `state.status === 'error'`: a later Home/Base/View/Record/Builder operation catches a non-auth error and calls `setState({ status: 'error' })`. This discards the current `ready` payload, hides all navigation and supplies no way to reload the last authorized workspace.

401/403 are intentionally different: they are handled by existing fail-closed identity/permission paths and must never gain a retry that could bypass verified Telegram/browser identity.

## Live AI Conversation Visual-Rejection Gate — 2026-07-27

### Evidence and scope

The user opened the public workbench at `https://stage07.jiangtest1.online` and selected its visible `AI 对话` action. The supplied screenshot shows the old modal headed `AUTHORIZED AI COLLABORATION`, with three fixed columns for employee selection, form-style question parameters and blank safe history. It has no persistent turn timeline, no bottom composer, no server-returned skill strip and no current-record safety rail.

A read-only SSH probe, using the existing project key and without reading runtime values or changing server state, resolved the public static `current` link to `stage09-p1-20260725-r39`. The public root currently references `index-ClvZQGCh.js` and `index-CBGJFEX0.css`, consistent with that older static release.

### Required release invariant

The public UI is acceptable only when all of the following are true:

1. Every label exposed as `AI 对话` in the sidebar, Home toolbar, ready state, assistant dock, Base canvas and record detail invokes `openCollaboration` and renders `CollaborationWorkbench`.
2. `AssistantContextWorkbench` remains reachable only through explicitly named `智能汇总` and authorized business-context inspection actions. It must not be used as an alias, fallback, or mobile variation of `AI 对话`.
3. The deployed static directory contains the same candidate identifier as the sealed source and venv, passes `verify-static-artifact-parity.sh`, and is switched together with both `current` links.
4. After activation, an authorized human browser screenshot must visibly show the Ledgerline workbench: context header, chronological answer area, safety scope rail, skill controls and fixed bottom composer. A status-code-only probe cannot satisfy this criterion.

### Release order

1. Run the targeted entry-flow tests, full Mini App regression and production build from the exact candidate.
2. Package `mini-app/dist` as the candidate static directory with an exact-id marker and hash manifest; do not copy it over the existing `r39` directory.
3. Upload and validate source, venv and static candidates under one new artifact identifier; run release validators and the static-parity gate before any pointer changes.
4. Atomically switch the three `current` links, run bounded health and static probes, then have the authorized browser repeat the `AI 对话` click and retain the resulting screenshot as acceptance evidence.
5. If any validation or visual check fails, restore all three links to their previous matching identifiers. Do not leave a newer source or venv paired with stale static files.

## Target Interaction Contract

```text
non-auth bootstrap failure
-> safe network error page
-> "重新加载工作区"
-> bootstrap refetch
-> existing verified bootstrap + Home load path

non-auth failure after a workspace was selected
-> safe network error page
-> "重新加载工作区"
-> use already verified bootstrap payload and last selected workspace id
-> existing Home endpoint reload
-> ready workspace Home

401 / 403
-> existing denied state only
-> no retry control and no development identity fallback
```

The recovery action always restarts at the authorized Home boundary. It does not replay a write, record mutation, import commit, draft confirmation or provider invocation; this prevents accidental duplicate side effects and keeps error handling independent of individual panel state.

The recovery surface follows the existing quiet workspace visual language: a compact centered message stack with a clearly visible primary control, a hover/focus state and an explicit disabled loading state. It is deliberately not a full-screen illustration or a generic AI-style empty state; the error is operational, not a new product destination.

## Implementation Steps

### Step 1: Red tests

Files:

- Modify: `mini-app/src/test/browser-session-recovery.test.tsx`

Add two failing tests with the real `App` and controlled fetch sequence:

1. Initial bootstrap network failure renders exactly one enabled `重新加载工作区` control; clicking it issues a second bootstrap request and reaches the safe workspace Home after a valid response.
2. A non-auth Home reload failure after valid bootstrap renders the same control; clicking it retries Home for the same workspace and reaches Home.

The existing 401 test must assert that this control is absent. Tests may mock transport because the behavior under test is React recovery state, while production identity and API behavior already have backend coverage.

### Step 2: Minimal App recovery implementation

Files:

- Modify: `mini-app/src/app/App.tsx`

Add a local recovery callback before terminal renders. It chooses exactly one of two existing operations:

- no usable bootstrap payload: `bootstrapQuery.refetch()`;
- usable bootstrap payload: `loadWorkspaceHome()` for the current safe workspace id, falling back only to the first bootstrap membership.

The callback puts the recovery control into its disabled loading state while the existing request is in flight, never exposes API error detail, and does not run when the session was invalidated. The terminal denied branches remain unchanged.

### Step 2a: Recovery control affordance

Files:

- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css`

Give the recovery message and its button explicit semantic classes. Style the action as the same restrained blue primary control used for other low-risk actions: readable contrast, a keyboard-visible focus ring, hover feedback and an unavailable/loading cursor. The error surface must remain responsive on narrow screens and must not add decoration that hides the cause or competes with the normal workspace UI.

### Step 3: Focused and full verification

Run, in order:

```text
npm.cmd test -- --run src/test/browser-session-recovery.test.tsx --maxWorkers=1
npm.cmd run test:run
npm.cmd run build
```

Capture the initial unavailable-API screen and the same screen after the new recovery control appears. A successful button click against a live authorized fixture remains separate browser acceptance evidence; no fake browser success claim is allowed.

## Static Artifact Parity Gate

The release verifier intentionally requires only `browser-handoff.html` inside the sealed source release. Full UI assets are separately deployed under `/var/www/stage09-p1/<artifact-id>`.

For every candidate that changes `mini-app/**`:

1. Run `npm.cmd run build` from the exact candidate worktree.
2. Create a complete external static artifact from that build, containing `index.html`, the referenced JS/CSS assets and `browser-handoff.html`.
3. Record a static manifest with release candidate id and file hashes.
4. Before activation, verify source, venv and static candidates exist and have the same candidate id.
5. Atomically switch all three current links, then probe `/`, `/index.html`, one referenced asset and `/health`.
6. If static artifact verification fails, leave all current links unchanged; source-only activation is permitted only when the candidate proves there was no `mini-app/**` change.

This preserves the existing split-artifact security model while preventing a future UI change from leaving the old public bundle active.

### Executable Parity Contract

The policy above is enforced by the sealed, read-only `deploy/stage09-native/scripts/verify-static-artifact-parity.sh` verifier rather than a deployment checklist alone. It takes one artifact id and derives only these fixed target paths:

```text
source  /opt/stage09-p1/releases/<artifact-id>
venv    /opt/stage09-p1/venv/<artifact-id>
static  /var/www/stage09-p1/<artifact-id>
```

It rejects links, mismatched paths, a missing source `mini-app/dist/browser-handoff.html`, a missing executable venv interpreter, absent static `index.html` / `browser-handoff.html`, a missing exact-id marker, an absent or malformed hash manifest, hash drift, and a Vite `index.html` reference to a missing local asset. The static manifest deliberately excludes itself and lists only relative regular files, so a manifest cannot escape the static candidate or validate an old sibling directory. Its output is generic and must never print release paths, file contents, credentials, or manifest values.

The verifier is read-only. It does not package files, change a `current` link, restart services or alter Nginx. Activation must call it after candidate upload and before pointer switching. Its shell fixture tests cover: valid same-id source/venv/static candidates; mismatched marker; missing static entry point; referenced asset deletion; hash mutation; source/static link rejection; and malformed manifest rejection.

## Build Output Cache Partition — 2026-07-27

### Trigger

The recovery build remains functionally correct, but Vite reports one `513.48 kB` minified application chunk. The warning is actionable because the workbench is a Telegram-first client: a browser that already cached React should not have to re-download it merely because application code changes.

### Architecture And Contract

The change is limited to the Vite production-output graph. It introduces deterministic vendor chunks for the three stable dependency families already present in the client:

```text
application chunk
  -> local Mini App screens, protected API adapter, state and styles
vendor-react
  -> react + react-dom
vendor-query
  -> @tanstack/react-query
vendor-icons
  -> lucide-react
```

This is not runtime feature loading and does not change React component ownership, API paths, Telegram launch identity, persisted state, request headers, service-worker policy, static artifact manifest contract, or browser routes. Vite continues to emit content-hashed filenames, so the existing external static manifest records every changed file and `verify-static-artifact-parity.sh` continues to protect activation. The purpose is cache isolation: dependency code changes infrequently, while application code changes per Stage09 task.

### Implementation Steps

1. Add a pure `createBuildOutputOptions()` factory in `mini-app/vite.config.ts`. It returns only the named dependency partitions above, so unit tests can assert the deployment-relevant chunk contract without starting Vite.
2. Wire that factory into Vite's production `rolldownOptions.output.manualChunks` configuration. Do not add a service worker, CDN rewrite, new dependency or runtime import boundary.
3. First add a focused failing config test for the exact three stable partitions; then implement the factory and config wiring.
4. Run the focused config test, the full serial Mini App suite and production build. The build must emit multiple content-hashed chunks and no individual chunk may trigger Vite's `500 kB` advisory.
5. Treat the emitted files as an ordinary future static candidate: do not deploy from the local `dist/`, and do not switch source/venv/static pointers in this task.

### Acceptance Criteria

- The named vendor partitions are explicit, deterministic and covered by a focused test.
- Production build succeeds without the previous oversized-chunk warning.
- Existing proxy contract and complete serial Mini App regression remain green.
- No external static artifact, server pointer, Telegram state or business data is modified.

## AI Workbench Initial Focus Stability — 2026-07-27

### Finding And Root Cause

During the serial Mini App regression, the AI workbench focus contract failed once: the portal content was present but the composer `textarea` still left `document.body` focused. The component appended its portal in a layout effect, then deferred composer focus to `requestAnimationFrame` in a normal effect. Rendering or test discovery can therefore observe the input before the future animation frame runs.

### Minimal Repair

The initial composer focus now runs in the immediately following `useLayoutEffect`. React executes layout effects in declaration order, so the portal node is already attached before the textarea is focused. The later skill-selection focus remains asynchronously scheduled because it intentionally follows a state update and is not part of the initial mount contract.

The regression test replaces `requestAnimationFrame` with a callback that never executes and asserts that initial focus still reaches the composer. It fails against the deferred implementation and passes only when mount focus is independent of an animation frame. This change does not alter dialog keyboard trapping, Escape behavior, scope/permission handling, provider invocation, or user data.

## Acceptance Criteria

- Network error pages have an actionable recovery control with no raw error disclosure.
- A successful retry returns to an authorized Home; it never repeats the failed write/panel action.
- 401/403 remain fail-closed and do not render the recovery control.
- Focused red/green regression, full serial Mini App regression and production build pass.
- A candidate with Mini App changes cannot be deployed without a verified matching static artifact.
- No production/Telegram/LLM/business-record write occurs during local implementation verification.
