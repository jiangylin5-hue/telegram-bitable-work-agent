# Recharge Workflow

## Status

- Document status: scenario draft
- Scope: Telegram 充值请求到 AI 草稿、财务/生产确认、受控执行、余额回读和审计回传
- Current Progress: 2026-07-04 完成充值闭环业务逻辑设计，并补充 Bitable endpoint。

## 1. Business Value

充值流程是第一阶段最有价值的业务切片，因为它同时涉及销售、客户、财务、生产、金额、币种、账户、收款证据、真实执行、余额回读、失败处理和审计。

传统流程中，充值请求容易散落在 Telegram 聊天、人工表格、财务记录、账户后台和口头确认之间。系统要把它变成结构化闭环：

```text
客户/销售消息
-> AI 识别充值意图
-> recharge draft
-> 财务确认收款
-> 生产确认账户和执行条件
-> 受控充值执行
-> execution log
-> balance readback
-> Telegram 回传
```

## 1.1 Bitable Endpoint

充值流程的终点必须是多维表格中的记录、状态和视图更新。Telegram 回复只是通知层，不是流程终点。

| Layer | Endpoint |
| --- | --- |
| Main table | `recharge_records` |
| Linked records | `customers`、`account_assets`、`account_inventory`、`payment_profiles`、`messages`、`service_records`、`execution_logs` |
| Views | 充值视图、AI 草稿队列、服务看板、账户资产表、卡资源视图、审计视图 |
| Key statuses | `needs_more_info`、`pending_finance_confirmation`、`pending_production_confirmation`、`executing`、`succeeded`、`failed`、`readback_failed` |
| Automation | 财务确认提醒、生产确认提醒、执行 ticket、余额回读 job、Telegram 回传、客户日报更新 |
| Agent output | recharge draft、execution result、readback status、customer reply draft |

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Customer | 在 Telegram 提出充值需求或提供付款信息 |
| Sales | 维护客户关系，补充客户、账户、金额等信息 |
| Finance | 核对收款证据、金额、币种、到账状态 |
| Production/Ops | 核对账户、执行条件、风险状态，确认是否可充值 |
| Recharge And Binding Agent | 查询账户 ID、余额、绑卡状态，在确认后执行 Meta 绑卡充值 |
| Finance Reconciliation Agent | 辅助核对收款证据、金额、币种和财务异常 |
| Account Inventory Agent | 校验账户库存归属、账户状态、是否已分配给该客户 |
| Card Resource Agent | 提供 tokenized profile、卡状态、额度和一卡一户策略 |
| Backend Service | 权限、幂等、状态机、审计、执行入口 |

## 3. Preconditions

最小前置条件：

- Telegram group 已绑定 customer。
- 发送者已绑定系统 user 或被标记为 customer contact。
- customer 存在。
- account asset 存在，或消息中包含可匹配账户线索。
- 充值币种、金额、账户至少能被 AI 提取或进入补资料状态。

## 4. Trigger

触发来源：

- Telegram 群消息，例如“客户 A 给账户 X 充 1000U”。
- Sales 在 Mini App 提交自然语言请求。
- Finance 上传或录入收款证据。
- Production 从待办创建充值草稿。

## 5. Workflow

### 5.1 Message Intake

系统接收 Telegram update，保存：

- Telegram update id。
- chat id。
- message id。
- sender id。
- raw text / caption。
- attachments metadata。
- received_at。
- idempotency key。

### 5.2 AI Extraction

Recharge And Binding Agent 从消息中提取并校验：

- customer candidate。
- account candidate / Meta account id。
- current balance。
- bound card profile。
- amount。
- currency。
- payment method / tokenized card profile candidate。
- collection evidence reference。
- requested execution time。
- urgency。
- missing fields。
- risk flags。

LLM 调用要求：

- Provider: OpenRouter-compatible API。
- 输出必须符合 JSON schema。
- 置信度低时不得创建 executable draft，只能创建 `needs_more_info`。
- 不允许模型编造账户、金额、到账状态。

### 5.3 Draft Creation

系统创建 `service_drafts`：

