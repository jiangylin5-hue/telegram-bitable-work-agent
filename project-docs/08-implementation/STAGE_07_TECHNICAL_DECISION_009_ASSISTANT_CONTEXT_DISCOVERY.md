# Stage07 Technical Decision 009: Personal Assistant Context Discovery

## Status

- Decision status: proposed; explicit user confirmation is required before implementation.
- Scope: one coherent Home-to-assistant context-discovery slice over existing Stage06 digital employees and the approved S5 safe adapter.
- Does not authorize: employee publication lifecycle, knowledge sources, durable memory, generic chat history, record search, Telegram group/contact routing, external send or deployment.

## Problem

TD005/TD006 already provide an approved and implemented safe loop:

```text
open authorized Base Canvas
-> transient {baseId, viewId, recordId?}
-> active employee contact
-> summarize or draft_update
-> controlled draft confirmation
```

The Workspace Home assistant entry may currently list safe contacts, but it has no server-authorized way to discover a permitted view. The client must therefore not infer context from Home cache, generic Base/view APIs, a browser-supplied identifier or local storage. A Home assistant that merely looks interactive but cannot establish an authorized work context is not a usable first-product surface.

## Existing Reusable Foundation

| Existing asset | Reuse in this decision | Never expose to browser |
| --- | --- | --- |
| `DigitalEmployee` | current `workspace_id`, `base_id`, `accessible_tables`, `accessible_views`, `allowed_actions`, `status` | field policy, confirmation policy, response style and raw scope arrays |
| S5 contact directory | safe active contact projection and caller membership gate | generic Stage06 employee DTO |
| S5 invocation adapter | fixed `summarize` and `draft_update` mapping, live runtime and field-filtered response | runtime mode, raw prompt/tool/provider payload or generic invoke result |
| Stage06 view authorization | existing Base/table/view/caller intersection | raw `config`, `permission_policy`, record values and hidden fields |
| TD001 protected QueryClient | memory-only user/workspace keys, cancellation and cleanup | persistence, URL routing or cross-workspace cache |

The recommendation deliberately continues the existing FastAPI + SQLAlchemy + LangGraph-first architecture. LangGraph differentiates short-lived thread state from cross-thread stores; neither is introduced in this decision, so the product does not invent a client-side memory mechanism before retention and deletion rules are approved. [Official LangGraph memory documentation](https://docs.langchain.com/oss/python/langgraph/add-memory)

## Options

| Option | Product result | Contract change | Advantages | Risks / decision |
| --- | --- | --- | --- | --- |
| A — retain Canvas-only context | Assistant can invoke only from an already-open Canvas, exactly as TD006. | none | Already implemented; smallest attack surface. | Rejected as the next product step: Home assistant remains contextless and cannot complete a useful summary flow. |
| B — server-composed contact-to-view catalog **(recommended)** | From Home, a user selects a safe contact and then one permitted saved view to run `summarize`; `draft_update` still requires an open current record in Canvas. | two safe read endpoints and a Mini App route/state addition; no schema migration or new permission action. | Delivers a usable personal-assistant MVP while reusing existing authorization and S5 invoke contract. Avoids a record label, chat-history, memory and lifecycle model. | Requires exact safe DTO and stale-scope rules. Must be explicitly approved before code. |
| C — full Package4 at once | Workspace Bot lifecycle, multi-Base scopes, record picker, durable threads, knowledge sources, per-user memory and Telegram binding. | several migrations, APIs, permission/retention/audit policies and external gates. | Broadest product coverage. | Rejected for the next substage: combines independent high-risk domains and would delay the first usable Home assistant. |

## Recommended Option B

### Product Flow

```text
Workspace Home
-> open Personal Assistant
-> existing safe contact page
-> select one active contact
-> server-composed permitted-view page for that contact
-> select one view
-> existing safe S5 summarize invocation
-> safe answer + opaque citations
-> optional "打开 Base 继续处理" handoff
```

The optional handoff opens only the contact's existing Base by reusing the already-authorized `openBase(BaseSummary)` chain. It does not preselect a record, reveal a record label, create a draft or turn the contact into a published/team Bot.

### Proposed Safe Read Contracts

| Route | Request | Safe response | Server checks |
| --- | --- | --- | --- |
| `GET /mini-app/digital-employees/{employee_id}/assistant-context` | cursor/limit only | `{ employee: {id,name,description,base_id}, views: [{id,name,view_type}], next_cursor, has_more }` | active employee; current workspace member; `digital_employee.invoke`; caller-readable employee Base; employee view scope; caller-readable view |
| `GET /mini-app/digital-employees/{employee_id}/assistant-context/views/{view_id}` | none | `{ id, name, view_type, base_id }` for selection re-read | all preceding checks plus exact selected view membership |

No route returns a table ID, field ID, view configuration, member policy, record, record display label, employee configuration, draft detail, runtime metadata, trace, provider metadata or raw error body. The second route is a protected re-read used only before invocation/handoff; it is not a generic view API.

The existing `POST /mini-app/digital-employees/{employee_id}/invocations` remains the only invocation command. The browser sends the re-read `{base_id, view_id}` only for the fixed `summarize` intent. `draft_update` stays disabled in Home and remains Canvas-record-only under TD006.

### Authorization and Error Policy

Effective authority is unchanged:

```text
employee configured Base/view scope
-> caller active workspace membership and action
-> caller current Base/view/field/record scope
```

| Situation | Result | Client cleanup |
| --- | --- | --- |
| contact is inactive, cross-workspace or no longer readable | indistinguishable `404` | remove exact contact/catalog keys and clear selection |
| current caller lacks invoke/view access | `403` generic boundary | remove current workspace S5/assistant subtree; no prior view remains |
| session expired | `401` generic boundary | clear all protected Stage07 state |
| view vanished or leaves employee scope | `404` fixed reselect state | remove exact catalog/selection keys; no stale invoke |
| `409` or `422` from existing invocation | fixed reread/reselect guidance | retain no remote data beyond typed local instruction |
| network, malformed body or `5xx` | fixed retry state | render no server detail, prior view or inferred fallback |
| workspace/contact/view changes while request is pending | newest target only | generation mismatch discards old response and invocation result |

### Explicit Non-Goals

- `digital_employees.status` remains the existing `active` gate; no `draft|published|disabled` lifecycle is added.
- Existing base-bound employee scope remains unchanged; no multi-Base relation or workspace-wide scope is added.
- There is no record picker, record label algorithm, default/primary field migration or direct Home `draft_update`.
- There is no assistant thread, message history, LangGraph checkpointer/store, memory namespace, retention period, clear/delete action or browser persistence.
- There is no knowledge source, file indexing, vector retrieval, shared memory, Telegram alias/group binding, notification send or external action.

## Approval Boundary

Approval of Option B authorizes only the two safe read endpoints, their tested server authorization/projection, one Home assistant context surface, protected client state and existing S5 `summarize` reuse. It authorizes no schema migration, new permission action, lifecycle, memory, knowledge, record discovery, Telegram behavior or external operation.
