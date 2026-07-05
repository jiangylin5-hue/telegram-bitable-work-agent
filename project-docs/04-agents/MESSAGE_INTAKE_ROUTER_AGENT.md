# Message Intake Router Agent

## Status

- Document status: agent draft
- Scope: Telegram 消息入口、噪声过滤、意图分类、客户/账户线索识别、路由
- Current Progress: 2026-07-04 重命名并重写原 Telegram Triage Agent。

## 1. Business Role

Message Intake Router Agent 负责把 Telegram 群里的自然语言消息变成可处理的业务入口。它像一个接线员和分诊员，判断消息是否和业务有关、属于哪个客户、涉及哪个动作、应该交给哪个 Agent。

## 1.1 Bitable Endpoint

Message Intake Router Agent 的终点不是聊天回复，而是让消息进入多维表格：

| Output | Table / View |
| --- | --- |
| 原始消息 | `messages` / Telegram 收件箱 |
| 业务 workflow | workflow/service draft table / AI 草稿队列 |
| 无关消息 | `messages.ingestion_status = ignored` / Telegram 收件箱 |
| 路由结果 | workflow state / 审计视图 |

## 2. Workflow

```text
Telegram message
-> normalize text and attachments
-> identify customer/group/sender
-> classify intent
-> resolve account/card/money/email candidates
-> update search state
-> route to target agent
-> create workflow if business-related
```

## 3. State

```text
MessageRoutingState
- source_message_id
- chat_id
- sender_identity_id
- customer_candidates
- account_candidates
- intent_type
- confidence
- target_agent
- missing_context
- noise_reason
```

## 4. Search State

```text
SearchState
- customer_search_results
- account_search_results
- recent_message_refs
- open_workflow_refs
- selected_customer_id
- selected_account_ids
```

## 5. Tools

Read:

- `query_group_binding`
- `query_sender_identity`
- `query_customer_candidates`
- `query_account_candidates`
- `query_recent_messages`
- `query_open_workflows`

Mutation:

- `create_workflow`
- `append_message_to_workflow`
- `mark_message_irrelevant`

## 6. LLM Usage

使用 OpenRouter 模型进行意图分类和实体抽取。输出必须是 JSON。

Intent types:

- `account_inventory`
- `recharge_binding`
- `finance_reconciliation`
- `card_resource`
- `customer_report`
- `customer_reply`
- `irrelevant`
- `unknown`

## 7. Required Skills

- Telegram message understanding。
- multilingual intent classification。
- customer/account entity resolution。
- noise filtering。
- routing decision。

## 8. Acceptance Criteria

- 能识别充值、绑卡、账户分配、卡资源、日报、财务相关消息。
- 能把不相关聊天标记为 irrelevant。
- 低置信度进入人工分诊，不乱建任务。
- 路由结果可审计。
