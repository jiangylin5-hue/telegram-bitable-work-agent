# Bitable Schema Blueprint

## Status

- Document status: active blueprint draft
- Scope: 覆盖全部已确认业务场景的多维表格总蓝图，包括 table、field、linked record、view、permission、automation、Agent 起点和 workflow 落点
- Current Progress: 2026-07-04 新增多维表格总蓝图，明确多维表格是业务核心、所有工作流设计核心、Agent 出发点和落脚点。

## 1. Purpose

本文档是 Telegram 多维表格和工作智能体项目的业务数据蓝图。

它解决一个核心问题：所有业务、工作流、Agent、权限、自动化和后端执行，都必须能落到一套可见、可查、可审计的多维表格结构中。

本项目的设计顺序必须是：

```text
业务对象
-> 多维表格 table
-> 字段和字段类型
-> linked records
-> role-based views
-> permissions
-> automations
-> Agent start context
-> Agent tools and execution
-> updated table record/view/audit
```

Agent 不是从空白聊天框出发，也不是从自己的记忆出发。Agent 的出发点必须是多维表格中的记录、视图、筛选结果、关联上下文和授权检索结果。Agent 的落脚点必须是多维表格中的记录、状态、视图、自动化、执行日志、日报或审计事件。

## 2. Non-Negotiable Rules

- 不存在没有多维表格终点的业务流程。
- 不存在只停留在 Telegram 回复里的业务结果。
- 不存在只停留在 Agent memory、未落表 JSON、prompt 输出或口头结论里的业务事实。
- 不存在绕过多维表格权限的 Agent 查询。
- 不存在绕过多维表格状态和审计的真实外部执行。
- PostgreSQL 是事实存储层，多维表格是业务操作层，Agent 是在操作层上工作的数字员工。
- 视图不是前端筛选；视图必须承载权限、角色任务、状态队列、自动化触发和 Agent 工作上下文。

## 3. Business Domain To Table Map

| Business domain | Main tables | Primary views | Primary agents | Workflow endpoint |
| --- | --- | --- | --- | --- |
| Telegram 消息入口 | `messages`、`customer_groups`、`telegram_identities` | Telegram 收件箱、未识别消息视图、客户群视图 | Message Intake Router Agent | message record + route status + service draft |
| 客户管理 | `customers`、`customer_groups` | 客户总表、销售客户视图、风险客户视图 | Message Intake Router Agent、Customer Reporting Agent | customer record + owner/scope/status update |
| 账户库存/生产账户 | `account_inventory`、`account_status_events` | 账户库存视图、未启用账户视图、库存异常视图 | Account Inventory Agent | inventory record + status event |
| 账户分配 | `account_assignments`、`account_inventory`、`account_assets` | 分配待确认视图、客户账户视图、账户资产表 | Account Inventory Agent、Operations Supervisor Agent | assignment record + inventory status update |
| 账户资产运营 | `account_assets`、`account_daily_metrics`、`account_status_events` | 账户资产表、低余额视图、异常账户视图 | Account Inventory Agent、Customer Reporting Agent | account asset record + daily metric + status event |
| 服务草稿 | `service_drafts`、`messages` | AI 草稿队列、待补资料视图、待确认视图 | Message Intake Router Agent、Operations Supervisor Agent | service draft record + status |
| BM invite / 分户 | `service_records`、`account_assignments`、`execution_logs` | 服务看板、BM invite 视图、审计视图 | Account Inventory Agent、Recharge And Binding Agent | service record + execution log + account status event |
| 卡资源/卡台 | `payment_profiles` | 卡资源视图、可用卡视图、卡异常视图 | Card Resource Agent | payment profile record + resource status |
| 绑卡 | `account_card_bindings`、`payment_profiles`、`account_assets`、`execution_logs` | 绑卡视图、账户资产表、敏感审计视图 | Card Resource Agent、Recharge And Binding Agent | card binding record + execution log |
| 收款核对 | `collection_records`、`recharge_records` | 财务收款视图、待财务确认视图 | Finance Reconciliation Agent | collection record + finance confirmation status |
| 充值 | `recharge_records`、`execution_tickets`、`execution_logs` | 充值视图、待生产确认视图、readback 异常视图 | Finance Reconciliation Agent、Recharge And Binding Agent | recharge record + execution log + readback status |
| 客户每日消耗 | `account_daily_metrics`、`customer_daily_reports` | 客户日报视图、客户消耗明细视图 | Customer Reporting Agent | customer report record + delivery status |
| 公司日报 | `company_daily_reports`、`customer_daily_reports`、`risk_events` | 公司日报视图、管理驾驶舱视图 | Customer Reporting Agent、Operations Supervisor Agent | company report record + review/send status |
| 风险事件 | `risk_events`、`account_daily_metrics` | 风险仪表盘、低余额视图、stale data 视图 | Customer Reporting Agent、Operations Supervisor Agent | risk event record + escalation status |
| 人工确认/执行票据 | `execution_tickets`、`ops_audit_events` | 待确认视图、执行票据视图、审计视图 | Operations Supervisor Agent | execution ticket + audit event |
| 执行证据/审计 | `execution_logs`、`ops_audit_events` | 审计视图、失败执行视图、provider 回读视图 | Operations Supervisor Agent | execution log + audit timeline |
| Agent 运行记录 | `agent_runs`、`vector_documents` | Agent 运行视图、检索文档视图 | All agents | agent run record + redacted tool trace |

