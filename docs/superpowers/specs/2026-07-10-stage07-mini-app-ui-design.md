# Stage07 Mini App UI Design

## Status

- Status: approved design, implementation not started
- Date: 2026-07-10
- Scope: Telegram Mini App and desktop-browser UI for the generic workspace, multidimensional-table and digital-employee platform
- Visual baseline: the reviewed `Work Queue Atlas` concept is the Workspace Home parent direction; the reviewed `Workspace Ledger` concept is the Base/table direction; the reviewed `Conversation Desk` concept is the Bot/draft-confirmation direction
- Non-goal: this specification does not authorize schema, API-contract or permission-model implementation changes

## Product Intent

The Mini App is the main collaboration surface for a Telegram-first workspace platform. It serves two equally important audiences:

- builders and workspace managers, who need dense desktop workflows for Base creation, schema/view configuration, import and governance;
- members and operators, who need fast mobile workflows for work queues, records, Bot conversations and controlled confirmations.

The product follows Feishu Base product grammar and adopts Telegram interaction grammar for Bot contacts, conversations and group-mention handoffs. It is an independent platform: no Feishu/Lark API integration or compatibility is implied.

## Confirmed Decisions

| Area | Decision |
| --- | --- |
| Home information architecture | One permission-aware Workspace Home, not separate builder/member applications |
| Home priority | Balanced recent Bases and actionable work queue; queue takes the dominant visual position |
| Primary visual direction | `Work Queue Atlas`: action queue first, recent Bases second, personal assistant available but not dominant |
| Base direction | `Workspace Ledger`: dense, table-first desktop canvas after a Base is opened |
| Bot direction | `Conversation Desk`: contextual conversation plus visible data scope and explicit draft confirmation |
| Desktop/mobile | Same authority and feature set; desktop favors construction/governance, mobile favors processing/confirmation/conversation |
| Desktop navigation | Persistent sidebar with permission-gated management area |
| Mobile navigation | Bottom navigation: Home, Bases, Bots, More |
| View support | Preserve saved Grid, Kanban, Calendar and Form semantics; adapt presentation and editing pattern for mobile |
| Visual language | True white canvas, cool-gray hierarchy, one restrained azure-blue accent, fine separators, 8px radii, compact purposeful typography |
| Rejected visual language | Dark dashboard, AI-purple glow, glassmorphism, gradient decoration, card-wall/bento layout, generic assistant landing-page treatment |
| AI writes | Every Bot-originated write is a record-change draft requiring explicit user confirmation |

## Information Architecture

```text
Workspace Home
+-- Today / My Work
|   +-- assigned records
|   +-- record-change drafts awaiting confirmation
|   +-- group @Bot mentions
|   `-- notifications and controlled follow-ups
+-- Recent Bases
|   `-- Base -> table -> saved view -> record detail
+-- Digital Employees
|   +-- team Bot contacts
|   `-- personal assistant
`-- Management (only when authorized)
    +-- members, roles and permissions
    +-- Base, table, field and view configuration
    +-- templates and imports
    `-- team Bot configuration and publication
