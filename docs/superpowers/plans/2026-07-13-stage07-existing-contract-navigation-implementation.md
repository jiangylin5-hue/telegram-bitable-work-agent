# Stage07 Existing-Contract Navigation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Home/Bases shell controls into an authorized, memory-only Base-directory route that hands selections to the existing Canvas flow.

**Architecture:** Reuse `api.workspaceBases`, the existing protected QueryClient and `openBase`. `App.tsx` owns route state and failure mapping; a new presentational Base directory owns only safe rendering. The plan changes no server code, data contract, schema, permission rule, dependency, URL router or browser persistence.

**Tech Stack:** Existing React, TypeScript, TanStack Query, Vite, Testing Library, Vitest and CSS.

## Execution Record

- Status: implemented-local on 2026-07-13. The original task checkboxes below retain the approved TDD execution order; the evidence record supersedes their pre-execution wording.
- Actual test surfaces: `base-directory.test.tsx`, `app-shell-navigation.test.tsx`, `workspace-navigation.test.tsx` and `protected-query-state.test.ts`.
- Final local evidence: focused `4` files / `18` tests, full Mini App `49` files / `199` tests, and `npm.cmd run build` passed.
- Actual scoped query key: `navigationKeys.bases(scope)` returns `['stage07', userId, workspaceId, 'navigation', 'bases']`.
- No browser control, backend/API/schema/permission/dependency/URL/storage/Bot/queue change, external provider call, Telegram operation or deployment occurred.

## Global Constraints

- Route state is exactly `'home' | 'bases'` in React memory.
- Directory response is only existing `BaseSummary[]` from `api.workspaceBases`.
- Protected directory key is `['stage07', userId, workspaceId, 'navigation', 'bases']`.
- Reuse `openBase`, `clearProtectedWorkspace`, `denyInvalidSession` and `denyWorkspace`; do not duplicate authorization.
- No schema, API, permission, role, dependency, URL/storage, queue, Bot, personal-assistant, memory or knowledge change.
- Do not control the user's browser. Manual UI observation remains a separate user-controlled acceptance step.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `mini-app/src/app/BaseDirectory.tsx` | pure safe directory state/rendering only |
| `mini-app/src/app/AppShell.tsx` | desktop/mobile Home/Bases callback controls and active state |
| `mini-app/src/app/protectedQuery.ts` | reusable navigation directory key helper |
| `mini-app/src/app/App.tsx` | scoped route lifecycle, fetch/error mapping and `openBase` handoff |
| `mini-app/src/styles.css` | directory desktop/mobile layout in existing visual system |
| `mini-app/src/test/base-directory.test.tsx` | pure presentational/accessibility states |
| `mini-app/src/test/navigation-closure-app-flow.test.tsx` | request order, exact cleanup and stale-scope regression |
| Stage07 navigation BDD/SDD/module/index/trace docs | evidence reconciliation only after implementation |

### Task 1: Add a pure safe Base directory component

**Files:**
- Create: `mini-app/src/app/BaseDirectory.tsx`
- Create: `mini-app/src/test/base-directory.test.tsx`

**Interfaces:**
- Consumes: `BaseSummary` from `./api`.
- Produces: `BaseDirectory` with `state`, `bases`, `onOpenBase`, `onHome` and `onRetry` props.

- [ ] **Step 1: Write the failing component tests**

```tsx
render(<BaseDirectory state="ready" bases={[{ id: 'base-1', name: 'CRM', source_type: 'blank' }]} onOpenBase={onOpenBase} onHome={onHome} onRetry={onRetry} />)
fireEvent.click(screen.getByRole('button', { name: '打开 CRM' }))
expect(onOpenBase).toHaveBeenCalledWith({ id: 'base-1', name: 'CRM', source_type: 'blank' })
expect(screen.queryByText('base-1')).not.toBeInTheDocument()
```

Add separate assertions for `loading` (`aria-busy`), `empty` (Home button and no create action), and `retryable` (fixed retry button and no raw error prop).

- [ ] **Step 2: Run the component test before implementation**

Run: `npm.cmd test -- --run src/test/base-directory.test.tsx`

Expected: FAIL because `../app/BaseDirectory` does not exist.

- [ ] **Step 3: Implement the closed component**

