# Telegram Ingestion Module

## Status

- Document status: module draft
- Scope: Telegram Bot webhook、群绑定、消息入库、去重、Agent 触发
- Current Progress: 2026-07-04 完成 Telegram 接入模块设计。

## 1. Module Purpose

Telegram Ingestion Module 负责把 Telegram 群消息安全、可追踪地接入系统，并为 AI 意图识别和多维表格草稿生成提供标准化输入。

它不负责业务执行，也不直接创建真实服务记录。它只做消息接入、身份线索、去重、初步分类和任务入队。

## 2. Responsibilities

- 接收 Telegram webhook update。
- 校验 webhook secret。
- 解析 chat、message、sender、attachment metadata。
- 根据 chat id 识别 customer group 绑定。
- 根据 sender id 识别系统 user 或 customer contact。
- 写入 `messages`。
- 创建 agent intent extraction job。
- 对重复 update 做幂等处理。
- 记录 ingestion audit。

## 3. What It Does Not Do

- 不把 Telegram sender 直接当作系统权限。
- 不直接执行充值、分户、绑卡。
- 不直接把所有消息变成服务草稿。
- 不保存未脱敏敏感附件正文。
- 不让 LLM 读取未授权群消息。

## 4. Data Inputs

Telegram update:

- `update_id`
- `message.message_id`
- `message.chat.id`
- `message.from.id`
- `message.text`
- `message.caption`
- `message.date`
- attachment metadata

System context:

- customer group binding。
- user identity binding。
- group permission policy。
- bot config。

## 5. Data Outputs

- `messages` record。
- `ops_audit_events` record。
- Redis job: `agent.intent_extract`。

## 6. Idempotency

建议幂等键：

```text
telegram:update:{bot_id}:{update_id}
telegram:message:{chat_id}:{message_id}
```

重复消息处理：

- 如果 update 已处理，直接返回 success。
- 如果 message 已入库，不重复创建 agent job。
- 如果同一 message 触发多个 intent，只能由 agent 结果创建多个 draft candidate，不由 ingestion 层拆分。

## 7. Permission Model

Ingestion 只做最小权限线索判断：

- chat 是否被授权接入。
- chat 是否绑定 customer 或 internal workspace。
- sender 是否已绑定 user。
- sender 是否是 customer contact。

真正业务权限在 Service Draft / Confirmation 模块校验。

## 8. Agent Trigger

创建 `agent.intent_extract` job 时传入：

- `trace_id`
- `message_id`
- `chat_id`
- `customer_group_id`
- `sender_identity_type`
- `received_at`

不在 job payload 中放 raw sensitive attachment。

## 9. Failure Handling

| Failure | Handling |
| --- | --- |
| invalid webhook secret | reject, security log |
| unknown chat | store as unbound or reject by config |
| duplicate update | idempotent success |
| database unavailable | return retryable error |
| attachment too large | store metadata only, mark attachment_skipped |

## 10. Acceptance Criteria

- Telegram update 可幂等入库。
- 未绑定群不会触发业务草稿。
- 已绑定群消息可触发 intent extraction job。
- message 与 source Telegram id 可追踪。
- 不产生真实业务执行。

