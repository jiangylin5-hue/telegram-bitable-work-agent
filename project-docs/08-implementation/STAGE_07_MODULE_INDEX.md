# Stage 07 Module Index

## Status

- Document status: active module index
- Scope: Stage07 ownership and interaction map

| Module document | Primary responsibility | Interacts with |
| --- | --- | --- |
| [App Shell And Workspace](modules/STAGE_07_APP_SHELL_AND_WORKSPACE.md) | identity bootstrap, workspace context, navigation and Home queues | all feature modules and Stage06 authorization |
| [Bitable Work Surface](modules/STAGE_07_BITABLE_WORK_SURFACE.md) | Base/table/view/record and builder interactions | AppShell, permissions, import/template and draft context |
| [Digital Employee Hub](modules/STAGE_07_DIGITAL_EMPLOYEE_HUB.md) | team contacts, personal assistant, Telegram handoff and drafts | AppShell, Bitable surface, draft service and proposed contract gate |
| [Governance And Permission UI](modules/STAGE_07_GOVERNANCE_AND_PERMISSION_UI.md) | members, roles, field permissions, audit and Bot administration | AppShell, Bitable schema and server authorization |

No module may bypass `AppShell` route context, server permission results, shared error states or the controlled draft lifecycle.

Current state and package-level evidence are tracked in [Stage 07 Requirement Traceability Audit](STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md); it is the required companion for implementation and acceptance claims.
