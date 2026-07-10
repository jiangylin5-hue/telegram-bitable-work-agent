# Stage 07 SDD

## Status

- Document status: active Stage07 design detail
- Scope: UI architecture, module boundaries and interaction flows
- Current Progress: planned; no code implementation has started

## 1. Architecture Overview

```text
Telegram Mini App / desktop browser
-> AppShell and identity bootstrap
-> permission-filtered route/view models
-> feature modules
   -> WorkspaceHome | BaseCanvas | RecordDetail | BotHub | Governance
-> Stage06 API gateway
-> authorization / records / drafts / audit services
```

The browser never determines effective role, field visibility or Bot authority. It renders server-filtered models and treats a missing or rejected authorization result as deny-by-default.

## 2. Module Boundaries

| Module | Owns | Receives | Produces |
| --- | --- | --- | --- |
| `AppShell` | bootstrap, routing, desktop/mobile navigation, global state presentation | verified identity, workspace membership, feature flags | authorized route context or safe failure state |
| `WorkspaceHome` | grouped work queues, recent Bases and deep-link landing | queue/read models, route context | navigation intents only |
| `BaseCanvas` | saved-view rendering, table toolbar, builder entry | Base/table/view schema and paged records | record/view/schema mutation requests |
| `RecordDetail` | full record view/edit and field-level draft context | permitted field model and record | validated record edit or draft-review intent |
| `BotHub` | team contacts, personal assistant, context selector and conversation | permitted employee model, selected resource scope | read/query intent or draft proposal display |
| `DraftConfirmation` | immutable proposal diff, confirm/reject lifecycle | draft, execution status, audit reference | one idempotent confirm/reject command |
| `Governance` | members, roles, permissions, audit and Bot administration | management authorization and paged admin models | authorized administration request |

## 3. Identity And Route Bootstrap

1. The client obtains the platform-specific Mini App or desktop identity proof.
2. The backend verifies it through the Stage06 identity adapter and returns current user plus active workspace memberships; client-provided roles are ignored.
3. `AppShell` selects a workspace only from returned memberships, then requests the navigation/read model.
4. A missing identity, expired proof, inactive membership or denied workspace produces a full-screen safe recovery state. It does not fall back to cached privileged data.
5. Deep links carry resource identifiers as routing hints only. Backend authorization resolves the authoritative workspace/base/table/view/record chain before the route displays content.

## 4. Workspace Home Flow

```text
open Home
-> request authorized queue summary
-> render Today / Drafts / @Mentions / Assigned groups
-> user selects row
-> resolve durable destination
-> BaseCanvas, RecordDetail or DraftConfirmation
```

Queue rows contain safe summary fields, stable IDs, resource type, destination and server-provided action availability. The client does not reconstruct a queue by merging unfiltered records, notifications and drafts.

## 5. Base, View And Record Flow

1. `BaseCanvas` loads Base metadata, table list and permitted saved views.
2. Selecting a view requests its schema plus a paginated, permission-filtered record window.
3. Grid retains row/column anatomy; mobile applies field priority and horizontal access, then opens `RecordDetail` for complete permitted editing.
4. A direct user record mutation returns a refreshed version and updates only the authorized local record cache.
5. A conflict, deleted record or revoked permission discards stale local data and reloads the authoritative view state.

## 6. Bot And Draft Flow

```text
open Bot contact / personal assistant
-> explicitly establish allowed context
-> server evaluates configured scope + caller scope + chat scope
-> Bot produces read response or record_change_draft
-> DraftConfirmation renders field diff
-> user confirms or rejects
-> backend writes once, returns status and audit reference
```

Team Bot context is constrained by published configuration and current caller permission. Personal assistant starts context-free. The UI must visibly distinguish both paths and never show one user's private memory to another user.

## 7. Governance Flow

`Governance` routes are absent until server navigation data includes the matching management capability. Management screens request independently paginated members, roles, permission summaries and audit events. Field-level permission editors use the same schema identifiers as `BaseCanvas`; they do not duplicate local permission semantics.

## 8. Error And Recovery Design

| State | Required UI behavior |
| --- | --- |
| loading | density-matched skeleton; no stale protected content |
| empty | explain absence and show creation/import action only when authorized |
| denied | generic access boundary, no inaccessible name/value/field leak |
| session expired | clear cached protected model and restart identity bootstrap |
| network failure | retain only already-authorized visible state, expose retry |
| draft expired/conflicted | disable action, fetch authoritative status, show audit/deep link when available |
| idempotent replay | show returned terminal result, never duplicate execution |

## 9. Observability And UX Evidence

Client telemetry may record route, safe resource type, action outcome, latency class and error code. It must not record raw record values, hidden fields, Bot prompts/responses, Telegram text, knowledge documents or memory content. Visual QA evidence must be sanitized and tied to the BDD scenario.

## 10. Implementation Boundary

The SDD defines UI responsibilities but does not authorize contract extensions listed in `STAGE_07_SOURCE_OF_TRUTH.md`. Those flows remain feature-gated until a dedicated backend decision is approved.
