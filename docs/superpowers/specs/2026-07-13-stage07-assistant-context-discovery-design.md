# Stage07 Personal Assistant Context Discovery Design

## Status

- Status: TD009 Option B design approved on 2026-07-13; implementation plan review remains required before code.
- Recommended decision: TD009 Option B — server-composed contact-to-view catalog.
- Implementation precondition: explicit approval of the detailed implementation plan. No code, migration or endpoint exists because of this document.

## User Outcome

A workspace member can start from Home, choose a contact that is already safe for that workspace, choose one view the contact and caller may both use, request a bounded summary, and then open the same Base to continue normal table work. The assistant never pretends to know a record, workspace search result, team conversation, memory or knowledge source that was not server-authorized.

## Interaction States

| State | Visible content | Allowed action | Forbidden interpretation |
| --- | --- | --- | --- |
| `assistant-idle` | fixed explanation and safe contacts | select contact | no default employee or inferred context |
| `contacts-loading` | fixed loading copy | close/retry only | no cached old contacts |
| `contacts-empty` | fixed unavailable copy | close | no create/publish employee action |
| `contact-selected` | selected contact and loading view catalog | cancel/change contact | no view inferred from employee configuration in client |
| `views-ready` | safe view names/types only | select exact view | no table/field/record/policy content |
| `views-empty` | fixed no-available-view copy | select another contact/close | no generic view browse fallback |
| `view-selected` | visible selected context chip | summarize, clear selection, open Base | no Home draft creation |
| `summary-pending` | disabled duplicate action | wait/cancel close | no optimistic answer |
| `summary-ready` | safe answer and opaque citations | open Base/clear/retry a new summary | citations never expand into record values |
| `retryable` | fixed retry copy | retry exact current catalog/summary | raw HTTP/provider error absent |
| `denied`/`expired`/`missing` | existing generic boundaries or fixed reselection copy | re-enter/reselect | no previous contact/view remains interactive |

## Responsive Shape

Desktop uses the existing Home assistant dock as the entry point and opens a labelled workbench with a left contact list and right context/result column. Mobile uses the existing modal/sheet convention: contact list first, view list next, then the selected-context summary action. Both use the same memory route/state and the same server read models; mobile does not receive a reduced authorization rule.

No generated image, new icon system, gradient, dark dashboard, card wall or browser-specific route is needed. The existing `Work Queue Atlas` visual language and `DraftEmployeeHub` safe-dialog composition are reused.

## Security Design

1. The client stores only opaque employee/base/view IDs in component memory and TD001 user/workspace-scoped query data.
2. Contact selection never grants scope. Every catalog read and summary invocation recomputes employee, Base, view and caller intersections on the server.
3. The catalog is a safe projection, not a generic navigation proxy: it contains only contact/display view fields required by the picker.
4. A selected view is re-read by the server before summary. A late response from a prior workspace/contact/view cannot set state or invoke the runtime.
5. The client sends no action/runtime/provider configuration and no record value. It uses only the existing fixed `summarize` intent.
6. The Home surface deliberately cannot create a draft. It directs a user to the existing Base Canvas/Record flow, where TD006's current-record guard still applies.

## Acceptance Design

- A permitted contact can expose only its intersection of employee view scope and caller-readable views.
- A caller cannot use a contact/view from another workspace or inaccessible Base; response is closed to a generic boundary.
- Selecting one permitted view sends only the existing fixed `summarize` request and receives only safe answer/citation output.
- Empty, stale, malformed, `401`, `403`, `404`, `409`, `422`, `5xx`, retry and workspace replacement states never render raw server/provider data or a prior selection.
- The package has unit/API/client tests, a proportional local PostgreSQL authorization check, production build, document reconciliation and user-controlled visual review only if later requested.

## Out of Scope

TD009 Option B is not a partial implementation of the full Package4 lifecycle, memory or knowledge roadmap. Those remain separate decisions after the first Home assistant loop is accepted.
