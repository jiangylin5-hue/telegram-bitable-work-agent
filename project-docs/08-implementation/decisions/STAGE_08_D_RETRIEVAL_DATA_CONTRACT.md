# Stage08 Package D：RAG、pgvector 与检索安全数据合同

## Status

- Current Progress Update (2026-07-21)：Package D D0–D5 已关闭。最终独立复审为 `0 Critical / 0 Important / 1 Minor`；disposable pgvector 中 migration `20260720_0032 → 20260720_0031 → 20260720_0032`、唯一 head、`vector=0.8.5`、GIN/HNSW 以及 D1–D5 matrix `236 passed / 0 skip` 均已真实验证。D5 的 held-session member/source/Memory revoke 均拒绝且不会新建 outbox/audit/idempotency，测试后 source/chunk/outbox/idempotency/audit 均为 0。唯一 Minor 是 D5 API test module 对既有 Starlette deprecation warning 的类别级测试过滤范围可继续收窄；它不作用于 production code，不阻断 Package D，记录为后续测试卫生项。Package E 可按既定 LangGraph 协作计划开始；真实 provider、Telegram、生产部署仍未开始。

- Document status：`approved implementation boundary derived from the user-approved Stage08 plan`。
- Scope：Package D 的 `KnowledgeSource`、`KnowledgeChunk`、受控索引事件、`RetrievalProvider`、检索前后授权、引用安全投影、pgvector 环境门禁与留存行为。
- Current Progress：2026-07-21 Package D 已完成 D0 专用 disposable pgvector environment 与 D1 strict contracts/ORM/migration；D2 source projection、deterministic chunking、Memory root-lineage lifecycle 和 reference-only outbox 已在两轮修复后通过第三次独立复审（`0 Critical / 0 Important / 0 Minor`，D2 40、D1+D2 96、Memory+D2 124）。D3 index worker/test embedding/cleanup state machine 已在首轮 review 的 replay drift、post-lock read exception、embedding overflow 三项修复后通过 fresh independent review（`0 Critical / 0 Important / 0 Minor`；77 D3、133 D1+D3、161 Memory+D3、7 dedicated pgvector）。D4 已关闭：首轮 review 的 identity-map stale revalidation、lifecycle timestamp 与 Memory root fingerprint 缺口以局部 `populate_existing` + `no_autoflush` current-state read 收口，fresh independent review 为 `0 Critical / 0 Important / 0 Minor`（112 provider/service、178 D1-D4、15 dedicated pgvector；`vector=0.8.5`、head `20260720_0032`、cleanup 为 0）。D5 受控 reindex API 与 Package D 最终 PostgreSQL evidence 现可开始；尚未创建真实 embedding/LLM provider 调用或任何外部 provider 行为。现有 `STAGE06_LOCAL_DATABASE_URL` PostgreSQL 18 未安装 `vector` 扩展，不能作为 Package D 证据；专用 Docker pgvector 仍仅用于 D 的 disposable integration。
- Preconditions：Package A/B/C 已关闭；PostgreSQL 是事实、权限、来源、删除与审计真源；`pgvector` 是已确认首发索引技术，Milvus 不在本包范围内。

## 1. 目标和绝对边界

Package D 让数字员工能够从**已授权、可重建、可撤销的知识投影**中进行混合检索。它不把向量数据库当作业务真源，也不使向量命中本身成为读取授权。

允许的首发来源类型：

| `source_type` | 当前来源 | 内容来源与限制 |
| --- | --- | --- |
| `memory_item` | 已激活、当前可读的 `Stage08MemoryItem` | 只使用既有安全 projection；群聊原文、transport/source carrier、隐藏字段均不进入。 |
| `document_projection` | 已授权的文件/文档抽取投影 | 仅接收服务端 adapter 产出的安全文本投影；本包不新增客户端 raw 文件上传、文件下载或对象存储。 |
| `approved_summary` | 经未来受控工作流批准的摘要 | 必须有 source/version/scope；Package D 只定义承载合同，不创建 LLM 摘要。 |

禁止：

