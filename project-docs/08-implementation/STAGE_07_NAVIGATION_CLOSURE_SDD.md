# Stage07 Existing-Contract Navigation Closure SDD

## Status

- Status: approved design specification; implementation pending.
- Scope: use existing Base summaries to close the shell's Home/Bases navigation loop.

## Architecture

```text
AppShell Home/Bases action
-> App memory route state
-> navigationKeys.bases({ userId, workspaceId })
-> api.workspaceBases(workspaceId, { signal })
-> existing GET /workspaces/{workspace_id}/bases
-> safe BaseDirectory projection
-> existing openBase(base)
-> existing Canvas authorization chain
```

The new directory component is presentational. It accepts one typed `BaseSummary[]` collection and fixed UI state callbacks. It neither owns authorization nor requests generic data. `App.tsx` remains the only place that performs protected fetching, handles identity/session failure and invokes `openBase`.

## Module Boundaries

| Module | Owns | Receives | Prohibitions |
| --- | --- | --- | --- |
| `AppShell` | selected navigation affordance on desktop/mobile | active route and callbacks | no fetch, role inference or resource routing |
| `BaseDirectory` | safe list/empty/loading/retry presentation | typed Base summaries and callbacks | no fetch, cache, local filtering, persistence or guessed resource |
| `App.tsx` | route state, protected query, response/error mapping and Base handoff | verified bootstrap/workspace, API client | no new backend contract or Base-derived table/view selection |
| `protectedQuery.ts` | stable directory query key | verified user/workspace scope | no persistent cache or cross-workspace key |

## Data Contract

```ts
type NavigationRoute = 'home' | 'bases'
type BaseDirectoryState = 'idle' | 'loading' | 'ready' | 'empty' | 'retryable'
```

The only directory response is the existing `Promise<{ bases: BaseSummary[] }>` from `api.workspaceBases`. `BaseSummary` remains `{ id, name, source_type, status? }`. `App.tsx` keeps the current `BaseSummary[]` separate from the string state and clears it before a loading/retryable transition. A component must never receive a raw endpoint object, HTTP response, error body, table/view/record payload or policy.

## Protected Query and Lifetime Rules

1. The query key is `['stage07', userId, workspaceId, 'navigation', 'bases']`.
2. `openBases` captures a route request generation before starting the query.
3. A result may set route state only if its generation, active workspace and session latch are still current.
4. Workspace replacement increments the generation and existing `clearProtectedWorkspace` cancels/removes the old directory query with every other old-scope key.
5. `401` delegates to existing `denyInvalidSession`; `403` delegates to `denyWorkspace`; `404` removes the exact directory query and returns a fixed Home recovery; retryable failures retain no row data.
6. `openBase` increments its existing canvas generation and reuses existing table/view/schema/record reads. Directory code passes the exact safe `BaseSummary` unchanged.

## Rendering and Accessibility

- Home/Bases controls are `button` elements with `aria-current="page"` on the active route.
- The directory has a labelled `main`/heading, a labelled list, named Base-row buttons and a labelled Home return action for empty/retryable/missing states.
- Desktop and mobile use the same route state and labels; CSS changes only layout density.
- A loading state exposes `aria-busy`; retry uses a fixed labelled button; error detail is never rendered.

## Security Rules

- Server authorization is final; no Base entry is inferred from a Home cache or a browser identifier.
- The browser stores route state only in a component state variable and protected cache entries have `gcTime: 0`.
- Directory selection cannot expose a table/view/record until the existing server calls succeed.
- Bots/More remain outside this component's authority. Capability-gated Governance continues through the existing callback.

## Verification Scope

The package requires client tests and a production build. It does not require a backend change, database migration or external operation. Manual UI review remains pending under the user-directed no-browser-control boundary.
