# Stage 02 Module Index

## Status

- Document status: active module index
- Scope: Stage 02 复杂模块索引、模块边界、对应文档、实现文件和验收入口
- Current Progress: 2026-07-04 建立 Stage 02 模块索引，复杂模块以后可在本索引下拆独立模块文档。

## 1. Module Reading Rule

开发前先看本索引，确认要改的模块属于哪个边界。

如果一个模块开始超过本索引描述的边界，必须先补模块文档，再开发。

## 2. Module Index

| Module | Complexity | SDD Section | Primary files | Tests | Stage |
| --- | --- | --- | --- | --- | --- |
| App Core | low | `STAGE_02_SDD.md#31-app-core-module` | `backend/app/main.py`, `core/*` | health test | 02.0 |
| Database And Migration | high | `STAGE_02_SDD.md#32-database-and-migration-module` | `models/*`, `alembic/*` | metadata + migration smoke | 02.0 |
| Bitable View | high | `STAGE_02_SDD.md#33-bitable-view-module` | `services/bitable_views.py`, `routes/views.py` | view unit/integration | 02.0 |
| Permission And Audit | high | `STAGE_02_SDD.md#34-permission-and-audit-module` | `services/permissions.py`, `services/audit.py` | permission/audit tests | 02.0 |
| Outbox | high | `STAGE_02_SDD.md#35-outbox-module` | `services/outbox.py`, `workers/outbox_dispatcher.py` | outbox tests | 02.0 |
| Mock Telegram Ingestion | medium | `STAGE_02_SDD.md#36-mock-telegram-ingestion-module` | `services/telegram_ingestion.py`, `routes/mock_telegram.py` | mock telegram tests | 02.1 |
| Mock Agent | medium | `STAGE_02_SDD.md#37-mock-agent-module` | `agents/mock_router.py`, `agents/mock_reporting.py` | agent tests | 02.1 / 02.3 |
| Service Draft And Confirmation | high | `STAGE_02_SDD.md#38-service-draft-and-confirmation-module` | `services/service_drafts.py`, `services/confirmation.py` | state machine tests | 02.1 |
| Recharge | high | `STAGE_02_SDD.md#39-recharge-module` | `services/recharge.py`, `adapters/providers_mock.py` | recharge vertical tests | 02.1 |
| Account Inventory | high | `STAGE_02_SDD.md#310-account-inventory-module` | `services/account_inventory.py` | inventory tests | 02.2 |
| Reporting | high | `STAGE_02_SDD.md#311-reporting-module` | `services/reporting.py`, `agents/mock_reporting.py` | report tests | 02.3 |

## 3. Complex Module Split Rule

以下模块如果开发中单文件超过 250 行或职责开始混杂，必须拆独立模块文档：

- Bitable View。
- Permission And Audit。
- Outbox。
- Service Draft And Confirmation。
- Recharge。
- Account Inventory。
- Reporting。

独立模块文档命名：

```text
project-docs/08-implementation/modules/<MODULE_NAME>.md
```

模块文档必须包含：

- Scope。
- Inputs。
- Outputs。
- State machine。
- Permissions。
- Tools / dependencies。
- What it does not do。
- Tests。
- Acceptance Criteria。

## 4. No-Crossing Rules

- Route 不写业务规则。
- Repository 不判断业务权限。
- Service 不绕过 audit。
- Worker 不直接改核心表。
- Agent 不直接写数据库。
- Adapter 不决定业务状态。
- View API 不写业务状态。

