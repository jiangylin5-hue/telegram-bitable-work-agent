# Stage08 Package E：LangGraph 多数字员工协作设计

## 状态与范围

- Status：`基于用户已确认的 Stage08 架构、Package A-D 已关闭后的实施设计`
- Scope：在不改变 Package A-D 的权限、Memory、Context、RAG、草稿与审计真源的前提下，实现一个 LangGraph 协调器，把受控上下文、群聊窗口、检索结果和草稿动作组织成可取消、可降级、可审计的协作运行。
- 不在范围：真实 OpenRouter/embedding 调用、生产部署、Milvus、Telegram 发送、文档上传、一般用户可写记录、持久化 LangGraph checkpoint、原始 prompt/response/群正文/检索正文的长期留存。

## 方案比较与选定方案

| 方案 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- |
| 直接把现有 Stage06 Live Agent 扩展为总控 | 改动少 | 会混淆旧 AgentRun、允许原始 prompt 模式，并把权限/上下文边界藏在单个节点中 | 不采用 |
| 纯确定性编排，不保留 Provider 端口 | 最安全 | 无法承接长群上下文压缩、分析与后续真实 LLM 评测 | 不采用 |
| **类型化 LangGraph + 私有端口 + 默认不可用 Provider** | 可并行读取、权限可复核、测试可注入确定性适配器，Package F 可独立接真实模型 | 初期运行时会在需要模型能力时显式降级 | **采用** |

## 核心架构

```text
POST /api/stage08/assistant/query
  -> 已验证 identity + 服务端 scope resolver
  -> AssistantQueryCommand（不含有效权限、字段白名单或检索 filter）
  -> Stage08CollaborationCoordinator / LangGraph
       plan
       -> fan-out: C3 composite context | D4 retrieval | general-advice marker
       -> fan-in
       -> optional process-local group compression
       -> analyst provider port
       -> policy gate
       -> optional existing Tool Gateway draft path
       -> terminal mapper + safe AgentRun/audit
  -> AssistantQueryResponse（安全 answer、引用标签、可选 draft ref）
```

协调器只编排，不直接访问 ORM、SQL、Telegram、HTTP 或 provider key。所有业务读取继续通过 C3/D4/Stage06 service boundary；所有草稿继续经过既有 `ExecutionPlan -> Stage08ToolGateway -> RecordChangeDraft`；最终权限以调用时的 caller、employee、workspace、view/field、群绑定、业务关系与 source lifecycle 的交集为准。

## 协作状态和节点边界

### 1. 私有 process-local 状态

LangGraph `Stage08CollaborationState` 只在一次请求进程内存中生存，包含：服务端命令、当前 actor、私有 C3 composite、私有 D4 evidence、子节点结果、取消令牌、预算用量和 terminal reason。它不得作为 API 输入/输出、日志、审计、Redis value、数据库行或 LangGraph checkpoint 被序列化。

图以 `checkpointer=None` 编译。请求取消或进程中断不会恢复一个旧的私有状态；“重试/恢复”只能从原始受控 command 重新开始，并重新计算所有权限、source 和业务关系。

### 2. 节点职责

| 节点 | 允许做什么 | 禁止做什么 |
| --- | --- | --- |
| `plan_request` | 解析已验证 command、派生固定预算、确认 employee 当前状态 | 读取表、检索、调用模型、写入 |
| `read_composite_context` | 调用 C3 `compose`/`render` 的私有接口并消费当前证据 | 保存群正文、扩大 view/group scope |
| `read_retrieval` | 用 D4 opaque authority 和 provider 搜索，再拿私有 evidence/safe citations | 用 source/chunk 命中代替授权、泄露分数/ID |
| `mark_general_advice` | 在允许时写入无事实依据标记 | 伪装为业务事实 |
| `fan_in` | 合并标签化读结果，保留失败/省略原因 | 因一个子图失败丢弃其他合法证据 |
| `compress_group_context` | 仅在 C3 表示 `group_compression_pending` 时，通过私有端口生成当前 invocation digest | 把群正文/digest 写入任何持久化位置 |
| `analyse` | 将已授权材料交给分析端口，验证结构化答复 | 再读工具、创建草稿、编造事实 |
| `policy_gate` | 校验动作 tier、引用、预算、current authority、草稿契约 | 自行确认草稿或绕过 Tool Gateway |
| `materialize_draft` | 仅对通过 gate 的 `draft_update` 调用既有 ticket/Tool Gateway | 直接更新 record 或 Telegram 发送 |
| `finalize` | 生成安全 API DTO、最小 AgentRun/audit 摘要 | 持久化原始 query/answer/evidence/私有状态 |

