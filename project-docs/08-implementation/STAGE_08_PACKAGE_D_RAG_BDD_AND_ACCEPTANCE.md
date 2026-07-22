# Stage08 Package D：RAG 与 pgvector BDD / 验收合同

## Status

- Current Progress Update (2026-07-21)：Package D 已关闭。D0–D5 最终独立复审 `0 Critical / 0 Important / 1 Minor`，完成 disposable pgvector migration `0032 → 0031 → 0032`、唯一 head、`vector=0.8.5`、GIN/HNSW 和 `236 passed / 0 skip` 的真实本地证据。受控 D5 API 的 current-state membership/source/Memory revoke 均 fail closed 且零副作用；clean readback 为 source/chunk/outbox/idempotency/audit `0`。Minor 仅为 D5 测试模块中既有 Starlette deprecation warning 的过滤粒度，应后续收窄；不影响运行时或 Package D 关闭。Package E 可以开始，真实 provider/Telegram/部署仍不在本包结论内。

- Document status：`approved development boundary`。
- Scope：可重建 Knowledge source/chunk、pgvector+keyword 混合候选、检索前后权限重读、引用安全投影和索引生命周期。
- Current Progress：Package C 已关闭。Package D 的数据/安全合同和逐任务 TDD 计划已写入；D0 已通过独立复审：专用 `pgvector/pgvector:pg17` container 的 `vector=0.8.5` 可用，未配置专用变量时明确 skip 且不能回退 default/native database。native PostgreSQL 仍无 extension。D1 strict contracts/ORM/migration 已通过 fresh review；首轮发现的 chunk copied `workspace_id/source_version` 漂移风险已由 source unique + exact composite FK 收口（62 tests、真实 FK attacks、downgrade/re-upgrade 均通过）。D2 经两次最小修复和第三次独立复审关闭：真实新行 supersession、root lineage、同 type+规范化 scope（含 identity token）完整性、旧 source/chunk 同步不可读、唯一 cleanup 及 trace SHA-256 引用均通过独立验证（`0 Critical / 0 Important / 0 Minor`；40/96/124 focused regressions）。D3 已关闭：first-review 的 indexed replay drift、post-lock read exception、embedding overflow 均已最小修复并通过 fresh independent review（`0 Critical / 0 Important / 0 Minor`；77/133/161 focused + 7 dedicated pgvector）。D4 已关闭：通过局部 `populate_existing` + `no_autoflush` 当前态重读消除 source revoke/employee pause 的 identity-map stale 缺口，source/chunk terminal timestamp 与 Memory root fingerprint 均 fail-closed；fresh independent review `0 Critical / 0 Important / 0 Minor`（112/178 focused、15 dedicated pgvector，测试清理为 0）。D5 现进入管理端 reference-only reindex API 与 Package D 最终证据实施；尚未创建真实 embedding/LLM provider 调用或任何外部 provider 行为。
- Out of scope：Milvus、真实 embedding/LLM provider、Telegram、文档 upload/download/object storage、LangGraph、Coordinator、用户 query API、生产部署。

## 1. BDD

### D-B01：只接受服务端安全来源投影

**Given** 一个 active workspace 和当前可验证的 `memory_item`、`document_projection` 或 `approved_summary` source

**When** 内部 adapter 注册 `KnowledgeSource`

**Then** source 必须带 workspace、收窄 scope、source ref、正 content version、规范化 hash 和固定 source type。

**And** adapter 只能交付安全 projection；raw Message 字段、群窗口、transport、隐藏字段、客户端 body、任意 URL/token、prompt/response 均被拒绝。

**And** 同逻辑 source 的内容变化创建新版本，不覆盖旧 source；旧版本进入 `replaced` 并立即不可读。

### D-B02：可重建切片与索引不等于真源

**Given** 一个 current active source projection

**When** reference-only reindex event 被 worker 消费

**Then** worker 先锁定并重读 source status/version/hash/scope，再以 `1,200` code points、`200` overlap 的确定性规则生成最多 `1,000` chunks。

**And** chunk 只保存安全 projection 的片段、hash、keyword terms、profile-bound vector 和最小生命周期字段；outbox/audit/error 不保存正文、embedding 或 query。

**And** source/hash/profile/权限任一漂移、部分 chunk 失败或未配置 embedding provider 时，不能把 partial result 标为 indexed，也不能泄露旧 chunk。

