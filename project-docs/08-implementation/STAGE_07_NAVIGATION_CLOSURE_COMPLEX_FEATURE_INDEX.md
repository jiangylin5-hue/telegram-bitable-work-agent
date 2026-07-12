# Stage07 Existing-Contract Navigation Closure Complex Feature Index

## Status

- Status: approved implementation index.
- Scope: the stateful boundaries that make a simple Base directory security-sensitive.

| Feature | Complexity source | Invariant | Failure evidence |
| --- | --- | --- | --- |
| user/workspace-scoped directory cache | delayed async reads can cross a workspace boundary | key includes verified `userId` + `workspaceId`; old scope is removed | delayed Workspace A response never renders in Workspace B |
| route and Canvas interaction | navigation change can race an existing canvas/open request | Bases has no local table/view selection; `openBase` remains authoritative | selection request order starts only after exact Base row action |
| fixed error presentation | raw response can disclose resource existence/details | only known state copy is rendered | 401/403/404/5xx body text absent from DOM |
| empty Base scope | UI may invent a create or sample resource | permitted empty response has no action beyond Home | no Base row/create/queue/Bot control appears |
| desktop/mobile parity | two navigation surfaces can diverge | both invoke the same `selectNavigation` callback | tests exercise both labelled controls |
| capability non-expansion | visual navigation can imply a privilege | More preserves existing governance callback only | no new role/action/API request appears |

## Index and Storage Decision

No persistence structure, database index, migration or browser storage is introduced. The directory uses the existing authorized Base list and the existing memory-only TanStack query client.

## Acceptance Dependencies

- Existing `api.workspaceBases` strict parser.
- Existing `openBase` server-authorized Canvas chain.
- Existing `clearProtectedWorkspace`, `denyInvalidSession` and `denyWorkspace` behavior.
- Focused Mini App tests and production build.
- User-controlled manual UI verification remains separate and pending.
