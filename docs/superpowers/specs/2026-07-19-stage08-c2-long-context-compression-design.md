# Stage08 C2 长群上下文与临时压缩设计

## Status

- Design status：用户于 2026-07-19 确认采用本设计方向；在将其写回 Stage08 BDD、D3 decision 和实施计划前保留本文件作为设计真源。
- Scope：C2 的受控群消息投影、长窗口选择、D3 `best_effort_group_deletion`、可受控删除，以及 C3/E 的临时上下文压缩分层。
- Out of scope：不改变 C1 v1；不把群上下文摘要写入 `MemoryItem`、候选记忆、RAG、pgvector、Redis、AgentRun、审计或日志；不新建 Telegram HTTP client、webhook endpoint、公开 API、Mini App 页面或 Provider 调用。

## 1. 已确认的产品语义

`context` 是当前 Agent 调用可见、调用结束即丢弃的信息；`memory` 是跨调用保存并可以再次检索的信息。群上下文的压缩摘要属于前者：它不能因为“摘要有价值”而自动进入后者。

长期可复用的群结论、风险、偏好或决策仍只能走既有 Package B Memory 候选、权限、确认、审计和生命周期路径；本设计不增加群消息到 Memory 的旁路。

## 2. 已确认的 D1–D6 值

| 决定 | 已确认值 |
| --- | --- |
| D1 原文治理 | 只为新到达且已授权的 group/supergroup 创建受控最小投影；历史 `Message.raw_text`、`raw_caption`、`normalized_text` 永不作为 C2 读取来源，不回填、不因本任务删除历史 Message。 |
| D2 长上下文 | 每个合格群最多 120 个投影片段、来源最大年龄 30 天、单片段 500 Unicode code points、C2 原始工作窗口最多 60,000 code points；最终给 Agent 的固定群上下文窗口为 24,000 code points。 |
| D2 压缩 | 若合格原始窗口超过 24,000 code points，保留最新 24 个片段（最多 12,000 code points），把其余已选历史压缩为最多 12,000 code points 的短命 `GroupContextDigest`。不足 24,000 时不调用压缩。来源超过 120 条时，history 继续按 7 天 half-life、`event_at DESC`、内部稳定 tiebreak 选择。 |
| D3 lifecycle | `best_effort_group_deletion`：新消息和已知 edit 更新形成可重读 version；受控人工删除和 30 天 retention purge 立即擦除投影正文并使当前调用失效。普通群删除/revoke 不是 Bot API 可可靠获得的事实，不能承诺自动即时失效。 |
| D4 业务关联 | 使用 active、版本化的 Stage06 binding → 单一 C1 customer `PlatformRecord` + 单一 project `PlatformRecord` 映射。空值、多个 active mapping、workspace 不一致或 relation 漂移全部 fail closed。 |
| D5 authority | 只有内部 `Stage08GroupContextAuthorityFactory` 能从已验证 actor、employee 和当前 workspace 自行解析 binding/mapping，产生不可序列化的内存 authority。HTTP、Mini App、Telegram update、outbox、audit 和客户端 JSON 都不能构造它。 |
| D6 evidence | `label=group_context`，`source_type=group_message_fragment`，呈现 ID 为 `group_context:NN`；scope 仅公开 `workspace/group/customer/project` 维度类别而不公开值。C3 独占 merge、全局预算与 renderer；C3 前 C2 pack 不可被消费者使用。 |

## 3. 分层架构

```text
existing trusted Telegram ingress (new / edited update only)
  -> controlled group projection (new rows only; no historical raw read)
  -> C2: authorization + lifecycle re-read + 120-fragment window
  -> C3: merge and global budget decision
  -> E Coordinator: ephemeral ContextCompressor when C2 window > 24,000 chars
  -> latest raw fragments + ephemeral digest
  -> one current Agent invocation
  -> process state discarded; no Memory write
```

为实现 D1，旧 C2 “不触及 parser/ingestion”边界需缩窄为：不得新增 Telegram 网络、webhook、polling 或外部读取；允许在**既有、已验证的入站持久化事务**中，为 new/edited update 写入最小投影。这个例外不读取历史 raw column、不回填、不发 Telegram，也不改变用户授权模型。

C2 不调用 LLM。它只构建内部、不可序列化的 `GroupContextWindow` 和一个固定 `compression_required` 信号。C3 决定该群窗口与表格/Memory evidence 的总预算；E Coordinator 才通过已批准的 Provider 路径调用 `ContextCompressor`。这确保“自动总结”不会偷渡到 C2、也不会绕过后续真实 Provider 评测。

## 4. D3 数据合同与物理数据边界

### 4.1 受控群消息投影

新表名建议为 `stage08_group_message_projections`，仅用于新接收的 group/supergroup 消息。每行包含：

- 仅内部可见的 source `Message` reference 与 active group-business mapping reference；
- `content_fragment`：入站时规范化并截断到 500 code points 的正文或 caption 片段；它是唯一允许持久化的群正文副本；
- `content_version`、`event_at`、可选 `edited_at`、`retention_expires_at`、`lifecycle_status` 和内部稳定 tiebreak；
- 不输出的 chat/message/update/source identifiers，且不允许进入 DTO、renderer、audit、error、trace、cache 或测试快照。

`event_at` 的初始值来自 Telegram `message.date` 转成 UTC；late delivery 只影响入库时间，不能改变排序。同一 `event_at` 仅使用内部 tiebreak；tiebreak 不可输出。old Message row 一律没有该合同，永远不可读。

