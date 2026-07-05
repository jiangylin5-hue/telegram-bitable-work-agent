# Multidimensional Table Module

## Status

- Document status: module draft
- Scope: 多维表格业务底座、表/字段/视图/记录抽象
- Current Progress: 2026-07-04 完成多维表格模块第一版设计，并新增 `BITABLE_SCHEMA_BLUEPRINT.md` 作为表、字段、视图、权限、自动化和 Agent 落点总蓝图。

## 1. Module Purpose

本模块负责把广告代理商业务对象组织成类似飞书多维表格的结构化数据和多视图工作台。

第一阶段不做通用无代码平台，而是围绕本项目固定业务对象构建“业务多维表格”。

本模块是所有业务 workflow 的终点。Telegram、Agent、队列、执行工具产生的业务结果，都必须回写为本模块管理的记录、状态、视图、自动化或审计事件。

详细表格蓝图见 [Bitable Schema Blueprint](BITABLE_SCHEMA_BLUEPRINT.md)。本模块说明抽象和边界，蓝图文档定义具体业务表、字段、视图、权限、自动化和 Agent 起点/落点。

## 2. Core Objects

| Object | Meaning |
| --- | --- |
| Base | 一个业务空间，例如 account operations workspace |
| Table | 业务表，例如 customers、account_assets、service_drafts |
| Field | 字段定义，例如 status、amount、owner、linked_account |
| Record | 具体业务记录 |
| View | 面向角色的视图，例如充值视图、服务看板、风险仪表盘 |
| Automation | 状态变化触发提醒、日报、升级 |

第一阶段可以用固定 schema 实现这些概念，不需要让用户自由建表。

## 3. Required Views

- Telegram 收件箱。
- AI 草稿队列。
- 客户总表。
- 账户库存表。
- 账户资产表。
- 充值视图。
- 卡资源视图。
- 服务看板。
- 客户日报视图。
- 公司日报视图。
- 风险仪表盘。
- 审计视图。

## 3.1 Workflow Endpoints

| Workflow | Required table/view endpoint |
| --- | --- |
| Telegram 消息接入 | `messages` table + Telegram 收件箱 |
| 服务草稿 | `service_drafts` table + AI 草稿队列 |
| 服务记录 | `service_records` table + 服务看板 |
| 账户生产 | `account_inventory` table + 账户库存表 |
| 账户分配 | `account_assignments` table + 账户库存表/客户总表 |
| 账户状态事件 | `account_status_events` table + 账户时间线 |
| 收款核对 | `collection_records` table + 财务收款视图 |
| 充值 | `recharge_records` table + 充值视图 |
| 绑卡 | `account_card_bindings` table + 绑卡视图/账户资产表 |
| 风险事件 | `risk_events` table + 风险仪表盘 |
| 客户日报 | `customer_daily_reports` table + 客户日报视图 |
| 公司日报 | `company_daily_reports` table + 公司日报视图 |
| 执行授权 | `execution_tickets` table + 执行票据视图 |
| 执行结果 | `execution_logs` table + 审计视图 |
| 权限/确认 | `ops_audit_events` table + 审计视图 |

## 4. Field Types

建议支持：

- text。
- number。
- money。
- currency。
- single_select。
- multi_select。
- user。
- datetime。
- relation。
- attachment_ref。
- formula_readonly。
- status。
- sensitive_text。

敏感字段必须结合 field permission。

## 5. View Permission

视图不是简单前端筛选，后端必须按权限输出：

- record permission。
- field permission。
- action permission。
- agent permission。

例如销售可以看自己的客户和服务进度，但不一定能看完整卡资源、执行失败敏感原因或全局财务金额。

## 6. Data Source

多维表格视图从 PostgreSQL 业务表生成。第一阶段不建议单独做一套通用 EAV 数据模型，因为业务表需要强约束、事务和清晰关系。

策略：

- 核心事实使用 normalized tables。
- 视图配置使用 `table_views` / `view_filters` / `view_columns`。
- 字段权限使用 policy 表。
- 聚合指标可以使用 materialized view 或缓存，后续确认。

## 7. LLM Usage

允许：

- 根据当前视图解释数据。
- 总结筛选结果。
- 生成字段补全建议。
- 生成客户回复草稿。

禁止：

- 绕过 service layer / Tool Gateway 直接修改表记录。
- 绕过字段权限读取敏感字段。
- 编造不存在的记录。

## 8. Acceptance Criteria

- 业务对象清晰映射为表和视图。
- 后端输出视图时执行权限过滤。
- 敏感字段不会出现在无权限响应中。
- Agent 读取视图数据也受相同权限约束。
