# Stage 07 Source Of Truth

## Status

- Document status: active Stage07 planning source of truth
- Scope: Telegram Mini App and desktop browser UI for the generic workspace, Bitable and digital-employee platform
- Current Progress: 2026-07-12 Package 1 and bounded Package 2 paths through F2 are `implemented-local`. V1-1 through V1-15 are `partial-local`: real FastAPI + disposable PostgreSQL Browser evidence proves owner/editor/viewer Canvas separation, allowed Base/Table/Field intersection, hidden-field omission, numeric lookup projection and one owner Record Detail relation edit through the existing versioned PATCH with authoritative reread. The complete existing-contract template/import package is `implemented-local`: its typed transport, shelf/install, draft-template save, server preview, scalar mapping and explicit commit have component/API, local PostgreSQL, production-build and focused Browser evidence. S3 Governance Readback is `implemented-local` with Browser external-environment evidence pending. S4 Governance Write is a bounded local vertical slice: GW-A01--GW-A05/GW-A08 are evidenced; GW-A06/GW-A07 retain their explicit negative-lifecycle gap. TD005 Option A and TD006 Option A are approved; S5 Draft and Digital Employee Hub is `partial-local` within its six safe-route, two-column, conditional-index boundary. Safe contact/draft review, terminal transition, allowlisted citations and the transient current-Canvas invocation UI are implemented; it neither reads generic context nor persists context. The protected Base queue now returns only pending drafts with newest-first keyset pagination; a disposable local PostgreSQL measurement (`512` pending / `1,536` terminal) reused the existing Base/status index in `0.913 ms`, so no optional S5 partial-index migration is justified. Browser loopback access was refused, so S5 visual/four-width evidence is explicitly unaccepted. TD007 Option A is approved for S6.1: its complete identity/deep-link document package specifies official Telegram `initData` verification, binding-backed identity and opaque expiring resource pointers; implementation-plan review is still required and no S6 code, migration, Telegram configuration or external operation exists. Real stale/type-invalid states, numeric-filter mutation, Telegram, staging and production remain unaccepted. Package 4 beyond TD005/TD006/TD007 remains contract-gated.

