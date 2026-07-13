# Stage07 Technical Decision 011: Team Bot Entry And Permission-Filtered View Knowledge

## Status

- Decision status: approved for implementation by the user on 2026-07-14 after A+B direction and the detailed implementation plan were reviewed.
- Scope: S5.3, one Team Bot entry surface plus one-shot, permission-filtered knowledge summaries over existing employee-scoped Base views.
- Code status: partial-local implementation is complete within `docs/superpowers/plans/2026-07-14-stage07-s5-team-bot-knowledge-entry-implementation.md`: four safe routes, a server-only 101/100 runtime window, redacted audit/idempotency receipt and an isolated Home workbench. No schema/migration/index/RBAC action/dependency, Telegram operation, browser control or deployment was added. Evidence and gaps are recorded in `evidence/stage07-s5-team-bot-knowledge.md`.

## Product Problem

TD010 makes a Base-bound digital employee manageable and TD009 provides a personal, opt-in Home summary path. Neither provides a visibly separate, server-authorized Team Bot surface that lets a workspace member use an active employee's existing view scope as a shared team knowledge source.

The current safe summary command intentionally reads a one-record context. Treating that sample as a team knowledge system would be misleading, while exposing generic Stage06 routes, arbitrary record search or an unbounded provider prompt would violate the platform constitution.

## Reusable Foundation

| Existing asset | Reuse in S5.3 | Explicitly not exposed |
| --- | --- | --- |
| TD010 `DigitalEmployee` | active lifecycle, one Base, `accessible_tables`, `accessible_views`, fixed `summarize`, member eligibility | raw scope/policy/runtime/provider configuration |
| TD005 safe invocation | authorization, safe answer/citation projection, runtime service, audit and idempotency patterns | generic runtime mode, tools or provider payloads |
| TD009 context discovery | server-composed permitted-view catalog and exact selection reread | personal context state, record picker or generic views |
| Stage06 saved-view query | stored view filter/sort, field-read filtering and record authorization | browser-selected query/field policy or hidden values |
| TD001 protected QueryClient | user/workspace-prefixed in-memory keys, cancellation and scoped cleanup | URL/localStorage/sessionStorage persistence |
| LangGraph/OpenRouter runtime | one-shot server-owned summary execution | thread store, durable memory or a new agent framework |

## Options

| Option | Product result | Data/API impact | Decision |
| --- | --- | --- | --- |
| A — Team Bot entry with existing scoped views as knowledge **(selected)** | A member selects an eligible active employee and a server-permitted saved view, then asks one bounded question/summarize request. | Four narrow safe routes; no new table, index, permission action or dependency. | Selected: turns existing employee scope into usable shared knowledge without creating a second knowledge-permission system. |
| B — durable independent knowledge-source model | Managers separately attach tables/views/files and configure retrieval policies. | new relation, migration/indexes, source lifecycle, retention/deletion, sync and audit semantics. | Deferred: duplicates TD010 scope before the Base-view path is proven. |
| C — Canvas-only Team Bot | Show a Team Bot affordance but require the already-open Canvas. | no new read routes. | Rejected: repeats TD006 and leaves Workspace Home without a team knowledge workflow. |

## Selected Contract: A+B as One S5.3 Package

```text
Workspace Home "团队 Bot"
-> server-authorized active/eligible employee contact
-> server-composed permitted saved-view knowledge catalog
-> exact view re-read at selection and invocation
-> fixed-size, field-filtered view knowledge window
-> one-shot LangGraph summary + opaque citations + redacted audit
-> optional authorized Base handoff for existing Canvas-only draft_update
```

The Team Bot is a product surface over existing active employees, not a second employee type or a published Telegram identity. Its knowledge source is exactly a selected saved view already in the employee's configured scope and currently readable by the caller.

### Product Rules

1. Only an `active` employee with `summarize` in `allowed_actions`, current `digital_employee.invoke` authority and (when selected) a current `DigitalEmployeeMemberGrant` may appear or execute.
2. A Team Bot summary has exactly one selected view. The server uses the view's stored filter/sort and caller field filtering to construct the knowledge window; the browser never sends records, fields, query rules, a row limit or scope policy.
3. The fixed server-owned knowledge window is the first `100` permitted rows in that saved-view order. If no row is permitted, the server returns a fixed empty-context result without a provider call. If the window is truncated, the safe result says so without revealing inaccessible totals.
4. The optional instruction is a one-shot question of at most `600` characters. It is not a thread, memory, tool call, browser role claim or provider configuration.
5. Team Bot Home supports only `summarize`. A member who needs `draft_update` must explicitly open the authorized Base and use the existing TD006 Canvas-record-only flow; S5.3 adds no Home record picker or direct write.

### Proposed Safe Mini App Contract

| Route | Authority | Request / response boundary |
| --- | --- | --- |
| `GET /mini-app/workspaces/{workspace_id}/team-bot-contacts` | active member + existing `digital_employee.invoke` | paged active, member-eligible, summary-capable safe contact summaries only |
| `GET /mini-app/team-bots/{employee_id}/knowledge-contexts` | existing `digital_employee.invoke` | employee safe summary and caller-permitted employee-scoped saved views only |
| `GET /mini-app/team-bots/{employee_id}/knowledge-contexts/{view_id}` | same | exact safe selected-view reread `{id,name,view_type,base_id}` only |
| `POST /mini-app/team-bots/{employee_id}/summaries` | existing `digital_employee.invoke` + `Idempotency-Key` | closed `{base_id,view_id,instruction?}`; safe answer, opaque citations, truncation flag and opaque audit reference only |

No Team Bot route returns record values, record labels, field/table IDs, view configuration, employee policy, member identity, runtime/provider settings, trace, prompt history, raw provider errors or generic Stage06 DTOs.

### Effective Authority

```text
employee active lifecycle and configured Base/view scope
-> assigned-member eligibility when access_mode = assigned
-> caller active workspace membership and existing action
-> caller current Base/view/field/record authorization
-> server-owned selected-view knowledge window
```

Every selector and the summary command recomputes this intersection. A contact or view that was readable at catalog time may disappear before invocation; the command fails closed rather than using cached context.

## Explicit Non-Goals

- no `digital_employee_knowledge_sources` table, files/URLs, embeddings, pgvector query, external retrieval, cross-Base source or broad record search;
- no personal/shared memory, chat thread, message persistence, LangGraph checkpointer/store, retention/deletion control or browser persistence;
- no separate employee publish lifecycle, new RBAC action, group membership model or bypass of TD010 member eligibility;
- no Home `draft_update`, record picker, direct record write, automatic confirmation, employee self-confirmation or automatic notification;
- no Telegram identity/group routing, Bot configuration/send, external action, staging/production operation or deployment claim.

## Approval Boundary

The user approved the A+B direction, reviewed the document package, and instructed execution on 2026-07-14. Implementation remains confined to the four safe routes, fixed knowledge-window semantics, strict Mini App state and existing authorization/runtime reuse stated here.
