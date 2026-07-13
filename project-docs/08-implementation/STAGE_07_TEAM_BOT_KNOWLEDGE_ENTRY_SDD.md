# Stage07 Team Bot Knowledge Entry SDD

## Status

- Status: TD011 proposed software design; code waits for user review of this document package and a separate approved implementation plan.
- Scope: Team Bot is a Home workbench over active employees; knowledge is one safe selected saved-view window, not a durable knowledge system.

## Architecture

```text
Workspace Home Team Bot workbench
-> closed contacts / knowledge-context reads
-> strict user/workspace-scoped client state
-> exact selected-view reread
-> server-only permission-filtered 100-row knowledge window
-> existing LangGraph summary runtime
-> safe answer/citations + redacted audit
-> optional existing authorized Base handoff
```

The design reuses FastAPI, SQLAlchemy 2.x, existing Stage06 view reads, TD010 eligibility, TD005 invocation/audit/idempotency patterns and TD001 QueryClient. It adds no agent framework, ORM, queue, vector library or browser persistence.

## Durable Data And Index Decision

S5.3 creates no table, migration or physical index. `DigitalEmployee.accessible_tables`, `DigitalEmployee.accessible_views`, `DigitalEmployee.status`, `DigitalEmployeeMemberGrant`, existing saved-view storage and existing idempotency/audit records remain authoritative.

The knowledge window is an in-process command value, never a database resource or client cache payload:

```python
@dataclass(frozen=True)
class TeamBotKnowledgeWindow:
    employee_id: UUID
    base_id: UUID
    view_id: UUID
    row_limit: Literal[100]
    row_count: int
    truncated: bool
```

Only field-filtered record data is passed from this value into the existing runtime; the browser receives neither the value nor its records.

## Safe Contract

```ts
type TeamBotContact = {
  id: string
  baseId: string
  name: string
  description: string
  availableIntents: ['summarize']
}

type TeamBotKnowledgeContext = {
  employee: { id: string; name: string; description: string; baseId: string }
  views: Array<{ id: string; name: string; viewType: 'grid' | 'kanban' | 'calendar' | 'form' }>
  nextCursor: string | null
  hasMore: boolean
}

type TeamBotSummaryRequest = {
  baseId: string
  viewId: string
  instruction?: string
}

type TeamBotSummary = {
  kind: 'summary' | 'empty_context'
  answer: string
  citations: Array<{ recordId: string }>
  knowledgeWindowTruncated: boolean
  auditEventId: string
}
```

All request models use `extra='forbid'`. Parsers require exact roots, opaque non-empty IDs, bounded strings and known view types. They reject policy, scope arrays, row payloads, provider/runtime/trace data, member identity, field/table IDs, prompt history and raw error objects.

## Route And Authorization Matrix

| Route | Existing action | Server-side checks | Result |
| --- | --- | --- | --- |
| contacts | `digital_employee.invoke` | active membership, workspace/Base visibility, active employee, assigned eligibility and configured `summarize` | safe paged contacts |
| catalog / selection | `digital_employee.invoke` | active employee, eligibility, employee Base, scoped view, caller-readable view and safe view type | safe catalog / exact selection |
| summary | `digital_employee.invoke` | all catalog checks re-run; `summarize` allowed; body Base equals employee Base; selected view still scoped/readable | safe summary/empty receipt |

No new action is introduced. Entry visibility is a server-provided hint only; every route independently authorizes.

## Knowledge Assembly And Runtime

1. Resolve employee and current caller with TD010 `is_member_eligible_for_employee` after active-status and existing action checks.
2. Recompute the catalog intersection with the same employee Base, `accessible_views`, configured table scope, current Base visibility and `get_view_presentation` authorization used by TD009.
3. Re-read the exact selected view. Reject any missing, cross-Base, unsupported, out-of-scope or revoked view before reading rows.
4. Call existing `list_view_records` with a server-owned probe limit of `101`; use the saved view's current filter/sort and caller field filtering. Pass only the first `100` permitted rows to the runtime and set `truncated` when the 101st permitted row exists. The browser supplies no limit/cursor/query/row data.
5. If zero permitted rows remain, write a redacted `empty_context` audit event and return the fixed result without invoking a provider.
6. Otherwise construct the internal window and call the existing configured `summarize` path with only that field-filtered window and bounded instruction.
7. Filter citations with the existing visible-record citation guard; emit record IDs only. Persist a redacted audit state containing durable IDs, `row_count`, truncation, outcome and replay reference, never question text, record values, field names or provider output diagnostics.

The summary command requires an idempotency key. Its fingerprint includes workspace, actor, employee, Base, view and normalized instruction. Same-key/same-payload replay returns the stored safe result; changed payload returns conflict before a new runtime call.

## State And Cache Lifecycle

All keys start with `{userId, workspaceId, 'team-bot'}`. Contacts, catalog, selection and result use separate descendants. No Team Bot key is reused by TD009 Personal Assistant, even when they refer to the same employee/view.

| Event | Required cleanup/result |
| --- | --- |
| close, workspace switch or session `401` | cancel/remove the Team Bot subtree; `401` also follows global protected-state cleanup |
| `403` | remove current workspace Team Bot subtree and show fixed denied boundary |
| employee/view `404` | remove exact contact/catalog/selection/result descendants and require reselect |
| `409`/`422` | retain only typed local instruction; remove remote result and offer reread/retry |
| malformed/network/`5xx` | fixed retry copy; do not render raw body or stale result |
| late request | request generation/scope identity rejects it; it cannot reopen or mutate replacement state |

## UI Boundary

The Home workbench visibly labels itself `团队 Bot` and explains that it has no personal memory. It offers only contact selection, view selection, bounded one-shot instruction, summarize, result/citations and an explicit `打开 Base 继续处理` action. Team Bot does not show a transcript, message composer history, model selector, provider control, record picker, direct draft control, policy/JSON editor or a Telegram control.

## Failure And Safety Boundary

Provider failure writes only a fixed outcome/code audit summary, returns fixed retry copy and never retries automatically. A response is never presented as successful unless the safe command outcome and audit reference are durable. No provider credentials or raw request/response enters logs, audit, QueryClient or DOM.