## 4. Table Blueprint

### 4.1 `customers`

Purpose: 客户主数据，是客户、账户、服务、日报、风险和 Telegram 群的中心关联点。

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | uuid | 客户唯一 ID |
| `name` | text | 客户展示名 |
| `normalized_name` | text | 去重和搜索用标准名 |
| `owner_user_id` | user relation | 负责销售或负责人 |
| `status` | status | `active`、`paused`、`blocked`、`archived` |
| `risk_level` | single_select | `low`、`medium`、`high`、`unknown` |
| `telegram_primary_group_id` | relation | 主客户群 |
| `report_delivery_policy` | jsonb / single_select | 日报是否自动发送、是否需复核 |
| `notes` | sensitive_text | 客户备注 |
| `created_at` / `updated_at` | datetime | 创建和更新时间 |

Linked records:

- `customer_groups`
- `account_inventory`
- `account_assignments`
- `account_assets`
- `service_drafts`
- `service_records`
- `recharge_records`
- `risk_events`
- `customer_daily_reports`

Views:

- 客户总表。
- 销售客户视图：只看自己负责客户。
- 风险客户视图：按 `risk_level`、低余额、blocked 任务筛选。
- 日报客户视图：按 `report_delivery_policy` 和日报状态筛选。

Agent boundary:

- Message Intake Router Agent 可以读取客户名称、群绑定和 owner 信息做路由。
- Customer Reporting Agent 可以读取客户、账户和日报策略生成报告。
- Agent 不得在无权限时读取 `notes`。

### 4.2 `customer_groups`

Purpose: Telegram 群和客户之间的绑定表，是 Telegram 入口进入业务表格的第一道关系。

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | uuid | 群绑定记录 |
| `customer_id` | relation | 关联客户 |
| `telegram_chat_id` | text | Telegram chat id |
| `group_title` | text | 群名称 |
| `group_type` | single_select | `customer_group`、`internal_ops`、`finance`、`unknown` |
| `status` | status | `active`、`disabled`、`unknown` |
| `last_message_at` | datetime | 最近消息时间 |

Views:

- 客户群视图。
- 未绑定群视图。
- 群消息活跃视图。

Automation:

- 新群或未知群消息进入未绑定群视图。
- 群禁用后，相关消息不触发服务草稿，只保留消息记录。

### 4.3 `telegram_identities`

Purpose: Telegram 用户和系统用户/客户联系人之间的映射。

| Field | Type | Meaning |
| --- | --- | --- |
| `telegram_user_id` | text | Telegram 用户 ID |
| `username` | text | Telegram username |
| `user_id` | user relation | 内部系统用户 |
| `customer_id` | relation nullable | 客户联系人所属客户 |
| `contact_type` | single_select | `internal_user`、`customer_contact`、`unknown` |
| `status` | status | `active`、`disabled`、`unknown` |

Views:

- 内部用户身份视图。
- 客户联系人视图。
- 未识别身份视图。

Permission rule:

- Telegram 身份只能作为身份线索，不能直接等同于系统权限。

### 4.4 `messages`

Purpose: Telegram 原始消息和业务识别结果的事实表。

| Field | Type | Meaning |
| --- | --- | --- |
| `telegram_update_id` | text | Telegram update 去重 |
| `telegram_chat_id` | text | 来源 chat |
| `telegram_message_id` | text | 来源 message |
| `sender_identity_id` | relation | 发送者身份 |
| `customer_group_id` | relation | 关联客户群 |
| `customer_id` | relation nullable | 解析出的客户 |
| `raw_text` | sensitive_text | 原始文本 |
| `normalized_text` | text | 规范化文本 |
| `message_type` | single_select | text / attachment / command / system |
| `intent_status` | status | `unclassified`、`routed`、`ignored`、`needs_review`、`failed` |
| `intent_type` | single_select | recharge / bm_invite / card_binding / account_request / report_query / risk_query / unknown |
| `received_at` | datetime | 收到时间 |
| `trace_id` | text | 链路追踪 |

Views:

- Telegram 收件箱。
- 未识别消息视图。
- 待人工确认消息视图。
- 已生成草稿消息视图。

Agent start:

- Message Intake Router Agent 从 Telegram 收件箱开始。
- 只读取已授权群、已授权字段和最近上下文。

Workflow endpoint:

- 消息不会直接触发真实操作。
- 消息必须先落为 `messages` record，再由 Agent 生成 `service_drafts` 或进入 `ignored` / `needs_review`。

### 4.5 `service_drafts`

Purpose: AI 或人工生成的待确认服务草稿，是从消息到真实业务服务之间的缓冲层。