```tsx
export type BaseDirectoryState = 'loading' | 'ready' | 'empty' | 'retryable'
type Props = {
  state: BaseDirectoryState
  bases: BaseSummary[]
  onOpenBase: (base: BaseSummary) => void
  onHome: () => void
  onRetry: () => void
}

export function BaseDirectory({ state, bases, onOpenBase, onHome, onRetry }: Props) {
  if (state === 'loading') return <main aria-label="Bases" aria-busy="true">正在加载 Bases…</main>
  if (state === 'empty') return <main aria-label="Bases"><h1>Bases</h1><p>当前工作区没有可访问的 Base。</p><button type="button" onClick={onHome}>返回首页</button></main>
  if (state === 'retryable') return <main aria-label="Bases"><h1>Bases</h1><p>暂时无法加载 Bases，请稍后重试。</p><button type="button" onClick={onRetry}>重试</button><button type="button" onClick={onHome}>返回首页</button></main>
  return <main aria-label="Bases"><h1>Bases</h1><div aria-label="Base 列表">{bases.map((base) => <button type="button" key={base.id} aria-label={`打开 ${base.name}`} onClick={() => onOpenBase(base)}><strong>{base.name}</strong><span>{base.source_type}</span></button>)}</div></main>
}
```

Do not render an ID, status, table/view/record detail, Base create action or arbitrary error text.

- [ ] **Step 4: Run the component test after implementation**

Run: `npm.cmd test -- --run src/test/base-directory.test.tsx`

Expected: PASS with ready/loading/empty/retryable state assertions.

- [ ] **Step 5: Commit the isolated component**

```powershell
git add mini-app/src/app/BaseDirectory.tsx mini-app/src/test/base-directory.test.tsx
git commit -m "feat(stage07): add safe base directory surface"
```

### Task 2: Make AppShell navigation callbacks real on desktop and mobile

**Files:**
- Modify: `mini-app/src/app/AppShell.tsx`
- Modify: `mini-app/src/test/base-directory.test.tsx`

**Interfaces:**
- Add `activeRoute: 'home' | 'bases'` and `onNavigate: (route: 'home' | 'bases') => void` to `AppShellProps`.
- Both desktop and mobile Home/Bases controls call `onNavigate`.

- [ ] **Step 1: Extend the failing test for both navigation surfaces**

```tsx
render(<AppShell workspace={workspace} workspaces={[workspace]} activeRoute="bases" onNavigate={onNavigate} onWorkspaceChange={vi.fn()}>content</AppShell>)
expect(screen.getAllByRole('button', { name: 'Bases' })).toHaveLength(2)
fireEvent.click(screen.getAllByRole('button', { name: 'Home' })[0])
expect(onNavigate).toHaveBeenCalledWith('home')
expect(screen.getAllByRole('button', { name: 'Bases' })[0]).toHaveAttribute('aria-current', 'page')
```

- [ ] **Step 2: Run the focused test before changing AppShell**

Run: `npm.cmd test -- --run src/test/base-directory.test.tsx`

Expected: FAIL because `activeRoute` and `onNavigate` are not accepted props.

- [ ] **Step 3: Replace Home/Bases fragment anchors with buttons**

```tsx
<button className={activeRoute === 'home' ? 'nav-item active' : 'nav-item'} type="button" aria-current={activeRoute === 'home' ? 'page' : undefined} onClick={() => onNavigate('home')}><Home aria-hidden="true" size={18} /><span>工作区</span></button>
<button className={activeRoute === 'bases' ? 'nav-item active' : 'nav-item'} type="button" aria-current={activeRoute === 'bases' ? 'page' : undefined} onClick={() => onNavigate('bases')}><Table2 aria-hidden="true" size={18} /><span>Bases</span></button>
```

Apply the same callback and active state to the mobile Home/Bases controls. Leave Bots and unavailable More as non-selected presentation items; do not add a new handler.

- [ ] **Step 4: Run focused tests after the AppShell change**

Run: `npm.cmd test -- --run src/test/base-directory.test.tsx`

Expected: PASS; both surfaces use the same callback and active route semantics.

- [ ] **Step 5: Commit the navigation control change**

```powershell
git add mini-app/src/app/AppShell.tsx mini-app/src/test/base-directory.test.tsx
git commit -m "feat(stage07): wire home and bases navigation controls"
```

### Task 3: Add scoped directory lifecycle and Base handoff in App

**Files:**
- Modify: `mini-app/src/app/protectedQuery.ts`
- Modify: `mini-app/src/app/App.tsx`
- Create: `mini-app/src/test/navigation-closure-app-flow.test.tsx`

