# Telegram 多维表格和数字员工平台产品简报

## Status

- Document status: active product brief
- Project mode: Stage06 platform pivot, generic product first
- Source inputs:
  - [Stage 06 LarkSuite Benchmark Audit](../08-implementation/STAGE_06_LARKSUITE_BENCHMARK_AUDIT.md)
  - [Implementation Source Of Truth](../00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
  - [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md)
- Current Progress: 2026-07-09 Rewritten from an advertising-agency-specific brief into a generic Feishu-like multidimensional table, no-code workspace and table-bound digital employee platform brief. Advertising workflows are now treated as optional templates/samples.

## 1. One Sentence

本项目要开发一个 Telegram-first 的通用多维表格与无代码工作台：用户可以自建 base/table、导入表格、配置权限和视图，并基于表格随时创建可 `@` 使用的数字员工，让数字员工在权限范围内查询、总结、生成草稿、推进队列和写入审计。

## 2. Product Positioning

本项目是：

- 通用多维表格平台。
- 无代码业务工作台。
- Telegram Mini App-first 的协作入口。
- 支持桌面浏览器复杂配置的工作台。
- 表格上下文里的数字员工平台。
- 模板和导入驱动的业务系统搭建工具。
- 权限、确认、审计、可追踪记录优先的 Agent 工作系统。

本项目不是：

- Feishu/Lark API 集成项目。
- 只服务广告代理商的垂直工具。
- 纯聊天机器人。
- 纯 Excel 替代品。
- 不受权限约束的 autopilot。
- Stage06 直接生产上线项目。

## 3. Product Users

Stage06 不再把用户限定在广告代理商岗位。默认用户是任何需要把业务流程沉淀到表格和数字员工里的团队：

| User type | Need |
| --- | --- |
| Workspace owner | 创建 workspace、管理成员、权限、模板和安全开关 |
| Builder | 创建 base/table/view/form，导入 Excel/CSV，配置字段 |
| Operator | 在表格和视图中处理任务、队列、状态和记录 |
| Manager | 查看跨表状态、审计、队列和风险 |
| Telegram user | 通过 Mini App 或 `@数字员工` 处理业务 |
| Digital employee creator | 基于 table/view 创建可复用数字员工 |

## 4. Core Product Flow

```text
Telegram entry or desktop route
-> workspace
-> create/import base
-> configure table fields and views
-> install or save template
-> configure permissions
-> create digital employee from base/table/view
-> @ digital employee or use Mini App
-> agent reads permitted schema/records
-> agent answers or creates record_change_draft
-> user confirms write-like action
-> record update + audit event
```

## 5. Core Product Objects

| Object | Meaning |
| --- | --- |
| Workspace | 团队/组织边界，承载成员、权限、Telegram 绑定和多个 base |
| Base | 一个业务应用或数据应用，类似一个可搭建的多维表格应用 |
| Table | 结构化数据表 |
| Field | 字段定义、类型、校验、显示和权限 |
| Record | 一条业务数据，字段值用通用 JSONB 承载 |
| View | 表格、看板、日历、表单等操作视角 |
| Linked Record | 表间关联 |
| Lookup | 从关联记录读取展示值 |
| Import Job | CSV/Excel 导入、字段推断、预览确认 |
| Template | 可安装的 base/table/view/agent 初始方案 |
| Digital Employee | 绑定 base/table/view 和权限的 Agent 配置 |
| Record Change Draft | Agent 或用户发起的待确认写入草稿 |
| Automation Event | 队列、状态推进、通知和后续 workflow 的触发记录 |
| Audit Event | 权限、确认、写入、拒绝、通知、Agent 工具调用证据 |

## 6. Stage06 Feature Boundary

Stage06 必做：

- workspace/base/table/field/record/view 通用模型。
- JSONB-backed generic record values。
- 字段类型：text、number、date、status、single_select、multi_select、user、checkbox、url、email、phone、json、linked_record、lookup。
- 视图：grid/table、kanban、calendar、form-lite。
- CSV 和 Excel 导入，包含类型推断、预览确认和保存为模板。
- 官方模板：CRM/customer management、project/task、customer service/ticket、inventory/asset。
- 广告代理商模板：只作为弱化的官方样例。
- Telegram Mini App 主入口。
- 桌面浏览器兼容入口。
- 基于 base/table/view 创建数字员工。
- `@数字员工` 路由。
- 权限交集：`agent_configured_scope ∩ caller_user_scope ∩ telegram_chat_scope`。
- Agent 查询/总结、创建/更新草稿、队列状态推进、受控通知。
- write-like action 默认 draft-confirmation。
- 全链路 audit。
- production-like pilot 验收。

Stage06 设计预留但不完整实现：

- formula engine。
- attachment storage/preview。
- dashboard builder。
- workflow builder。
- digital clone/persona。

## 7. Templates

Stage06 官方模板优先顺序：

| Template | Purpose |
| --- | --- |
| CRM / Customer Management | 客户、联系人、跟进、状态 |
| Project / Task | 项目、任务、负责人、进度、截止日期 |
| Customer Service / Ticket | 工单、优先级、状态、回复草稿 |
| Inventory / Asset | 资产、库存、分配、异常 |
| Advertising Agency Sample | 历史业务能力样例，非默认主线 |

模板应该包含：

- tables
- fields
- views
- sample records
- recommended permissions
- optional digital employee presets
- import mapping hints

## 8. Digital Employee Experience

用户创建数字员工时，应配置：

- 名称。
- 描述。
- 可访问 base/table/view。
- 可读字段。
- 可执行动作。
- 回复风格。
- 是否需要确认。
- Telegram alias。

数字员工可做：

- 回答“这张表/这个客户/这个项目现在怎样”。
- 总结某个 view 中的记录。
- 找出异常、逾期、缺字段、重复记录。
- 创建或更新 record draft。
- 把队列项从一个状态推进到另一个状态。
- 生成受控通知草稿。

数字员工不可做：

- 绕过表格权限。
- 绕过用户权限。
- 绕过 Telegram chat scope。
- 自己确认自己的高风险写入。
- 在无 audit 的情况下声称已处理。

## 9. Stage06 Success Definition

Stage06 成功不是“写了一批平台文档”，而是能进入 production-like pilot：

```text
Telegram entry
-> Mini App
-> generic base/table
-> template or import
-> digital employee
-> permission check
-> draft confirmation
-> audit event
-> safety close
```

验收时至少应证明：

- 可从空 workspace 创建或安装一个通用 base。
- 可导入一个 CSV/Excel 并确认字段类型。
- 可在表格视图中增改查记录。
- 可创建数字员工并在 Telegram 中 `@` 使用。
- 数字员工读写受权限交集控制。
- 写入默认进入确认草稿。
- 确认后记录更新并写 audit。
- 安全开关能关闭外部发送和高风险 Agent 执行。

## 10. Historical Materials

旧广告代理商文档、Stage02-05 文档和迁移版立项文档保留为：

- historical context;
- implementation evidence;
- future official template input;
- safety boundary reference.

它们不再定义产品主线。