- 将 `Message.raw_text`、`raw_caption`、`normalized_text`、完整群窗口、C2 private authority/window、模型 prompt/response、chain-of-thought、密钥或隐藏字段写入 source、chunk、embedding metadata、日志、审计或 API；
- 由 HTTP/Mini App 客户端直接提交 `projection_text`、scope、filter、embedding、source status 或引用 ID；
- 使用向量索引反推权限、客户/项目范围、字段权限或删除状态；
- 在 Package D 调用外部 embedding/LLM/Telegram、启用 Milvus、写入业务记录、创建草稿、修改现有 C1/C2/B Memory 合同；
- 以未完成的文件 transport/解析能力冒充“已支持任意附件”。文件 adapter 只能接收其他受控服务已产生的投影。

## 2. 数据模型

### 2.1 `Stage08KnowledgeSource`

新表 `stage08_knowledge_sources` 是可重建索引的来源登记，不是业务事实副本。字段：

| 字段 | 规则 |
| --- | --- |
| `id` | UUID；仅内部、审计和 FK 使用，不进安全引用。 |
| `workspace_id` | 非空 FK；所有检索与生命周期的第一收窄维度。 |
| `source_type` | 仅 `memory_item`、`document_projection`、`approved_summary`。 |
| `source_ref` | JSON object；只含 server-derived entity kind/id/version reference，不含正文、transport、URL、token 或身份原文。 |
| `scope` | JSON object；至少 workspace，允许 customer/project/base/table/view/field 等**收窄**维度；禁止 group/chat/user 明细和任意扩权维度。 |
| `projection_text` | 可检索的安全文本投影；仅 `active` / `replaced` 的当前可重建版本可有正文。删除、撤权、过期后必须清空。 |
| `projection_hash` | `SHA-256`（64 hex），计算自规范化 projection 和 content version。 |
| `content_version` | 正整数、单 source reference 单调递增；同一 source 的旧版本不覆盖。 |
| `status` | `pending`、`active`、`replaced`、`revoked`、`expired`、`deleted`。 |
| `supersedes_id` | 可选自引用；只指向同 workspace、同 source logical identity 的旧版本。 |
| `valid_until` / `revoked_at` / `deleted_at` | 生命周期事实；到期或撤权在读取路径同步拒绝。 |

数据库约束至少保证 enum、JSON object、hash 格式、正版本、同 workspace 的 `(source_type, logical source fingerprint, content_version)` 唯一性，以及 active 版本不能携带空 projection。`source_ref` 和 `scope` 中任何 UUID 不得出现在 API、citation 或异常消息。

### 2.2 `Stage08KnowledgeChunk`

新表 `stage08_knowledge_chunks` 是 source projection 的可删索引片段：

| 字段 | 规则 |
| --- | --- |
| `id` | UUID；只在内部 FK 和重建校验使用。 |
| `source_id` / `workspace_id` | 非空 FK + 复制 workspace 收窄字段，二者必须一致。 |
| `source_version` / `ordinal` | 不可变来源版本和从零开始的稳定排序；`(source_id, source_version, ordinal)` 唯一。 |
| `chunk_text` | 源 projection 的连续片段；`indexed` 才可有正文。变为 `stale/deleted` 时必须清空。 |
| `chunk_hash` | 规范化片段 hash；支持可重建对比，不能替代正文权限检查。 |
| `keyword_terms` | 服务端从 `chunk_text` 生成的受限检索 token 数组；用于 GIN 关键词候选，不对外返回。 |
| `embedding_profile` / `embedding_version` | 已批准、固定维度 profile 的版本；未配置 production embedding 时只能为 `pending`，不能伪装成语义向量。 |
| `embedding` | `pgvector` `vector` 列；仅可由 embedding adapter 写入，尺寸必须匹配 profile。 |
| `status` | `pending`、`indexed`、`stale`、`deleted`、`failed`。 |

向量索引只存 embedding；最小过滤字段保留在 PostgreSQL 行（workspace/source version/status/scope 关系）中。任何候选命中仍必须回 source 和权限服务重新验证。

### 2.3 索引和扩展

- Alembic migration 必须先执行 `CREATE EXTENSION IF NOT EXISTS vector`，并在 downgrade 中只删除本包表/索引，不删除共享 extension。
- `vector` 列使用 package profile 维度约束；首发 HNSW 仅在 profile 确定后建立，使用 cosine distance。profile/dimension 变化创建新 profile/version 和可重建 index，不覆盖旧 embedding。
- 关键词索引使用 `GIN(keyword_terms)`；中文采用服务器内确定性的 CJK 双字切分加 Latin/digit token，避免把外部中文分词服务引入 Package D。
- 建立 `(workspace_id, status, source_version)` 与 source lifecycle 查询索引。HNSW 不是权限索引；权限先用关系/结构化过滤收窄。

