# Stage07 Draft and Digital Employee Hub BDD and Acceptance

## Status

- Status: approved TD005 Option A BDD; S5 implementation is in progress and every acceptance row remains unevaluated until evidence is recorded.
- Scope: safe S5 contact, explicit context, employee invocation, draft diff and terminal confirmation/rejection only.

## BDD Scenarios

### DE-01 Contact directory is a safe projection

Given a caller is an active workspace member
When they open the Hub
Then each returned contact is active, reachable through the caller's existing Base scope and contains only safe display metadata plus server-derived fixed intents.

Given a contact is disabled, outside the selected Base, inaccessible through caller scope or belongs to another workspace
When the directory is read
Then it is omitted rather than represented as a disabled configuration row with hidden scope data.

### DE-02 Context is explicit and intersectional

Given a caller selects a contact
When they choose a summary view or draft target record
Then server validation proves every ID belongs to the selected Base, employee configured scope and caller current scope before invocation.

Given context is missing, cross-Base, stale, hidden or no longer readable
When an invocation is submitted
Then it fails closed with a stable code and no model/tool call, draft or audit success is created.

### DE-03 Browser cannot choose an arbitrary agent action or runtime

Given a malicious browser sends `action`, `runtime_mode`, `proposed_values`, provider fields or an unapproved intent
When it reaches the S5 invocation endpoint
Then strict validation rejects it before runtime execution.

Given a permitted `summarize` intent
When it completes
Then the response contains only safe answer/citation content and never records arrays, runtime metadata, skill evidence, employee configuration or trace.

### DE-04 Draft creation remains a proposal

Given a permitted `draft_update` employee intent on a selected record
When the runtime proposes an update
Then the only durable write-like result is one `pending_confirmation` draft and audit event; the source record version and values do not change.

Given an employee lacks draft action/table scope or the caller lacks current read scope
When it attempts the same intent
Then no draft or record mutation is persisted.

### DE-05 Draft detail is field-filtered and immutable

Given a pending draft contains readable and hidden field changes
When a reviewer opens its S5 detail
Then only readable supported field rows expose label/type/before/proposed safe render values; hidden/unsupported rows, creator identity, trace, policy and expected record version are absent.

Given a field becomes hidden after draft creation
When the draft is reread
Then it disappears from the display; confirm availability is recomputed by the server and cannot rely on the earlier read.

### DE-06 Confirm is atomic, versioned and auditable

Given a reviewer has current confirm plus record/field write authority and a draft revision matches
When they confirm with a fresh idempotency key
Then one locked transaction rechecks the draft, record revision and every proposed field, writes the record once, sets draft `confirmed`, increments draft version, writes one sanitized audit event and persists its opaque audit reference.

Given two valid confirm commands race
When one commits first
Then the other receives fixed stale/terminal conflict and performs no record or audit write.

### DE-07 Reject is idempotent and cannot change a record

Given a reviewer has reject authority and a matching pending draft revision
When they reject with a fresh idempotency key
Then one locked transaction sets `rejected`, increments draft version and records one sanitized audit event without calling record update.

Given the same reject command replays
When it reaches the backend
Then it returns the same safe terminal receipt; a changed key/payload or stale revision conflicts.

### DE-08 UI lifecycle fails closed

Given `401`
When contact, invocation or draft state is active
Then all S5 protected queries are cancelled/removed before expired-session rendering.

Given `403`, `404`, `409`, `422`, `5xx` or network failure
When an S5 request fails
Then cleanup scope, retained typed intent, fixed feedback and explicit reread/retry follow the SDD; raw error detail never reaches DOM, URL or telemetry.

### DE-09 Responsive terminal review is reachable

Given `1440`, `1280`, `430` and `390` widths
When a permitted reviewer opens a draft and confirms or rejects it
Then contact/context/diff/terminal state controls are labelled, reachable, pending-safe and return focus predictably.

### DE-10 S5 does not impersonate S6

Given a browser opens the Hub
When it sees a contact or terminal draft receipt
Then it cannot create/publish a contact, persist memory, access knowledge, claim Telegram identity, route a group mention, send notification or execute an external action.

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- | --- |
| DE-A01 | safe contact projection and cross-workspace omission | API/unit and PostgreSQL isolation tests | unevaluated |
| DE-A02 | explicit context intersection before runtime | service/API denial matrix | unevaluated |
| DE-A03 | fixed invocation intents and safe result projection | strict parser/API/runtime tests | unevaluated |
| DE-A04 | draft creation remains non-mutating | service/API/real runtime or injected-LangGraph proof | unevaluated |
| DE-A05 | field-filtered immutable draft diff | schema/detail/hidden-field regression and Browser inspection | unevaluated |
| DE-A06 | confirm lock/revision/idempotency/audit reference | migration, disposable PostgreSQL race/replay/rollback tests | unevaluated |
| DE-A07 | reject has no record write and is replay-safe | service/API/PostgreSQL tests | unevaluated |
| DE-A08 | protected client cleanup and no raw errors | transport/query/App delayed-response tests | unevaluated |
| DE-A09 | four-width accessible Hub/draft path | synthetic built-client Browser matrix and console scan | unevaluated |
| DE-A10 | no S6 capability leaks | route inventory, DTO/parser/DOM negative tests | unevaluated |

### 2026-07-12 Interim Implementation Evidence (not acceptance closure)

| Covered behavior | Fresh evidence | Acceptance gap retained |
| --- | --- | --- |
| safe summary projection | focused backend unit run: `11 passed`; malicious citation fields and unknown record IDs are dropped, and a cross-Base view is denied before runtime | real provider and stale/hidden context matrix remain absent |
| safe client transport | focused Mini App run: `4 files / 11 tests`; strict parser retains only `answer` and `{recordId}` citations | no invocation control is rendered before TD006 chooses a context source |
| terminal draft baseline | local PostgreSQL integration run: `1 passed`; existing confirm replay path remains executable | race/rollback/reject matrices and conditional-index measurement remain pending |
| production compilation | `npm.cmd run build` completed after the safe invocation transport change | no four-width S5 Browser matrix has been run |

These checkpoints move implementation forward but do not change any `unevaluated` acceptance row to accepted. DE-A01 through DE-A10 require the complete specified evidence, including the TD006-approved invocation path where applicable.

## Prohibited Claims

S5 may not claim personal memory, knowledge retrieval, team/contact publication lifecycle, Telegram deep-link identity, group mention execution, external notification/send, production readiness, Stage07 completion or a general agent/chat platform.