```

The Home never turns chat into the system of record. Each queue row, Bot mention or assistant response resolves to a persisted Base, view, record, draft or audit event.

## Core Screens And Flows

### Workspace Home

The Home is a queue-first command surface.

- The central column groups `Today`, `Awaiting confirmation`, `@Mentions`, and `Assigned to me` as dense, actionable rows.
- Every row exposes the durable destination: Base, saved view and, when applicable, record or draft.
- Recent Bases appear in a narrow supporting rail with authentic small view previews, not marketing cards.
- The personal assistant is a collapsible right-side dock on desktop and a dedicated mobile tab. It never permanently consumes the primary work canvas.
- Only authorized management items are rendered. Hiding inaccessible data is preferred over disabled controls that reveal protected resource names.

### Base And Table Canvas

- Opening a Base enters the table-first `Workspace Ledger` mode.
- Desktop preserves the full table toolbar, view switcher, field/schema controls, filtering, sorting, grouping and record detail drawer.
- Grid remains a grid. Mobile may prioritize selected columns, horizontal scrolling and a full-screen record detail/editor; it must not transform a table into unrelated decorative cards.
- Kanban, Calendar and Form honor their saved semantics. Mobile changes gestures and density, not the meaning of a view.

### Team Bots And Personal Assistant

Team Bots are Workspace contacts. Members may open a private conversation, follow a Telegram group `@` deep link into relevant context, and see only allowed scopes. Administrators configure, test, publish and govern these contacts.

Personal assistant is private by default. It has no workspace/Base/table/record context until the user explicitly selects it. The UI presents selected context as a clear, removable scope chip and must not imply that the assistant searched unselected work data.

### Draft Confirmation

Every Bot write proposal is rendered as a diff, not a vague instruction:

```text
Bot proposal
-> affected Base / table / record
-> field-level before and proposed-after values
-> explicit Confirm or Reject
-> confirmed backend execution
-> audit link and final status
```

The user sees `submitting`, `confirmed`, `rejected`, `expired`, and `conflicted` states. A client-side success state is never treated as a committed record write.

## Digital Employee Product Model

The approved experience requires two digital-employee classes.

| Class | User experience | Data isolation |
| --- | --- | --- |
| Team-shared Bot contact | Admin-created, workspace-published contact with persona, skills, curated knowledge and explicit Base/table/view scope; available in Telegram groups through `@` | Shared configuration, but user memory and personal conversation state are isolated by user |
| Personal assistant | Private everyday assistant for writing, research and work follow-up; work context is opt-in | Private to the owning user |

Team Bot publication flow:

```text
Draft configuration
-> private test
-> publish as workspace contact
-> bind permitted group and data scope
-> enable @ entry
```

Knowledge sources for the first release are explicitly selected Bases/views and controlled document materials. Retrieval must dynamically filter by the invoking user's effective permissions. Arbitrary workspace crawling is out of scope.

## Responsive Rules

| Concern | Desktop browser | Telegram Mini App/mobile |
| --- | --- | --- |
| Navigation | persistent left sidebar | bottom navigation plus More sheet |
| Workspace Home | central queue with recent-Base rail and collapsible assistant dock | single-column queue, recent Bases and Bot entries as dense lists |
| Tables | full toolbar, schema inspector, wide grid | field priority, horizontal grid access, full-screen record editor |
| Draft review | side-by-side diff and context rail | sequential diff sections with sticky confirm/reject controls |
| Builder/governance | primary surface | supported but lower density through sheets and full-screen editors |

No layout may use fixed desktop-width surfaces, hover-only actions or a `100vh` assumption that conflicts with mobile browser chrome.

## Component Boundaries

| Component | Responsibility |
| --- | --- |
| `AppShell` | responsive navigation, workspace switcher, permission-aware route chrome |
| `WorkspaceHome` | queue groups, recent Bases, deep links and collapsed assistant entry |
| `BaseCanvas` | Base/table/view canvas and desktop/mobile presentation variants |
| `RecordDetail` | record read/edit surface, field visibility and draft context |
| `BotHub` | team Bot contacts, personal assistant, explicit scope selection and Telegram handoff |
| `DraftConfirmation` | immutable diff presentation, confirm/reject lifecycle and audit handoff |
| `Management` | members, roles, configuration, import/template and Bot governance |
| shared state primitives | loading, empty, error, denied and expired states; no duplicated ad-hoc status UI |

Components receive permission-filtered view models. They do not infer access from a frontend role string or access raw records directly.

## State, Errors And Safety

Required first-class states:

- loading skeletons matching the final density;
- meaningful empty states that lead to creation/import only when permitted;
- permission denied without leaking inaccessible record names or field values;
- expired Mini App session or deep-link context with safe re-entry;
- network failure with retry and no false success result;
- draft conflict or expiration with a refreshed authoritative state;
- group Bot mention that has insufficient caller, chat or Bot scope.

The frontend must fail closed: lack of a usable permission result, execution ticket or confirmation outcome cannot enable a write control.

## Backend Contract Boundary

Existing Stage06 backend readiness supports generic workspaces/Bases/tables/views, authorization, audits, record-change drafts and base-bound digital employees. The following work is a proposed Stage07 contract extension, not yet implementation authority:

1. workspace-level digital employees with explicit multiple Base/table/view scopes;
2. employee kind (`team_shared` or `personal`), draft/test/published lifecycle and Telegram contact/group binding;
3. curated knowledge-source registration and permission-filtered retrieval metadata;
4. user-partitioned Bot memory, including clear/delete controls and auditable partition boundary;
5. Mini App verified identity adapter and deep-link context contract;
6. UI-oriented paginated queue, notification and draft read models where existing endpoints are insufficient.

Any schema, API or permission change for these capabilities requires a separate technical decision and explicit user confirmation before implementation.

## Stage07 Delivery Packages

1. **UI Foundation** - React/Vite shell, tokens, responsive navigation, identity/bootstrap boundary and shared state primitives.
2. **Bitable Work Surface** - Workspace Home, Base/table/view/record experiences, builder and import/template controls.
3. **Governance Surface** - members, roles, permissions, audit readback and administrative configuration.
4. **Digital Employee Surface And Contract Gate** - Bot contacts, personal assistant, draft confirmation and the separately approved backend extension.

The packages are a coherent Stage07 delivery but may be accepted independently. Package 4 cannot silently retrofit the Stage06 base-bound employee model.

## Acceptance Criteria

- Workspace Home is queue-first and routes every action to a durable table, record, draft or audit destination.
- Desktop and mobile both support core member operation; desktop additionally supports high-density building/governance.
- Grid/Kanban/Calendar/Form preserve their saved semantics across breakpoints.
- Unauthorized fields/resources are neither rendered nor leaked in empty/denied states.
- Bot writes always show field-level drafts and require explicit confirmation before backend execution.
- Team Bot and personal assistant contexts are visibly distinct; personal assistant work context is opt-in.
- A team Bot contact cannot present or retrieve another member's memory.
- Telegram group `@` handoff lands on the correct authorized workspace/Base/view/record context.
- Draft confirmation, rejection, conflict and expiration remain auditable and do not create false-success UI.
- Visual QA covers the selected light design system at desktop and mobile viewports; no dark/gradient/glow/card-wall fallback is introduced.

## Risks And Non-Goals

### Risks

- The selected Bot product model exceeds the current `base_id`-bound employee backend and needs an approved contract evolution.
- Telegram Mini App identity verification and desktop identity must converge on the Stage06 request-identity adapter without trusting client role claims.
- High-density builder features are hard to make effective on narrow screens; mobile must prioritize operation over desktop-parity layout.
- Knowledge ingestion, retrieval quality and retention policy are not yet a completed product subsystem.

### Non-Goals

- Feishu/Lark API integration or compatibility;
- unrestricted Bot memory, arbitrary workspace crawling or raw document access;
- direct Bot record writes, self-confirmation or confirmation-bypass flows;
- production rollout, broad Telegram sends, provider writes, funds movement or account operations;
- changing the confirmed frontend technical baseline.

## Review Gate

This design is approved by the user as a product and visual specification. The detailed Stage07 plan is drafted as part of the requested documentation package, but remains review-only. Do not start frontend or backend implementation before the user reviews this package and separately confirms any required schema/API/permission change.