- Template/Import Package Update: the approved existing-contract package is `implemented-local`. Typed template/import transport, shelf/install, draft-template save, server preview, scalar mapping and explicit commit have fresh component/API, build, real disposable PostgreSQL and focused Browser evidence. Browser CSV/XLSX upload is explicitly unaccepted because the available automation API cannot choose a file. No schema/API/permission/dependency expansion was made; Telegram, staging and production remain unaccepted. See [local evidence](evidence/stage07-template-import-ui.md).
- Governance Package Update: S3 has delivered the approved read-only projections locally. S4 implemented TD004's narrowly versioned member-role and field-policy commands plus existing V1 view-grant reuse; its remaining negative-lifecycle acceptance gaps are recorded in `evidence/stage07-governance-write.md`.
- Substage Delivery Update: Stage07 now uses the S0--S6 coherent-substage roadmap. S5 has approved TD005 and TD006 decision/design/BDD/SDD/module/index/plan packages plus local implementation evidence. TD007 Option A now has its decision/design/BDD/SDD/module/index documents and awaits one implementation-plan review; S6.2 external Bot delivery/manual smoke remains independently user-authority-gated. See [Substage Delivery Roadmap](STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md).

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
6. [Stage07 F1 Field Builder Plan](STAGE_07_SUBSTAGE_F1_FIELD_BUILDER_PLAN.md)
7. [Stage07 F2 Relation/Lookup Design](../../docs/superpowers/specs/2026-07-11-stage07-f2-relation-lookup-design.md)
8. [Stage07 F2 Relation/Lookup Implementation Plan](../../docs/superpowers/plans/2026-07-11-stage07-f2-relation-lookup-implementation.md)
9. [Stage07 F2 Relation/Lookup BDD And Acceptance](STAGE_07_F2_RELATION_LOOKUP_BDD_AND_ACCEPTANCE.md)
10. [Stage07 F2 Relation/Lookup SDD](STAGE_07_F2_RELATION_LOOKUP_SDD.md)
11. [Stage07 F2 Relation/Lookup Work Surface](modules/STAGE_07_F2_RELATION_LOOKUP_WORK_SURFACE.md)
12. [Stage07 F2 Relation/Lookup Complex Feature Index](STAGE_07_F2_RELATION_LOOKUP_COMPLEX_FEATURE_INDEX.md)
13. [Stage07 V1 Saved View Builder Design](../../docs/superpowers/specs/2026-07-11-stage07-v1-saved-view-builder-design.md)
14. [Stage07 V1 BDD And Acceptance](STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md)
15. [Stage07 V1 SDD](STAGE_07_V1_VIEW_BUILDER_SDD.md)
16. [Stage07 V1 Work Surface](modules/STAGE_07_V1_VIEW_BUILDER_WORK_SURFACE.md)
17. [Stage07 V1 Complex Feature Index](STAGE_07_V1_VIEW_BUILDER_COMPLEX_FEATURE_INDEX.md)
18. [Stage07 V1 Saved View Builder Implementation Plan](../../docs/superpowers/plans/2026-07-11-stage07-v1-saved-view-builder-implementation.md)
19. [Stage07 Template And Import Design](../../docs/superpowers/specs/2026-07-12-stage07-template-import-design.md)
20. [Stage07 Template And Import BDD And Acceptance](STAGE_07_TEMPLATE_IMPORT_BDD_AND_ACCEPTANCE.md)
21. [Stage07 Template And Import SDD](STAGE_07_TEMPLATE_IMPORT_SDD.md)
22. [Stage07 Template And Import Work Surface](modules/STAGE_07_TEMPLATE_IMPORT_WORK_SURFACE.md)
23. [Stage07 Template And Import Complex Feature Index](STAGE_07_TEMPLATE_IMPORT_COMPLEX_FEATURE_INDEX.md)
24. [Stage07 Template And Import Implementation Plan](../../docs/superpowers/plans/2026-07-12-stage07-template-import-implementation.md)
25. [Stage07 Template And Import Local Evidence](evidence/stage07-template-import-ui.md)
26. [Stage07 Governance Safe Read Model Decision](STAGE_07_TECHNICAL_DECISION_003_GOVERNANCE_SAFE_READ_MODEL.md)
27. [Stage07 Governance Readback Design](../../docs/superpowers/specs/2026-07-12-stage07-governance-readback-design.md)
28. [Stage07 Governance Readback BDD And Acceptance](STAGE_07_GOVERNANCE_READBACK_BDD_AND_ACCEPTANCE.md)
29. [Stage07 Governance Readback SDD](STAGE_07_GOVERNANCE_READBACK_SDD.md)
30. [Stage07 Governance Readback Work Surface](modules/STAGE_07_GOVERNANCE_READBACK_WORK_SURFACE.md)
31. [Stage07 Governance Readback Complex Feature Index](STAGE_07_GOVERNANCE_READBACK_COMPLEX_FEATURE_INDEX.md)
32. [Stage07 Governance Readback Implementation Plan](../../docs/superpowers/plans/2026-07-12-stage07-governance-readback-implementation.md)
33. [Stage07 Governance Write Decision](STAGE_07_TECHNICAL_DECISION_004_GOVERNANCE_WRITE_CONTRACT.md)
34. [Stage07 Governance Write Design](../../docs/superpowers/specs/2026-07-12-stage07-governance-write-design.md)
35. [Stage07 Governance Write BDD And Acceptance](STAGE_07_GOVERNANCE_WRITE_BDD_AND_ACCEPTANCE.md)
36. [Stage07 Governance Write SDD](STAGE_07_GOVERNANCE_WRITE_SDD.md)
37. [Stage07 Governance Write Work Surface](modules/STAGE_07_GOVERNANCE_WRITE_WORK_SURFACE.md)
38. [Stage07 Governance Write Complex Feature Index](STAGE_07_GOVERNANCE_WRITE_COMPLEX_FEATURE_INDEX.md)
39. [Stage 07 SDD](STAGE_07_SDD.md)
40. [Stage 07 API Data Security Contract](STAGE_07_API_DATA_SECURITY_CONTRACT.md)
41. [Stage 07 BDD And Acceptance](STAGE_07_BDD_AND_ACCEPTANCE.md)
42. [Stage 07 Module Index](STAGE_07_MODULE_INDEX.md)
43. [Stage 07 Test Plan](STAGE_07_TEST_PLAN.md)
44. [Stage 07 Risk Register](STAGE_07_RISK_REGISTER.md)
45. [Stage 07 Implementation Plan](STAGE_07_IMPLEMENTATION_PLAN.md)
46. [Stage 07 Acceptance Checklist](STAGE_07_ACCEPTANCE_CHECKLIST.md)
47. [Stage07 Substage Delivery Roadmap](STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md)
48. [Stage 07 Progress](STAGE_07_PROGRESS.md)
49. [Stage 07 Requirement Traceability Audit](STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md)
50. [Technical Decision 001: Protected Query State](STAGE_07_TECHNICAL_DECISION_001_PROTECTED_QUERY_STATE.md)
51. [Stage07 Draft and Digital Employee Hub Decision](STAGE_07_TECHNICAL_DECISION_005_DRAFT_EMPLOYEE_HUB.md)
52. [Stage07 Draft and Digital Employee Hub Design](../../docs/superpowers/specs/2026-07-12-stage07-s5-draft-employee-hub-design.md)
53. [Stage07 Draft and Digital Employee Hub BDD And Acceptance](STAGE_07_DRAFT_EMPLOYEE_HUB_BDD_AND_ACCEPTANCE.md)
54. [Stage07 Draft and Digital Employee Hub SDD](STAGE_07_DRAFT_EMPLOYEE_HUB_SDD.md)
55. [Stage07 Draft and Digital Employee Hub Work Surface](modules/STAGE_07_DRAFT_EMPLOYEE_HUB_WORK_SURFACE.md)
56. [Stage07 Draft and Digital Employee Hub Complex Feature Index](STAGE_07_DRAFT_EMPLOYEE_HUB_COMPLEX_FEATURE_INDEX.md)
57. [Stage07 Draft and Digital Employee Hub Plan](../../docs/superpowers/plans/2026-07-12-stage07-s5-draft-employee-hub-implementation.md)
58. [Stage07 S5 Context Binding Decision](STAGE_07_TECHNICAL_DECISION_006_S5_CONTEXT_BINDING.md)
59. [Stage07 S5 Context Binding BDD And Acceptance](STAGE_07_S5_CONTEXT_BINDING_BDD_AND_ACCEPTANCE.md)
60. [Stage07 S5 Context Binding SDD](STAGE_07_S5_CONTEXT_BINDING_SDD.md)
61. [Stage07 S5 Context Binding Work Surface](modules/STAGE_07_S5_CONTEXT_BINDING_WORK_SURFACE.md)
62. [Stage07 S5 Draft and Digital Employee Hub Local Evidence](evidence/stage07-s5-draft-employee-hub.md)
63. [Stage07 S6 Telegram Mini App Identity and Deep-Link Decision](STAGE_07_TECHNICAL_DECISION_007_TELEGRAM_MINI_APP_IDENTITY_AND_DEEP_LINK.md)
64. [Stage07 S6 Telegram Mini App Identity and Deep-Link Design](../../docs/superpowers/specs/2026-07-12-stage07-s6-telegram-identity-deep-link-design.md)
65. [Stage07 S6 Telegram Mini App Identity and Deep-Link BDD and Acceptance](STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_BDD_AND_ACCEPTANCE.md)
66. [Stage07 S6 Telegram Mini App Identity and Deep-Link SDD](STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_SDD.md)
67. [Stage07 S6 Telegram Mini App Identity and Deep-Link Work Surface](modules/STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_WORK_SURFACE.md)
68. [Stage07 S6 Telegram Mini App Identity and Deep-Link Complex Feature Index](STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_COMPLEX_FEATURE_INDEX.md)
69. [Stage07 S6 Telegram Mini App Identity and Deep-Link Implementation Plan](../../docs/superpowers/plans/2026-07-12-stage07-s6-telegram-identity-deep-link-implementation.md)

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

