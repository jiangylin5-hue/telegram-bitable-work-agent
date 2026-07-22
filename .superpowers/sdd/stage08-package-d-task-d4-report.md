# Stage08 Package D / Task D4 检索 Provider 实现证据报告

## Status

- Status: `fresh-state remediation implemented; awaiting another fresh independent review`
- Scope: D4 内部不透明检索授权、PostgreSQL-first 结构化候选收窄、关键词/向量混合排序、Memory 只读重验、私有 evidence 及安全 citation/view。
- Gate: 本报告只记录 D4 实现和本地证据；不宣布 D4、Package D 或 Stage08 完成。关闭 D4 仍需一次新的独立复审。
- Worktree: 保留现有 dirty worktree；未执行 Git stage/commit/reset/checkout/clean/push/PR。

## Changed Files

- Modified: `backend/app/runtime/stage08_retrieval_contracts.py`
- Created: `backend/app/services/stage08_retrieval_provider.py`
- Created: `backend/tests/unit/test_stage08_retrieval_provider.py`
- Modified: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Created: `.superpowers/sdd/stage08-package-d-task-d4-report.md`

未修改 model、migration、UoW interface、`stage08_retrieval.py`、Memory/C1/C2 行为、API/route、Docker/configuration、runtime default、Git 状态或外部系统。

## Implemented Behavior

### 不透明授权与权限交集

- `Stage08RetrievalAuthorityFactory` 是唯一有效 issuer；直接构造、伪造 actor、跨 workspace/employee/caller 和已过期授权均 fail closed。
- 创建和每次消费时重读 workspace/member/role、DigitalEmployee status/version/config、base/table/view 及 member grant。
- 只允许具有严格 `query` capability 的 active DigitalEmployee，并使用既有 `resolve_business_scope` 重读当前可见 customer-project linked-record 关系。
- 不新增 Telegram/chat/group 授权。未知、group、Telegram 或 identity 元数据候选在排序前被丢弃。
- authority/result/evidence 为 module-private、slots-only、不可序列化对象，`repr` 为固定不透明标记，不提供公开可读的私有字段。

### PostgreSQL-first 候选和混合排序

- query 在规范化后只接受 `1..500` Unicode code points，`limit` 只接受 `1..12`；query 不持久、不写 audit/log/error/repr/citation。
- SQLAlchemy 候选查询先根据 workspace、source/chunk lifecycle、current source version、base/table/view 及 customer/project scope 收窄。
- 关键词候选使用 PostgreSQL array overlap `&&`，对应 D1 GIN index；显式注入固定测试 profile adapter 时，向量候选使用 pgvector cosine distance `<=>`，表达式与 8 维 partial HNSW index 一致。
- 关键词 score 为确定性归一化 term overlap；显式测试向量的混合权重为 keyword `0.6` / vector `0.4`，并以稳定元数据打破平局。
- 默认 runtime 不选择、不实例化 `TestHashEmbeddingProvider`；未显式注入 adapter 时只返回关键词结果和明确 `keyword_only` degradation，不伪造 vector score。
- provider/verifier/query-vector 异常均收敛为固定失败/丢弃行为，不回显底层 exception 或 sentinel。

### 候选后重读和安全输出

- `memory_item` 每次消费均调用 `read_memory_projection(..., lifecycle_mode="read_only")`，校验当前 active version、TTL、safe scope、source ref、canonical projection hash 和 deterministic chunk；不直接读 Memory `payload`。
- 候选首次通过后，生成内部 evidence 或 citation/view 前再次重读 authority、source lifecycle/version/hash、chunk indexed 状态、scope、business relation 和 source-specific verifier。
- revoke、expire、supersede、source/chunk/version/hash/scope/record/relation/authority 漂移都使命中失效，不等待 cleanup，不引发 Memory lifecycle/audit 副作用。
- D4 只有 `memory_item` 的已批准 origin verifier。`document_projection` 与 `approved_summary` 在没有完整 origin verifier 前严格 fail closed。
- safe citation 只有 display ordinal、固定 `retrieved_material` label、source-type category 和 scope category；safe model 执行 exact-shape 验证，包括对 `model_construct`/强制污染对象的攻击。
- safe output 不包含 UUID、scope 值、query、chunk text、score、vector/profile、actor/authority、URL、filename 或 Memory payload。

## TDD RED -> GREEN Evidence

### Initial RED