| Field | Type | Meaning |
| --- | --- | --- |
| `draft_type` | single_select | recharge / bm_invite / card_binding / account_assignment / risk_followup / customer_reply / daily_report |
| `status` | status | `draft`、`needs_more_info`、`pending_confirmation`、`rejected`、`confirmed`、`manual_review`、`blocked` |
| `customer_id` | relation | 客户 |
| `account_asset_id` | relation nullable | 账户资产 |
| `account_inventory_id` | relation nullable | 库存账户 |
| `source_message_id` | relation nullable | 来源消息 |
| `created_by_type` | single_select | user / agent |
| `created_by_id` | text | 创建者 |
| `payload` | jsonb | 结构化草稿内容 |
| `missing_fields` | jsonb | 缺失字段 |
| `risk_flags` | jsonb | 风险标记 |
| `confidence` | number | AI 置信度 |
| `idempotency_key` | text | 幂等键 |
| `trace_id` | text | 链路追踪 |

Views:

- AI 草稿队列。
- 待补资料视图。
- 待财务确认视图。
- 待生产确认视图。
- blocked 草稿视图。

Automation:

- `needs_more_info` 触发补资料提醒。
- `pending_confirmation` 进入对应角色待办。
- `confirmed` 创建 `service_records` 或具体业务记录。

### 4.6 `service_records`

Purpose: 已确认服务记录，承载 BM invite、绑卡、充值、风险跟进等服务生命周期。

| Field | Type | Meaning |
| --- | --- | --- |
| `service_type` | single_select | recharge / bm_invite / card_binding / account_assignment / risk_followup |
| `status` | status | `pending`、`executing`、`succeeded`、`failed`、`blocked`、`manual_review` |
| `customer_id` | relation | 客户 |
| `account_asset_id` | relation nullable | 账户资产 |
| `source_draft_id` | relation nullable | 来源草稿 |
| `confirmed_by_user_id` | user relation | 确认人 |
| `confirmed_at` | datetime | 确认时间 |
| `idempotency_key` | text | 幂等键 |
| `trace_id` | text | 链路追踪 |

Views:

- 服务看板。
- 我的待办服务。
- 执行中服务。
- 失败服务。
- BM invite 服务视图。
- 绑卡服务视图。
- 充值服务视图。

Endpoint rule:

- 任何对客户承诺“已处理/已成功”的服务，都必须能追溯到 `service_records`、`execution_logs` 或明确的 blocked/failed 状态。

### 4.7 `account_inventory`

Purpose: 账户库存台账，管理每天生产出来的账户、未启用账户、分配给谁、当前状态。

| Field | Type | Meaning |
| --- | --- | --- |
| `platform` | single_select | meta |
| `external_account_id` | sensitive_text | 外部账户 ID |
| `inventory_status` | status | `produced`、`unused`、`reserved`、`allocated`、`activated`、`disabled`、`blocked`、`recycled`、`archived` |
| `production_batch_id` | text | 生产批次 |
| `produced_by_user_id` | user relation | 生产人员 |
| `assigned_customer_id` | relation nullable | 分配客户 |
| `assigned_user_id` | user relation nullable | 分配操作人 |
| `assigned_at` | datetime nullable | 分配时间 |
| `status_reason` | sensitive_text | 状态原因 |

Views:

- 账户库存视图。
- 未启用账户视图。
- 已预留账户视图。
- 已分配账户视图。
- blocked / disabled 账户视图。
- 每日生产账户视图。

Agent start:

- Account Inventory Agent 从账户库存视图和未启用账户视图开始。

Agent landing:

- 创建库存记录。
- 推荐候选账户。
- 创建 `account_assignments`。
- 写入 `account_status_events`。

### 4.8 `account_assignments`

Purpose: 账户分配历史，记录账户给了谁、谁确认、是否释放。

| Field | Type | Meaning |
| --- | --- | --- |
| `account_inventory_id` | relation | 库存账户 |
| `customer_id` | relation | 客户 |
| `assigned_by_user_id` | user relation | 发起分配人 |
| `confirmed_by_user_id` | user relation nullable | 确认人 |
| `assignment_status` | status | `proposed`、`confirmed`、`cancelled`、`released` |
| `assigned_at` | datetime | 分配时间 |
| `released_at` | datetime nullable | 释放时间 |
| `trace_id` | text | 链路追踪 |

Views:

- 分配待确认视图。
- 客户账户视图。
- 历史分配视图。

Automation:

- `confirmed` 更新 `account_inventory.inventory_status = allocated`。
- `released` 更新库存为 `unused` 或 `recycled`，具体取决于状态事件。

### 4.9 `account_status_events`

Purpose: 账户状态事件表，记录账户从生产、分配、启用、绑卡、充值、异常、回收的状态轨迹。

| Field | Type | Meaning |
| --- | --- | --- |
| `account_inventory_id` | relation nullable | 库存账户 |
| `account_asset_id` | relation nullable | 账户资产 |
| `customer_id` | relation nullable | 客户 |
| `event_type` | single_select | produced / reserved / assigned / activated / bound_card / recharged / blocked / disabled / recycled / note |
| `before_status` | text nullable | 变更前状态 |
| `after_status` | text nullable | 变更后状态 |
| `reason` | sensitive_text | 状态原因 |
| `source_entity_type` | text | 来源实体类型 |
| `source_entity_id` | uuid nullable | 来源实体 |
| `actor_type` | single_select | user / agent / system / worker |
| `actor_id` | text | 操作者 |
| `created_at` | datetime | 创建时间 |