### 3. 并行、预算和取消

- `read_composite_context`、`read_retrieval`、`mark_general_advice` 使用 LangGraph fan-out/fan-in；最大并发读子图为 3。
- 每个 run 固定：图深度最多 3、读子图最多 3、检索 chunk 最多 12、总 wall-clock 30 秒、单 provider 20 秒、重试最多 2 次。
- 取消在每个节点边界与 provider 调用前后检查；任一取消使运行进入 `cancelled`，不产生草稿或外部动作。
- 单个只读子图失败写入固定 reason 并降级：若仍有合法业务证据则继续分析；否则只有 `general_advice` 才可返回建议；没有 advice 权限时 `no_evidence`。任何权限、source lifecycle 或私有状态重验失败均 fail closed。

## Provider 与长上下文策略

Package E 定义两个内部端口：`ContextCompressor` 和 `AnalysisProvider`。两者均可由测试注入确定性 fake；默认运行时是 `Unavailable`，不会发生网络调用。

当 C3 状态为 `group_compression_pending` 时，协调器是唯一允许调用 `ContextCompressor` 的组件。压缩输入、私有 source-version set 和输出 digest 都被封装为不可序列化对象，只存活到 `finalize`。端口不可用、超时或校验失败时丢弃群上下文，保留可用 C1/RAG 证据，或按规则降级；绝不缓存/记忆化原文或摘要。

`AnalysisProvider` 输出必须是严格 schema：`answer_text`、只含本次安全 display ordinal 的 `citation_ordinals`、`action`、可选 `draft_intent`。它不能输出 record/source/chunk ID、字段键、权限、工具调用、raw prompt 或 chain-of-thought。真实模型选择、质量阈值、成本/延迟和真实调用属于 Package F。

## 公共 API 和持久化

`POST /api/stage08/assistant/query` 请求仅包含：`workspace_id`、`employee_id`、`intent`、`query`、`requested_action`、可选 `target_record_id`、`idempotency_key`。`query` 最多 600 code points，只在本次内存运行中使用；审计、AgentRun、idempotency 和 error 不存储它。

客户端不能提交 view/base/table/field/group/customer/project scope、检索 filter、Memory scope、有效权限、role、employee policy、budget、tool invocation、draft values、ticket/terminal state。服务端从 employee 的可访问 views（最多前三个、稳定排序）、当前 actor、目标记录与现有 C1/C2/D4 规则派生这些事实。

响应只含 `status`、安全 `answer`、安全 citation labels、`degradation_codes`、可选当前用户可读的 `draft_id`；没有原始证据、UUID/source/chunk/field、score/vector、authority、provider 或错误细节。复用现有 `AgentRun`，但只写 graph version、terminal state、计数、固定错误/降级码、引用数量、ticket/draft reference 是否存在和聚合时延；不需新增 schema/migration。

## 草稿、权限和幂等

`requested_action=read_only` 不产生 ticket/draft。`requested_action=draft_update` 仅在 employee 当前允许 `draft_update`、目标 record 当前可见且 `AnalysisProvider` 的结构化 `draft_intent` 通过 policy gate 时可继续。gate 重新读取 employee/member/record/view/field/source，并使用现有 `begin_execution_plan`、idempotency、ticket、Tool Gateway 与 `RecordChangeDraft` 服务；产物只能是 `pending_confirmation` 草稿。

同一 workspace、actor、employee、intent、请求动作、目标 record 和规范化 query 的相同 idempotency key 必须安全重放同一安全 response；不同语义冲突为 409。query 本身不进入 fingerprint 的可读日志，只在内存中哈希。任何失败/撤权/取消都不得留下 `in_progress` 幂等记录、草稿或未终结 ticket。

## 验收与风险

Package E 通过条件：图 topology/state 校验、并行/预算/取消/降级、C3/D4 current-state reread、无 checkpoint/泄露、policy-before-draft、ticket/idempotency/audit、API redaction 和真实 local PostgreSQL 回归均通过独立复审。

已知风险：默认 Provider 不可用时不会产出真实模型质量；这是刻意限制，Package F 必须在合成数据隔离中真实评测后才可启用。D5 API 测试 warning filter 的非阻断卫生项不被本设计扩大或忽略。
