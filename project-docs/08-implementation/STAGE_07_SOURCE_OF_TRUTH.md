# Stage 07 Source Of Truth

## Status

- Document status: active Stage07 planning source of truth
- Scope: Telegram Mini App and desktop browser UI for the generic workspace, Bitable and digital-employee platform
- Current Progress: 2026-07-10 Package 1 and a bounded Package 2 vertical path are implemented locally: approved bootstrap/Home/navigation, field-filtered Base/view/record reads, server-filtered scalar record creation, responsive renderers, scalar version-aware edit and authorized in-Base table switching. F1 independent Field Builder has an approved design specification but no implementation evidence yet. The current requirement-by-requirement gap is recorded in `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`; Package 3 and Package 4 remain incomplete or contract-gated.

## 1. Stage Goal

Stage07 makes the Stage06 backend-ready platform usable through one responsive React/Vite application. It must make the table system, permission system, record-change drafts and audits visible and operable without changing their authority boundaries.

```text
verified identity -> workspace member -> permission-filtered UI
-> Workspace Home -> Base/table/view/record
-> Bot proposal -> record_change_draft -> explicit confirmation -> audit
```

## 2. Confirmed Direction

- One Workspace Home serves builders, managers, operators and viewers through permission-aware visibility.
- The Home is queue-first: assigned records, drafts, `@` mentions and controlled follow-ups dominate; recent Bases are supporting context.
- `Work Queue Atlas` is the selected Home visual parent; `Workspace Ledger` is the selected Base/table canvas; `Conversation Desk` is the selected Bot and draft-review direction.
- Desktop is the primary surface for building, imports, schema/view configuration and governance. Mobile is the primary surface for processing, confirmation, record detail and Bot conversation.
- True white, cool gray, restrained azure blue, fine separators, compact UI typography and 8px radii are mandatory. Dark AI dashboards, decorative gradients, glows and card walls are forbidden.

## 3. Read Order

1. [AGENTS.md](../../AGENTS.md)
2. [Stage 07 Mini App UI Design](STAGE_07_MINI_APP_UI_DESIGN.md)
3. [Stage 07 Visual Reference Manifest](STAGE_07_VISUAL_REFERENCE_MANIFEST.md)
4. [Stage07 Mini App UI Design Specification](../../docs/superpowers/specs/2026-07-10-stage07-mini-app-ui-design.md)
5. [Stage07 F1 Field Builder Design](../../docs/superpowers/specs/2026-07-10-stage07-f1-field-builder-design.md)
6. [Stage 07 SDD](STAGE_07_SDD.md)
7. [Stage 07 API Data Security Contract](STAGE_07_API_DATA_SECURITY_CONTRACT.md)
8. [Stage 07 BDD And Acceptance](STAGE_07_BDD_AND_ACCEPTANCE.md)
9. [Stage 07 Module Index](STAGE_07_MODULE_INDEX.md)
10. [Stage 07 Test Plan](STAGE_07_TEST_PLAN.md)
11. [Stage 07 Risk Register](STAGE_07_RISK_REGISTER.md)
12. [Stage 07 Implementation Plan](STAGE_07_IMPLEMENTATION_PLAN.md)
13. [Stage 07 Acceptance Checklist](STAGE_07_ACCEPTANCE_CHECKLIST.md)
14. [Stage 07 Progress](STAGE_07_PROGRESS.md)
15. [Stage 07 Requirement Traceability Audit](STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md)
16. [Technical Decision 001: Protected Query State](STAGE_07_TECHNICAL_DECISION_001_PROTECTED_QUERY_STATE.md)

Stage06 is the backend contract baseline. Stage02-05 documents are historical capability evidence only.

## 4. Delivery Packages

| Package | Outcome | Gate |
| --- | --- | --- |
| 1. UI foundation | App shell, verified identity bootstrap, responsive tokens, global loading/error/denied states | existing Stage06 identity/permission contract works in the target environment |
| 2. Workspace and Bitable surface | queue-first Home, Bases, saved views, records, builders, import/template experiences | every interaction has an existing authorized durable resource endpoint |
| 3. Governance surface | members, roles, permissions, audit readback and configuration UI | no hidden field/resource is leaked in client data or UI state |
| 4. Digital employee surface | Bot contacts, personal assistant, field-level draft review and Telegram handoff | proposed employee/knowledge/memory contract is separately approved |

## 5. Required Scope

- Workspace switcher, member bootstrap and permission-aware navigation.
- Workspace Home queues: assigned records, draft confirmations, `@` mentions, controlled notifications and recent Bases.
- Base/table/view/record interactions for Grid, Kanban, Calendar and Form without changing saved semantics.
- Full builder configuration for Base/table/field/view, template/import and member/role/permission surfaces on desktop; lower-density but complete mobile pathways.
- Team Bot contact directory, personal assistant context picker and draft confirmation UI.
- Loading, empty, denied, expired-session, network-error and conflict states.
- Telegram deep links that resolve only after identity, workspace membership and resource authorization are checked.

## 6. Contract Gates

Approved Package 1/2 read-model boundary:

- `GET /mini-app/bootstrap` may expose only verified identity, active memberships and server-derived navigation capabilities.
- `GET /workspaces/{workspace_id}/home` may expose only authorized Base metadata and sanitized pending-draft queue summaries.
- `GET /workspaces/{workspace_id}/bases`, `GET /bases/{base_id}/tables` and `GET /bases/{base_id}/views` may expose only the safe navigation summaries defined in the API Data Security Contract. Base Canvas reuses existing authorized schema and view-record endpoints for the selected resource.
- `GET /views/{view_id}/presentation` and `GET /records/{record_id}` may expose only the normalized, field-read-filtered models defined in the API Data Security Contract. Schema, presentation, list and detail must make the same hidden-field decision.
- Both endpoints are read-only and must reuse Stage06 membership and action authorization. The client does not receive raw record values, draft before/proposed values, trace data, policies, or a role it can submit back to the server.

The following remain a separate, unapproved Package 4 contract gate:

Stage06 currently provides base-bound `DigitalEmployee` resources. The following are Stage07 proposals, not approved implementation work:

- workspace-level team Bot contacts with multiple Base/table/view scopes;
- personal assistant resource model;
- Bot draft/test/published lifecycle and Telegram group/contact bindings;
- curated knowledge-source registration and permission-filtered retrieval;
- per-user Bot memory partitions and retention/clear controls;
- production Telegram Mini App proof verification and durable deep-link resolver contract.

No schema migration, API endpoint, authorization rule or permission model for this list may be implemented without a dedicated technical decision and explicit user confirmation.

## 7. Non-Goals

- Feishu/Lark integration or API compatibility;
- direct AI writes, self-confirmation or audit bypass;
- unrestricted memory, arbitrary knowledge crawling or unfiltered document retrieval;
- production launch, broad Telegram sends, provider writes, funds movement or account operations;
- replacing the confirmed React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react baseline.

## 8. Stage Exit

Stage07 may be accepted only when its BDD, visual QA, responsive flows, permission-denial behavior and controlled-draft lifecycle pass against approved contracts. A production release remains a later, separate gate.