### D-B03：删除、撤权与过期优先于异步清理

**Given** 一个已 indexed source/chunk

**When** source 被 replaced、revoked、expired 或 deleted，或者 Memory/source relation/field visibility 发生漂移

**Then** source/chunk 在同一受控生命周期操作内先变为不可读；之后的异步 cleanup 只负责删除 vector、keyword terms 与正文、保留 tombstone。

**And** 检索路径永不等待 cleanup；只要 current source 无效，旧 embedding 命中也必须丢弃。

**And** cleanup event 重放、worker 并发或 process crash 不得恢复旧正文，且同 source/version reindex 幂等。

### D-B04：检索必须先收窄、后重读

**Given** 一个由服务端 factory 生成的 private retrieval authority

**When** `PostgresRetrievalProvider` 执行 keyword + vector + structured filter search

**Then** 先用 workspace、source type/status、content/profile version 与 customer/project/base/table/view 收窄候选，最多 12 个。

**And** 对每个候选再次检查 employee/caller/chat/source scope 交集、source lifecycle/version/hash，以及 source-specific verifier；`memory_item` 必须复用既有 `read_memory_projection(..., read_only)`。

**And** vector unavailable 时只能以标记明确的 keyword-only 降级运行；不能伪造 vector score 或把 test hash embedding 当作真实语义模型。

### D-B05：引用和错误信息不扩大可见性

**Given** 一个当前有权读取的 private retrieval evidence 集合

**When** Package D 生成内部 safe citation view 或遇到失败

**Then** 对外仅有 display ordinal、`retrieved_material` label、source type 与 scope category。

**And** source/chunk/record/field UUID、scope 值、文件名、URL、score、embedding、正文、Memory payload 和 actor/authority 不得出现于 DTO、`repr`、异常、audit 或日志。

### D-B06：管理 reindex 仍是受控动作

**Given** verified identity 与 existing workspace owner/admin/manager 权限

**When** 调用 `POST /api/stage08/knowledge/reindex`

**Then** 服务端只接受 workspace、allowlisted source ID、trace 和 idempotency key，并由服务端派生 Actor、scope、ticket、audit 和 outbox reference。

**And** 客户端提交 projection、chunk、embedding、query、filter、source status、scope 或 ticket state 一律 422/deny；非管理角色不能启动 reindex。

## 2. Acceptance Matrix

| Requirement | 必须通过的行为 | 最低证据 |
| --- | --- | --- |
| D-01 | source/chunk/version/reindex/delete 可重建且可恢复 | migration upgrade/downgrade、reference-only event、worker replay/partial failure、real pgvector PostgreSQL。 |
| D-02 | pgvector + keyword + structured filter 前后权限一致 | HNSW/GIN proof、pre/post authorization、field/relation/source/TTL/revoke/delete drift PostgreSQL tests。 |
| D-03 | citation 指向当前可访问 source/version/field | private evidence/safe citation/repr/exception/API security corpus。 |
| D-04 | provider 可替换，PostgreSQL 是权限真源 | provider contract、unavailable embedding keyword-only degradation、Milvus absence scan。 |

## 3. Required Evidence

```powershell
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_retrieval_api.py tests/integration/test_stage08_retrieval_pgvector.py
Pop-Location
```

预期：单一 migration head、专用 pgvector database 中无 skipped-as-pass，D-01 到 D-04 具备 real local PostgreSQL evidence。还必须记录 Docker container/image/extension 版本、compileall、privacy/external dependency scan、`git diff --check` 与 cleanup；这些均不是 production evidence。

## 4. Known Risks / Gates

- native `STAGE06_LOCAL_DATABASE_URL` 未安装 pgvector；它不能作为 Package D 成功环境。D0 未证明专用 container 的 `vector` extension 前，禁止进入 schema/migration 代码。
- 当前没有通用 document storage。source adapter 只承接 server-derived safe projection；新增文件 transport、object storage 或任意上传是独立架构/API/权限工作，不能在 D 中顺手实现。
- 真实 embedding model/profile、成本、外部 provider 与语义召回质量属于 F 的 isolated evaluation。D 的 deterministic adapter 只能用于本地 contract/HNSW tests。
- 未经新明确授权，禁止 Milvus、生产 Telegram、部署或真实 Provider 写入。