Views:

- 账户时间线。
- blocked 状态原因视图。
- 客户账户历史视图。

### 4.10 `account_assets`

Purpose: 已激活或已运营广告账户资产，承载余额、消耗、风险和绑定关系。

| Field | Type | Meaning |
| --- | --- | --- |
| `customer_id` | relation | 客户 |
| `account_inventory_id` | relation nullable | 来源库存账户 |
| `external_account_id` | sensitive_text | 外部账户 ID |
| `account_name` | text | 账户名 |
| `platform` | single_select | meta |
| `status` | status | `active`、`disabled`、`blocked`、`unknown` |
| `balance_amount` | money nullable | 当前余额 |
| `balance_currency` | currency nullable | 余额币种 |
| `spend_today` | money nullable | 今日消耗 |
| `spend_yesterday` | money nullable | 昨日消耗 |
| `spend_7d` | money nullable | 7 日消耗 |
| `last_read_at` | datetime nullable | 数据读取时间 |
| `risk_status` | status | `normal`、`low_balance`、`blocked`、`stale_data`、`unknown` |

Views:

- 账户资产表。
- 客户账户视图。
- 低余额视图。
- stale data 视图。
- blocked 账户视图。

Agent boundary:

- Customer Reporting Agent 可以读取账户指标生成日报。
- Recharge And Binding Agent 可以读取账户余额、绑定状态和 readback 状态。
- 无金额权限的用户和 Agent 不得读取完整金额字段。

### 4.11 `account_daily_metrics`

Purpose: 每日账户余额和消耗快照，是客户日报、公司日报和风险判断的事实来源。

| Field | Type | Meaning |
| --- | --- | --- |
| `account_asset_id` | relation | 账户资产 |
| `customer_id` | relation | 客户 |
| `metric_date` | date | 指标日期 |
| `balance_amount` | money nullable | 余额 |
| `balance_currency` | currency nullable | 余额币种 |
| `spend_amount` | money nullable | 当日消耗 |
| `spend_currency` | currency nullable | 消耗币种 |
| `freshness_at` | datetime | 数据新鲜度 |
| `source` | single_select | provider / manual / imported |
| `read_status` | status | `fresh`、`stale_data`、`missing_permission`、`readback_failed` |

Views:

- 客户消耗明细视图。
- 公司消耗汇总视图。
- stale data 视图。
- missing permission 视图。

Rule:

- 任何日报里的金额必须能追溯到 `account_daily_metrics`。
- stale data 不能被当作 0 消耗。

### 4.12 `payment_profiles`

Purpose: 卡台和支付资源表，只保存 tokenized / masked 支付资源，不保存 raw card。

| Field | Type | Meaning |
| --- | --- | --- |
| `provider` | text | 卡台或支付资源 provider |
| `tokenized_profile_id` | sensitive_text | tokenized profile |
| `masked_label` | text | 脱敏展示名 |
| `last4` | text nullable | 后四位 |
| `brand` | text nullable | 卡组织 |
| `status` | status | `active`、`inactive`、`blocked`、`reserved` |
| `customer_id` | relation nullable | 限定客户 |
| `limit_summary` | sensitive_text nullable | 额度摘要 |
| `last_checked_at` | datetime nullable | 最近检查时间 |

Views:

- 卡资源视图。
- 可用卡视图。
- 卡异常视图。
- 敏感审计视图。

Forbidden fields:

- raw card number。
- CVV。
- 完整卡图。
- 可直接用于盗刷的凭证。

### 4.13 `account_card_bindings`

Purpose: 账户与 tokenized payment profile 的绑定历史，承载一卡一户策略和绑卡执行状态。

| Field | Type | Meaning |
| --- | --- | --- |
| `account_asset_id` | relation | 账户资产 |
| `payment_profile_id` | relation | tokenized 支付资源 |
| `customer_id` | relation | 客户 |
| `binding_status` | status | `planned`、`pending_confirmation`、`executing`、`bound`、`failed`、`unbound`、`blocked` |
| `one_card_one_account_policy` | single_select | strict / relaxed_by_manager |
| `service_record_id` | relation nullable | 关联服务 |
| `execution_log_id` | relation nullable | 执行证据 |
| `bound_at` | datetime nullable | 绑定时间 |
| `unbound_at` | datetime nullable | 解绑时间 |
| `failure_reason` | sensitive_text nullable | 失败原因 |

Views:

- 绑卡视图。
- 账户绑定状态视图。
- 一卡一户冲突视图。
- 绑卡失败视图。

Automation:

- `planned` 进入生产确认。
- `bound` 更新账户状态事件。
- `failed` 触发失败升级和客户回复草稿。

### 4.14 `collection_records`

Purpose: 收款证据和财务确认表，避免把客户付款截图、线下打款和广告账户充值执行混为一谈。

| Field | Type | Meaning |
| --- | --- | --- |
| `customer_id` | relation | 客户 |
| `recharge_record_id` | relation nullable | 关联充值 |
| `amount` | money | 收款金额 |
| `currency` | currency | 币种 |
| `collection_method` | single_select | bank / crypto / card / other |
| `evidence_attachment_ref` | attachment_ref nullable | 收款证据引用 |
| `collection_status` | status | `missing`、`pending`、`confirmed`、`rejected`、`manual_review` |
| `confirmed_by_user_id` | user relation nullable | 财务确认人 |
| `confirmed_at` | datetime nullable | 确认时间 |
| `finance_note` | sensitive_text nullable | 财务备注 |