- `draft_type = recharge`。
- `status = draft` 或 `needs_more_info`。
- 关联 customer、account、message、extracted fields。
- 写入 AI extraction evidence。

### 5.4 Finance Confirmation

Finance 确认：

- 是否有收款证据。
- 收款金额是否匹配。
- 币种是否匹配。
- 是否到账。
- 是否存在重复收款或异常备注。

财务确认不能直接等同于广告账户充值成功。

### 5.5 Production Confirmation

Production/Ops 确认：

- account 是否属于 customer。
- account 是否可充值。
- account 是否风险异常。
- provider / card platform 是否可用。
- 当前用户是否有确认执行权限。

### 5.6 Controlled Execution

如果权限、策略、幂等、风险都通过，后端创建执行 job。

真实 provider 调用必须由 controlled service 发起，不由 LLM、Telegram 或前端直接发起。

### 5.7 Execution Log

执行完成后写入：

- execution id。
- provider name。
- provider request id。
- provider response summary。
- success / failed / pending。
- amount。
- currency。
- account id。
- executed_at。
- error code。
- error message redacted。

### 5.8 Balance Readback

充值执行成功不等于余额回读成功。

readback 状态：

- `readback_pending`
- `readback_succeeded`
- `readback_failed`
- `readback_not_supported`

如果 readback 失败，Telegram 回传必须明确：“充值执行已提交/成功，但余额回读失败”，不能说余额已更新。

## 6. Data Handling

主要数据表：

- `messages`
- `service_drafts`
- `service_records`
- `recharge_records`
- `collection_records`
- `execution_logs`
- `ops_audit_events`
- `account_assets`

敏感数据：

- 收款凭证附件只保存文件引用和脱敏摘要。
- 不保存完整银行卡、CVV、未脱敏支付凭证。
- 金额字段需要字段权限控制。

## 7. Permission Checks

必须校验：

- user 是否绑定系统身份。
- user 是否有 customer scope。
- user 是否能查看 account。
- user 是否能创建 recharge draft。
- finance 是否能确认 collection。
- production 是否能确认 recharge execution。
- agent 是否能读取相关 message、customer、account、amount 字段。

## 8. LLM Usage

允许调用 LLM：

- 意图识别。
- 字段抽取。
- 缺失信息提示。
- 风险摘要。
- 客户回复草稿。
- 日报摘要。

禁止 LLM：

- 判断真实到账。
- 判断真实充值成功。
- 绕过 Tool Gateway、人工确认和 `execution_ticket` 直接调用充值 provider。
- 生成没有证据的成功承诺。

## 9. What We Do

- 把 Telegram 充值消息转成结构化草稿。
- 分离收款确认、充值执行、余额回读。
- 提供财务和生产双确认机制。
- 用幂等键防止重复充值。
- 保留 audit event 和 execution log。
- 回传 Telegram 明确状态和证据。

## 10. What We Do Not Do

- 不让 AI 绕过确认和受控工具直接充值。
- 不把客户付款截图直接视为到账。
- 不把充值执行成功直接视为余额回读成功。
- 不保存 raw payment credential。
- 不在第一阶段做完整财务账本、发票、结算。

## 11. Failure Handling

| Failure | Handling |
| --- | --- |
| 缺金额 | `needs_more_info`，提醒 sales/customer |
| 缺账户 | `needs_more_info`，提示候选账户 |
| 收款未确认 | `pending_finance_confirmation` |
| 金额异常 | `manual_review` |
| 权限不足 | `permission_denied` audit |
| 重复请求 | idempotency hit, link existing record |
| provider 失败 | `execution_failed`, write execution log |
| readback 失败 | `readback_failed`, do not claim balance updated |

## 12. Acceptance Criteria

- Telegram 充值消息能生成 recharge draft。
- 草稿包含 customer、account、amount、currency、source_message。
- 缺字段时进入 `needs_more_info`。
- 财务确认和生产确认分离。
- 确认后执行必须有 idempotency key。
- 执行结果必须写 execution log。
- readback 状态必须单独展示。
- Telegram 回传不能越权承诺成功。
