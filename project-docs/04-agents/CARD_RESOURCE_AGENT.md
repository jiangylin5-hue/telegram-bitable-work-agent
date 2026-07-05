# Card Resource Agent

## Status

- Document status: agent draft
- Scope: 卡台资源、tokenized profile、卡状态、额度、可用性、卡账户绑定策略
- Current Progress: 2026-07-04 重写原 Card Platform Agent，明确其负责卡资源而不是绑卡执行本身。

## 1. Business Role

Card Resource Agent 负责管理卡台里的卡资源和 tokenized payment profile。它给 Recharge And Binding Agent 提供可用卡资源，但真实绑卡执行由 Recharge And Binding Agent 在 execution ticket 下调用。

## 2. Responsibilities

- 维护卡资源库存。
- 查询卡状态。
- 查询 tokenized profile。
- 检查额度、可用性、风控状态。
- 检查一卡一户策略。
- 记录卡资源分配和占用。

## 2.1 Bitable Endpoint

Card Resource Agent 的所有输出必须回到多维表格：

| Output | Table / View |
| --- | --- |
| 卡资源库存 | `payment_profiles` table / 卡资源视图 |
| 可用 tokenized profile | 卡资源视图 filtered by active/available |
| 卡分配给账户 | payment profile assignment / 账户资产表 / 卡资源视图 |
| 卡状态变化 | card status event / 卡资源视图 |
| 卡台异常 | risk/event record / 审计视图 |

## 3. State

```text
CardResourceState
- payment_profile_id
- provider
- tokenized_profile_id
- masked_label
- status
- assigned_account_id
- assigned_customer_id
- usage_policy
- limit_status
- risk_status
```

## 4. Tools

Read:

- `query_card_resources`
- `query_available_payment_profiles`
- `query_payment_profile_usage`
- `query_card_platform_status`

Mutation:

- `reserve_payment_profile`
- `release_payment_profile`
- `mark_payment_profile_inactive`
- `record_payment_profile_assignment`

Execution:

- `execute_card_platform_operation` only with ticket for card-platform real writes。

## 5. LLM Usage

允许：

- 根据脱敏卡资源状态解释可用性。
- 推荐候选 tokenized profile。
- 生成卡资源日报。

禁止：

- 读取 raw card number。
- 读取 CVV。
- 输出完整卡图或未脱敏凭证。
- 绕过一卡一户策略。

## 6. Required Skills

- card inventory management。
- tokenized profile selection。
- policy checking。
- sensitive data redaction。
- provider status interpretation。

## 7. Acceptance Criteria

- 能查询可用卡资源。
- 能记录卡资源分配给哪个账户。
- 能支持一卡一户策略。
- 不泄漏 raw card。
