# Stage07 S5 Context Binding Work Surface

## Status

- Status: proposed TD006 Option A module; implementation blocked on explicit decision approval.
- Ownership: bridge an already-open authorized Canvas to fixed TD005 invocation intents without exposing Canvas data to the Hub.

## Functional Modules

| Module | Can do after approval | Cannot do |
| --- | --- | --- |
| Current Canvas bridge | pass opaque Base/view/record IDs from App root | fetch generic context for Hub, preserve a context or assert authorization |
| Contact selection | select a server-visible TD005 contact | reveal contact scope/configuration or choose an implicit default |
| Intent controls | enable server-derived `summarize` / `draft_update` when current context is complete | choose arbitrary action/runtime/provider or submit raw values |
| Safe result | show safe summary or open returned draft pointer | render raw records, citations with fields, trace or model evidence |
| Failure boundary | retain local instruction and require explicit reread/retry | auto-resubmit, retain stale result or expose server errors |

## State and Transition Rules

```text
Home / no Canvas
-> Hub shows no-canvas-context

Current Base + view
-> summary context available

Current Base + view + open record
-> draft-update context available

Canvas/workspace/Hub closes
-> discard transient context and result
```

The transition is derived from current UI state only. It does not update a record, draft, employee configuration or user membership.

## Data Exclusion List

The module must never receive: `record.values`, schema fields, view filters, accessible scope arrays, policy, runtime/model/provider information, raw error body, Telegram identifiers, stored instruction history or generic query payloads.

## Acceptance Ownership

This module owns proposed CB-A01--CB-A06. It contributes no proof for employee lifecycle, memory, knowledge, Telegram or external-action features.
