# Stage 07 Visual Reference Manifest

## Status

- Document status: active visual acceptance reference
- Scope: Stage07 desktop visual language and its responsive translation; it does not define API, authorization, data content or behaviour.
- Current Progress: 2026-07-10 the user-provided source images are retained under `assets/stage07/` and are the durable visual baseline for later design QA. No claim is made that every current screen already matches them pixel for pixel.

## 1. Purpose And Boundary

The three retained images make the approved `Work Queue Atlas`, `Conversation Desk` and `Workspace Ledger` directions concrete. They are product-grammar references only. The project must not copy their product names, user identities, record values, business data, brand marks, source code or external API contracts.

All functional authority remains project-native:

```text
verified identity -> authorized workspace/Base/table/view -> server-filtered UI
```

Visual resemblance never authorizes a client-side queue, a hidden field, a Bot action, a confirmation or a record mutation.

## 2. Retained Reference Assets

| Asset | Visual role | Later QA target |
| --- | --- | --- |
| [work-queue-atlas-reference.png](assets/stage07/work-queue-atlas-reference.png) | `Work Queue Atlas`: queue-first Home, compact task rows, recent Base rail and personal-assistant dock. | Workspace Home at desktop widths. |
| [conversation-desk-reference.png](assets/stage07/conversation-desk-reference.png) | `Conversation Desk`: team/personal assistant list, contextual conversation, selected-record summary and explicit confirmation rail. | Future Package 4 Bot/draft screens only after their separate contract gate. |
| [workspace-ledger-reference.png](assets/stage07/workspace-ledger-reference.png) | `Workspace Ledger`: dense table canvas, tabbed work modes, table toolbar, row grid and narrow assistant rail. | Base/table/field/view Builder desktop surface. |

The source images are intentionally not used as in-product background images or mock data. They are comparison targets for the rendered interface.

## 3. Non-Negotiable Visual Grammar

### 3.1 Shared desktop shell

- A calm true-white workspace with cool-gray surfaces and fine one-pixel dividers, rather than dark panels, gradients, glows or decorative card walls.
- A narrow persistent navigation rail, a dense central work surface and optional supporting rails. Supporting rails must aid the current task; they cannot crowd out the active table or queue.
- Restrained azure blue indicates selection and the primary action. Status colors communicate state only and do not replace text labels.
- Compact Chinese product typography, small but readable toolbar controls, low-elevation surfaces and approximately 8px corner treatment. Shadows are reserved for floating layers such as drawers, sheets and the mobile action dock.

### 3.2 Work Queue Atlas

- The central column is a work queue, grouped by durable state such as today, pending confirmation, mentions and assignments. Rows retain table-like alignment and direct resource destinations.
- Recent Bases form a slim visual preview rail, not a competing dashboard card wall.
- The personal-assistant dock is context-aware and informational until its backend contract exists; it must not imply unauthorised search or a live Bot conversation.

### 3.3 Workspace Ledger

- The table is the primary desktop object: its title, saved-view selector and schema/view toolbar form one compact band above a high-density grid.
- Grid columns, row numbers, selection affordances, pagination and status chips preserve table semantics. Mobile may change density and use a full-screen detail/editor, but must not silently turn a saved grid into unrelated cards.
- Builder actions belong near the table/view controls and appear only from server capability hints. A fieldless table keeps the honest empty state until F1 supplies a real action.

### 3.4 Conversation Desk

- The assistant surface is a calm three-pane desktop workflow: assistant/contact navigation, conversation/context and a review rail.
- A draft-confirmation rail must show the authorised current context, selected durable records, field-level impacts and unmistakable confirm/reject actions. The visual source does not permit the client to fabricate draft values or confirmation availability.

## 4. Responsive Translation

The retained references are desktop sources. Existing Stage07 responsive rules remain authoritative: desktop favours building/governance, while mobile favours processing, confirmation, detail and conversation. A narrow viewport retains the same server-authorised resource and saved-view semantics; it may collapse rails into sheets or tabs, preserve horizontal table access and use a full-screen editor.

## 5. Visual Acceptance Method

For each covered surface, compare a fresh rendered screenshot with its corresponding asset at the same viewport and a comparable state. Check shell proportions, hierarchy, type density, border/radius treatment, selection blue, toolbar placement, right-rail purpose and mobile collapse behaviour. Record visible mismatches; do not claim image-level fidelity from unit tests or mock data alone.

Required later evidence remains `1440px`, `1280px`, `430px` and `390px`, plus zero relevant browser console errors. These source images establish the desktop design target; they do not replace real Telegram Mini App verification or any permission/security acceptance.
