# Stage07 Personal Assistant Context Discovery Work Surface

## Status

- Status: implemented as a bounded `partial-local` TD009 Option B surface on 2026-07-13.
- Scope: Home personal-assistant context discovery through existing safe employee contacts and one server-composed saved-view catalog.

## Functional Modules

| Module | Existing base | Implemented responsibility | Explicit boundary |
| --- | --- | --- | --- |
| Home assistant entry | `WorkspaceHome.tsx` | opens the context workbench with no selected context | no default contact, search or context persistence |
| Contact selector | S5 `DraftEmployeeHub` safe contacts | selects existing active safe contact | no employee edit/publish/configuration data |
| View catalog | new narrow Mini App read adapter | returns current employee/caller permitted views | no generic Base/view API reuse in the workbench |
| Context workbench | new client component | state machine for contact → view → summary | no `draft_update`, record picker or conversation history |
| Summary action | existing S5 invocation adapter | reuses fixed `summarize` intent | no runtime/action/provider choice |
| Base continuation | existing `openBase` | opens the selected employee Base after explicit user action | no implicit record/view selection or draft creation |

## State Ownership

| State | Owner | Lifetime | Clear trigger |
| --- | --- | --- | --- |
| contacts | existing S5 protected query | user/workspace scope | identity/workspace loss or Hub close |
| selected contact/view IDs | workbench React state | component memory only | contact/view/workspace change or close |
| catalog and selected-view DTO | assistant protected query keys | user/workspace scope | current resource failure, replacement or close |
| instruction | workbench React state | component memory only | contact/view/workspace change or close |
| summary answer/citations | workbench React state | current invocation generation only | replacement, close or failed reread |

## User Actions

| Action | Preconditions | Server interaction | Safe result |
| --- | --- | --- | --- |
| open assistant | active workspace | existing contact load | fixed idle/contact state |
| choose contact | contact visible in S5 projection | context catalog read | safe view names/types only |
| choose view | view visible in catalog | selected-view re-read | safe selected context chip |
| summarize | selected view current, fixed intent allowed | existing S5 invocation | safe answer and opaque citations |
| open Base | selected contact current | existing Base handoff reads | ordinary authorized Canvas |
| create draft | none from Home | none | unavailable; requires Canvas record TD006 path |

## Excluded Surfaces

- Team Bot public/published lifecycle, multi-Base scope editor and Telegram contact/group bindings.
- Record search, labels, saved context history, assistant threads, memory partitions or deletion controls.
- Knowledge sources, indexing, retrieval, embeddings or vector search.
- Notification/external-action send, autonomous record write or direct Agent tool access.

## Acceptance Dependencies

1. TD009 Option B approval.
2. Existing S5 contact and invocation safety behavior remains unchanged.
3. Existing view/Base authorization can produce a closed permitted-view intersection without returning generic view configuration.
4. Focused DTO/API/component/App-flow tests and a full Mini App regression pass prove the implemented local path; dedicated delayed replacement/revocation and database evidence remain open.
