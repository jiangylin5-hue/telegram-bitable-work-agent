# Stage08 复杂 Agent 项目路线图

**Goal：** 将复杂 Agent 运行时拆成可独立交付的实施包；从受控工具执行开始，以可量化的检索与协作质量收口。

## 实施包顺序

| 实施包 | 交付物 | 依赖 | 退出门槛 |
| --- | --- | --- | --- |
| A | Runtime Foundation 与类型化 Tool Gateway | Stage06/07 的授权、审计、草稿和幂等服务 | 每个工具都有类型合同、作用域交集、预算、execution ticket 与审计轨迹 |
| B | Business Memory | A | 表格事件与高置信群聊候选能生成有版本、可撤销、带作用域的 Memory，且不保存原始转录 |
| C | Context Engineering | A、B | Planner 可以构造有界的实时查表、群窗口、Memory 与通用建议上下文，并输出证据标签 |
| D | RAG / pgvector Retrieval | B、C | 文件及批准来源具备版本/chunk/检索能力，且有检索前后授权核验与删除/reindex 保证 |
| E | LangGraph Coordinator 与专长子图 | A-D | 协调器能进行受限并行读取、证据分析、草稿创建，并在失败时安全降级 |
| F | Evaluation 与 Operations | A-E | 标注质量语料、单 case 隔离、脱敏遥测和 Milvus 决策指标达到验收要求 |

## 全局约束

- PostgreSQL 是权限、来源版本、Memory、TTL、撤权、删除和审计的真源；`pgvector` 是首发检索索引。
- 未达到明确指标前不得引入 Milvus：百万级 chunk、延迟/并发 SLO 失败，或已证实的高吞吐多向量/批处理需求。
- 权限始终是 employee、caller、workspace/base/table/view/field 和 Telegram chat scope 的交集。
- 默认所有写入类动作创建 draft。只有单独批准的低风险动作和测试群 allowlist 可自动执行，但仍必须具备 execution ticket 与审计。
- 不得在 AgentRun 或 Memory 中持久化原始 provider prompt、原始模型回复、密钥、思维链或任意完整群聊转录。
- 任何实施包都不改变 Stage07 验收状态，也不授权生产部署、不受限 Telegram 发送或通用 Agent 安装工具。

## 实施顺序

1. 先执行 `2026-07-17-stage08-runtime-foundation-implementation-plan.md` 中的 Package A。
2. Package A 验收后再为 Package B 编写并审批独立的迁移/API/安全计划，因为自动 Memory 引入新的留存与删除合同。
3. Package B 在 local PostgreSQL 中完成并被观察后，再联合编写与审批 Package C、D 计划。
4. 检索合同稳定后再编写与审批 Package E；避免让协调器依赖暂定 schema。
5. Package F 在 A-E 期间增量实施；Milvus 决策必须以测量证据而非预测为依据。

## 项目级验收证据

- 合同、拒绝、预算、幂等、策略与脱敏的 unit tests；
- 每个持久化实施包的 local PostgreSQL migration 和事务测试；
- 使用显式 actor/employee/chat scope 的 API contract tests；
- 只使用合成数据的、隔离的真实 Provider 评测；
- 每包独立 evidence 文档，记录命令、结果、数据边界与剩余风险。

