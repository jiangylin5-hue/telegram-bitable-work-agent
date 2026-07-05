# Telegram 多维表格和工作智能体新项目产品简报

## Status

- Document status: product brief draft
- Project mode: new project, not constrained by prior SaaS implementation
- Source inputs:
  - [迁移版立项文档](MULTIDIMENSIONAL_AGENT_PROJECT_INITIATION.md)
  - [飞书多维表格与多维表格智能体调研](../00-research/FEISHU_BITABLE_AND_AGENT_RESEARCH.md)
- Current Progress: 2026-07-04 基于迁移文档和飞书调研，形成新项目产品边界，并明确真实写入只能通过人工确认和受控执行工具触发。

## 1. 项目一句话

本项目要开发一个面向广告代理商业务的 Telegram 多维表格和工作智能体系统：用 Telegram 承接客户、销售、生产、财务和客服的自然沟通，用多维表格沉淀客户、账户、服务、充值、风险和审计数据，用 AI 工作智能体把消息转成草稿、待办、提醒、日报和可验证的业务进展。

## 2. 新项目边界

本项目可以重新开发，不要求继承旧广告 SaaS 的框架、目录、Stage 结构或技术栈。

旧项目立项文档中有价值的是：

- 真实业务场景。
- 飞书多维表格的产品参考方向。
- Telegram + 多维表格 + AI 工作智能体的产品形态。
- AI 不绕过权限、人工确认、执行票据和受控工具执行高风险写入的安全边界。
- 客户、账户、服务记录、充值、风险、审计等业务对象。

旧项目立项文档中不应被直接视为本项目既定事实的是：

- 已存在的 FastAPI/PostgreSQL/Stage 07 后端实现。
- 已存在的 `/api/employee-ops/...` 接口。
- 已存在的 employee 权限模型。
- 已存在的数据库 schema。
- 已存在的前端 `/app`。

这些内容可以作为参考，但需要在本项目重新确认。

## 3. 产品定位

本项目不是通用飞书竞品，也不是通用 Excel/表格替代品。

本项目是：

- 广告代理商客户服务与账户生产的结构化工作台。
- Telegram 消息到业务草稿、待办和审计记录的转化系统。
- 面向销售、生产、财务、客服和管理者的多维业务表格。
- 以 AI 工作智能体为核心的数字员工系统。
- 有权限、有确认、有审计、有执行证据的业务操作系统。

本项目不是：

- AI 自动投放系统。
- 纯聊天机器人。
- 纯 CRM。
- 纯工单系统。
- 允许 AI 直接充值、绑卡、下户或执行资金/账户写入的 autopilot。

## 4. 核心业务对象

第一版产品设计应围绕这些对象展开：

| Object | Meaning |
| --- | --- |
| Customer | 客户主体、归属销售、Telegram 群、服务历史、风险状态 |
| Telegram Group | 客户群、内部协作群、成员、消息来源、授权范围 |
| Message | Telegram 原始消息、摘要、意图识别、证据引用 |
| Account Asset | 广告账户、状态、余额、消耗、风险、权限、绑定关系 |
| Service Draft | AI 或员工生成的待确认服务草稿 |
| Service Record | 已确认服务、状态机、责任人、执行状态、失败原因 |
| Recharge Record | 收款、充值请求、执行结果、余额回读状态 |
| Payment Profile | 脱敏/Tokenized 卡资源或支付资源 |
| Risk Event | 低余额、封户、异常消耗、数据延迟、权限缺失 |
| Execution Log | 真实执行证据、外部系统返回、执行 ID |
| Audit Event | 权限、确认、状态变更、失败、拦截和人工复核记录 |

## 5. 核心工作流

第一版推荐围绕一条闭环展开：

```text
Telegram 消息
-> AI 意图识别
-> 结构化服务草稿
-> 多维表格待确认队列
-> 员工确认 / 补资料 / 驳回 / 升级
-> 后端受控执行或 blocked
-> execution log / audit event
-> Telegram 回传状态
-> 日报和风险摘要
```

优先业务切片建议：

```text
客户充值请求
-> Telegram 消息识别
-> recharge draft
-> 财务确认收款证据
-> 生产确认账户和执行条件
-> controlled recharge execution
-> execution log
-> balance readback
-> Telegram 回传
```

## 6. AI 工作智能体边界

AI 工作智能体可以做：

- 读取授权 Telegram 消息和业务表数据。
- 抽取客户、账户、金额、币种、邮箱、动作类型和缺失信息。
- 生成充值、下户、绑卡、风险跟进、客户回复草稿。
- 建议任务分派对象和优先级。
- 生成销售、生产、财务、管理日报。
- 解释服务状态、失败原因、execution log 和 readback 状态。
- 识别重复请求和可能的幂等命中。

AI 工作智能体不可以做：

- 绕过人工确认、`execution_ticket` 和受控工具，直接执行充值、绑卡、BM invite 或任何真实外部写入。
- 绕过员工确认、权限校验、策略校验和审计记录。
- 接触 raw card number、CVV、完整卡图或未脱敏支付凭证。
- 把未知、过期、缺权限的数据编造成事实。
- 在没有 execution log 的情况下声称真实操作成功。

## 7. 多维表格视图

第一版建议设计这些视图：

| View | User |
| --- | --- |
| Telegram 收件箱 | AI、客服、销售 |
| AI 草稿队列 | 生产、财务、管理 |
| 客户总表 | 销售、客服、管理 |
| 账户资产表 | 生产、运营 |
| 充值视图 | 财务、生产 |
| 服务看板 | 销售、生产、客服 |
| 风险仪表盘 | 生产、管理 |
| 审计视图 | 管理、运营 |

## 8. 已确认技术基线与 Stage 02 决策

已确认技术基线：

- 后端语言和框架：Python 3.12+ + FastAPI。
- ORM / 迁移：SQLAlchemy 2.x + Alembic。
- 数据库：PostgreSQL + pgvector。
- 队列：Redis first，Temporal 作为未来复杂工作流候选。
- Agent 编排：LangGraph-first。
- LLM Provider：OpenRouter-compatible API。
- Telegram 形态：Bot API + Webhook + Mini App。

Stage 02 已确认：

- 业务范围同时覆盖充值闭环、账户库存、客户/公司日报，但按垂直切片顺序交付。
- Telegram 第一版先使用 mock webhook。
- 外部执行器第一版使用 mock/sandbox adapter。
- 权限模型第一版不做多租户 `tenant_id`。
- LLM prompt 和输出第一版只保存脱敏摘要。
- 第一版采用 outbox table 保证数据库事务和 Redis job enqueue 一致。

后续阶段再确认：

- 多维表格 UI 采用 Telegram Mini App，还是先做 Web 管理台。
- 何时接入真实 Telegram Bot。
- 何时接入真实 Meta/BM/卡台/充值 provider。

## 9. 第一阶段验收标准草案

- Telegram 授权群消息可以进入消息表，并保留来源引用。
- AI 可以从指定消息中生成结构化服务草稿。
- 草稿必须进入人工确认队列；真实写入只能在确认后通过 `execution_ticket` 和受控执行工具触发。
- 员工可以确认、驳回、补资料或升级复核。
- 确认后执行必须产生 execution log 或明确 blocked/failed 原因。
- 充值流程必须区分收款证据、充值执行和余额回读。
- 所有关键状态变更必须写入 audit event。
- AI 回复或日报必须引用结构化状态，不能编造未确认事实。
