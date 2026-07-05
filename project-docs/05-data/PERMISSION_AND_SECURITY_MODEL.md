# Permission And Security Model

## Status

- Document status: security model draft
- Scope: RBAC、scope、字段权限、动作权限、Agent 权限、敏感数据
- Current Progress: 2026-07-04 完成第一版权限和安全模型。

## 1. Permission Principles

- Telegram 身份不是系统权限。
- AI Agent 也必须受权限控制，但可以拥有高权限工具能力。
- 权限按 record、field、action、view、agent 五层设计。
- 所有确认、驳回、执行、权限拒绝都要 audit。
- 敏感字段默认不可见，按角色和 scope 授权。

## 2. Roles

| Role | Main permission |
| --- | --- |
| sales | 查看自己客户，创建服务草稿，查看服务进度 |
| customer_service | 查看授权客户，生成客户回复草稿，跟进异常 |
| production | 查看分配账户，确认执行下户/绑卡/充值 |
| finance | 查看收款、金额、充值财务状态，确认收款证据 |
| manager | 查看全局仪表盘，处理高风险复核 |
| admin | 配置权限、系统设置、审计 |
| agent | 通过授权工具查库、统计、生成草稿/日报，并在人工确认后执行受控动作 |

## 3. Permission Layers

### 3.1 Record Permission

控制谁能看哪些：

- customers。
- account_assets。
- messages。
- service_drafts。
- service_records。
- recharge_records。
- risk_events。

第一版建议以 customer/account scope 为主。

### 3.2 Field Permission

敏感字段：

- amount。
- balance。
- spend。
- payment profile。
- failure reason。
- execution response summary。
- customer sensitive notes。
- Telegram raw text。

无权限时：

- 后端不返回字段。
- Agent context 不包含字段。
- 日报聚合时脱敏。

### 3.3 Action Permission

动作：

- create_draft。
- confirm_draft。
- reject_draft。
- escalate_review。
- execute_after_confirmation。
- view_audit。
- export_data。
- manage_permissions。

Agent 不拥有“自我确认”权限。Agent 可以拥有 execute tool 调用权限，但必须提供有效 `execution_ticket`，该 ticket 必须由有权限的人类确认动作后生成。

### 3.4 View Permission

视图：

- 客户总表。
- 账户资产表。
- 服务看板。
- 充值视图。
- 风险仪表盘。
- 审计视图。

每个视图按 role 和 scope 输出数据。

### 3.5 Agent Permission

控制 Agent：

- 能读取哪些表。
- 能读取哪些字段。
- 能读取哪些 Telegram 群。
- 能调用哪些 tools。
- 能生成哪些 draft types。

## 4. Sensitive Data Policy

禁止保存：

- raw card number。
- CVV。
- 完整卡图。
- 未脱敏支付凭证。

限制保存：

- tokenized payment profile。
- masked last4。
- payment provider id。
- error response summary。
- Telegram raw text。

## 5. Audit Policy

必须审计：

- login / identity binding。
- permission denied。
- draft create/update。
- human confirmation。
- manual review。
- execution job creation。
- execution result。
- field permission violation。
- agent tool call。
- LLM output rejected。

## 6. Agent Security And Execution Ticket

Agent context 构造前必须先做权限过滤。Agent 访问数据库必须通过 query/statistics tools，不允许直接数据库连接。

`execution_ticket` 是 Agent 执行真实动作的前置凭证。

Ticket 必须包含：

- `ticket_id`
- `approved_by_user_id`
- `approved_at`
- `expires_at`
- `allowed_action`
- `allowed_customer_id`
- `allowed_account_id`
- `amount_limit` nullable
- `payment_profile_id` nullable
- `risk_snapshot`
- `permission_snapshot`
- `idempotency_key`
- `trace_id`

Ticket 只能使用一次，过期失效。高风险动作可要求二次确认。

Agent 禁止：

- 获取 raw sensitive field。
- 无 ticket 调用真实外部写入 tool。
- 修改权限。
- 删除 audit。
- 读取无关客户。

## 7. Acceptance Criteria

- 任何 API 响应前做权限过滤。
- 任何 Agent context 前做权限过滤。
- 确认和执行分离。
- 敏感字段默认不可见。
- 权限拒绝写 audit。
