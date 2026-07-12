# Stage07 S5 Context Binding SDD

## Status

- Status: proposed TD006 Option A implementation specification; no code authority before explicit approval.
- Scope: a transient App-root-to-Hub context bridge, not a new storage, permission or API subsystem.

## Components and Data Flow

```text
authorized current Base Canvas
-> App root extracts opaque base/view/record IDs
-> DraftEmployeeHub receives transient CurrentCanvasInvocationContext
-> fixed safe intent request
-> existing TD005 S5 invocation adapter
-> safe summary or draft pointer
-> existing S5 draft review path
```

The Canvas continues to own its own generic data queries. The Hub does not receive those query results and makes no generic network request. The bridge is one-way: the Hub cannot navigate the Canvas, change selected view/record or create a context.

## Type Boundary

```ts
type CurrentCanvasInvocationContext = {
  baseId: string
  viewId: string
  recordId: string | null
}

type HubInvocationInput = {
  contactId: string
  intent: 'summarize' | 'draft_update'
  instruction: string
}
```

`HubInvocationInput` is local component state only. It is discarded on close, workspace change, Canvas change, denied state and unmount. It is never serialized to URL, localStorage, telemetry or a generic API.

## UI State Model

| State | Required presentation | Prohibited behavior |
| --- | --- | --- |
| no-canvas-context | label that an open Base/view is needed | guessing a Base, showing stale chips or offering arbitrary IDs |
| view-context | show opaque selected-context label supplied by App root | displaying schema/records or implying full employee scope |
| record-context | enable `draft_update` only if a record ID exists | editing proposed values or source record directly |
| contact-not-selected | show context but no submit | choosing a default contact |
| invocation-pending | lock only the submitted control and retain instruction | streamed raw runtime state or local success |
| summary-ready | render safe answer/citations | record arrays, model metadata or trace |
| draft-ready | open server-returned draft pointer | locally construct a diff |
| stale/denied/error | fixed feedback and explicit retry/reread | automatic resubmit or raw server error |

## App Root Responsibilities

1. Derive the context only from current ready `canvas.base`, `canvas.view` and optional `canvas.detail`.
2. Set the context to absent when any required Canvas component is absent, when workspace changes, or when a new Canvas request supersedes the old one.
3. Pass only IDs to the Hub. Do not pass `records`, `schema`, `presentation`, `detail.values`, capability flags or query keys.
4. Keep all invocation network calls in the existing safe S5 API client. The hub must use user/workspace-scoped S5 query keys only.

## S5 Adapter Responsibilities

The existing server adapter remains authoritative. Before runtime it resolves current identity, employee, employee Base, view, record and caller scope. For `draft_update`, the current idempotency ledger reserves and replays the safe draft pointer. A client context bridge must not weaken those checks or substitute a local authorization condition.

## Error and Cleanup Rules

| Event | Client action |
| --- | --- |
| Canvas context changes before completion | invalidate local invocation version; discard response |
| `401` | existing complete protected-state cleanup and denied boundary |
| `403` | clear current protected workspace boundary; no old context remains |
| `404` | remove exact S5 result/draft context and show fixed unavailable state |
| `409` / `422` | retain only typed local instruction; explicit reread/retry, never automatic submit |
| `5xx` / network | fixed local failure; do not display server `detail` |

## Accessibility and Responsive Requirements

- Focus order is contact → current context → intent → instruction → submit → result/draft.
- At 430/390 widths, current-context and submit controls remain reachable in the full-height Hub sheet with 44px targets.
- Context status uses text, not colour alone. A missing record is announced before a disabled draft-update control.
- Closing returns focus to the original Hub trigger; a Canvas-triggered Hub may return focus only while the trigger remains connected.

## Non-Implementation Boundary

This specification intentionally provides no Home context picker, record search endpoint, selection persistence, memory, knowledge retrieval, Telegram context or external execution. Those would need a separately approved API/data decision.