首先创建 D4 单元测试并运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py
```

初始收集失败为预期的缺失实现：`RetrievalSafeCitation` 尚不存在。这不是测试拼写或环境故障。

### Corrective REDs

新增攻击用例在修正前分别暴露了以下问题：

1. forged Actor role 可与当前 member role 不一致；
2. safe citation 未拒绝伪造的非法 category/exact-shape；
3. 私有 hit snapshot 误用 dataclass，可被常见序列化机制识别；
4. verifier exception sentinel 可逃离内部边界；
5. malformed source fingerprint 未及时丢弃；
6. 真实 PostgreSQL 集成测试最初为 `1 failed, 7 deselected`，证明旧候选路径没有实际执行 GIN `&&` 和 pgvector `<=>`。第一次 SQLAlchemy 修正又暴露 generic ARRAY comparator 不支持 `.overlap()`，改为受控 SQLAlchemy `op("&&")` 后定向集成测试转绿。

上述修正均仅收紧 D4 已批准合同，没有放宽权限、safe DTO 或 source verifier。

### Final GREEN

所有 pytest 命令均从 `backend` 执行，禁用 pytest cache 且将 warning 提升为 error。

```text
D4 provider + D2/D3 service:        106 passed in 2.78s
D1 contracts + D2/D3 + D4:         172 passed in 3.76s
D4 targeted real PostgreSQL:         1 passed, 7 deselected in 2.11s
dedicated PostgreSQL pgvector:        8 passed in 2.67s
compileall:                           exit 0
```

命令：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/runtime/stage08_retrieval_contracts.py app/services/stage08_retrieval_provider.py
```

## Dedicated PostgreSQL / pgvector Evidence

- D0 专用本地测试数据库：仅通过 `STAGE08_RAG_DATABASE_URL` 显式配置，未回退 default/native database URL。
- Container image: `pgvector/pgvector:pg17`（继承 D0/D3 已审证据；本任务未改变 Docker 状态）。
- Fresh integration assertion: PostgreSQL extension `vector=0.8.5`、GIN keyword index、8 维 partial HNSW test-profile index、source/chunk 复合 FK 全部存在。
- Fresh Alembic head: `20260720_0032 (head)`。
- D4 SQL listener 实际捕获了 `keyword_terms && ...` 与 vector cosine `<=>` 语句；不是仅检查 index DDL 或在 Python 中模拟排序。
- 集成用例在同一 rollback transaction 中证明：真实 source/chunk 索引 -> hybrid search -> safe citation -> 默认 keyword-only degradation -> source revoke 后 evidence/citation 立即消失。
- 本任务尝试的 Docker CLI fresh inspect 因当前 sandbox 无法访问 Windows Docker named pipe 而失败；不将它误报为 fresh Docker health 证据。数据库连接与全部 8 个集成测试是当前 fresh 可用性证据。

## Static / Privacy / Boundary Verification

AST 与 source scan 对 D4 production files 的结果：

```text
forbidden provider/network/Telegram/LLM/LangGraph/Milvus imports: []
direct Memory payload / Message-sensitive attribute reads:       []
TestHashEmbeddingProvider runtime construction/calls:             0
private hit dataclass:                                             false
```

- 未引入 `requests`、`httpx`、OpenAI/OpenRouter、Telegram、LangGraph、Redis、Anthropic、Cohere、Milvus、外部 embedding SDK、network client 或 provider key/environment dependency。
- provider 不写 audit/outbox/log。单元测攻击 query、UUID、chunk body、score/vector/profile、actor/authority 和 exception sentinel，未在 safe model、`repr` 或异常中发现回显。
- SQL 路径仅使用 SQLAlchemy 受控查询及现有 UoW session；service 中无 raw SQL、凭证或跨边界直连。
- `git diff --check`: exit `0`。
- D4 路径在共享 dirty worktree 中仍为 untracked，因此未将空 path diff 当作证据；已检查完整当前文件和静态 AST。

## Skipped Tests and External Actions

- 最终规定的 106/172/8 测试中无 skip。D4 定向命令的 7 个 deselected 是 `-k` 筛选，不是 skip；随后已全部执行。
- 未运行整个 backend suite；D4 brief 要求的 D1-D4 focused matrix 和专用 pgvector module 已完整执行，package/full-backend closure 属于后续门禁。
- 未进行真实 embedding/LLM/OpenRouter/Telegram/HTTP/Redis/LangGraph/browser/Mini App/staging/production/deployment 调用或写入。
- 未读写 native Stage06 PostgreSQL 行；集成只使用 D0 专用本地 pgvector 数据库。

