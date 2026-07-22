# Stage08 C2 D3 群长上下文数据合同决策记录

## Status

- Document status：approved decision / C2 Task 4 implementation and independent review complete。
- Scope：固定 C2 的 D1–D6、受控群消息投影、D4 mapping、D5 authority、长窗口和 C3/Package E 交接合同。
- Current Progress：2026-07-20 C2 Task 1–4 已完成任务级 TDD 与独立复审。C2 现有 source provenance `group`/`supergroup`/`unknown`、受控 ingress、private authority、fresh materialization、窗口预算、expiry/purge 和 PostgreSQL 迁移/回退证据；Task 5 将完成 package-level drift/privacy 收口和 C3 handoff。C2 仍无公开 API、Provider、Telegram network、Memory/RAG/C1/C3 merge 或部署行为。
- Decision：采用 `best_effort_group_deletion`，群长窗口是单次调用的 Context，不是 Memory。

## 1. Scope 与非目标

本决策记录是 C2 D2/D3 实现的唯一合同权威。C2 将在已有、已验证的 Telegram 入站持久化事务中，仅对新到达的授权 group/supergroup 消息和已知 edit 写入最小受控投影；之后按当前 authority、mapping、business scope、lifecycle 和 retention 重读并选择私有长窗口。

本决策不授权：

- 读取、迁移、回填或删除历史 `Message.raw_text`、`raw_caption`、`normalized_text`；
- 新建 Telegram 网络请求、webhook endpoint、polling、公开 API、Mini App 入口或发送路径；
- C2 调用 Provider、生成摘要、合并 C1/C2、执行全局预算或给 Agent 渲染可消费上下文；
- 把群正文、窗口、digest 或 source-version set 写入 Memory、candidate、数据库、Redis、RAG/pgvector、`AgentRun`、audit、log 或 LangGraph checkpoint；
- 声称普通群远端 delete/revoke 可被 Bot API 可靠、实时感知。

## 2. 事实、Context、Memory 与知识库分层

| 层级 | 定义 | C2 边界 |
| --- | --- | --- |
| 表格事实 | 可审计、实时业务事实的真源 | C2 只用已授权 customer/project record 收窄 scope，不以群文本覆盖表格事实 |
| Context | 当前调用的受权实时现场信息，调用结束后丢弃 | `GroupContextWindow` 与未来的 `GroupContextDigest` 只能属于此层 |
| Memory | 跨任务可复用的协作经验，必须通过既有 Package B 的 candidate、权限、冲突、审计和生命周期门槛 | C2 不得创建或提升 Memory；任何长期结论必须走 Package B |
| 知识库 | 稳定资料及其可重建检索投影 | C2 不将群窗口或 digest 写入 KnowledgeSource、RAG 或向量索引 |

因此，临时 `GroupContextDigest` 即使包含有价值的决策、风险或待办，也仍只是当前 invocation 的 Context，不得变成 Memory 或知识库条目。

## 3. 已确认 D1–D6

| Decision | Binding value |
| --- | --- |
| D1 原文治理 | 仅 new authorized group/supergroup inbound message 和 known edit 创建受控投影。历史 `Message.raw_text`、`raw_caption`、`normalized_text` 永不是 C2 input，不回填，也不由本任务删除。 |
| D2 长窗口 | retention 30 天；最多 120 fragments；单片段 500 Unicode code points；raw work window 最多 60,000 code points；最终 group context 最多 24,000 code points；最新 24 raw fragments 最多 12,000 code points；ephemeral digest 最多 12,000 code points；history half-life 7 天。 |
| D3 lifecycle | `best_effort_group_deletion`。known edit、server-authorized purge 与 retention expiry 是可靠失效事实；普通群远端 delete/revoke 没有通用可信 Bot API event，不得承诺自动立即失效。 |
| D4 业务关联 | 一个 active Stage06 `chat_user` binding 必须映射到且仅映射到一个当前同 workspace customer `PlatformRecord` 和一个 project `PlatformRecord`。null、歧义、多 active mapping、workspace 不同或 relation drift 全部 fail closed。 |
| D5 可信 authority | 仅内部 `Stage08GroupContextAuthorityFactory` 可从 verified actor、employee 和 current workspace 自行解析 binding/mapping，并创建非 Pydantic、非 JSON、不可序列化的私有 authority。HTTP、Mini App、Telegram update、outbox、audit 或客户端字段均不能构造它。 |
| D6 evidence | `label=group_context`，`source_type=group_message_fragment`，display id `group_context:NN`。scope 只暴露维度类别，不暴露值。C3 前 C2 不可被消费；C3 独占 C1/C2 merge、全局预算和 renderer。 |

