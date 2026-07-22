# Stage08 Package D / D4 Fresh Current-State Remediation 独立复审报告

## Review Result

- Review date：2026-07-21
- Result：`PASS`
- Findings：`0 Critical / 0 Important / 0 Minor`
- Closure eligibility：当前 D4 fresh-current-state remediation 具备交由 root agent 考虑关闭 D4 的条件；本报告不自行关闭 D4，也不授权或宣布 D5、Package D、Stage08、真实 provider 质量或部署完成。
- Review boundary：完整对照 fresh-state review/remediation brief、原 D4 review report、更新后 D4 report、Package D data/BDD contract，并复审当前 provider、safe contracts 及 unit/integration tests。唯一写入为本报告；未修改 application、tests、config、database schema、Git 或外部系统。

## Findings

### Critical

无。

原 `C-01` 已被收口：SQLAlchemy 路径不再依赖普通 `Session.get` / `Session.scalars` 的旧 identity-map 对象作为消费期事实。在 authority 和 held hit 重验前，实现使用受控 ORM `select(...)` 的局部 `populate_existing=True, autoflush=False`，并以 `session.no_autoflush` 包围完整重验链。未使用 `expire_all()`。

### Important

无。

原 `I-01` 已被收口：PostgreSQL structured candidate query、InMemory candidate 和 post-selection/render 重验都要求 active source 的 `revoked_at/deleted_at` 为空，indexed chunk 的 `deleted_at` 为空。矛盾状态只 fail closed，没有自动修补或 lifecycle/audit/outbox 写入。

### Minor

无。

原 `M-01` 已被收口：`memory_item` 消费期沿当前 `supersedes_id` 链逐节读取 metadata，验证同 workspace、current/superseded status、严格版本顺序、相同 `memory_type`、完整规范化 scope（含 `identity_token`）、source refs 和无循环，最后重算 `SHA-256("memory_lineage:" + root_id)` 与 source fingerprint 精确比较。

## Fresh Current-State Functional Evidence

### 1. Search 后的数据库当前事实

专用 pgvector integration 用例先在 SQLAlchemy Session 中保留成功检索结果，再用绕过 ORM identity-map 对象写入的 SQLAlchemy Core `UPDATE` 改变当前数据库行，并先反查确认当前事实。复审重跑确认：

- source 已 revoked 后，private evidence 为空、citation 为空、safe view `result_count=0`；
- DigitalEmployee 已 paused 后，authority 重验失效，private evidence/citation/view 均不再释放原结果；
- source fingerprint 被改为格式正确但根谱系错误的值后，held hit 被丢弃。

复审另外执行了一次不修改源码的专用 PostgreSQL view-drift 探针：保留 search result 后用 Core `UPDATE` 将对应 view 改为非 active，数据库反查确认后再消费结果；`render_private_evidence=None`、citations 为空、safe view `result_count=0`，命令输出 `VIEW_DRIFT_PROBE PASS`。这覆盖了 review brief 要求的 employee 之外至少一项 view/permission 当前事实漂移。

### 2. 局部刷新与无关 pending state

- `_fresh_scalars` 只对指定 statement 设置 `populate_existing=True, autoflush=False`。
- `_build_authority_snapshot`、candidate verifier 和 fresh reads 均受 `session.no_autoflush` 保护。
- integration 用例在 Session 中加入一条无关 pending Workspace，调用 held-result safe view 后该对象仍在 `session.new`，直连数据库仍查不到该行。
- static scan：`expire_all=0`。

### 3. Terminal timestamps

InMemory 和专用 PostgreSQL 均覆盖：

- active source + non-null `revoked_at`；
- active source + non-null `deleted_at`；
- indexed chunk + non-null `deleted_at`。

对已保留结果的 evidence/citation 和新的 candidate search 都返回无命中，且没有 audit/lifecycle/outbox 副作用。

### 4. Memory root fingerprint

单元用例确认以下组合都 fail closed：

- 64-hex 格式正确但根 ID 错误；
- 另一条有效 Memory lineage 的 fingerprint；
- current item self-cycle。

同一用例在修改前先确认合法当前 same-workspace lineage 仍可读。provider 未直接读取 `Stage08MemoryItem.payload`；只复用既有 `read_memory_projection(..., lifecycle_mode="read_only")` 的受控 projection，复审过程未输出任何 payload 值。

## Mandatory Verification

所有 pytest 命令都从 `backend` 执行，禁用 pytest cache，并使用 `-W error`。