Views:

- 财务收款视图。
- 待财务确认视图。
- 金额异常视图。

Rule:

- `collection_status = confirmed` 只代表收款确认，不代表广告账户充值成功。

### 4.15 `recharge_records`

Purpose: 充值业务记录，分离收款、充值执行、余额回读。

| Field | Type | Meaning |
| --- | --- | --- |
| `service_record_id` | relation | 服务记录 |
| `customer_id` | relation | 客户 |
| `account_asset_id` | relation | 账户资产 |
| `collection_record_id` | relation nullable | 收款记录 |
| `amount` | money | 充值金额 |
| `currency` | currency | 币种 |
| `collection_status` | status | `missing`、`pending`、`confirmed`、`rejected` |
| `execution_status` | status | `not_started`、`queued`、`executing`、`succeeded`、`failed`、`blocked` |
| `readback_status` | status | `not_started`、`pending`、`succeeded`、`failed`、`not_supported` |
| `readback_at` | datetime nullable | 回读时间 |
| `execution_ticket_id` | relation nullable | 执行票据 |

Views:

- 充值视图。
- 待财务确认视图。
- 待生产确认视图。
- 执行中充值视图。
- readback failed 视图。

Automation:

- 财务确认后进入生产确认。
- 生产确认后创建 `execution_ticket`。
- 执行完成写 `execution_logs`。
- readback 后更新余额和日报相关数据。

### 4.16 `risk_events`

Purpose: 风险事件表，记录低余额、空耗、数据过期、权限缺失、封户、异常消耗等。

| Field | Type | Meaning |
| --- | --- | --- |
| `customer_id` | relation nullable | 客户 |
| `account_asset_id` | relation nullable | 账户 |
| `risk_type` | single_select | low_balance / zero_spend / stale_data / missing_permission / blocked_account / abnormal_spend / readback_failed |
| `severity` | single_select | low / medium / high |
| `source_metric_id` | relation nullable | 来源指标 |
| `source_metric` | jsonb | 脱敏来源摘要 |
| `freshness_at` | datetime nullable | 数据新鲜度 |
| `status` | status | `open`、`acknowledged`、`resolved`、`ignored` |
| `owner_user_id` | user relation nullable | 处理人 |

Views:

- 风险仪表盘。
- 低余额视图。
- stale data 视图。
- readback failed 视图。

Agent boundary:

- Customer Reporting Agent 可以基于风险事件生成客户可读解释。
- Agent 不得编造投放原因或承诺账户恢复。

### 4.17 `customer_daily_reports`

Purpose: 每个客户每天的账户消耗、余额、充值、绑卡、异常和待补资料日报。

| Field | Type | Meaning |
| --- | --- | --- |
| `customer_id` | relation | 客户 |
| `report_date` | date | 报告日期 |
| `report_payload` | jsonb | 结构化日报 |
| `visibility_scope` | jsonb | 可见字段和收件人范围 |
| `delivery_status` | status | `draft`、`review_required`、`queued`、`sent`、`failed` |
| `reviewed_by_user_id` | user relation nullable | 复核人 |
| `sent_at` | datetime nullable | 发送时间 |
| `trace_id` | text | 链路追踪 |

Views:

- 客户日报视图。
- 待复核日报视图。
- 发送失败日报视图。

Rule:

- 客户日报只能包含该客户有权看到的数据。
- 每个数值必须来自 `account_daily_metrics`、`recharge_records`、`account_card_bindings` 或 `risk_events`。

### 4.18 `company_daily_reports`

Purpose: 公司级日报，汇总所有客户消耗、充值、库存、绑卡、风险和待办。

| Field | Type | Meaning |
| --- | --- | --- |
| `report_date` | date | 报告日期 |
| `report_payload` | jsonb | 结构化全局日报 |
| `delivery_status` | status | `draft`、`review_required`、`queued`、`sent`、`failed` |
| `sent_at` | datetime nullable | 发送时间 |
| `trace_id` | text | 链路追踪 |

Views:

- 公司日报视图。
- 管理驾驶舱视图。
- 公司异常汇总视图。

Permission:

- 仅 Manager/Admin 或授权管理角色可查看。

### 4.19 `execution_tickets`

Purpose: 人工确认后授权 Agent 或 worker 执行真实外部动作的一次性票据。

| Field | Type | Meaning |
| --- | --- | --- |
| `approved_by_user_id` | user relation | 批准人 |
| `approved_at` | datetime | 批准时间 |
| `expires_at` | datetime | 过期时间 |
| `allowed_action` | single_select | recharge / bind_card / bm_invite / card_platform_action |
| `allowed_customer_id` | relation nullable | 限定客户 |
| `allowed_account_id` | relation nullable | 限定账户 |
| `amount_limit` | money nullable | 金额上限 |
| `payment_profile_id` | relation nullable | 限定卡资源 |
| `risk_snapshot` | jsonb | 风险快照 |
| `permission_snapshot` | jsonb | 权限快照 |
| `idempotency_key` | text | 幂等键 |
| `status` | status | `issued`、`used`、`expired`、`revoked` |
| `used_at` | datetime nullable | 使用时间 |
| `trace_id` | text | 链路追踪 |