**Interfaces:**
- Add `navigationKeys.bases(scope)` returning `protectedQueryKey(scope, 'navigation', 'bases')`.
- `App.tsx` owns `navigationRoute`, `baseDirectoryState`, `baseDirectoryRequestVersion` and `selectNavigation`.
- `selectNavigation('bases')` uses `queryClient.fetchQuery({ queryKey: navigationKeys.bases(scope), queryFn: ({ signal }) => api.workspaceBases(workspaceId, { signal }) })`.

- [ ] **Step 1: Write failing App-flow tests**

```tsx
fireEvent.click(await screen.findByRole('button', { name: 'Bases' }))
expect(await screen.findByRole('button', { name: '打开 项目中心' })).toBeInTheDocument()
expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/bases', expect.any(Object))
fireEvent.click(screen.getByRole('button', { name: '打开 项目中心' }))
expect(fetchMock).toHaveBeenCalledWith('/bases/base-2/tables', expect.any(Object))
```

Add delayed Workspace A directory promise plus Workspace B switch assertion: resolve the old promise after the switch and assert its Base name is absent. Add `401`, `403`, `404`, empty and `503` tests that assert fixed state copy and absence of raw `detail`.

- [ ] **Step 2: Run the App-flow test before implementation**

Run: `npm.cmd test -- --run src/test/navigation-closure-app-flow.test.tsx`

Expected: FAIL because Bases is a fragment anchor and no directory request occurs.

- [ ] **Step 3: Add the key and route state**

```ts
export const navigationKeys = {
  bases: (scope: ProtectedScope): QueryKey => protectedQueryKey(scope, 'navigation', 'bases'),
}
```

```ts
type NavigationRoute = 'home' | 'bases'
const [navigationRoute, setNavigationRoute] = useState<NavigationRoute>('home')
const [baseDirectoryState, setBaseDirectoryState] = useState<BaseDirectoryState>('loading')
const [baseDirectoryBases, setBaseDirectoryBases] = useState<BaseSummary[]>([])
const baseDirectoryRequestVersion = useRef(0)
```

On workspace selection, increment `baseDirectoryRequestVersion`, set the route to `home`, and rely on existing `clearProtectedWorkspace` to cancel/remove all old protected keys.

- [ ] **Step 4: Implement exact directory loading and failure mapping**

```ts
async function loadBaseDirectory() {
  const scope = { userId: readyState.bootstrap.identity.user_id, workspaceId: activeWorkspace.id }
  const requestVersion = ++baseDirectoryRequestVersion.current
  setNavigationRoute('bases')
  setBaseDirectoryBases([])
  setBaseDirectoryState('loading')
  try {
    const { bases } = await queryClient.fetchQuery({ queryKey: navigationKeys.bases(scope), queryFn: ({ signal }) => api.workspaceBases(scope.workspaceId, { signal }) })
    if (requestVersion !== baseDirectoryRequestVersion.current || sessionInvalidated.current || activeWorkspaceId.current !== scope.workspaceId) return
    setBaseDirectoryBases(bases)
    setBaseDirectoryState(bases.length ? 'ready' : 'empty')
  } catch (error) {
    if (requestVersion !== baseDirectoryRequestVersion.current || isAbortError(error)) return
    if (error instanceof ApiError && error.status === 401) return void denyInvalidSession()
    if (error instanceof ApiError && error.status === 403) return void denyWorkspace(scope)
    if (error instanceof ApiError && error.status === 404) {
      queryClient.removeQueries({ queryKey: navigationKeys.bases(scope) })
      setBaseDirectoryBases([])
      setNavigationRoute('home')
      return
    }
    setBaseDirectoryState('retryable')
  }
}
```

Use an internal `BaseDirectoryState` shape matching Task 1 rather than passing an error object. Render `BaseDirectory` only when no Canvas/modal state is active and `navigationRoute === 'bases'`. Row selection calls `void openBase(base)`; Home selection increments the directory generation, clears only the directory component state, and returns to the existing Home content.

- [ ] **Step 5: Run the App-flow test after implementation**

Run: `npm.cmd test -- --run src/test/navigation-closure-app-flow.test.tsx`

Expected: PASS for safe directory request, exact Base handoff, empty/retryable fixed copy, 401/403/404 cleanup and delayed workspace replacement discard.

