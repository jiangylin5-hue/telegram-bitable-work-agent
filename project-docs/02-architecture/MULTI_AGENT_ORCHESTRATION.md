# Multi-Agent Orchestration

## Status

- Document status: architecture draft
- Scope: 高权限 multi-agent 编排、LangGraph graph、state、search state、tool gateway、execution ticket、agent collaboration
- Current Progress: 2026-07-04 根据用户反馈重写 Agent 架构：Agent 可授权查库统计、人工确认后执行真实动作，所有结果回写多维表格。

## 1. Design Goal

本项目的 Agent 是数字员工系统，不是只生成草稿的弱助手。它们要承担真实岗位职责：

- 从 Telegram 消息中理解业务需求。
- 查询客户、账户库存、账户余额、账户绑定卡、服务记录。
- 统计客户每日消耗和公司全局日报。
- 管理账户库存：未启用、已分配、分给谁、当前状态。
- 协助生产人员完成账户生产和分户。
- 协助执行 Meta 后台绑卡充值。
- 在人工确认后，通过受控工具执行真实动作。

技术目标是让 Agent 权限高、能力强，但所有数据访问和执行动作都经过 Tool Gateway、权限策略、execution ticket、审计和日志。

所有 Agent 的设计必须遵守多维表格宪法：Agent 的输入来自多维表格记录/视图，Agent 的动作改变多维表格记录/状态/视图，Agent 的执行结果回写到多维表格审计和执行日志。Agent 不创建游离在多维表格之外的业务事实。

## 2. Mature Architecture Reuse

优先复用成熟 GitHub/官方生态：

- LangGraph: graph、state、checkpoint、supervisor/sub-agent、human-in-the-loop。
- OpenRouter: OpenAI-compatible API，统一模型入口。
- FastAPI: Tool Gateway 和后端 API。
- PostgreSQL + SQLAlchemy: 强业务事实和事务。
- Redis: job、worker、异步执行、日报调度。

不自研通用 Agent framework，不让 LLM 裸连数据库或裸调 provider。

## 3. Agent Topology

```text
Operations Supervisor Agent
        |
        +--> Message Intake Router Agent
        +--> Account Inventory Agent
        +--> Recharge And Binding Agent
        +--> Finance Reconciliation Agent
        +--> Card Resource Agent
        +--> Customer Reporting Agent
        |
        v
Tool Gateway
        |
        +--> Database Query Tools
        +--> Statistics Tools
        +--> Draft / Task / Report Tools
        +--> Execution Ticket Tools
        +--> Controlled Execution Tools
        +--> Notification Tools
        +--> Retrieval Tools
```

## 4. Agent Catalog

| Agent | Business role | Main capability |
| --- | --- | --- |
| Operations Supervisor Agent | 调度主管 | 维护全局 workflow state，决定任务路由、协作顺序、人工确认点 |
| Message Intake Router Agent | Telegram 消息入口 | 消息分类、客户识别、意图路由、噪声过滤、上下文补全 |
| Account Inventory Agent | 账户库存/账户生产 | 管理库存账户、未启用账户、已分配账户、客户归属、账户状态和生产任务 |
| Recharge And Binding Agent | 绑卡充值执行 | 在 Meta 后台绑卡、充值，登记账户 ID、余额、绑定卡，一卡一户约束 |
| Finance Reconciliation Agent | 财务核对 | 核对收款、金额、币种、充值额度、财务异常，不直接代表充值成功 |
| Card Resource Agent | 卡资源/卡台 | 管理卡台资源、tokenized profile、卡状态、额度、可用性，供绑卡充值调用 |
| Customer Reporting Agent | 客户消耗与日报 | 统计每个客户每日账户消耗，发送客户日报和公司全局日报 |

## 5. Collaboration Workflows

### 5.1 充值绑卡闭环

```text
Message Intake Router
-> Recharge And Binding Agent extracts account/amount/card need
-> Account Inventory Agent verifies account ownership/status
-> Card Resource Agent selects available tokenized profile if needed
-> Finance Reconciliation Agent verifies collection/amount if recharge
-> Supervisor requests human confirmation
-> execution_ticket issued
-> Recharge And Binding Agent calls controlled Meta/card/recharge tools
-> execution log + readback
-> recharge/account/card table views updated
-> Customer Reporting Agent includes result in daily report
```

### 5.2 账户库存分配闭环

```text
Production creates new account inventory records
-> Account Inventory Agent marks unused/available
-> Sales/customer request account
-> Router identifies account request
-> Account Inventory Agent selects candidate inventory account
-> human confirms assignment
-> account status changes to allocated / activated
-> account inventory view updated
-> audit event records who got which account
```

### 5.3 客户日报闭环

```text
Scheduled daily job
-> Customer Reporting Agent queries all customer account spend
-> Account Inventory Agent enriches account status
-> Recharge And Binding Agent provides balance/readback facts
-> Finance Reconciliation Agent provides recharge/collection facts
-> Customer Reporting Agent generates customer-level report
-> customer_daily_reports table/view updated
-> Supervisor sends customer report through Telegram after policy check
-> Company-wide report generated for manager/admin
```

## 6. State Design

