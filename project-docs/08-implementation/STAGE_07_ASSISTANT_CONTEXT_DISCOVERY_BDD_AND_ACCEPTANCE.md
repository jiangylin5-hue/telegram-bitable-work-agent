# Stage07 Personal Assistant Context Discovery BDD and Acceptance

## Status

- Status: proposed under TD009 Option B; no implementation evidence yet.
- Scope: authorized Home contact-to-view selection and existing safe `summarize` invocation only.

## BDD Scenarios

### ACD-01 Home starts without an implied work context

Given a member opens Personal Assistant from Workspace Home
When no contact and view have been selected
Then the UI explains that a permitted context must be selected
And it does not infer a default employee, Base, view, record, memory or workspace search result.

### ACD-02 Contacts remain the existing safe projection

Given the member can read and invoke permitted digital employees
When the assistant loads contacts
Then it receives only the approved S5 contact projection
And it does not receive employee scope arrays, policies, runtime configuration, provider metadata or Telegram identity.

### ACD-03 View catalog is the employee/caller intersection

Given the member selects an active safe contact
When the context catalog is requested
Then the server returns only views belonging to the contact's Base that are in employee scope and currently readable by the caller
And the browser cannot widen the result by submitting a Base, table, view or role claim.

### ACD-04 Selected view is re-read before summary

Given a safe view is visible in the catalog
When the member selects it and requests a summary
Then the server revalidates the employee, Base, view and caller intersection
And the browser sends only the existing fixed `summarize` intent plus opaque IDs and optional bounded instruction.

### ACD-05 Home cannot create a draft without an open record

Given a member selected a contact and view from Home
When they inspect available assistant actions
Then Home offers summary only
And draft creation remains unavailable until the existing Canvas has an open current record under TD006.

### ACD-06 Empty and retryable context are explicit

Given a contact has no currently permitted views, or the catalog request is malformed, unavailable or returns `5xx`
When the catalog resolves
Then the UI shows fixed empty or retryable copy
And it shows no stale view, generic view browser, inferred Base, raw server error or provider error.

### ACD-07 Authorization and resource loss fail closed

Given a contact, Base or selected view becomes inaccessible
When catalog, selected-view re-read or summary returns `401`, `403` or `404`
Then the existing session/workspace/exact-resource cleanup applies
And no previous context remains actionable.

### ACD-08 Scope replacement discards stale assistant results

Given Workspace A contact/view catalog or summary is unresolved
When the member changes workspace, contact, selected view or closes the assistant
Then the pending generation is invalidated
And a late result cannot render, invoke or open a Base in the replacement state.

### ACD-09 No hidden Package4 expansion

Given this package is implemented
When its source/API/migration inventory is inspected
Then it contains no employee lifecycle, multi-Base scope, record picker, primary-field algorithm, memory, knowledge, chat persistence, Telegram routing, notification or external-action behavior.

## Failure Matrix

| Boundary | `401` | `403` | `404` | `409`/`422` | malformed/`5xx`/network |
| --- | --- | --- | --- | --- | --- |
| contacts | complete protected-state expiry | workspace/S5 subtree denied | fixed unavailable/reload | n/a | fixed retry, no old rows |
| view catalog | complete protected-state expiry | workspace/S5 subtree denied | clear selected contact/context | cursor/reselection state only | fixed retry, no old views |
| selected-view re-read | complete protected-state expiry | workspace/S5 subtree denied | clear exact selected view | fixed reselect | fixed retry, no prior invoke |
| summary invocation | complete protected-state expiry | workspace/S5 subtree denied | clear exact context | keep only typed instruction; require reread | fixed retry, no answer/citations |

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- | --- |
| ACD-A01 | Home has no default/inferred context | client component/application test | proposed |
| ACD-A02 | safe contact response has no configuration/raw metadata | API schema/parser/negative test | proposed |
| ACD-A03 | catalog returns only employee/caller/Base/view intersection | service/API + local PostgreSQL authorization matrix | proposed |
| ACD-A04 | summary re-read uses only fixed existing intent | request-body and service regression | proposed |
| ACD-A05 | Home has no `draft_update`/record creation fallback | client negative test and source review | proposed |
| ACD-A06 | empty/retryable/raw-error suppression works | client delayed/error matrix | proposed |
| ACD-A07 | `401`/`403`/`404` cleanup fails closed | API/client scope cleanup matrix | proposed |
| ACD-A08 | workspace/contact/view/close replacement discards late result | deferred-promise client regression | proposed |
| ACD-A09 | no Package4 lifecycle/memory/knowledge/Telegram expansion | migration/API/dependency inventory | proposed |
| ACD-A10 | build and user-controlled visual review | production build; manual-only review if requested | proposed |

## Non-Goals

- Any persistent conversation, user-memory, shared memory or knowledge retrieval.
- Record context discovery or a primary display-field choice.
- Employee publish/disable or multi-Base lifecycle.
- Telegram handoff, Bot configuration, send or production evidence.
