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
| [Digital Employee Hub](modules/STAGE_07_DIGITAL_EMPLOYEE_HUB.md) | team contacts, personal assistant, Telegram handoff and drafts | AppShell, Bitable surface, draft service and proposed contract gate |
| [Governance And Permission UI](modules/STAGE_07_GOVERNANCE_AND_PERMISSION_UI.md) | members, roles, field permissions, audit and Bot administration | AppShell, Bitable schema and server authorization |

No module may bypass `AppShell` route context, server permission results, shared error states or the controlled draft lifecycle.

F2 detailed behavior/design/navigation lives in [F2 BDD](STAGE_07_F2_RELATION_LOOKUP_BDD_AND_ACCEPTANCE.md), [F2 SDD](STAGE_07_F2_RELATION_LOOKUP_SDD.md) and [F2 Complex Feature Index](STAGE_07_F2_RELATION_LOOKUP_COMPLEX_FEATURE_INDEX.md). Current state and package-level evidence are tracked in [Stage 07 Requirement Traceability Audit](STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md); it is the required companion for implementation and acceptance claims.
