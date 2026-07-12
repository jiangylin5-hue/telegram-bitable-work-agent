# Stage07 Draft and Digital Employee Hub BDD and Acceptance

## Status

- Status: TD005/TD006 implementation evidence is reconciled below. S5 remains `partial-local`: only rows whose stated local evidence is complete are marked `implemented-local`; Browser/provider-dependent rows remain explicitly partial.
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
| DE-A01 | safe contact projection and cross-workspace omission | API/unit and PostgreSQL isolation tests | implemented-local — focused backend/real local PostgreSQL evidence covers safe projection and cross-Base denial. |
| DE-A02 | explicit context intersection before runtime | service/API denial matrix | implemented-local — Base/view/record intersection, cross-Base and post-selection hidden-view denial, plus a record filtered out of the current View, fail before runtime and before a draft-invocation idempotency reservation. |
| DE-A03 | fixed invocation intents and safe result projection | strict parser/API/runtime tests | partial-local — fixed intent and strict `{recordId}` citation/result transport are covered; real provider evidence is absent. |
| DE-A04 | draft creation remains non-mutating | service/API/real runtime or injected-LangGraph proof | partial-local — bounded adapter and terminal draft loop are implemented; configured real-provider evidence is absent. |
| DE-A05 | field-filtered immutable draft diff | schema/detail/hidden-field regression and Browser inspection | partial-local — safe detail DTO/UI exists; a fresh server reread hides a post-creation revoked field and recomputes `can_confirm=false`. Field-filtered Browser inspection is absent. |
| DE-A06 | confirm lock/revision/idempotency/audit reference | migration, disposable PostgreSQL race/replay/rollback tests | implemented-local — real local PostgreSQL proves replay, concurrent winner/loser ledger behavior and terminal audit reference. |
| DE-A07 | reject has no record write and is replay-safe | service/API/PostgreSQL tests | implemented-local — real local PostgreSQL proves replay and unchanged record values/version. |
| DE-A08 | protected client cleanup and no raw errors | transport/query/App delayed-response tests | partial-local — strict parser, fixed error rendering, stale Canvas-result discard, and delayed old-workspace terminal `401/403` isolation are covered; full draft failure matrix remains unaccepted. |
| DE-A09 | four-width accessible Hub/draft path | synthetic built-client Browser matrix and console scan | partial-local — build passes, but both available Browser surfaces refused the local fixture. |
| DE-A10 | no S6 capability leaks | route inventory, DTO/parser/DOM negative tests | implemented-local — no S6 delivery/mint route or generic context persistence is added; strict DTO/parser/client boundaries are covered. |

### 2026-07-12 Interim Implementation Evidence (not acceptance closure)

| Covered behavior | Fresh evidence | Acceptance gap retained |
| --- | --- | --- |
| safe summary projection and context intersection | backend unit plus local PostgreSQL run: `18 passed`; malicious citation fields and unknown record IDs are dropped; cross-Base, post-selection hidden View and record-filtered-out-of-current-View contexts fail before runtime, draft creation or invocation-ledger reservation; terminal concurrency is locked; and a post-creation field revoke hides the diff/value then disables confirmation | real provider remains absent |
| safe client transport and TD006 Option A bridge | focused Mini App run: `4 files / 18 tests`; strict parser retains only `answer` and `{recordId}` citations; Canvas UI sends only current Base/view and disables draft creation without an open record; an old-workspace delayed terminal `401/403` cannot deny or repopulate the replacement workspace | no generic context source/persistence is allowed; Browser matrix remains unavailable |
| terminal draft baseline and queue query | real local PostgreSQL proves confirm replay, reject no-record-write, concurrent confirm rolls back the losing command's ledger, and a `512` pending / `1,536` terminal queue measurement reuses the existing Base/status index for the bounded pending-only route | full field-filtered Browser matrix remains pending; the optional partial index is intentionally not created |
| production compilation | `npm.cmd run build` completed after the current-Canvas invocation UI change | both available browsers refused the temporary loopback fixture; no S5 visual observation is claimed |

This reconciliation does not promote S5 or Stage07 to complete. DE-A03--DE-A05 and DE-A08--DE-A09 retain the exact provider/Browser/failure-matrix limits above; TD006 remains only the approved opaque transient context bridge.

## Prohibited Claims

S5 may not claim personal memory, knowledge retrieval, team/contact publication lifecycle, Telegram deep-link identity, group mention execution, external notification/send, production readiness, Stage07 completion or a general agent/chat platform.