## 3. 生命周期与索引事件

```text
authorised source projection
  -> KnowledgeSource pending
  -> reference-only outbox event
  -> chunk + local embedding/index job
  -> indexed

source version replacement / TTL / revoke / delete
  -> source becomes replaced/revoked/expired/deleted
  -> synchronous read deny
  -> reference-only cleanup event
  -> chunks stale/deleted, projection/chunk text scrubbed
```

1. 业务来源和 audit 先提交；索引请求复用既有 `OutboxEvent`，payload 只包含 `workspace_id`、`knowledge_source_id`、`content_version`、事件类型、request fingerprint 和 `trace_id`（其值只能是 server-derived `trace_ref`）。`trace_ref = SHA-256("stage08-knowledge-trace-v1:" + caller_trace_id)`；原始 `caller_trace_id` 不得进入 outbox payload、`trace_id` column、错误、audit 或返回结果。
2. 同一 source/version 的 `index_requested` 必须幂等。worker 锁定 source 行，重新验证 status/version/hash/scope，才可创建或重建 chunks。
3. 任何 source replacement、Memory revoke/expiry/delete、document projection revoke/delete 或 approved summary supersede 都先同步令旧 source/chunk 不可读，再异步清理 embedding/keyword/chunk 正文。
4. 清理失败只可留下 `stale/deleted` tombstone 与脱敏错误码；检索路径不得读 stale/deleted 行，也不得等待 worker 才拒绝。

### 3.1 Memory supersession 的逻辑来源身份

- `memory_item` 的逻辑来源身份不是当前 `MemoryItem.id`。系统沿同一 workspace 的 `supersedes_id` 链追溯到根 Memory item，使用 `logical_source_fingerprint = SHA-256("memory_lineage:" + root_memory_item_id)`；当前活动 item 的 `version` 仍是 `content_version`，`source_ref.memory_item_id` 仍指向当前 item。
- 链中出现缺失节点、循环、跨 workspace、版本不单调、Memory type 不一致、标准化 `MemoryScopeProjection` 不完全一致（含 `identity_token`），或无法通过既有 read-only Memory 投影验证时，注册必须 fail closed，且不得创建 Knowledge source 或 outbox event。这里的 type + scope 与既有 Memory materializer 的 logical identity 定义一致；不得仅凭可伪接的 `supersedes_id` 合并两条业务记忆。
- 注册新版本时必须锁定同一逻辑 fingerprint 的 active/pending source：旧 source 标记为 `replaced`、其 chunks 同步转为不可读状态，并创建一次 reference-only cleanup request；新 source 以 `supersedes_id` 链接旧 source。旧索引在 cleanup 前也不得被检索路径读取。
- 该规则不读取、回填或持久化被 supersede 的 Memory 原文；C2 群聊 Context 仍不能进入 RAG。
5. reindex 必须新建 content version；不得原地覆盖 active chunk。失败将新版本标 `failed`，旧 active version 是否保留取决于来源当前版本验证；一旦来源已替换/撤销，旧版本也不可读。

## 4. Embedding 与 chunk 规则

- canonicalization：Unicode NFC、换行归一、去除控制字符；hash 计算前不进行隐式翻译、摘要、模型改写或隐私放宽。
- chunk：最大 `1,200` code points、overlap `200`、单 source 最多 `1,000` chunks、单 projection 最多 `1,000,000` code points；若超限，source 标 `failed` 并只记录固定错误码，不截断成假完整知识。
- `keyword_terms` 最大 `256` 项、每项最大 `64` code points；chunk 文本不进入审计或 API。
- `EmbeddingProvider.embed_batch(profile, texts)` 是内部接口。首发只提供 test deterministic adapter 与 `UnavailableEmbeddingProvider` fail-closed 默认值；**不在 Package D 选择、调用或记录真实外部 embedding provider**。真实 provider/profile 需在后续独立配置与 F 的合成评测中启用。

## 5. 检索权限、Provider 与引用

有效检索权限：

```text
employee configured retrieval scope
∩ caller workspace/base/table/view/field scope
∩ optional current Telegram chat scope
∩ KnowledgeSource scope
∩ source current validity/version/deletion state
∩ source-specific reread result
```

