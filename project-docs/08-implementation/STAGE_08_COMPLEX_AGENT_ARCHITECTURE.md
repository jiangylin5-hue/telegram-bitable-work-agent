# Stage08 复杂 Agent 底层架构与模块规范

## Status

- Scope：定义 Stage08 运行时组件、数据流、状态、权限和故障边界。
- Status：planning baseline；任何实现必须遵守本文件与 `STAGE_08_SOURCE_OF_TRUTH.md`。

## 1. 分层架构

```text
入口层：Mini App / Telegram / HTTP API
  -> 身份与 Scope Resolver
  -> Runtime API
  -> Coordinator Graph
      -> Context Planner
      -> Structured Data Agent
      -> Group Context Agent
      -> Knowledge Retrieval Agent
      -> Analyst Agent
      -> Draft Agent
      -> Policy Gate
  -> Tool Gateway / Retrieval Provider / Memory Service
  -> PostgreSQL + pgvector / Redis queue-cache / audit
```

入口层只提供身份与请求，不允许提交任意 graph state。Runtime API 将身份、员工、当前 workspace/base/view、群聊和动作意图投影为受控 `ExecutionPlan`。

## 2. 模块职责

| 模块 | 输入 | 输出 | 禁止事项 |
| --- | --- | --- | --- |
| Identity and Scope Resolver | request identity、employee、chat/view | caller/employee/chat 权限交集 | 以 Telegram 身份代替工作区权限 |
| Context Planner | 请求、有效 scope、budget | 类型化读取计划、来源预算 | 直接取表或直接调用 provider |
| Tool Gateway | `ToolInvocation` | 脱敏事实、计数、实体引用 | raw SQL、任意 adapter、直接发送 |
| Group Context Agent | chat scope、时间窗 | 最近窗口、历史检索引用、Memory 候选 | 全量群转录、跨群检索 |
| Retrieval Provider | 已授权 source set、query | chunk 引用与分数 | 充当权限真源 |
| Memory Service | 事件/候选、来源、scope | 版本化 `MemoryItem` | 覆盖旧事实、无来源写入 |
| Analyst Agent | 已投影证据 | 标签化结论、不确定性 | 编造内部事实、创建外部动作 |
| Draft Agent | 合法目标、证据、proposal | `record_change_draft`/任务草稿 | 确认草稿、直接改记录 |
| Policy Gate | 计划、结果、action tier | allow/deny/escalate、ticket 状态 | 绕过授权、预算或审计 |

## 3. Coordinator 状态机

`queued -> planning -> reading -> analysing -> policy_check -> completed|draft_pending|denied|failed|cancelled|timed_out`。

- `planning`：只有 Context Planner 运行；预算在此冻结。
- `reading`：结构化查表、群聊与检索可并行，但每项产生独立 trace child span。
- `analysing`：只能消费投影后的 evidence，不能新增读取或写入。
- `policy_check`：验证引用、字段可见性、动作等级、预算和草稿合同。
- 终态必须写入 `AgentRun`；失败只能保存固定错误码与脱敏摘要。

## 4. 预算与并发规范

首发默认上限：图深度 3、工具调用 7、重试 2、读取子图并发 3、单 run 墙钟 30 秒、单 provider 调用 20 秒、检索 chunk 12。超限立即进入 `timed_out` 或 `denied`，不隐式延长。

读取可以并行；写入/草稿/Memory 状态转换必须串行、幂等并取得 ticket。任何子图失败不得自动重试另一种高风险动作；仅可回退为带 `general_advice` 标签的回答。

## 5. PostgreSQL、Redis 与 pgvector

- PostgreSQL：业务事实、权限、source、Memory、ticket、draft、audit、删除/TTL 状态的真源。
- `pgvector`：首发 embedding 索引；chunk 必须保留 source version 与可重建标志。
- Redis：短期 queue、取消信号、限流、运行中状态；Redis 丢失不可导致权限放宽或 Memory 丢失。
- 向量命中后必须回 PostgreSQL 重新读取 source validity、relation scope、field visibility 和删除状态。

## 6. Milvus 抽象

`RetrievalProvider.search(authority, query, filters, limit) -> RetrievalResult` 是唯一检索接口。首发 `PostgresRetrievalProvider` 采用 pgvector。未来 `MilvusRetrievalProvider` 只同步 `chunk_id`、embedding、最小过滤属性、source version 和删除 tombstone；源正文、最终权限和删除决定仍由 PostgreSQL 决定。

迁移必须满足：历史重建校验、双写/回放、按 `chunk_id/source_version` 比对、撤权/删除 SLA、回退到 Postgres provider 的开关和压测报告。