- [ ] **Step 6: Commit lifecycle behavior**

```powershell
git add mini-app/src/app/protectedQuery.ts mini-app/src/app/App.tsx mini-app/src/test/navigation-closure-app-flow.test.tsx
git commit -m "feat(stage07): add protected base directory navigation"
```

### Task 4: Integrate existing visual system and run affected regression

**Files:**
- Modify: `mini-app/src/styles.css`
- Modify: `mini-app/src/test/navigation-closure-app-flow.test.tsx`

**Interfaces:**
- `.base-directory`, `.base-directory-list`, `.base-directory-row` and state classes use existing color, spacing and mobile breakpoint tokens.

- [ ] **Step 1: Add a failing class/semantic assertion**

```tsx
expect(screen.getByRole('main', { name: 'Bases' })).toHaveClass('base-directory')
expect(screen.getByRole('button', { name: '打开 项目中心' })).toHaveClass('base-directory-row')
```

- [ ] **Step 2: Run the assertion before style/component class implementation**

Run: `npm.cmd test -- --run src/test/navigation-closure-app-flow.test.tsx`

Expected: FAIL because the component lacks the documented classes.

- [ ] **Step 3: Add scoped CSS only**

```css
.base-directory { max-width: 1180px; margin: 0 auto; padding: 28px; }
.base-directory-list { display: grid; gap: 8px; }
.base-directory-row { display: grid; grid-template-columns: 1fr auto; text-align: left; }
@media (max-width: 680px) { .base-directory { padding: 16px 16px 88px; } .base-directory-row { min-height: 48px; } }
```

Use existing CSS variables/classes for colors, type, border and focus outlines. Do not introduce a design-system dependency, gradient, card wall or separate mobile component.

- [ ] **Step 4: Run affected client regressions and build**

Run: `npm.cmd test -- --run src/test/base-directory.test.tsx src/test/navigation-closure-app-flow.test.tsx src/test/app-shell.test.tsx src/test/table-switch.test.tsx`

Expected: PASS with no failures.

Run: `npm.cmd run build`

Expected: `✓ built` and a production Vite bundle.

- [ ] **Step 5: Commit visual integration**

```powershell
git add mini-app/src/styles.css mini-app/src/test/navigation-closure-app-flow.test.tsx
git commit -m "feat(stage07): style responsive base directory navigation"
```

### Task 5: Reconcile Stage07 evidence without overclaiming UI inspection

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_NAVIGATION_CLOSURE_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_07_NAVIGATION_CLOSURE_SDD.md`
- Modify: `project-docs/03-modules/STAGE_07_NAVIGATION_CLOSURE_WORK_SURFACE.md`
- Modify: `project-docs/08-implementation/STAGE_07_NAVIGATION_CLOSURE_COMPLEX_FEATURE_INDEX.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`

**Interfaces:**
- Consumes exact Task 4 test/build output and no browser automation observation.
- Produces `implemented-local` only for NC-A01 through NC-A07 when the stated evidence exists.

- [ ] **Step 1: Mark only evidenced local rows**

Record exact focused test file/count, build result, changed files and cleanup. Keep user-controlled manual visual QA, real provider/Telegram and whole-stage acceptance explicitly pending.

- [ ] **Step 2: Run documentation integrity checks**

Run: `git diff --check`

Expected: exit `0`.

Run: `rg -n "TODO|TBD|placeholder" project-docs/08-implementation/STAGE_07_NAVIGATION_CLOSURE_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_07_NAVIGATION_CLOSURE_SDD.md project-docs/03-modules/STAGE_07_NAVIGATION_CLOSURE_WORK_SURFACE.md project-docs/08-implementation/STAGE_07_NAVIGATION_CLOSURE_COMPLEX_FEATURE_INDEX.md`

Expected: no output.

- [ ] **Step 3: Commit evidence reconciliation**

```powershell
git add project-docs/08-implementation project-docs/03-modules docs/superpowers/plans/2026-07-13-stage07-existing-contract-navigation-implementation.md
git commit -m "docs(stage07): reconcile navigation closure evidence"
```

## Plan Self-Review

- NC-01 through NC-07 map to Tasks 1 through 5.
- Every new runtime surface has a typed boundary and one corresponding test target.
- The plan never adds an endpoint, schema, permission, route URL, persistent cache, queue, Bot or Package 4 model.
- Browser-control automation is excluded; manual UI review remains a separate pending acceptance item.
