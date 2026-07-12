# Stage07 S5 Context Binding BDD and Acceptance

## Status

- Status: proposed companion to TD006 Option A; no behavior is implemented from this document until TD006 is approved.
- Scope: bind one already-authorized current Base Canvas to fixed S5 invocation intents.

## BDD Scenarios

### CB-01 Context is explicit but not a browser authority claim

Given an authorized user has an open current Canvas with a Base and view
When they open the S5 Hub
Then the Hub may receive only opaque `baseId` and `viewId` from App root state, and no generic schema, record values, role or capability object.

Given the user returns to Home, switches workspace or the Canvas closes
When the Hub is next opened
Then no previous context is restored from storage, URL or transient stale state.

### CB-02 Summary is limited to the active Canvas view

Given a selected active contact and a current Canvas Base/view
When the user chooses the server-derived `summarize` intent
Then the browser sends exactly that Base/view pair and an optional bounded instruction.

Given the contact lacks the intent, the current Canvas is missing, or the Base differs from the contact Base
When a submit would otherwise be available
Then the control is absent or disabled with fixed local explanation; no request is made.

### CB-03 Draft update needs an open current record

Given a selected active contact, current Canvas Base/view and open record
When the user chooses server-derived `draft_update`
Then the request contains only the opaque current record ID and a new idempotency key.

Given no record is open
When the user reads the Hub
Then it states that draft creation requires an open record and cannot invent a picker, direct values or a record ID.

### CB-04 Server revalidates all intersections

Given a browser tampers with a Base, view or record ID
When the S5 invocation reaches the backend
Then the server, not the Canvas state, verifies employee scope, caller scope and resource membership; a failed intersection creates no runtime success, draft or audit success.

### CB-05 Result remains a safe terminal of the invocation

Given a permitted summary completes
When it is rendered
Then only the S5 safe answer and allowed safe citations appear; records, prompts, runtime/provider metadata, traces and skill evidence do not appear.

Given a permitted draft result completes
When it is rendered
Then it opens only the returned safe draft pointer and the existing immutable draft review flow; it does not render proposed values from invocation output.

### CB-06 Failure and focus are fail-closed

Given context disappears, the server returns a typed error, or the network fails
When the invocation attempt ends
Then no local success is inferred, typed instruction remains only in component state, fixed local feedback is shown and retry/reread is explicit.

Given the Hub closes, Canvas changes or workspace changes during an invocation
When the request resolves
Then stale output is discarded and focus returns predictably without persisting context.

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- | --- |
| CB-A01 | no generic object or client persistence enters Hub | type/DOM/query negative tests | proposed |
| CB-A02 | summary sends only current Canvas Base/view | App flow and malformed-context tests | proposed |
| CB-A03 | draft update requires current open record plus idempotency key | App/API replay tests | proposed |
| CB-A04 | server rejects cross-Base/stale/hidden scope | API/unit and PostgreSQL denial matrix | proposed |
| CB-A05 | safe result only and no raw runtime disclosure | parser/DOM regression tests | proposed |
| CB-A06 | responsive/focus/failure lifecycle | Browser width and delayed-response checks | proposed |

## Deliberate Non-Goals

- Home standalone Base/view/record browsing or a generic record picker;
- saving a context, recent context, instruction history or personal memory;
- employee creation, publication, lifecycle configuration or Telegram routing;
- direct record write, raw prompt export, provider/runtime selection or external action.
