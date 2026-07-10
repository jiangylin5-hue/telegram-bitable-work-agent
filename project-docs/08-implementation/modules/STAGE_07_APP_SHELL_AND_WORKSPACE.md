# Stage 07 App Shell And Workspace Module

## Scope

`AppShell` owns verified session bootstrap, workspace selection, responsive navigation and global protected-state handling. It is the only module that turns a URL/deep-link hint into an authorized route context.

## Interaction Contract

1. Receive Mini App/desktop identity proof and call the server bootstrap endpoint.
2. Store only returned safe identity, memberships and selected workspace identifier in memory.
3. Request capability/navigation model for the selected membership.
4. Render desktop sidebar or mobile bottom navigation from that model.
5. Pass immutable workspace/resource route context to feature modules.
6. On session expiry, `401`, membership revocation or workspace switch, cancel protected requests and clear workspace-scoped cache before showing recovery UI.

## Home Composition

`WorkspaceHome` receives server queue groups and recent Base summaries. It does not fetch all records and derive tasks locally. Selecting a row emits a typed destination: `base`, `view`, `record`, `draft`, `bot_conversation` or `audit`.

## Failure Rules

The shell never retains a prior workspace as fallback after a failed switch. Management navigation is absent rather than disabled when capability is missing. Deep links are retried only after server authorization resolves their resource chain.