## 4. D3 精确数据合同

### 4.1 `stage08_group_business_context_bindings`

| Field | Contract |
| --- | --- |
| `id` | 内部 UUID primary key，不进入公开输出 |
| `workspace_id` | 当前 workspace reference |
| `telegram_binding_id` | Stage06 active `chat_user` binding reference |
| `customer_record_id` | 同 workspace 的唯一当前 customer `PlatformRecord` reference，不可为 null |
| `project_record_id` | 同 workspace 的唯一当前 project `PlatformRecord` reference，不可为 null |
| `mapping_version` | 从 1 开始的单调版本 |
| `status` | `active` 或 `inactive`；一个 `telegram_binding_id` 同时最多一个 `active` mapping |
| `created_at` / `updated_at` | UTC 创建/更新时间，不代替消息 `event_at` |

数据库约束与 service re-read 必须同时保证 active uniqueness、workspace 一致与 customer/project relation 当前有效。任一失败均使整个 group source unavailable，不得退回到其他 mapping。

### 4.2 `stage08_group_message_projections`

| Field | Contract |
| --- | --- |
| `id` | 内部 UUID primary key，同时可作为同 `event_at` 的稳定内部 tiebreak；不得输出 |
| `source_message_id` | 仅指向本功能启用后由同一 trusted ingress transaction 处理的 new/edited `Message` row；不授权读取该 row 的历史 raw 字段 |
| `business_context_binding_id` | 创建时的 active group-business mapping reference |
| `content_fragment` | 入站时规范化、最多 500 Unicode code points 的正文或 caption 片段；这是 C2 唯一允许持久化的群正文副本 |
| `source_chat_type` | 不可变内部 provenance：仅 `group`、`supergroup` 或 migration 安全值 `unknown`；历史 `unknown` 永不可读。它不保存 chat ID、message ID、用户名或正文，且不进入公开输出。 |
| `content_version` | 从 1 开始；同一 `source_message_id` 的每个 known edit 创建下一版本；`(source_message_id, content_version)` 唯一 |
| `event_at` | Telegram `message.date` 转换为 UTC；新版本不改写源消息事件顺序 |
| `edited_at` | known edit 时的可选 UTC 时间；只表达已知 edit，不用作源消息排序时间 |
| `retention_expires_at` | 精确为 `event_at + 30 days`，且必须大于 `event_at` |
| `lifecycle_status` | `active`、`superseded` 或 `purged`；只有未过期 `active` 版本可读 |
| `created_at` / `updated_at` | UTC 投影行时间，仅用于内部生命周期，不改变 `event_at` 排序 |

空或不安全内容不创建可读投影。known edit 创建新 version 并将前一 active version 改为 `superseded`。server-authorized purge 与 retention expiry 必须幂等擦除 `content_fragment`并标记 `purged`；已过期、`superseded` 或 `purged` 行均不可列为 active source。该投影及 source/mapping reference 均不是 API contract。

### 4.3 允许的 ingress 例外

“不新增 ingestion”的精确含义是：C2 不新增 Telegram 网络、webhook endpoint、polling、outgoing request 或历史 raw read；允许既有 verified local ingress transaction 在同一本地事务内对 new/edited update 写入上述受控投影。入站路径不得构造 D5 authority，也不得因投影写入触发 Provider、Telegram 发送或 Memory 写入。

## 5. 窗口、status 与 omission 合同