Views:

- 执行票据视图。
- 待执行视图。
- 过期/撤销票据视图。

Rule:

- 高风险真实外部写入必须有有效 `execution_ticket`。

### 4.20 `execution_logs`

Purpose: 真实外部执行证据，任何成功声明都必须能关联到执行日志。

| Field | Type | Meaning |
| --- | --- | --- |
| `service_record_id` | relation | 服务记录 |
| `execution_ticket_id` | relation nullable | 执行票据 |
| `provider` | text | 外部系统 |
| `provider_request_id` | text nullable | 外部请求 ID |
| `provider_response_id` | text nullable | 外部响应 ID |
| `execution_status` | status | `succeeded`、`failed`、`pending`、`blocked` |
| `request_summary` | jsonb | 脱敏请求摘要 |
| `response_summary` | jsonb | 脱敏响应摘要 |
| `error_code` | text nullable | 错误码 |
| `error_message_redacted` | sensitive_text nullable | 脱敏错误 |
| `executed_at` | datetime | 执行时间 |
| `trace_id` | text | 链路追踪 |

Views:

- 审计视图。
- 执行失败视图。
- provider 回读视图。

### 4.21 `ops_audit_events`

Purpose: 权限、状态变更、确认、拒绝、失败、拦截和 Agent 工具调用的审计时间线。

| Field | Type | Meaning |
| --- | --- | --- |
| `trace_id` | text | 链路追踪 |
| `actor_type` | single_select | user / agent / system / worker |
| `actor_id` | text | 操作者 |
| `event_type` | text | 事件类型 |
| `entity_type` | text | 实体类型 |
| `entity_id` | uuid nullable | 实体 ID |
| `before_state` | jsonb nullable | 脱敏前状态 |
| `after_state` | jsonb nullable | 脱敏后状态 |
| `permission_snapshot` | jsonb nullable | 权限快照 |
| `created_at` | datetime | 事件时间 |

Views:

- 审计视图。
- 权限拒绝视图。
- Agent 工具调用审计视图。

### 4.22 `agent_runs`

Purpose: Agent 运行记录，保存脱敏输入、输出、工具调用和模型信息。

| Field | Type | Meaning |
| --- | --- | --- |
| `agent_name` | text | Agent 名称 |
| `graph_name` | text | LangGraph graph |
| `model_provider` | text | openrouter |
| `model_name` | text | 模型名 |
| `prompt_version` | text | prompt 版本 |
| `input_summary` | jsonb | 脱敏输入摘要 |
| `output_summary` | jsonb | 脱敏输出摘要 |
| `tool_calls` | jsonb | 工具调用摘要 |
| `status` | status | `succeeded`、`failed`、`needs_review` |
| `trace_id` | text | 链路追踪 |
| `started_at` / `completed_at` | datetime | 起止时间 |

Views:

- Agent 运行视图。
- Agent 失败视图。
- 高风险工具调用视图。

### 4.23 `vector_documents`

Purpose: SOP、历史案例、provider 错误说明、回复模板和客户上下文的检索辅助资料。

| Field | Type | Meaning |
| --- | --- | --- |
| `doc_type` | single_select | sop / historical_case / provider_error / reply_template / customer_note |
| `title` | text | 标题 |
| `content_redacted` | text | 脱敏内容 |
| `embedding` | vector | pgvector embedding |
| `source_entity_type` | text nullable | 来源实体 |
| `source_entity_id` | uuid nullable | 来源实体 ID |
| `visibility_scope` | jsonb | 可见范围 |

Rule:

- 向量检索只能提供上下文，不是业务事实来源。
- Agent 输出业务结论必须引用业务表记录，而不是只引用向量文档。

### 4.24 Bitable Metadata Tables

Purpose: 支撑多维表格视图、字段展示、权限和自动化配置。

| Table | Purpose | Minimum fields |
| --- | --- | --- |
| `table_views` | 视图定义 | `id`、`table_name`、`view_name`、`view_type`、`role_scope`、`status` |
| `view_columns` | 视图列配置 | `view_id`、`field_name`、`display_name`、`order_index`、`visible_if_permission` |
| `view_filters` | 视图筛选配置 | `view_id`、`field_name`、`operator`、`value`、`role_scope` |
| `field_permissions` | 字段权限 | `table_name`、`field_name`、`role`、`can_read`、`can_write`、`masking_rule` |
| `automation_rules` | 自动化规则 | `trigger_table`、`trigger_event`、`condition_json`、`action_type`、`status` |

First-stage rule:

- 第一阶段可以用代码固定配置这些视图和规则，但文档和数据库设计必须预留这些概念。
- 视图配置不等于业务事实，业务事实仍在 normalized business tables。

## 5. Required Role-Based Views

