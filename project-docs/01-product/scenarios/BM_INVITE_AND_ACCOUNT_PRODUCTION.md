# BM Invite And Account Production

## Status

- Document status: scenario draft
- Scope: 分户、BM invite、账户生产相关服务草稿和确认流程
- Current Progress: 2026-07-04 完成分户/账户生产场景设计，并补充 Bitable endpoint。

## 1. Business Value

分户和 BM invite 是广告账户服务中的核心生产动作。它通常涉及客户、账户、邮箱、BM 权限、生产人员、重复邀请、失败原因和客户回传。

系统要把“群里说一句给某邮箱下户”变成可审计流程，而不是让员工在多个浏览器里手动找账户、复制邮箱、执行邀请、再回群口头反馈。

## 1.1 Bitable Endpoint

分户和 BM invite 的终点必须是多维表格中的服务记录、账户库存状态、账户资产状态和执行审计更新。

| Layer | Endpoint |
| --- | --- |
| Main table | `service_records` with `service_type = bm_invite` |
| Linked records | `customers`、`account_inventory`、`account_assets`、`account_assignments`、`messages`、`execution_logs` |
| Views | 账户库存视图、服务看板、账户资产表、客户账户视图、审计视图 |
| Key statuses | `draft`、`needs_more_info`、`pending_production_confirmation`、`executing`、`succeeded`、`failed`、`blocked` |
| Automation | 生产确认提醒、重复邀请拦截、执行 ticket、Telegram 回传、账户状态事件写入 |
| Agent output | account operation draft、BM invite execution log、account status event、customer reply draft |

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Sales | 收集客户下户需求 |
| Customer | 提供 buyer email、BM 信息或账户需求 |
| Production/Ops | 确认账户和执行条件 |
| Account Inventory Agent | 校验库存账户、账户归属、账户状态和分配历史 |
| Recharge And Binding Agent | 在需要 Meta 侧动作时通过受控工具执行 BM invite / 相关账户操作 |
| Backend Service | 权限、幂等、执行和审计 |

## 3. Trigger

- Telegram 消息提到“下户”“开账户”“邀请 buyer@example.com”。
- Sales 在 Mini App 创建 account production draft。
- Production 手动创建 BM invite draft。

## 4. Workflow

```text
Telegram message
-> Message Intake Router Agent routes to Account Inventory Agent
-> extract customer/account/email/action
-> create BM invite draft
-> Production confirms
-> execution_ticket issued
-> permission + idempotency + account state check
-> Recharge And Binding Agent calls controlled BM invite execution tool
-> execution log
-> Telegram callback
```

## 5. Data Handling

关键字段：

- customer id。
- account id。
- buyer email。
- invite type。
- requested role。
- BM permission state。
- previous invite records。
- source message id。
- idempotency key。

唯一性建议：

- `account_id + buyer_email + invite_type + active_window` 防重复邀请。
- 每次执行请求必须有 client request id。

## 6. Permission Checks

必须校验：

- actor 是否可查看 customer/account。
- actor 是否可创建 BM invite draft。
- production 是否可确认执行。
- account 是否属于 customer。
- account 是否支持该 invite type。
- email 格式和域名是否合规。
- 是否存在重复 pending invite。

## 7. LLM Usage

允许：

- 识别“下户”“分户”“邀请”“开账户”等自然语言意图。
- 抽取邮箱、账户、客户、角色。
- 生成缺失信息提示。
- 生成客户回复草稿。

禁止：

- 绕过 Tool Gateway、人工确认和 `execution_ticket` 直接调用 BM API。
- 编造 BM 权限 ready。
- 在没有 execution log 时声称邀请已完成。

## 8. What We Do

- 生成 account production draft。
- 确认后由受控后端执行。
- 记录重复邀请和失败原因。
- 将结果回传 Telegram。

## 9. What We Do Not Do

- 不做自动投放开户策略。
- 不让 AI 决定客户是否有资格开户。
- 不让 Telegram 消息直接触发 BM invite。
- 不跳过生产确认。

## 10. Failure Handling

| Failure | Handling |
| --- | --- |
| 缺 buyer email | needs_more_info |
| 邮箱格式错误 | validation_failed |
| account 不匹配 customer | blocked |
| BM 权限缺失 | blocked |
| 重复 invite | idempotency_hit |
| provider 失败 | execution_failed |

## 11. Acceptance Criteria

- Telegram 下户消息能生成结构化 draft。
- 邮箱、账户、客户必须被校验。
- 重复 invite 不重复执行。
- 真实执行必须有 execution log。
- 客户回传必须引用执行状态。