| Verification | Fresh result |
| --- | --- |
| `test_stage08_retrieval_provider.py + test_stage08_retrieval_service.py` | `112 passed in 2.64s` |
| D1 contracts + D2/D3 + D4 focused matrix | `178 passed in 3.41s` |
| dedicated `test_stage08_retrieval_pgvector.py` | 首次因 reviewer shell 未继承 `STAGE08_RAG_DATABASE_URL` 而 `15 skipped`，未计为成功；显式设置唯一 D0 disposable DSN 后 fresh 重跑 `15 passed in 7.02s`，无 skip |
| `compileall` provider | exit `0` |
| PostgreSQL view-drift reviewer probe | `VIEW_DRIFT_PROBE PASS` |
| `git diff --check` | exit `0`；共享 dirty worktree 只有既有 CRLF warning，无 whitespace error |

## Dedicated PostgreSQL / pgvector Evidence

- 只使用 D0 已授权的 loopback disposable pgvector database，未回退 `DATABASE_URL`、native Stage06 PostgreSQL 或外部环境。
- Fresh extension version：`vector=0.8.5`。
- Fresh database revision 与 Alembic head：`20260720_0032`、单一 head。
- 完整 15 个 integration 用例保留原 GIN `keyword_terms &&` 与 pgvector cosine `<=>` 真实 SQL 证据，并新覆盖 source/employee/fingerprint/timestamp fresh-state 重验。
- 测试及 reviewer probe 回滚后：`stage08_knowledge_sources=0`、`stage08_knowledge_chunks=0`、knowledge source outbox rows `=0`。

## Static / Privacy / Scope Review

Static scan 结果：

```text
expire_all=0
external_imports=0
raw_sql=0
direct_memory_payload=0
test_provider_construction=0
```

- production provider 无 OpenRouter/OpenAI/HTTP/Telegram/LangGraph/Milvus 或外部 embedding SDK 导入，无 network/provider key/environment dependency。
- 无 raw SQL；只使用 SQLAlchemy 受控 expression。Core `UPDATE` 只在 integration/reviewer probe 中用于制造数据库当前事实。
- 未构造默认 `TestHashEmbeddingProvider`；未显式注入时仍为明确 keyword-only degradation。
- safe citation 仍只有 ordinal、`retrieved_material`、source type category 和 scope category；safe view 不包含 UUID、query、chunk text、score/vector/profile、actor/authority 或 provider 异常细节。
- `document_projection` / `approved_summary` 仍因缺少已批准 origin verifier 而 fail closed，未扩张 API、UoW、schema、permission、provider 或网络边界。

## Skipped Work and External Actions

- 有效验证轮次无 skip；首次因 reviewer shell 未设专用变量的 15 skip 已明确废弃，随后同一模块 15/15 fresh 通过。
- 未运行 full backend suite；本轮只执行 review brief 规定的 D1–D4 focused 和完整 dedicated pgvector matrix。
- 未调用真实 embedding/LLM/OpenRouter/Telegram/HTTP/Redis/LangGraph/browser/Mini App/staging/production/deployment。
- 未修改 Docker 容器、Git state 或任何外部系统。

## Remaining Risks

1. D4 仍只有 `memory_item` source-specific verifier；`document_projection` / `approved_summary` 按合同故意 fail closed。
2. 只有 deterministic test embedding adapter，默认 runtime 是 keyword-only。本复审不证明真实语义召回质量、外部 provider 可用性、成本/延迟或 production readiness。
3. D4 仍是内部 provider，没有 Coordinator/LangGraph/prompt assembly、用户 query API、Telegram/group RAG 或生产索引管理 API。
4. 本轮没有运行 full backend suite；Package D 级关闭还应由后续任务按阶段计划补齐。

## Cleanup

- 所有 dedicated PostgreSQL 用例与 reviewer probe 在外层 transaction 中 rollback，Session/connection/engine 均关闭或 dispose。
- Fresh 数据库读回确认 source/chunk/knowledge-outbox 计数均为 0。
- 未创建临时脚本、dataset、credential、log 或外部 artifact。
- D0 disposable pgvector container 保留供后续 Package D 任务使用；它不是 staging/production 证据。

结论：原 D4 review 的 stale identity-map、terminal timestamp 和 Memory root fingerprint 三项缺口已在当前代码中被 fresh 证据收口。本报告建议 root agent 可考虑关闭 D4，然后依现行计划和文档门禁决定是否进入 D5。
