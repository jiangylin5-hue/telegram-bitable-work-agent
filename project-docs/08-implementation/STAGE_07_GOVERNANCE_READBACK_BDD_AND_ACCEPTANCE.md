# Stage07 Governance Readback BDD And Acceptance

## Status

- Status: proposed, awaiting Technical Decision 003 and user approval
- Scope: read-only member directory and Base audit timeline only

## BDD Scenarios

### GR-01 Capability hint is not authority

Given Bootstrap says `can_manage_workspace=false`
When the App Shell renders
Then the governance entry is absent.

Given a stale or manipulated client renders an entry
When its member or audit request reaches the backend
Then the backend independently requires `member.read` or `audit.read`; local visibility never grants access.

### GR-02 Members are closed, paged and workspace-scoped

Given an active caller with `member.read`
When they open Governance for Workspace A
Then the first member page contains only `{id,user_id,role,status}`, `workspace_id`, opaque cursor metadata and no profile/invitation/policy/action data.

When they request the next page
Then the cursor is sent unchanged and rows append only after the response validates the same Workspace A.

When the caller changes Workspace before that page resolves
Then the old request is cancelled or discarded and no old member row renders in Workspace B.

### GR-03 Member empty and failure states do not invent a management action

Given a permitted empty member page
Then the UI explains that no active membership is available and shows no invite/create action.

Given malformed data, network failure or server `5xx`
Then the UI shows fixed retry copy and does not display raw body, cached role map or guessed rows.

### GR-04 Audit requires a safe Base selection

Given the operator is in Governance
When no Base is selected
Then no audit request is made.

Given the operator selects a Base from the existing authorised Base summaries
When `audit.read` succeeds
Then each row renders only time, actor type, a fixed/allowlisted event label and entity type.

No trace, actor ID, entity ID, before/after state, permission snapshot, record value, field key, notification text or error detail appears in DOM, query key, URL or telemetry.

### GR-05 Audit pagination preserves only the authorised first page

Given an audit first page and a next cursor
When the next page fails
Then existing first-page rows remain and a fixed retry control targets only that cursor.

When the next page succeeds
Then duplicate event IDs are ignored and the next cursor replaces the prior cursor.

### GR-06 Denial and missing recovery fail closed

Given `401`
Then all Stage07 protected state is cancelled and removed before the expired-session boundary.

Given `403` for members or audit
Then active workspace governance state is removed and the generic denied boundary is shown without resource existence detail.

Given `404` for the audit Base
Then only that exact audit query is removed; members and another permitted Base remain untouched.

### GR-07 Mobile remains a complete read-only path

Given widths 1440, 1280, 430 and 390
When an authorised user opens members and then Base audit
Then every control has a labelled reachable path, continuation control, retry state and focus-safe return. No hidden desktop-only write control exists.

## Acceptance Matrix

| ID | Requirement | Evidence required | Status |
| --- | --- | --- | --- |
| GR-A01 | server-authorised, paginated safe member read model | API/unit/integration denial and pagination tests | proposed |
| GR-A02 | server-authorised, redacted audit read model | DTO/redaction/legacy endpoint isolation tests | proposed |
| GR-A03 | exact protected query cleanup/race containment | App/query tests for 401/403/404/scope replacement | proposed |
| GR-A04 | no raw governance/audit data reaches UI state | parser/component negative tests | proposed |
| GR-A05 | disposable PostgreSQL authorization and cursor path | local PostgreSQL evidence | proposed |
| GR-A06 | focused Browser reachability and console scan | built client, synthetic local data | proposed |

## Prohibited Claims

No result from this package may claim role/permission management, invite lifecycle, audit forensic detail, Bot administration, Telegram proof, staging/production readiness or Stage07 completion.
