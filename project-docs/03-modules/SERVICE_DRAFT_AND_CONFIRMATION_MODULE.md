# Service Draft And Confirmation Module

## Status

- Document status: module draft
- Scope: 服务草稿、人工确认、状态机、执行闸门
- Current Progress: 2026-07-04 完成服务草稿与确认模块设计。

## 1. Module Purpose

本模块是 AI 和真实业务执行之间的安全缓冲层。AI、Telegram、员工都可以创建服务草稿，但真实执行必须经过确认、权限、策略、幂等和执行闸门。

## 2. Draft Types

- `recharge`
- `bm_invite`
- `card_binding`
- `risk_followup`
- `customer_reply`
- `daily_report`

第一阶段重点：

- `recharge`
- `bm_invite`
- `card_binding`

## 3. Draft State Machine

```text
draft
-> needs_more_info
-> pending_confirmation
-> rejected
-> confirmed
-> service_record_created
-> executing
-> succeeded
-> failed
-> blocked
-> manual_review
```

状态规则：

- `draft` 可以补资料、提交确认、驳回。
- `needs_more_info` 不能执行。
- `pending_confirmation` 只能由授权人确认。
- `confirmed` 必须立即创建 service record 或进入 blocked/manual_review。
- `executing` 不允许重复执行。
- `failed` 不允许危险自动重试，必须走新确认或安全 retry 策略。

## 4. Confirmation Actions

| Action | Meaning |
| --- | --- |
| confirm | 授权人确认草稿 |
| reject | 驳回草稿 |
| request_more_info | 要求补资料 |
| escalate | 升级管理复核 |
| cancel | 取消未执行草稿 |

每个动作必须写 audit event。

## 5. Permission Checks

确认前必须校验：

- actor identity。
- record scope。
- action permission。
- field permission。
- draft type permission。
- current state。
- risk policy。

Agent 不能拥有 `confirm` 权限。

## 6. Execution Gate

确认后系统运行 execution gate：

```text
permission check
-> state check
-> data completeness check
-> idempotency check
-> risk policy check
-> provider availability check
-> create execution job or blocked/manual_review
```

## 7. LLM Usage

允许：

- 生成 draft。
- 提醒缺字段。
- 生成风险提示。
- 生成客户回复草稿。
- 解释失败原因。

禁止：

- 自动 confirm。
- 自动 bypass risk。
- 直接创建 execution job。
- 修改 execution log。

## 8. Acceptance Criteria

- 每个 draft 有类型、状态、来源、trace id。
- 每个确认动作有 audit event。
- Agent 只能创建草稿，不能确认。
- 执行 job 只能由 service layer 创建。
- 幂等命中不会重复执行。

