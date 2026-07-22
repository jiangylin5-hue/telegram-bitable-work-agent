# Stage08 E3 安全执行适配层决策

## Status

- Status: accepted — 用户于 2026-07-22 确认方案 B。
- Scope: 仅修复 Package E / E3 在“分析 → Policy Gate → `pending_confirmation` 草稿”路径中的事务、审计和受控 mutation 契约冲突。
- Out of scope: 公开 API、数据库 schema/migration、全局角色模型、真实 Provider、Telegram、部署、直接 record 写入、草稿确认、Memory/RAG/C3/D4 合同变更。

## 1. 触发原因

E3 首轮独立复审发现：直接复用 Stage06 的 ticket、Tool Gateway 与草稿服务，会产生含 record/draft/ticket UUID 的既有 `AgentRun` 和 audit；同时 Stage06 UoW 无法为“当前权限重验、票据、草稿、终态”提供 E3 所需的同一 rollback 边界。原有私有 `draft_intent` 也不足以表达并校验具体字段和值。

这些问题使 E3 无法同时满足既有 Stage08 的最小审计白名单、草稿前消费期重验、无 orphan ticket/idempotency 与受控字段 mutation 要求。

## 2. 已确认决策

增加仅供 Stage08 E3 调用的 **安全执行适配层**。它复用既有 `ExecutionPlan`、`begin_execution_plan`、`Stage08ToolGateway` 与 `RecordChangeDraft`，但以显式、默认关闭的内部参数启用以下行为：

1. `safe_execution` 审计模式只影响 E3 调用；Stage06 与其他 Stage08 调用保持当前默认审计行为。
2. E3 调用链产生的 ticket、Gateway、draft-service 内部 AgentRun/audit 仅写白名单摘要：状态、动作、计数、错误码、trace hash、耗时和 ticket/draft 是否存在。不得写入 query、answer、private context、field key/value、record/draft/ticket UUID、provider 输出或工具实体引用。
3. 草稿使用已存在的 `RecordChangeDraft`，其数据库主键、外键和业务事实仍由 PostgreSQL 正常维护；“不得记录 UUID”仅约束 E3 的 AgentRun/audit/outbox/log/API 安全投影，不能取消业务表主键。
4. `DraftIntent` 保持不可序列化和 process-local，但扩展为受控 `field_key + JSON-safe value` 载体。它只在 Policy Gate 和 Gateway invocation 之间存活；不进入 AgentRun/audit/log/API/Redis/checkpoint。Policy Gate 必须在当前 record/table/field/actor/employee/scope 上重新校验该字段和值。
5. 新增 Stage08 专用 UoW 执行边界：InMemory 使用可回滚快照；SQLAlchemy 使用 `begin_nested()` savepoint。它涵盖消费期锁定、current-state 重验、ticket/idempotency reservation、Gateway 草稿创建以及终态摘要。拒绝、取消、异常、预算/超时和 Gateway 失败均 rollback 该边界，不保留 ticket、idempotency、draft 或内部审计残留。
6. 执行边界锁定 workspace、target record、active member、employee、相关 group binding/mapping 与被消费的 source lifecycle 行。所有能够撤权或变更这些对象的 Stage08/Stage06 写服务必须使用相同的锁顺序；无法锁定或发现任何 drift 时 fail closed。
7. 同一 idempotency key 先重新验证当前 scope，再从本次 E3 的 hash-only trace 查找已有 `pending_confirmation` 草稿并返回同一安全结果；不同 key 走新的完整 Policy Gate，不依赖“该 record 只有一个 pending draft”的全局计数。

## 3. 不采用的方案

| 方案 | 结论 | 原因 |
| --- | --- | --- |
| 放宽 E3 审计白名单，允许既有 Stage06 UUID 审计 | 拒绝 | 会违背 Stage08 私有上下文与最小审计边界。 |
| 直接 ORM 创建草稿、随后删除既有 audit | 拒绝 | 绕过 Tool Gateway、破坏审计完整性，且无法可靠回收已提交副作用。 |
| 保留不含字段和值的空 `proposed_values` 草稿 | 拒绝 | 不能校验字段权限或证明草稿来自受控 intent。 |
| 将安全模式做成公开 API/client 参数 | 拒绝 | 会扩大攻击面；只允许 E3 服务端内部构造。 |

## 4. 交付与验收

实现前必须更新 E3 计划、E 合同、BDD 和技术决策记录；不新增 migration 或公开 endpoint。

最低证据：

- RED/GREEN：unknown citation、非法 field/value、撤销 member/employee/record/mapping/source、provider unavailable/shape error、cancel、timeout、same/different idempotency、Gateway exception；
- 单元和服务测试验证全 trace 的所有 `AgentRun`/audit/outbox/log-safe projection 不含禁止字段；
- disposable loopback PostgreSQL 上的真实 SQLAlchemy UoW：成功草稿、same-key replay、rollback cleanup、双会话 lock/blocking/current-state drift 证据；
- fresh independent review 必须同时给出 spec compliance 与 code-quality 通过结论。

## 5. 风险与后续

这是一项受限的内部服务契约扩展，不改变最终业务模型和默认运行路径。E3 完成不代表 E4 API、Package F 真实 LLM 评测或生产部署已完成。

## 6. 2026-07-22 终态合同对齐

用户确认 E1 `AssistantTerminalStatus` 增加 `degraded`。仅 `AnalysisProviderOutcome(status="unavailable")` 使用该状态，并固定输出 `analysis_unavailable`、空 answer/citations/draft；无效、伪造或 shape drift 仍然是 `failed`。这是 E3 BDD 的既有要求与 E1 类型的最小对齐，不新增公开 API、schema、权限或真实 Provider。