| View | Main table | Primary users | Purpose |
| --- | --- | --- | --- |
| Telegram 收件箱 | `messages` | 客服、销售、Message Intake Router Agent | 把消息转成草稿或待处理项 |
| 未识别消息视图 | `messages` | 客服、运营 | 人工处理无法识别的消息 |
| AI 草稿队列 | `service_drafts` | 生产、财务、管理 | 确认、补资料、驳回、升级 |
| 客户总表 | `customers` | 销售、客服、管理 | 查看客户、负责人、状态、风险 |
| 销售客户视图 | `customers` | Sales | 只看自己负责客户 |
| 账户库存视图 | `account_inventory` | Production、Account Inventory Agent | 管理生产账户库存 |
| 未启用账户视图 | `account_inventory` | Production | 找可分配账户 |
| 客户账户视图 | `account_assets` / `account_assignments` | Sales、Production | 查看客户名下账户 |
| 账户资产表 | `account_assets` | Production、Customer Reporting Agent | 查看余额、消耗、风险、状态 |
| 卡资源视图 | `payment_profiles` | Card Resource Agent、授权生产 | 查看 tokenized 卡资源 |
| 绑卡视图 | `account_card_bindings` | Production、Recharge And Binding Agent | 处理绑卡计划、执行和失败 |
| 财务收款视图 | `collection_records` | Finance | 核对收款证据和金额 |
| 充值视图 | `recharge_records` | Finance、Production、Recharge And Binding Agent | 跟踪收款、执行和回读 |
| 服务看板 | `service_records` | 销售、生产、客服、管理 | 跟踪服务状态 |
| 客户日报视图 | `customer_daily_reports` | Customer Reporting Agent、Sales、客服 | 复核和发送客户日报 |
| 公司日报视图 | `company_daily_reports` | Manager/Admin | 管理层查看全局日报 |
| 风险仪表盘 | `risk_events` | Production、Manager | 处理低余额、封户、stale data |
| 执行票据视图 | `execution_tickets` | Manager/Admin、Operations Supervisor Agent | 查看真实执行授权 |
| 审计视图 | `ops_audit_events` / `execution_logs` | Manager/Admin、审计角色 | 查所有关键动作证据 |
| Agent 运行视图 | `agent_runs` | Admin、技术运营 | 查看 Agent 输入输出和工具调用摘要 |

## 6. Workflow Endpoint Matrix

| Workflow | Starts from | Must create/update | Final view |
| --- | --- | --- | --- |
| Telegram 消息识别 | `messages` in Telegram 收件箱 | `messages.intent_status`、`service_drafts` or `ignored` | AI 草稿队列 / 未识别消息视图 |
| 账户生产导入 | Production input / import | `account_inventory`、`account_status_events` | 账户库存视图 |
| 账户分配给客户 | 账户库存视图 / 客户请求 | `account_assignments`、`account_inventory.inventory_status`、`account_status_events` | 客户账户视图 |
| BM invite / 分户 | `service_drafts` | `service_records`、`execution_tickets`、`execution_logs`、`account_status_events` | 服务看板 / 审计视图 |
| 卡资源检查 | 卡资源视图 | `payment_profiles.status`、`ops_audit_events` | 卡资源视图 |
| 绑卡 | 绑卡草稿 / 卡资源视图 | `account_card_bindings`、`execution_tickets`、`execution_logs`、`account_status_events` | 绑卡视图 / 账户资产表 |
| 财务收款确认 | 财务收款视图 | `collection_records.collection_status`、`ops_audit_events` | 待生产确认视图 |
| 充值执行 | 充值视图 | `recharge_records`、`execution_tickets`、`execution_logs`、`account_daily_metrics` | 充值视图 / readback 视图 |
| 余额和消耗采集 | scheduled job | `account_daily_metrics`、`risk_events` | 账户资产表 / 风险仪表盘 |
| 客户日报 | scheduled job / manual request | `customer_daily_reports` | 客户日报视图 |
| 公司日报 | scheduled job / manager request | `company_daily_reports` | 公司日报视图 |
| 风险升级 | `risk_events` | `risk_events.status`、`service_drafts` or `service_records` | 风险仪表盘 / 服务看板 |
| 客户回复 | service/report/risk view | `service_drafts` or report delivery status | Telegram 回传 + 对应业务视图 |

## 7. Agent Start And Landing Matrix

| Agent | Starts from | Reads | Writes / lands on | Requires human confirmation |
| --- | --- | --- | --- | --- |
| Operations Supervisor Agent | AI 草稿队列、服务看板、执行票据视图、审计视图 | `service_drafts`、`service_records`、`execution_tickets`、`ops_audit_events` | 状态分派、确认请求、`execution_tickets`、audit events | 任何真实外部执行前 |
| Message Intake Router Agent | Telegram 收件箱、未识别消息视图 | `messages`、`customers`、`customer_groups`、recent `service_records` | `messages.intent_status`、`service_drafts` | 不执行真实外部动作 |
| Account Inventory Agent | 账户库存视图、未启用账户视图、客户账户视图 | `account_inventory`、`account_assignments`、`account_assets`、`customers` | 库存记录、分配建议、`account_assignments`、`account_status_events` | 分配账户给客户前 |
| Recharge And Binding Agent | 充值视图、绑卡视图、账户资产表 | `recharge_records`、`account_assets`、`payment_profiles`、`account_card_bindings`、`execution_tickets` | 充值执行结果、绑卡执行结果、readback 状态、execution logs | 充值、绑卡、BM invite 前 |
| Finance Reconciliation Agent | 财务收款视图、充值视图 | `collection_records`、`recharge_records`、`customers`、金额字段 | 财务确认建议、异常标记、`collection_records.collection_status` draft | 确认到账前 |
| Card Resource Agent | 卡资源视图、绑卡视图 | `payment_profiles`、`account_card_bindings`、`account_assets` | 卡资源推荐、卡状态更新建议、绑卡计划 | 使用卡资源执行绑定前 |
| Customer Reporting Agent | 客户日报视图、公司日报视图、账户资产表、风险仪表盘 | `account_daily_metrics`、`recharge_records`、`risk_events`、`customer_daily_reports` | `customer_daily_reports`、`company_daily_reports`、`risk_events` | 自动发送客户日报可按客户策略要求复核 |

