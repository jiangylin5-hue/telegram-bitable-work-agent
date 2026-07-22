# Stage07 Visual Rebaseline Design

## Status

- Scope: a frontend-only visual convergence of every existing Stage07 Mini App surface.
- User instruction: confirmed on 2026-07-16; generate one original Digital Employee desktop reference, then apply the approved visual language across all frontend pages.
- Target state: the original chat-generated Digital Employee reference is retained at `project-docs/08-implementation/assets/stage07/digital-employee-workbench-reference-v1.png` and is selected as the Digital Employee visual comparison target.
- Contract boundary: no schema, API, permission, capability, Telegram routing, provider, deployment or production change.

## Visual Sources

| Product surface | Required visual source | Primary implementation targets |
| --- | --- | --- |
| Workspace Home | `project-docs/08-implementation/assets/stage07/work-queue-atlas-reference.png` | `WorkspaceHome.tsx`, `AppShell.tsx` |
| Base, table, view and builders | `project-docs/08-implementation/assets/stage07/workspace-ledger-reference.png` | `BaseCanvas.tsx`, builder panels, template/import panels |
| Team Bot, personal assistant and draft confirmation | `project-docs/08-implementation/assets/stage07/conversation-desk-reference.png` | `TeamBotWorkbench.tsx`, `AssistantContextWorkbench.tsx`, `DraftEmployeeHub.tsx` |
| Digital Employee management | `project-docs/08-implementation/assets/stage07/digital-employee-workbench-reference-v1.png` | `DigitalEmployeeManagementWorkbench.tsx`, `App.tsx`, `AppShell.tsx` |

The first three sources are retained project assets. The fourth must be an original product mock, generated without vendor marks, copied product content or external identities. It is a visual comparator only; it never enters the Mini App as a background, embedded screenshot or data source.

## Shared Visual Contract

- Use a true-white work canvas, cool-gray low-contrast surfaces and one-pixel dividers. Azure blue is reserved for selection and the primary action.
- Keep 8px-radius, low-elevation controls. Shadows belong only to temporary mobile sheets and small contextual popovers.
- Use compact Chinese product typography, durable queue/table rows and support rails that serve the active task.
- Reject gradients, glows, dark AI panels, card-wall dashboards, decorative blobs, oversized marketing headings and generic step-wizard treatment.
- Preserve existing native labels, aria semantics, keyboard focus restoration, request cancellation, safe rereads and server-authoritative content.

## Covered Page Families

1. App shell, workspace navigation, workspace switcher and Base directory.
2. Queue-first Workspace Home, including recent Bases and assistant entry dock.
3. Workspace Ledger Base Canvas, all saved-view renderers, record detail and create-record flow.
4. Builder, field, relation/lookup, view, template and import work surfaces.
5. Governance read/write surfaces and view-access management.
6. Conversation Desk variants: Team Bot, personal assistant context and Draft Employee Hub.
7. Digital Employee directory, editable work scope, lifecycle, member assignment, status and audit projection.
8. Telegram deep-link recovery, authorization failure, loading, empty and error states.

## Digital Employee Workbench Direction

The generated desktop reference must depict an original four-column workbench: narrow global navigation, employee directory, central employee profile/work-scope canvas and a confirmation/audit rail. The central work surface presents status, safe scope, allowed fixed intents, current queue and authorization rows as structured information, rather than a chat transcript or a wizard. The mobile translation may collapse rails into ordered sections or sheets, but may not hide lifecycle state, member eligibility, expected-version recovery, confirmation requirements or audit context.

## Responsive and Safety Requirements

- Compare desktop at 1440px and 1280px. Compare mobile at 430px and 390px; no horizontal page scroll, hidden primary control, clipped text or inaccessible close/return focus.
- Retain the existing table horizontal-scroll behavior when a grid cannot fit mobile width.
- Keep every existing visible action wired to its current event handler and capability gate. A visual rewrite may not manufacture data, bypass server errors or change a confirmation action into an automatic write.
- Preserve the existing safe failure behavior: authentication/authorization errors clear protected state, stale mutations require reread, and external actions retain their current explicit controls.

## Visual Acceptance

For each desktop family, capture the same viewport and comparable state beside its source reference. Record P0/P1/P2 gaps in `mini-app/design-qa.md`; do not report visual completion until the comparison passes, current frontend tests pass, the production build passes and browser console inspection reports no relevant error.