`RetrievalProvider.search(...)` 只能接收由服务端 factory 生成的私有 retrieval authority、短命 query、固定 structured filter 和 limit。它按以下顺序运行：

1. 在 PostgreSQL 用 workspace/status/source type/profile/收窄 relation 预过滤候选；
2. 对关键词和 vector 分数做确定性加权、最多取 `12` 个候选；vector 不可用时显式降级为 keyword-only，不伪造 vector score；
3. 对每个候选重新验证 source status/version/hash、scope 与 source-specific access；Memory 复用 `read_memory_projection(..., read_only)`，其他 source 走其 server-side verifier；
4. 只将当前可读 chunk 作为 private retrieval evidence 返回调用栈；任何不确定性丢弃该候选；
5. citation 对外只生成稳定 display ordinal、`retrieved_material` label、source type 与 scope category，不包含 source/chunk/record/field UUID、名字、URL、score 或未授权正文。

`PostgresRetrievalProvider` 是唯一首发实现。未来 `MilvusRetrievalProvider` 只能实现同一接口并作为可重建副本；它不接收 source 正文、无权判定 deletion/permission，且本包不实现。

## 6. 管理 API 与审计

计划中的 `POST /api/stage08/knowledge/reindex` 只接受 `workspace_id`、allowlisted server-derived source selector、idempotency key 和 trace；route 从 verified identity 得出 Actor，复用现有 workspace owner/manager 检查与 runtime ticket/audit，不能接收 projection、chunk、embedding、query、scope 或 source terminal state。它创建 reference-only reindex event，不同步返回正文或检索结果。

本包不新增面向普通用户的 document upload、query 或 citation API；Package E 的协调器将在后续内部消费 `RetrievalProvider`。

审计可记录：source/chunk 计数、source type、状态、profile name/version、耗时、固定错误码、trace/hash reference。审计禁止记录 projection/chunk 文本、embedding、keyword terms、query、scope UUID、文件名、Memory payload、群/Message carrier 或 provider response。

## 7. 失败、留存和环境门禁

| 情形 | 行为 |
| --- | --- |
| `vector` extension / HNSW 不可用 | migration 预检失败，Package D 不可声称完成；不以纯内存 mock 代替 PostgreSQL 证据。 |
| embedding profile 未配置 | source/chunk 可保持 `pending`；检索只允许明确的 keyword-only 受控降级，不能称 vector index 已建立。 |
| source/version/scope/field/Memory drift | 丢弃候选；不回退旧 chunk、旧 source 或 raw origin。 |
| cleanup/outbox failure | synchronous reads 继续拒绝 stale/deleted；重试只能基于 reference-only event。 |
| chunk/hash/profile mismatch | source 标 `failed` 或 chunk 标 `stale`；不返回 partial stale evidence。 |

Package D 的本地 PostgreSQL 证据必须使用**专用、可丢弃且安装 pgvector 的数据库**，不能复用当前未装 vector 的 `STAGE06_LOCAL_DATABASE_URL` 作为成功证据。Docker pgvector container 只服务开发/测试，不等于 staging/production。

## 8. 验收映射

| Requirement | 本合同的最低证据 |
| --- | --- |
| D-01 | migration upgrade/downgrade、source/chunk version/rebuild/idempotent event、partial index failure 与 local PostgreSQL。 |
| D-02 | pgvector + keyword + structured prefilter，HNSW baseline，pre/post permission revalidation、TTL/revoke/delete/field/relation drift。 |
| D-03 | private evidence 与 safe citation projection，隐藏/删除/未授权 source 不可被 citation 或 exception 识别。 |
| D-04 | `RetrievalProvider` contract tests，Postgres provider fallback/keyword degradation；Milvus 未安装、未调用。 |

## 9. 已知风险

1. 当前 native PostgreSQL 没有 `vector.control`，不能运行本包实际 migration；必须先启动独立 pgvector test database。
2. 现有仓库无通用文档对象存储/下载/解析服务。本包只定义并实现 server-side safe `document_projection` adapter 合同；任何新文件 transport 需其自身架构/API/权限批准，不能借 D 偷渡。
3. 不配置真实 embedding provider 时，只有 deterministic test embedding 和显式 keyword-only runtime 降级；不得把测试向量的排序当作生产语义质量。
