# Stage12 Retrieval、Embedding 与 Chunk V2

> Parent index: [README.md](README.md)

## 9. Embedding 与 Chunk V2

### 9.1 Embedding 的职责边界

Embedding 用于：

- 模糊实体名和别名解析；
- 标题、描述、备注、总结等非结构化字段召回；
- Schema description 与用户表达匹配；
- 在已授权候选集合内部 rerank。

Embedding 不用于：

- 精确编号定位；
- 权限裁决；
- enum、status、date、number 的精确过滤；
- Join 的最终路径决定；
- Count、Group By、Sum；
- 写入 target 的最终确认。

### 9.2 三层索引

#### Schema Index

每个 Table/Field 形成版本化 schema document：

```text
workspace/base/table identity
table name/key/description
field name/key/type/description
enum options
linked target table
field aliases
schema version
```

#### Record Index

每条记录形成一个 record document，而不是跨记录混合 Chunk：

```text
record identity
table identity
display fields
可检索文本字段
typed filter fields 的安全摘要
record version
field visibility profile hash
```

敏感字段和不可见字段不得进入 embedding 文本。Embedding 本身视为衍生敏感数据，仍受 workspace、table、field scope 控制。

#### Relation Index

每条 linked-record edge 独立保存：

```text
source_table_id / source_record_id
link_field_id
target_table_id / target_record_id
direction
source_version / target_version
scope hash
```

Relation Index 用于候选扩展和路径审计，不用向量相似度决定 link 是否存在。

### 9.3 Chunk 策略

- Schema：一个 table header chunk + 每个 field 一个 field chunk。
- Record：一条记录一个 canonical record chunk；长文本字段按字段切分，保留 parent record ID。
- Relation：不将多条 edge 拼成自然语言大段；edge 使用结构化存储，必要时生成短摘要。
- 长文本 chunk 采用 token-aware 切分，重叠只用于句子连续性，不跨 record。
- 每个 chunk 必须带 `source_type`、`source_id`、`source_version`、`table_id`、`record_id`、`field_ids`、`scope_hash` 和 `content_hash`。

### 9.4 Embedding Profile

Stage12 不直接沿用 `stage08.test-hash-v1`。实施前用中文复杂 Query 集比较至少一个本地多语 embedding profile 和一个远程 profile，按 Recall@20、P95、成本、数据出境和运维复杂度选定唯一生产 profile。

选择结果必须固化为：

```text
profile_name
model_revision
dimension
normalization
distance_metric
max_input_tokens
batch_size
provider_location
data_residency
```

生产表使用固定维度 pgvector column；更换维度时新建 profile/version 和新索引，双写重建后切换，不原地解释旧向量。

### 9.5 Hybrid Retrieval

```text
Objective-specific query
-> exact identifier/entity match
-> structured filters
-> schema candidate retrieval
-> authorized BM25/keyword retrieval
-> authorized semantic retrieval
-> linked-record expansion
-> per-table quota
-> rerank
-> EvidenceBundle assembly
```

推荐默认预算：

- 精确实体候选不受向量 Top K 淘汰。
- 每个 Objective 最多 20 个 primary candidates。
- 每条 primary record 最多扩展 10 条授权 relation edges。
- LLM EvidenceBundle 默认最多 24 个 compact evidence nodes；全量聚合只传 aggregate 和必要 evidence sample，不传全部原始记录正文。
- 任何截断都设置 `truncated=true`，禁止回答“全部”“唯一”或精确总数，除非确定性 QueryResult 已完整计算。

### 9.6 EvidenceBundle

```json
{
  "version": "evidence-bundle.v2",
  "objective_id": "obj-01",
  "query_result_ref": "artifact:query-result",
  "nodes": [
    {
      "evidence_id": "ev-01",
      "kind": "record",
      "table_key": "work_items",
      "record_code": "MT-001",
      "fields": {"status": "blocked", "risk_level": "high"},
      "source_version": 3
    }
  ],
  "relations": [
    {
      "from": "PRJ-ATLAS",
      "field": "work_items.project_link",
      "to": "MT-001"
    }
  ],
  "aggregates": [],
  "scope_hash": "sha256",
  "complete": true
}
```

Provider 只能引用 `evidence_id`，最终 citation 由后端映射为安全显示对象。

### 9.7 索引构建与失效流程

索引不是直接在 Record 写事务中调用外部 Provider。推荐流程：