The following remain a separate Package 4 contract gate. TD005 Option A is the implemented bounded contact/context/draft-review exception over existing Stage06 resources. TD007 Option A is the approved S6.1 identity/deep-link design exception, but it may not enter code until its implementation plan is reviewed. Neither decision expands into employee lifecycle, memory, knowledge, group delivery or external action.

Stage06 currently provides base-bound `DigitalEmployee` resources. The following are Stage07 proposals, not approved implementation work:

- workspace-level team Bot contacts with multiple Base/table/view scopes;
- personal assistant resource model;
- Bot draft/test/published lifecycle and Telegram group/contact bindings;
- curated knowledge-source registration and permission-filtered retrieval;
- per-user Bot memory partitions and retention/clear controls;
- production Telegram Mini App proof verification.

No schema migration, API endpoint, authorization rule or permission model for this remaining list may be implemented without a dedicated technical decision and explicit user confirmation. TD007's reviewed S6.1 implementation plan is the sole identity/deep-link exception; it does not authorize production proof.

## 7. Non-Goals

- Feishu/Lark integration or API compatibility;
- direct AI writes, self-confirmation or audit bypass;
- unrestricted memory, arbitrary knowledge crawling or unfiltered document retrieval;
- production launch, broad Telegram sends, provider writes, funds movement or account operations;
- replacing the confirmed React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react baseline.

## 8. Stage Exit

Stage07 may be accepted only when its BDD, visual QA, responsive flows, permission-denial behavior and controlled-draft lifecycle pass against approved contracts. A production release remains a later, separate gate.