## Remaining Risks

1. D4 仍等待 fresh independent review；复审应重点攻击 authority 复制/漂移、assigned-member grant、SQL scope prefilter、post-selection Memory drift、render-time revoke 和 safe DTO/repr 泄漏。
2. D4 只有 Memory source-specific verifier；`document_projection`/`approved_summary` 需后续已批准的 origin verifier，当前故意 fail closed。
3. 只有确定性测试 embedding adapter，默认是 keyword-only。本证据不代表真实语义质量、外部 provider 可用、成本/延迟达标或 production readiness。
4. D4 是内部 provider；没有用户 query API、Coordinator/LangGraph、prompt assembly、Telegram/group RAG 或索引管理 API。
5. 本轮无 fresh Docker CLI health/image inspect；仅能引用 D0/D3 已审 image 证据，并以 fresh database integration 作为当前可连接证据。

## Temporary Cleanup

- PostgreSQL 集成测试使用外层 transaction，在 `finally` 中 rollback；不保留 workspace/base/table/record/Memory/source/chunk/audit/outbox 测试行。
- SQL event listener 在 `finally` 中移除，session/connection/engine 均关闭或 dispose。
- 未创建临时脚本、dataset、credential、log 或外部 artifact。
- D0 专用 disposable pgvector container 为后续 D5 保留；本任务未创建、重启或删除它，且不将它视为 staging/production。

## Fresh Current-State Remediation（2026-07-21）

### 触发与边界

D4 首次独立复审结果为 `FAIL: 1 Critical / 1 Important / 1 Minor`：

1. `Critical C-01`：普通 `Session.get` / `Session.scalars` 可从 SQLAlchemy identity map 返回旧 employee/source/chunk/record，数据库已撤权后仍可能释放私有正文。
2. `Important I-01`：active source 的 `revoked_at/deleted_at` 和 indexed chunk 的 `deleted_at` 未参与候选及渲染重验。
3. `Minor M-01`：Memory logical fingerprint 只检查 64-hex 格式，未重算 D2 的 `SHA-256("memory_lineage:" + root_id)`。

纠正仅修改 remediation brief 允许的 provider、D4 unit/integration tests 和本报告。未修改 contract、schema、migration、UoW interface、Memory/C1/C2/D3 service、API、Docker/configuration、Git 或外部系统。

### Corrective TDD RED

所有 RED 都在 production 纠正前执行：

```text
in-memory terminal timestamps:       3 failed
in-memory root/cross-lineage:        3 failed
dedicated pgvector fresh DB facts:   6 failed, 8 deselected
unrelated pending-state autoflush:   1 failed, 14 deselected
```

- 三个 terminal timestamp RED 表明：仅设置 source `revoked_at`、source `deleted_at` 或 chunk `deleted_at`，旧实现的 held result 仍会生成 private evidence。
- 三个 lineage RED 表明：格式合法但 root 错误的 fingerprint、另一条真实 Memory lineage 的 fingerprint 以及 current self-cycle 都未被拒绝。
- dedicated pgvector RED 在同一 SQLAlchemy session 保留已搜索 result，然后用独立 SQLAlchemy Core `UPDATE` 改写当前数据库行，且确认 DB 已是 revoked/paused/timestamp/fingerprint drift；旧 provider 仍返回 evidence、citation 和 `result_count=1`。
- 无关 pending Workspace RED 证明：仅在局部 fresh query 上设 `autoflush=False` 不够，后续 authority/source verifier 的普通 ORM query 仍会意外 flush 无关 session state。

### Minimal GREEN 实现

#### 局部 fresh-current-state 读取

- 只对 `SqlAlchemyStage06PlatformUnitOfWork` 启用新边界；InMemory UoW 保留直接当前对象验证。
- 使用受控 SQLAlchemy `select(...)` + `execution_options(populate_existing=True, autoflush=False)` 刷新指定行，并在完整 authority/candidate verifier 周围使用 `session.no_autoflush`。
- 未使用 `expire_all()`，未全局丢弃 identity map，未隐式 flush 无关 pending 对象。
- authority 局部刷新 workspace、DigitalEmployee、WorkspaceMember、employee member grant、base/table/view、field/view grant、请求的 customer/project record 与 relation rows；任一查询、数量或 shape 异常都 fail closed。
- 每次 held hit 渲染前以 ID/source version 精确刷新 `Stage08KnowledgeSource` 和 `Stage08KnowledgeChunk`；不再依赖普通 UoW getter 可能返回的旧对象。
- Memory 消费沿 `supersedes_id` 逐行刷新当前 item/predecessor metadata，然后才调用既有 `read_memory_projection(..., lifecycle_mode="read_only")`。任何异常只产生 unavailable/no-hit，不外泄异常文本、ID、score 或正文。