1. 在查询正文前重读 D5 authority、active binding/member/employee、D4 mapping、business scope 与 projection lifecycle/retention。
2. 只从一个当前合格且 `source_chat_type` 为 `group`/`supergroup` 的来源选择 30 天内、最多 120 个、每个最多 500 code points 的片段，raw window 最多 60,000 code points。`unknown` 只用于 migration 安全回填，永不作为 Context source。
3. 最新 24 个按 `event_at DESC, internal_tiebreak DESC` 保留，最多 12,000 code points；远端晚到达仅影响入库时间，不改变 `event_at` 顺序。
4. 其余 history 只按 7 天 half-life 的时间衰减、`event_at DESC` 与内部稳定 tiebreak 选择；不按 query、正文、关键词、embedding 或 LLM 排序。
5. C2 只输出私有、不可序列化的 `GroupContextWindow`，并按 `compression_required = raw_selected_chars > 24000` 设置信号。C2 不压缩、不调用 Provider、不产生 digest。

| Status | Exact condition | Safe output |
| --- | --- | --- |
| `group_context_unavailable` | authority/scope/mapping 无效，类型为 private/channel，无 eligible source，或全部 source 在重读时失效 | 空 private fragments；仅固定 count/status omission，无 text/identity |
| `group_context_partial` | 至少一个安全 fragment，且发生任何 count、char、age 或 budget omission | 仅选中的私有 fragments 与 count-only omission |
| `group_context_available` | 至少一个安全 fragment，且无 eligibility、age、count、char 或 budget omission | 仅当前重读通过的私有 fragments |

`GroupContextWindow` 的可验证/可观测投影仅允许 contract version、status、计数、预算用量和 `compression_required`；禁止 fragment text、raw identifier、UUID、binding/source reference、token、permission 或 scope value。

## 6. D5 authority 与重读边界

`Stage08GroupContextAuthorityFactory` 的输入只能是 verified `Actor`、`employee_id` 和 current `workspace_id`，并通过 UoW 自行解析当前 binding/mapping。它返回的 `_GroupContextAuthority` 和受控 purge 使用的 `_GroupProjectionHandle` 都是进程内私有对象，不是 Pydantic model、API parameter 或 JSON carrier。

在 window build 与每次后续 LLM/tool invocation 前，使用方必须重读 employee/caller/member/binding/mapping/business relation/version/purge/retention。任一 drift 都必须丢弃已有 window/digest 并从当前投影重建；不能将旧 fragment 降级为 Memory 或 general advice。

## 7. C3 / Package E 交接

- C3 仅在其独立合同通过后才可消费私有 C2 window，并负责 C1/C2 merge、跨 source 全局预算、信号传递与统一 renderer。
- 只有 Package E 可在未来已批准 Provider 路径中调用 `ContextCompressor`。它在 `compression_required=true` 时将非最新历史压缩为最多 12,000 code points 的调用内 `GroupContextDigest`，与最新 24 个 raw fragments（最多 12,000）组成最多 24,000 code points 的群 Context。
- compression failure、timeout、cancel 或脱敏失败时，未来 E 只能降级到仍符合预算的最新安全片段，不得直接把 raw work window 送给 Agent。
- digest 只在当前 invocation 的 process-local private memory 中存活，不得写入 `MemoryItem`、candidate、database、Redis、RAG/pgvector、`AgentRun`、audit、log 或 LangGraph checkpoint。

## 8. Lifecycle 事实与验收证据

| Fact | 必须的未来证据 |
| --- | --- |
| new/edit projection | unit 证明仅 mapped authorized group/supergroup new/edit 创建投影，不枚举历史 raw |
| version/order | unit + local PostgreSQL 证明 edit 产生新 version、旧 version superseded，且 late delivery 不改变 `event_at` 排序 |
| mapping/authority | unit + local PostgreSQL 证明 null/歧义/drift/wrong workspace/private/channel 在查正文前 fail closed |
| retention/purge | local PostgreSQL 证明过期同步不可读、purge 幂等擦除正文、并发 reader 不输出 stale fragment |
| budgets/status | table-driven unit 证明 30/120/500/60,000/24,000/24/12,000/7-day 边界、status/omission 与 `compression_required` |
| privacy/isolation | negative serialization/static scan 证明无 text/identifier carrier，无 Provider/Telegram network/API/Memory/RAG/Redis/LangGraph 副作用 |

本 Task 1 只产生文档合同，不得声称上述实现证据已存在。进入 Task 2 前必须先完成本文档包的 review；当前 C2 代码、migration 和测试仍为 unimplemented。
