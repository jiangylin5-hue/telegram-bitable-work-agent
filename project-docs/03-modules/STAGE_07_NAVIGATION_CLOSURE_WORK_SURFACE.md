# Stage07 Existing-Contract Navigation Closure Work Surface

## Status

- Status: approved implementation work surface.
- Scope: Home/Bases route closure using existing safe Base summaries only.

## Runtime Surface

| Surface | Existing owner | Change in this package | Boundary |
| --- | --- | --- | --- |
| Desktop primary navigation | `mini-app/src/app/AppShell.tsx` | Home/Bases become callbacks with active state | no URL router or fetch |
| Mobile navigation | `mini-app/src/app/AppShell.tsx` | same Home/Bases callbacks | no hidden desktop-only path |
| Base directory | new `mini-app/src/app/BaseDirectory.tsx` | safe list, loading, empty, retryable state | no API client/cache/resource inference |
| Route orchestration | `mini-app/src/app/App.tsx` | memory route, protected request and `openBase` handoff | no backend modification |
| Query key | `mini-app/src/app/protectedQuery.ts` | stable `navigation/bases` key helper | no persistence |
| Styling | `mini-app/src/styles.css` | directory density/breakpoint rules | no visual-system redesign |

## Read Contract Inventory

| Request | Existing API method | Safe response used | Not consumed |
| --- | --- | --- | --- |
| Base directory | `api.workspaceBases(workspaceId, { signal })` | `BaseSummary[]` | Base settings, tables, views, fields, records, policies |
| Base opening | existing `openBase(base)` | later existing Canvas reads | directory-owned default table/view selection |
| Home | existing `api.workspaceHome` | existing Home model | synthetic assigned/mention/notification rows |

## Event Inventory

| User action | App handler | Success result | Failure result |
| --- | --- | --- | --- |
| select Home | `selectNavigation('home')` | Home renders | no request/fallback needed |
| select Bases | `selectNavigation('bases')` | safe directory renders | typed retry/denied/missing/session boundary |
| retry directory | `loadBaseDirectory()` | same exact protected key rereads | fixed retry state remains |
| select Base | existing `openBase(base)` | authorized Canvas | existing Canvas failure/denied handling |
| switch workspace | existing `selectWorkspace` | target scope route is current | old directory result discarded |

## Explicit Non-Surfaces

- No Bot, personal assistant, memory or knowledge UI.
- No queue aggregation or generic search.
- No new management screen, API route, permission editor or role/capability.
- No route URL, browser storage, telemetry or analytics.
