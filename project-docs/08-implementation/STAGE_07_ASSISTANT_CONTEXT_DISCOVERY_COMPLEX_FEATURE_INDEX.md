# Stage07 Personal Assistant Context Discovery Complex Feature Index

## Status

- Status: implementation index reconciled for the bounded TD009 Option B local package on 2026-07-13.

| Feature | Complexity source | Required invariant | Evidence needed before local acceptance |
| --- | --- | --- | --- |
| employee-to-view intersection | employee Base/view scope and caller access can change independently | catalog rows exist only when employee, Base, view and caller intersections are all current | service/API matrix including cross-workspace, inactive employee, hidden view and post-grant/revoke cases |
| safe context DTO | generic view/employee objects carry forbidden configuration and policy data | adapter DTO contains only opaque IDs plus display name/type required for selection | schema/parser/response negative assertions |
| selected-view re-read | catalog content may become stale before a model invocation | summary may run only after exact selected-view revalidation in the current generation | delayed/revocation client and API tests |
| no Home draft creation | Home has no open current record to bind to the existing draft guard | Home renders no draft action, record picker or record label and sends no draft intent | client DOM/request inventory |
| protected cache replacement | contact/view/summary requests can outlive workspace or dialog state | old result cannot render, invoke or open a Base after contact/view/workspace/close replacement | deferred-promise application tests and query cleanup assertions |
| bounded instruction | free-form prompt can become an unbounded data channel | fixed maximum, no browser persistence and no raw server/provider errors | parser/request/DOM tests |
| future memory separation | LangGraph supports persistence but memory needs retention/clear/audit decisions | this package creates no checkpointer/store/assistant thread/memory namespace | dependency/migration/source inventory |

## Data and Index Decision

TD009 Option B adds no database table, index, migration or persistent client structure. It uses current `DigitalEmployee.base_id`, approved employee view scope and existing Base/view authorization. If a later decision adds a record picker, primary display-field rule, employee lifecycle or durable memory, it must supply its own schema/index/retention document rather than extending this package implicitly.

Verification confirms no TD009 migration or dependency was added. A local PostgreSQL intersection/revoke matrix is deliberately still absent, so no database performance or revocation claim is made.

## Failure Containment Rules

- Unknown IDs and inaccessible resources return fixed generic outcomes; a client must not distinguish existence from scope loss.
- A malformed/missing catalog field invalidates the complete page and leaves no previous view selectable.
- A late summary cannot restore answer/citations after a replacement generation.
- No safe DTO may be expanded with `config`, `permission_policy`, field metadata, record values, employee policy or runtime trace to simplify a later UI.

## Explicit Technology Reuse

- FastAPI dependency/authorization pattern and SQLAlchemy UoW remain the server boundary.
- Existing Stage06 view/employee services determine scope; no second permission engine is created.
- Existing S5 safe adapter and TD001 protected QueryClient are extended rather than reimplemented.
- LangGraph stays an internal runtime dependency; no new graph framework, memory SDK or persistent store is added in this decision.
