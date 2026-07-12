# Stage 07 Module Index

## Status

- Document status: active module index
- Scope: Stage07 ownership and interaction map

| Module document | Primary responsibility | Interacts with |
| --- | --- | --- |
| [App Shell And Workspace](modules/STAGE_07_APP_SHELL_AND_WORKSPACE.md) | identity bootstrap, workspace context, navigation and Home queues | all feature modules and Stage06 authorization |
| [Bitable Work Surface](modules/STAGE_07_BITABLE_WORK_SURFACE.md) | Base/table/view/record and builder interactions | AppShell, permissions, import/template and draft context |
| [F1 Field Builder Design](../../docs/superpowers/specs/2026-07-10-stage07-f1-field-builder-design.md) | safe independent field creation and immediate record/view follow-through | Bitable Work Surface, Stage06 authorization/audit/idempotency and protected query state |
| [F2 Relation/Lookup Work Surface](modules/STAGE_07_F2_RELATION_LOOKUP_WORK_SURFACE.md) | same-Base relation, bounded lookup, picker, safe renderer and state boundaries | Bitable Work Surface, F2 BDD/SDD/index, Stage06 authorization/audit/idempotency and protected query state |
| [V1 Saved View Builder Work Surface](modules/STAGE_07_V1_VIEW_BUILDER_WORK_SURFACE.md) | saved Grid/Kanban/Calendar/Form configuration, private/restricted member view access and safe server-backed query semantics | Bitable Work Surface, V1 BDD/SDD/index, F2 safe fields/candidates, Stage06 authorization/audit/idempotency and protected query state |
| [Template And Import Work Surface](modules/STAGE_07_TEMPLATE_IMPORT_WORK_SURFACE.md) | safe template shelf/install/save and CSV/XLSX preview/mapping/commit from existing Stage06 contracts | AppShell, Bitable Work Surface, Template/Import BDD/SDD/index, Stage06 authorization/audit/idempotency and protected query state |
| [Digital Employee Hub](modules/STAGE_07_DIGITAL_EMPLOYEE_HUB.md) | team contacts, personal assistant, Telegram handoff and drafts | AppShell, Bitable surface, draft service and proposed contract gate |
| [Governance And Permission UI](modules/STAGE_07_GOVERNANCE_AND_PERMISSION_UI.md) | members, roles, field permissions, audit and Bot administration | AppShell, Bitable schema and server authorization |
| [Governance Readback Work Surface](modules/STAGE_07_GOVERNANCE_READBACK_WORK_SURFACE.md) | bounded first Governance package: safe paged members and Base audit timeline | Technical Decision 003, AppShell, protected query state and Stage06 authorization/pagination |

No module may bypass `AppShell` route context, server permission results, shared error states or the controlled draft lifecycle.

F2 detailed behavior/design/navigation lives in [F2 BDD](STAGE_07_F2_RELATION_LOOKUP_BDD_AND_ACCEPTANCE.md), [F2 SDD](STAGE_07_F2_RELATION_LOOKUP_SDD.md) and [F2 Complex Feature Index](STAGE_07_F2_RELATION_LOOKUP_COMPLEX_FEATURE_INDEX.md). Current state and package-level evidence are tracked in [Stage 07 Requirement Traceability Audit](STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md); it is the required companion for implementation and acceptance claims.

V1 is design-only until user review. Its complete proposed contract lives in [V1 Design](../../docs/superpowers/specs/2026-07-11-stage07-v1-saved-view-builder-design.md), [V1 BDD](STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md), [V1 SDD](STAGE_07_V1_VIEW_BUILDER_SDD.md) and [V1 Complex Feature Index](STAGE_07_V1_VIEW_BUILDER_COMPLEX_FEATURE_INDEX.md).

The selected template/import package is `implemented-local`. Its implementation boundary remains [Template/Import Design](../../docs/superpowers/specs/2026-07-12-stage07-template-import-design.md), [BDD](STAGE_07_TEMPLATE_IMPORT_BDD_AND_ACCEPTANCE.md), [SDD](STAGE_07_TEMPLATE_IMPORT_SDD.md) and [Complex Feature Index](STAGE_07_TEMPLATE_IMPORT_COMPLEX_FEATURE_INDEX.md). It uses existing contracts only: no backend contract expansion, while Browser file-upload evidence remains explicitly unaccepted. See [local evidence](evidence/stage07-template-import-ui.md).

The next proposed coherent package is [Governance Readback](modules/STAGE_07_GOVERNANCE_READBACK_WORK_SURFACE.md). It is deliberately read-only and contract-gated by [Technical Decision 003](STAGE_07_TECHNICAL_DECISION_003_GOVERNANCE_SAFE_READ_MODEL.md): existing generic audit responses cannot be used in a browser because their fields exceed the Stage07 safe UI boundary. No implementation starts before user approval.
