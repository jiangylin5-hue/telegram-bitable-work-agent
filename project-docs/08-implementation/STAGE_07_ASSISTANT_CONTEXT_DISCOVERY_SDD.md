# Stage07 Personal Assistant Context Discovery SDD

## Status

- Status: approved boundary implemented locally on 2026-07-13; remaining revocation/database/browser acceptance is explicitly open.
- Scope: server-composed Home view discovery for one selected existing digital employee.

## Architecture

```text
WorkspaceHome assistant entry
-> AssistantContextWorkbench memory state
-> existing S5 safe contact page
-> selected employee id
-> protected assistant-context catalog read
-> employee/Base/view/caller intersection in backend service
-> safe view summary page
-> selected-view re-read
-> existing S5 `summarize` invocation
-> safe answer + opaque citations
```

The catalog is not a generic Bitable API facade. It is a narrow S5-adjacent read adapter. It owns no record data, no employee configuration and no authorization policy. `App.tsx` continues to own protected query lifetime/session failure; the backend is the only authority for every scope intersection.

## Proposed Safe Types

```ts
type AssistantContactContext = {
  employee: { id: string; name: string; description: string; baseId: string }
  views: Array<{ id: string; name: string; viewType: 'grid' | 'kanban' | 'calendar' | 'form' }>
  nextCursor: string | null
  hasMore: boolean
}

type AssistantSelectedView = {
  id: string
  name: string
  viewType: 'grid' | 'kanban' | 'calendar' | 'form'
  baseId: string
}
```

The parser rejects unknown `viewType`, missing/empty identifiers, extra response roots and any field outside the closed safe response. IDs are opaque transport values and are never rendered as user-facing labels.

## Endpoint Contract

| Endpoint | Input | Response | Forbidden payload |
| --- | --- | --- | --- |
| `GET /mini-app/digital-employees/{employee_id}/assistant-context?cursor=&limit=` | verified identity plus bounded cursor/limit | `AssistantContactContext` | table IDs, field IDs, record values, scope arrays, policies, configuration, provider/runtime/trace data |
| `GET /mini-app/digital-employees/{employee_id}/assistant-context/views/{view_id}` | verified identity | `AssistantSelectedView` | presentation/configuration, records, fields, permissions or raw errors |

The selected-view re-read runs immediately before existing S5 summary invocation. A client must not invoke using a catalog item that has not been re-read in the current generation.

## Implementation Correspondence

- `backend/app/api/routes/stage07_draft_employee_hub.py` exposes only the two specified read routes and uses the existing authorization/UoW/view-presentation services.
- `mini-app/src/app/api.ts` rejects unknown root keys and view types for both DTOs; `protectedQuery.ts` isolates and removes only the `assistant-context` subtree.
- `AssistantContextWorkbench.tsx` is a separate Home-only surface. `App.tsx` invalidates it on close/workspace replacement and removes the exact selected-view cache before a summary invocation.
- The workbench has no draft command, record picker, Base/view URL state, client persistence, runtime picker or raw-error rendering.

## Backend Resolution Algorithm

1. Resolve active request identity and current `DigitalEmployee`; inactive/missing employee is indistinguishable `404`.
2. Authorize the caller for existing `digital_employee.invoke` within the employee workspace.
3. Resolve employee Base and ensure the caller currently reads it through the same Base authorization path used by Canvas/S5 contacts.
4. Enumerate only saved views belonging to that Base.
5. Intersect those views with employee `accessible_views`; where the employee list is empty, use the existing employee scope semantics rather than an implicit browser default.
6. Intersect the result with the caller's current view/read authority and, for each view, its valid table relationship.
7. Sort by stable safe display name then opaque ID; apply existing cursor utility.
8. Map only the closed DTO. No generic view object crosses the adapter boundary.
9. For selected-view re-read, repeat steps 1–6 for the exact ID and return `404` for any missing/intersection failure.

The existing summary invocation repeats its own employee/Base/view/caller checks. The re-read prevents a stale selection from reaching it; it does not replace runtime authorization.

## Client State and Lifetime

All assistant keys must remain below TD001's verified scope:

```text
['stage07', userId, workspaceId, 'assistant-context', employeeId, cursor]
['stage07', userId, workspaceId, 'assistant-context', employeeId, 'view', viewId]
```

The workbench owns only `selectedEmployeeId`, `selectedViewId`, bounded instruction text, generation counters and safe answer state in memory. It clears selection, answer and pending state before a replacement contact/workspace/close transition. It does not use a URL, localStorage, sessionStorage, React Query persistence or a shared conversation store.

## UI Boundary

| Component | Responsibility | Must not do |
| --- | --- | --- |
| `WorkspaceHome` | opens assistant workbench | infer context or execute a request |
| `AssistantContextWorkbench` | contact/view selection, fixed summary action and safe answer display | fetch generic resources, create drafts or persist selection |
| `api.ts` | strict parsers and typed requests | expose generic backend view/employee fields |
| `protectedQuery.ts` | scoped assistant keys and exact cleanup helper | broaden cache lifetime or persistence |
| S5 invoke adapter | fixed summary command and final authorization | trust client catalog/selection |

## Explicit Security Properties

- The browser cannot name a Base; it receives one opaque Base ID only from the selected employee safe DTO and submits it solely to the existing invocation route.
- A contact with no permitted views is a valid empty result, not a reason to fall back to generic view listing.
- Citations remain the existing S5 opaque `{record_id}` values. The workbench neither dereferences them nor caches record content.
- `draft_update` is not rendered in Home. Opening a Base routes through existing `openBase`; only Canvas/Record Detail may supply TD006 context.
- No LangGraph checkpoint/store, dependency or migration is added. Durable memory and deletion semantics remain a later explicit decision.

## Verification Scope

Implementation requires red-first API/service/client tests, focused PostgreSQL intersection/revocation evidence, a production build and BDD reconciliation. Manual UI review remains user-controlled; no browser control is authorized by this specification.