编辑 update 写入新的 `content_version`，先前版本改为 `superseded`。受控删除调用只接受 server-side authority 和内部 projection handle：立即擦除 `content_fragment`，标记 `purged`，并让当前运行的 digest/window 作废。它不创建公开删除 route，也不允许客户端传 chat、message 或 binding ID。

普通群删除不产生可靠 Telegram update，因此 `best_effort_group_deletion` 只承诺：已知 edit、受控删除和 retention 期满会生效；未知的远端删除至多会保留到 30 天。Telegram 官方 `Update` 对普通群列出 `message` 和 `edited_message`，而 `deleted_business_messages` 只针对 connected-business 场景。该约束必须显示在运行和验收语义中。

### 4.2 Group-business mapping

新表名建议为 `stage08_group_business_context_bindings`。每个 active 行以 Stage06 chat-user binding 为根，绑定同 workspace 的一个 customer record 和一个 project record，并含 `mapping_version`、`status` 与创建/更新时间。数据库和服务共同保证：一个 binding 在同一时刻最多一个 active mapping；所有引用 record 经 table/base 重读后仍属于相同 workspace；任一歧义或状态变化使整个群 source unavailable。

### 4.3 删除与保留

`retention_expires_at = event_at + 30 days`。读取时过期立即不可用；受控 purge service 物理擦除 `content_fragment`，同时使所有带有该内部 source reference 的临时 window/digest 在下一次下游调用前重新构建。C2 不自行创建 scheduler、API 或审计正文；生产定时触发方式属于后续运行/部署配置，但 C2 必须提供可测试、幂等、无正文输出的 purge service。

## 5. 固定窗口、压缩和失效

1. C2 重读 authority、binding、member、employee、mapping、projection lifecycle 与 retention，只从一个合格 group/supergroup 选择最多 120 个片段。
2. `GroupContextWindow` 的原始字符数最多 60,000。最新 24 个片段按 `event_at DESC, tiebreak DESC` 保留；其余片段作为 history 候选，超过容量时按 7 天 half-life 选择。
3. C3 合并后，E Coordinator 计算该群部分是否超过 24,000 code points。未超限时直接使用受限片段；超限时提交一个调用内 `ContextCompressor` 请求。
4. `ContextCompressor` 输出最多 12,000 code points 的 `GroupContextDigest`，只应保留事实、决策、待办、风险、时间条件与未解决问题；不得输出 chat/member/customer/project/source identifier，也不得自行提出外部操作。
5. 最终群 context 是 digest（最多 12,000）加 24 条最新片段（最多 12,000），总量固定不超过 24,000 code points。任何字段或群级超限产生 count-only omission；至少一个片段可用但发生 omission 为 `group_context_partial`。
6. digest/window 的内部 source-version set 只留在当前调用的私有内存。每次下游 LLM/tool invocation 前重新验证；发现 version、mapping、member、scope、purge 或 retention 漂移时丢弃 digest 并从当前投影重建。该 private set 绝不写 LangGraph checkpoint、日志、audit、Redis 或数据库。

## 6. 安全与失败语义

- 任何 D1–D6 缺失、employee/caller/member/binding/mapping 无效、private/channel、歧义、workspace 不一致或没有合格投影时，返回 `group_context_unavailable`，并在任何正文查询前停止。
- `group_context_partial` 只说明有片段可用但有数量、字符、max-age 或预算 omission；omission 不能暴露被丢弃来源的 identity/text。
- `group_context_available` 表示至少一个片段可用且没有 eligibility/age/budget omission；它不表示 Telegram 普通群 delete/revoke 已被可靠观测。
- 任何 LLM compression failure、timeout、cancellation 或 redaction validation failure 均丢弃 digest，并只使用仍可容纳的最新安全片段；不能将原始 60,000-char window 绕过预算直接送给 Agent。

## 7. 阶段边界与验收

### C2 实现

- 最小投影 schema、版本/edit、30 天 retention/purge service、D4 mapping、opaque authority、长窗口选择、固定 DTO/status/omission 和 local PostgreSQL lifecycle evidence。
- 不实现 Provider 调用、可见删除 API、Memory 写入、RAG/pgvector、Redis、LangGraph/checkpoint、C1 改动或前端。

### C3 实现

- C1/C2 pack merge、跨 source 全局预算、`compression_required` 传播、统一 renderer 与无泄漏回归。

### Package E 实现

- 受控的 `ContextCompressor` Provider 调用、短命 digest state、每次下游调用前 source revalidation、压缩失败 fallback、真实 LLM 质量/成本/泄漏评测。

### 最低验收证据

- C2 单测：120/30 天/500/60,000/24,000/12,000 固定边界、稳定排序、half-life、状态/omission、authority 伪造、source carrier 和旧 raw 禁止。
- C2 local PostgreSQL：edit version、mapping/member/scope 漂移、expiry、受控 purge、双会话 re-read 与 legacy row fail closed。
- C3/E 后续：压缩只在超 24,000 时触发、digest 不持久化、失效后 rebuild、provider failure fallback、真实 Provider 质量/隐私/成本 evidence。

## 8. 明确不做

- 不读取、迁移或回填历史 `Message` 原文；不把 `content_fragment` 当作长期 Memory；不创建自动从群文本提取 Memory 的路径。
- 不承诺普通群远端删除的即时侦测；不新增 Telegram 网络调用或 webhook endpoint。
- 不在 C2 提前实现 C3 merge、E Coordinator、LLM compression 或生产定时部署。