```text
record/schema/link committed
-> transactional outbox: knowledge_projection.requested
-> projection worker reads current authorized source version
-> canonical projection + content hash
-> chunk builder
-> embedding batch request
-> validate dimension/profile/finite values
-> write new source_version/chunks/vector
-> mark version indexed
-> atomically switch active version
-> expire old version after rollback window
```

任何一步失败都保留旧 active version。删除或权限收缩优先于重建：先 revoke source/chunk，再异步清理向量，避免旧索引继续被召回。

失效条件包括：

- record visible field changed；
- field visibility changed；
- linked-record edge changed；
- table/schema description changed；
- employee/view scope changed；
- embedding profile changed。

#### 9.7.1 已确认：两段式授权投影事件

`record/schema/link committed` 只能确定资源和版本，不能确定未来请求的
`agent scope ∩ caller scope ∩ chat/view scope`。因此 mutation 事务不能直接构造带
`visibility_profile_hash` 的 caller-specific projection，也不能把最大权限文本写入索引。

TDR-019 已于 2026-07-30 确认，9.7 的 outbox 流程细化为：

```text
Stage06 authorized mutation committed
-> stage12.retrieval_source.changed（资源引用、版本、哈希 trace only）
-> authorization-aware indexing coordinator
-> re-read current authorized source for each registered/materialized visibility profile
-> stage12.retrieval_projection.requested（per visibility profile）
-> canonical projection / chunk / embedding / atomic activation
```

新出现的 visibility profile 只能按当前授权请求 lazy build，不能借用更宽权限的 vector。
权限收缩或删除仍先同步 revoke 受影响 source/chunk，再异步重建或清理。普通内容更新可为
rollback 保留旧 active version，但 EvidenceBundle 释放前必须重验当前 record/source version、
field scope 与 effective authority。

本节当前为 `accepted`，允许按 Stage12-D 计划修改内部事件 contract 并接入 Stage06 mutation；该确认不授权部署、生产 activation、真实 workspace 外部 embedding 或公共 API/SSE 变化。
决策真源见 `../../00-governance/TECHNICAL_DECISIONS.md` 的 TDR-019。

### 9.8 Canonical 文本构造

Record embedding 文本按稳定顺序构造：

```text
[table] 工作项
[record] MT-001
[title] Atlas launch checklist
[status] blocked
[priority] high
[summary] 等待范围确认
```

只包含当前调用者类别可检索的字段。JSON key、内部 UUID、审计字段、权限字段和不可见字段不进入文本。字段顺序按 schema position 固定，避免无业务变化时 hash 和 embedding 漂移。

长文本字段单独 chunk 时使用：

```text
parent_record_id
field_id
chunk_ordinal
start_token/end_token
field_content_hash
```

### 9.9 Hybrid 排序公式

先做硬过滤和实体 boost，再做可解释打分：

```text
score =
  0.35 * normalized_keyword_score
+ 0.35 * normalized_semantic_score
+ 0.20 * entity/schema_match_score
+ 0.10 * freshness_score
```

权重不是永久常量，必须通过 Evaluation V2 学习和版本化。精确编号命中设置独立 priority band，不与模糊结果混排。Relation expansion 记录不靠相似度进入，而靠已验证 link edge 进入，并标记 `retrieval_reason=linked_expansion`。

Reranker 的输入只包含已授权候选；如果使用 LLM reranker，必须限制为排序现有 candidate ID，不能生成新记录。每次返回保存 component scores 和 rank reason，便于审计错召回来源。

### 9.10 Embedding 模型选择与上线门

模型选择不是“选择最大模型”，而是按以下维度评分：

| 维度 | 权重 | 审计内容 |
| --- | ---: | --- |
| 中文 Recall@20 | 30% | 同义词、业务缩写、中文/英文混用 |
| 多表 Schema matching | 15% | 字段别名与表描述匹配 |
| P95 latency | 15% | 单条、batch、并发 |
| 数据驻留与隐私 | 15% | 是否出境、日志保留、删除策略 |
| 成本 | 10% | 每百万 token/字符和重建成本 |
| 运维复杂度 | 10% | 本地 GPU、扩缩容、Provider SLA |
| 版本可固定性 | 5% | revision、dimension、兼容性 |

候选 profile 必须在同一授权候选集和同一 Gold Case 上比较。选定后固定 model revision、dimension 和 normalization；不能让 Provider 自动漂移到“latest”。