#### 终止时间戳一致性

- PostgreSQL structured filters 新增 source `revoked_at IS NULL`、source `deleted_at IS NULL` 和 chunk `deleted_at IS NULL`。
- `_active_source` 与 `_valid_chunk_for_source` 执行同样的 fail-closed 判定，覆盖 InMemory candidate 和 post-selection/render 路径。
- 矛盾行只被拒绝，不自动修复、不写 lifecycle/audit。

#### Memory root-lineage fingerprint

- 对 current active item 及每个 predecessor 验证 UUID/workspace、status、正 version 且严格递减、无终止 timestamp、无 cycle、合法 source refs。
- 使用 `MemoryScopeProjection` 规范化完整 scope（包括 `identity_token`），要求所有 predecessor 的 `memory_type` 与规范化 scope 完全相同，并继续拒绝 group scope。
- 最终必须满足 `source.logical_source_fingerprint == SHA-256("memory_lineage:" + root_id)`；不再仅验证 64-hex 格式。
- provider 未直接读取 `Stage08MemoryItem.payload`。

### Corrective GREEN 证据

定向 RED 对应的最小 GREEN：

```text
in-memory terminal + lineage:       6 passed, 39 deselected in 1.37s
dedicated pgvector fresh attacks:   6 passed, 8 deselected in 5.08s
unrelated pending-state:            1 passed, 14 deselected in 2.18s
```

纠正后 brief 规定的回归矩阵：

```text
D4 provider + D2/D3 service:        112 passed in 2.91s
D1 contracts + D2/D3 + D4:         178 passed in 3.74s
dedicated PostgreSQL pgvector:       15 passed in 6.98s
compileall provider:                 exit 0
```

dedicated PostgreSQL 的 15 个用例中无 skip，并保留原有真实 GIN `keyword_terms &&`、pgvector cosine `<=>`、`vector=0.8.5`、GIN/HNSW index 与 revision `20260720_0032` 证据。新回归额外证明：

- DB source 在 search 后被 Core update 为 revoked，held result 的 evidence/citation/view 立即为空；
- DB DigitalEmployee 在 search 后被 Core update 为 paused，authority 重验失效且不释放正文；
- DB source fingerprint 改为格式合法但 root 错误的 hash 后，held hit 被丢弃；
- active/indexed 状态下单独出现 source/chunk terminal timestamp 时，held result 和新 candidate 均不可读；
- refresh 路径不会 flush 无关 pending Workspace row。

### Remediation Static / Privacy / Cleanup

- `expire_all` scan: `0`；只存在局部 `populate_existing` 与 `no_autoflush`。
- 无外部 provider/network/Telegram/LLM/LangGraph/Milvus import，无默认 `TestHashEmbeddingProvider(...)` 构造。
- 无 direct Memory `.payload` / Message field read；`projection["payload"]` 仍只是既有受控 read-only projection 输出。
- 无 raw SQL、credential、query/audit/outbox/log persistence；Core `UPDATE` 只存在 dedicated integration attack tests。
- `git diff --check`: exit `0`。
- 所有新 PostgreSQL 用例仍在外层 transaction 中 rollback，session/connection/engine 关闭；无测试行、脚本、credential 或 artifact 残留。D0 disposable pgvector container 继续为 D5 保留，不是 staging/production 证据。

### Remediation Remaining Gate

- 纠正实现必须接受新的 fresh independent review；本报告和 GREEN 数量不自行关闭 D4。
- D5、Package D、Stage08、真实语义 provider/质量、外部调用与 production deployment 仍为 open scope。
- `document_projection` / `approved_summary` 仍因缺少已批准 origin verifier 而 fail closed。
- 本轮未运行 full backend suite；只运行 remediation brief 规定的 focused D1–D4 和完整 dedicated pgvector matrix。

本报告不构成 D4、D5、Package D 或 Stage08 closure。只有在新的独立复审完成并明确通过后，才能由上层任务考虑更新 D4 状态。