## 8. Automation Blueprint

| Trigger | Condition | Action | Output |
| --- | --- | --- | --- |
| New Telegram message | known customer group | enqueue `agent.intent_extract` | `messages.intent_status` update |
| New Telegram message | unknown group or unknown sender | route to manual review | 未识别消息视图 |
| Draft created | missing required fields | notify owner / sales | `service_drafts.status = needs_more_info` |
| Recharge draft ready | collection missing | notify Finance | 财务收款视图 |
| Collection confirmed | recharge has account and amount | notify Production | 待生产确认视图 |
| Production confirms high-risk action | policy passes | issue `execution_ticket` | 执行票据视图 |
| Execution ticket issued | action queued | enqueue execution worker | `service_records.status = executing` |
| Provider execution succeeds | execution log written | update service/recharge/binding status | 服务看板 / 充值视图 / 绑卡视图 |
| Provider execution fails | retry policy exhausted | mark failed and notify owner | 失败执行视图 |
| Readback fails | execution succeeded but balance unknown | create risk event | readback failed 视图 |
| Daily metric job completes | metrics fresh | update account metrics and reports | 客户日报视图 / 公司日报视图 |
| Low balance detected | threshold crossed | create risk event and notify owner | 风险仪表盘 |
| Customer report ready | policy requires review | route to review queue | 待复核日报视图 |
| Customer report sent | Telegram delivery succeeds | update delivery status | 客户日报视图 |

## 9. Permission Blueprint

| Role | Default visible views | Sensitive field access | Action boundary |
| --- | --- | --- | --- |
| Sales | 销售客户视图、客户账户视图、服务看板、客户日报视图 | 自己客户的部分金额和服务状态 | 可创建请求和补资料，不能确认财务到账或真实执行 |
| Customer Service | Telegram 收件箱、服务看板、客户日报视图 | 客户可见范围内的信息 | 可回复客户、创建草稿，不能执行资金/账户动作 |
| Production/Ops | 账户库存视图、账户资产表、绑卡视图、充值视图、服务看板 | 授权账户和脱敏卡资源 | 可确认账户/绑卡/充值执行，受策略限制 |
| Finance | 财务收款视图、充值视图、公司日报部分财务指标 | 金额、收款证据脱敏摘要 | 可确认收款，不能代表 provider 执行成功 |
| Manager/Admin | 所有管理视图、审计视图、公司日报视图 | 按管理权限查看敏感字段 | 可审批高风险动作、配置策略和权限 |
| Agent | 由 agent permission 决定的视图和字段 | 默认最小化，按任务授权 | 低风险内部写入可直接走工具，高风险执行必须凭 ticket |

## 10. Business Completion Definition

一个业务流程只有同时满足以下条件，才算完成：

- 主业务表记录已创建或更新。
- 状态字段已进入明确终态或等待态。
- 必要的 linked records 已建立。
- 对应角色能在视图中看到结果。
- 自动化已经触发或明确无需触发。
- 真实外部执行有 `execution_logs`。
- 高风险动作有 `execution_tickets` 和 `ops_audit_events`。
- Telegram 回传只作为通知，并能引用表格记录或执行证据。

## 11. Implementation Notes

- 第一阶段可以用固定业务 schema 实现，不做用户自由建表。
- API 可以提供 Bitable-like view endpoints，例如 `GET /views/{view_key}/records`，但返回内容必须经过 record、field、action 和 agent permission 过滤。
- PostgreSQL normalized tables 是事实层；`table_views` 等 metadata 是展示和操作配置层。
- Agent 工具不得直接返回裸数据库全量字段，必须返回 view-safe 或 tool-safe schema。
- 任何新需求进入开发前，必须先更新本文档中的 table、view、automation 或 Agent landing point。

## 12. Acceptance Criteria

- 已确认业务场景都能在本文档中找到 table、view 和 workflow endpoint。
- 每个 Agent 都能找到自己的 start view 和 landing table。
- 每个高风险执行都能找到 human confirmation、execution ticket、execution log 和 audit event。
- 客户日报、公司日报和风险判断都有 metrics source 和 freshness。
- 卡台和绑卡不保存 raw card / CVV。
- Telegram 回复不是任何业务流程的唯一结果。
