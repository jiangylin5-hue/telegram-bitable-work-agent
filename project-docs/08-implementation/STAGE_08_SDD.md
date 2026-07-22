# Stage08 分包开发设计（SDD）

## Status

- Scope：Stage08 A-F 的实现顺序、模块责任、TDD、迁移、回滚和证据约束。
- Status：approved planning baseline；执行每个包前需确认其详细实施计划。

## A. Runtime Foundation

**目标：** 把 Manifest 的匹配结果变成只可调用 allowlist adapter 的 `ExecutionPlan`。

**实现单元：** contracts、execution budget、ticket model/migration、policy evaluator、tool gateway、服务编排、runtime API、审计/幂等、评测器子进程隔离。

**关键测试：** 未授权工具、超预算、同键重放/冲突、字段投影、草稿未确认、无 send path、ticket 并发、超时 case 不阻塞后续 case。

**退出条件：** 每个工具只经既有 service boundary；local PostgreSQL 证明 ticket/幂等；API 不能接收 raw prompt-like 输入；无新的外部写入。

## B. Business Memory

**目标：** 建立版本化、有来源、有 TTL、可撤销的 Memory。

**实现单元：** Memory/Source/Candidate 模型与迁移、表格事件 adapter、群聊高置信提取 graph、冲突检测、scope projection、删除/撤权队列与 audit。

**关键测试：** 同一来源幂等、冲突不覆盖、跨 workspace/群/项目拒绝、过期不可读、删除后 chunk 不可检索、群聊原文不写入 payload、审计脱敏。

**退出条件：** 表格与群聊两类来源有完整 provenance；删除/TTL/撤权在读取路径即时 fail closed。

## C. Context Engineering

**目标：** 用最小、可解释上下文支持实时查表、群聊和通用建议。

**实现单元：** `ContextPlan`、最近群窗口、历史时间衰减选择器、客户/项目关联 resolver、context compressor、evidence label renderer。

**关键测试：** 全表/全群不进 prompt、窗口顺序、超限截断、撤权 reread、资料不足转 `general_advice`、引用标签准确。

**退出条件：** 一次运行可证明为什么读取、读取多少、未读取什么，且原始群聊不被持久化。

## D. RAG and Indexing

**目标：** 为文件、可沉淀摘要和 Memory 提供可重建的混合检索。

**实现单元：** source ingest/versioning、文本提取投影、chunker、embedding adapter、pgvector index、关键词/结构化过滤、rerank、reindex/delete worker、`RetrievalProvider`。

**关键测试：** source 替换、partial index failure、删除 tombstone、前后权限核验、带过滤 HNSW 召回、无来源引用拒绝、provider fallback。

**退出条件：** PostgreSQL 迁移、rebuild、删除和权限测试通过；Milvus 未被引入。

## E. LangGraph Collaboration

**目标：** 实现 Coordinator 与七类专长节点的类型化协作。

**实现单元：** graph state、planner、并行 read fan-out/fan-in、analyst、draft、policy gate、cancellation、checkpoint 选择、run resumption、terminal mapper。

**关键测试：** 并行读取预算、子图失败降级、禁止 analyst 直接工具调用、draft 必经 policy、取消不会遗留 running ticket、状态机终态不可逆。

**退出条件：** 复杂请求有可读 trace；任一子图不能提升权限或跨越 action tier。

## F. Quality and Operations

**目标：** 将可靠性、质量、成本和检索扩展决策变成可量化门禁。

**实现单元：** 标注语料、golden assertions、真实 provider runner、时间/成本/召回遥测、red-team 权限集、SLO 报告、Milvus assessment。

**关键测试：** 每 case 独立超时、失败隔离、并行上限、无原始输出留存、回归阈值、模型切换、retrieval outage。

**退出条件：** 有可重复的合成 live suite 和真实 Provider 脱敏指标；Milvus 仅在触发门槛满足时进入技术决策。

## 共同工程规则

每包都遵循：先写 BDD/安全合同 -> 写失败测试 -> 最小实现 -> focused tests -> local PostgreSQL -> 证据文档 -> 独立审查。不得用总测试数量替代包级验收，不得以 Provider 成功替代权限/数据库/草稿验证。