State 是 LangGraph 流程中的结构化运行状态，不是聊天记录。它决定 Agent 现在知道什么、缺什么、下一步做什么、是否需要人工确认。

### 6.1 Global Workflow State

```text
WorkflowState
- trace_id
- workflow_id
- source_type
- source_message_id
- customer_id
- account_ids
- requested_action
- current_agent
- completed_agents
- pending_agents
- human_confirmation_required
- execution_ticket_id
- status
- errors
```

### 6.2 Agent Task State

```text
AgentTaskState
- agent_name
- task_id
- input_entities
- resolved_entities
- missing_fields
- permission_snapshot
- tool_results
- risk_flags
- proposed_action
- confidence
- next_action
```

### 6.3 Execution State

```text
ExecutionState
- execution_ticket_id
- approved_by_user_id
- allowed_action
- allowed_scope
- idempotency_key
- provider
- execution_status
- provider_request_id
- execution_log_id
- readback_status
```

## 7. Search State / Retrieval State

Search state 是 Agent 为了完成任务而维护的检索状态。它记录查过什么、命中了什么、哪些结果可信、哪些需要继续查。

```text
SearchState
- query_intent
- searched_sources
- customer_search_results
- account_search_results
- inventory_search_results
- card_resource_search_results
- historical_case_results
- sop_results
- selected_result_ids
- rejected_result_ids
- unresolved_questions
```

Search state 用途：

- 防止 Agent 每一步重复查相同数据。
- 记录为什么选中某个客户、账户、卡资源或历史案例。
- 支持人工复核 Agent 判断。
- 支持失败后恢复或重新路由。

Search state 不等于业务事实。业务事实仍以 PostgreSQL 当前记录为准。

## 8. Tool Gateway

Agent 通过 Tool Gateway 访问系统能力。

### 8.1 Database Query Tools

- `query_customer_profile`
- `query_customer_accounts`
- `query_account_inventory`
- `query_account_status`
- `query_account_balance_and_spend`
- `query_account_card_binding`
- `query_service_records`
- `query_recharge_records`
- `query_execution_logs`
- `query_customer_daily_spend`
- `query_company_daily_spend`

### 8.2 Statistics Tools

- `aggregate_customer_daily_spend`
- `aggregate_company_daily_spend`
- `aggregate_account_inventory_status`
- `aggregate_recharge_success_rate`
- `aggregate_card_binding_status`

### 8.3 Mutation Tools

- `create_service_draft`
- `update_account_inventory_status`
- `create_customer_report`
- `create_company_report`
- `create_risk_event`
- `create_task_assignment`

低风险内部写入可以由 Agent 直接调用，但必须经权限和 audit。

### 8.4 Execution Ticket Tools

- `request_execution_confirmation`
- `issue_execution_ticket`
- `validate_execution_ticket`
- `expire_execution_ticket`

Ticket 只能由有权限的人类确认后生成。

### 8.5 Controlled Execution Tools

- `execute_meta_card_binding`
- `execute_meta_recharge`
- `execute_bm_invite`
- `execute_card_platform_operation`
- `execute_balance_readback`

这些工具必须要求有效 `execution_ticket`。

## 9. Permission Model

每次 tool call 校验：

- agent identity。
- user/customer/account scope。
- field permission。
- action permission。
- tool permission。
- risk policy。
- execution ticket。
- idempotency key。

Agent 可以查库，但只能查授权范围内的数据；可以执行，但只能执行 ticket 授权的动作。

## 10. Skills Required By Agent

这里的 skills 不是 Codex 插件技能，而是业务 Agent 需要具备的能力模块：

| Skill | Meaning |
| --- | --- |
| intent classification | 识别消息属于充值、账户、卡、日报、财务等哪类任务 |
| entity resolution | 解析客户、账户、卡资源、金额、币种、日期 |
| inventory reasoning | 判断账户库存状态、是否可分配、分给谁 |
| spend aggregation | 聚合客户和公司每日消耗 |
| permission reasoning | 根据 scope、role、field/action policy 判断能否查/做 |
| execution planning | 把真实动作拆成确认、ticket、执行、回读、审计 |
| evidence-based reporting | 报告必须引用数据来源和 freshness |
| failure triage | 根据错误码、状态、readback、provider response 判断下一步 |

## 11. Audit And Observability

每次 Agent run 记录：

- `agent_run_id`
- `workflow_id`
- `trace_id`
- `agent_name`
- `state_snapshot`
- `search_state_snapshot`
- `tool_calls`
- `permission_snapshot`
- `execution_ticket_id`
- `human_confirmation_id`
- `output_summary`
- `created_entities`

## 12. Acceptance Criteria

- Agent 命名贴合真实岗位职责。
- Account Inventory Agent 明确管理账户库存。
- Recharge And Binding Agent 明确负责 Meta 绑卡充值和账户余额/绑卡登记。
- Customer Reporting Agent 明确负责客户每日消耗日报和公司全局日报。
- Agent 可通过授权工具访问数据库。
- Agent 可在人工确认后凭 ticket 调用受控执行工具。
- state、search state、workflow state、execution state 定义清楚。
- 协作流程清楚。
- 每个 Agent workflow 的终点都是多维表格记录、状态、视图、自动化或审计事件。
