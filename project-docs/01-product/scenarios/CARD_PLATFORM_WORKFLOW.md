# Card Platform Workflow

## Status

- Document status: scenario draft
- Scope: 卡台、tokenized payment profile、绑卡服务草稿和确认流程
- Current Progress: 2026-07-04 完成卡台/绑卡场景设计，并补充 Bitable endpoint。

## 1. Business Value

绑卡和卡台操作涉及支付资源，是本项目最敏感的业务之一。系统价值不是让 AI 自动绑卡，而是把卡资源、账户、客户、权限、执行、失败原因和审计统一管理，并避免员工接触或传播未脱敏支付凭证。

## 1.1 Bitable Endpoint

卡台和绑卡流程的终点必须是多维表格中的卡资源记录、账户绑定状态、执行日志和审计事件更新。

| Layer | Endpoint |
| --- | --- |
| Main table | `payment_profiles` and card binding records |
| Linked records | `customers`、`account_assets`、`account_inventory`、`service_records`、`recharge_records`、`execution_logs` |
| Views | 卡资源视图、账户资产表、充值视图、服务看板、敏感审计视图 |
| Key statuses | `available`、`reserved`、`bound`、`inactive`、`blocked`、`binding_failed` |
| Automation | 卡资源预占、生产确认提醒、执行 ticket、绑卡执行、失败升级、Telegram 回传 |
| Agent output | card resource recommendation、binding plan、binding execution result、redacted customer reply draft |

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Production/Ops | 确认账户和绑卡执行 |
| Finance | 关注卡资源状态和额度，不直接操作账户写入 |
| Card Resource Agent | 管理卡台资源、tokenized profile、卡状态、额度和可用性 |
| Recharge And Binding Agent | 在人工确认后执行 Meta 绑卡动作并登记账户绑定卡 |
| Backend Service | 敏感字段保护、权限、执行、审计 |

## 3. Trigger

- Telegram 消息提到“绑卡”“换卡”“卡台”“卡不可用”。
- Production 在 Mini App 创建 card binding draft。
- 卡台状态变化触发风险或待办。

## 4. Workflow

```text
Message / manual request
-> Card Resource Agent checks card resource candidates
-> identify account and tokenized profile candidate
-> Recharge And Binding Agent creates card binding plan
-> Production confirms
-> execution_ticket issued
-> sensitive permission check
-> controlled Meta card binding service
-> execution log
-> account/card binding state update
```

## 5. Data Handling

允许保存：

- tokenized payment profile id。
- masked card last4。
- card brand。
- provider profile id。
- status。
- limit summary。
- binding history。

禁止保存：

- raw card number。
- CVV。
- 完整卡图。
- 未脱敏支付截图。
- 可直接用于盗刷的敏感凭证。

## 6. Permission Checks

必须校验：

- actor 是否可查看 account。
- actor 是否有 card binding draft 权限。
- actor 是否有敏感字段查看权限。
- production 是否可确认绑卡。
- tokenized profile 是否可用于该 customer/account。
- 卡资源状态是否 active。
- 是否触发高风险复核。

## 7. LLM Usage

允许：

- 识别绑卡/换卡/卡不可用意图。
- 提示缺 tokenized profile。
- 解释脱敏卡台状态。
- 生成客户回复草稿。

禁止：

- 接触 raw card number / CVV。
- 绕过 Tool Gateway、人工确认和 `execution_ticket` 直接调用卡台写入接口。
- 给出绕过支付风控的建议。
- 把卡台 unknown 状态说成可用。

## 8. What We Do

- 把绑卡请求转成 card binding draft。
- 用 tokenized profile 作为唯一可执行支付资源引用。
- 对敏感字段做字段权限。
- 记录执行日志和失败原因。

## 9. What We Do Not Do

- 不保存 raw card。
- 不做完整卡资源财务管理。
- 不让 AI 或 Telegram 绕过确认和受控工具直接绑卡。
- 不给无权限用户显示敏感卡资源。

## 10. Failure Handling

| Failure | Handling |
| --- | --- |
| 缺 tokenized profile | needs_more_info |
| 卡资源 inactive | blocked |
| 无敏感字段权限 | permission_denied |
| provider unavailable | retry then failed safely |
| duplicate binding | idempotency_hit |

## 11. Acceptance Criteria

- 卡台相关消息能生成 draft。
- draft 不包含 raw card。
- 敏感字段权限生效。
- 真实绑卡必须 human confirm。
- 执行必须有 execution log。
