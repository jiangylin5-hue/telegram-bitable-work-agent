# Stage08 Package D / Task D3 Index Worker Evidence Report

## Status

- Status: `D3 integrity remediation implemented; awaiting a new fresh independent review`
- Scope: D3 内部 `EmbeddingProvider` 边界、索引 worker、cleanup worker、幂等重放、失效清理与专用 Docker pgvector 生命周期证据。
- Gate: 本报告不宣布 D3、Package D 或 Stage08 完成；必须经新的独立复审。
- Worktree: 保留已有 dirty worktree；未执行 Git stage/commit/reset/checkout/clean/push/PR。

## Changed Files

- Created: `backend/app/services/stage08_retrieval_embeddings.py`
- Modified: `backend/app/services/stage08_retrieval.py`
- Modified: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modified: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Created: `.superpowers/sdd/stage08-package-d-task-d3-report.md`

没有修改 model、migration、runtime contract、UoW interface、API/route、Docker topology、环境配置、Memory/C1/C2 行为或任何外部系统。

## Implemented Behavior

### Embedding boundary

- 新增内部 `EmbeddingProvider.embed_batch(profile, texts)` protocol。
- `UnavailableEmbeddingProvider` 不导入 HTTP/client/SDK/environment/provider key，只报固定码 `embedding_provider_unavailable`。
- `TestHashEmbeddingProvider` 仅支持 `stage08.test-hash-v1` / version `1` / dimension `8`，对相同 profile/text 产生确定、有限的 8 维 `float`。
- test provider 不是任何 production/runtime 默认值；worker 不显式传 provider 时只使用 fail-closed unavailable provider。
- worker 严格校验 profile 类型/名称、version 类型/值、dimension 类型/值、batch 数量、每个 vector 维度和每个数值的 finiteness；`bool` 不能冒充 version。

### Index worker

- `process_knowledge_index_event` 只接受 D2 的 exact reference-only event shape，同时校验 event type、aggregate type/id、workspace/source UUID、version、hash 和派生的 64-hex trace reference。
- 必须先通过 `lock_knowledge_source_for_lifecycle` 锁定 source，再重读 workspace/version/hash/status/TTL/safe projection。
- replaced/revoked/expired/deleted/missing/drifted source 返回安全 `discarded`，不创建 readable chunk，不复活 source。
- canonicalization/chunking 复用 D2 实现；所有 chunk 和 embedding 先组装、先校验，再以 `pending` 行加入，全部成功后才统一变为 `indexed`。
- provider unavailable、provider exception、partial batch、维度错误、NaN/Inf、profile 错误和已有 chunk 冲突都不会产生部分 readable chunk；返回仅包含固定错误码。
- source lock 获取异常在 index/cleanup 两条路径均收敛为固定 `knowledge_index_failed`，不回显数据库异常、source reference 或 body marker，也不改写 event/chunk。
- processed replay 校验已有 chunk 的 ordinal/text/hash/terms/profile/version/vector 后返回原 indexed count，不重复插入。
- 针对 PostgreSQL/pgvector 回读 vector 的数值容器差异，只在“已持久化 vector 重放复核”路径安全转为 `float`；provider 新输出仍保持严格 Python 数值类型验证。

### Cleanup worker

- `process_knowledge_cleanup_event` 同样重新锁定并校验 source reference。
- 只允许 `replaced` / `revoked` / `expired` / `deleted` 的精确 source version/hash 进入清理；active 或 drifted source 只返回 `discarded`。
- 清理同步清空 source `projection_text`，并对对应版本的每个 chunk 清空 `chunk_text`、`keyword_terms`、`embedding`、`embedding_profile`、`embedding_version`，最终留下 `deleted` tombstone 和 `deleted_at`。
- cleanup replay 保留第一次 `deleted_at`，不回填任何内容，返回稳定 cleaned count。

## TDD RED -> GREEN Evidence

### Initial worker RED

Command from `backend`:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py
```

Observed before D3 production code:

- Exit: `1`
- Collection errors: `1`
- Expected missing symbol: `process_knowledge_cleanup_event` / D3 worker 尚不存在。
- 失败不是测试拼写或环境问题。

首轮最小实现后，出现 `48 passed, 5 failed`；5 个失败均来自新测试直接篡改 Memory payload，违反既有 Memory source revalidation。测试改为通过受控 record/projection 生成长文本后，同一命令得到 `53 passed`。没有为了测试放宽 production 合同。

### Strict profile RED -> GREEN

Targeted command:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py -k "embedding_profile_metadata_is_strictly_fixed"
```

- RED: exit `1`, `1 failed, 3 passed, 53 deselected`；`version=True` 被 Python 相等比较误当成 `1`。
- GREEN: exit `0`, `4 passed, 53 deselected`；profile/version/dimension 改为类型和值同时严格匹配。

### Real pgvector replay RED -> GREEN

Configured dedicated integration command:

```powershell
$env:STAGE08_RAG_DATABASE_URL='<D0 dedicated local DSN>'
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
```

- RED: exit `1`, `1 failed, 6 passed`；首次 index 成功，但 pgvector 回读向量的数值容器与内存 `list[float]` 不同，replay 被误判为 conflict。
- GREEN: exit `0`, `7 passed in 1.54s`；已持久化 vector 复核兼容 pgvector 回读类型，仍严格要求 8 维有限数。

### Lock failure redaction RED -> GREEN

Targeted command:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py -k "source_lock_failure"
```

- RED: exit `1`, `1 failed, 57 deselected`；模拟行锁竞争/数据库异常的 sentinel 直接抛到上层。
- GREEN: exit `0`, `1 passed, 57 deselected`；index 和 cleanup 均仅返回固定错误码，原异常文本不进入 repr/event/chunk。

另外增加 hash 重算不匹配、1,000,001 code-point cap 和已有 chunk conflict 的无部分可读回归：targeted `3 passed, 58 deselected`。

## D3 Integrity Remediation: Review Findings and RED -> GREEN

Fresh independent review found three Important findings; this correction changes only the already-approved D3 worker boundary.

1. **Replay integrity conflict:** a finite but different 8-dimensional persisted vector, or altered indexed metadata, could pass replay or remain readable after a conflict. The worker now derives the fixed D3 TestHash vector through a pure helper in its pgvector float32 representation and compares all eight values exactly, along with source/workspace/version, ordinal, text/hash, terms, profile and embedding version. A mismatch synchronously clears every related non-deleted chunk body/terms/vector/profile/version and changes it to `stale`; the active source projection and event state are preserved.
2. **Post-lock chunk-read convergence:** index and cleanup now each catch `list_knowledge_chunks(...)` failures and return only a zero-count `knowledge_index_failed` result, without changing source/chunk/event state or exposing exception text.
3. **Embedding conversion convergence:** `_validated_embeddings` now catches all normal conversion, iteration and finiteness failures, including `OverflowError` from oversized integers and malicious iterable elements. It returns `None`, so the worker returns `embedding_output_invalid`, keeps the event pending and creates no partial chunk.

### Remediation RED

Command from `backend`:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py -k "replay_conflict or post_lock_chunk_read or embedding_failure"
```

Observed before the remediation production changes:

```text
6 failed, 5 passed, 56 deselected in 1.50s
```

The failures exactly reproduced the review findings: indexed metadata conflict remained readable; a different finite 8-vector was accepted as a replay; index/cleanup post-lock chunk reads leaked sentinel exceptions; and oversized-integer / exceptional-iterable embedding output escaped the worker boundary.

### Remediation GREEN

The same targeted command after the minimal correction:

```text
11 passed, 56 deselected in 1.06s
```

The dedicated PostgreSQL pgvector lifecycle regression was also extended to corrupt an actual stored vector to a finite eight-zero vector. It proves the following sequence in one rollback transaction: valid index -> valid replay -> finite-vector conflict -> `knowledge_index_failed` + stale/scrub -> terminal cleanup/replay. Fresh configured pgvector result: `7 passed in 1.23s`.

## Final Required Verification

所有 pytest 从 `backend` 运行，禁用 pytest cache 并将 warning 提升为 error。

```text
chunking + retrieval service:       77 passed in 1.95s
D1 contracts + D3 service:         133 passed in 2.55s
Memory contracts/service + D3:     161 passed in 2.32s
dedicated PostgreSQL pgvector:       7 passed in 1.23s
compileall:                           exit 0
```

Commands:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py
```

Dedicated database evidence:

```text
container image: pgvector/pgvector:pg17
container health: healthy
vector extension: 0.8.5
Alembic head: 20260720_0032 (head)
```

Integration assertions observed actual non-null 8-dimensional `vector` values, existing partial HNSW test-profile index, GIN keyword index, exact composite source/workspace/version FK, index replay without duplicate rows, cleanup tombstones/scrubbing, and zero readable `indexed` chunks after cleanup. The transaction rolled back its test rows; the D0 disposable container remains running for subsequent Package D tasks.

## Static / Privacy / Boundary Verification

AST and source scans over the two D3 production service files returned:

```text
forbidden provider/network/Telegram/LLM imports: []
raw Message attributes:                         []
direct Memory payload attributes:               []
TestHashEmbeddingProvider runtime calls:        []
raw caller trace payload assignment:            false
derived trace_ref payload assignment:            true
```

- No `requests`, `httpx`, OpenAI/OpenRouter, Telegram, LangGraph, Redis, Anthropic, Cohere, Milvus, external embedding SDK, network client or environment-key dependency was introduced.
- Worker results contain only status/count/fixed error code. Tests attack raw trace, event body marker and provider exception text; none appears in result repr.
- Event payload remains D2's exact five reference fields. No projection/chunk/scope/source_ref/body is added to outbox, result, error, log or audit.
- `git diff --check`: exit `0`; shared dirty worktree emitted only pre-existing LF-to-CRLF conversion warnings.
- Allowed D3 production/test paths remain untracked within the larger shared worktree, so an empty path diff was not treated as evidence; complete current files were inspected directly.

## Skipped Tests and External Actions

- No test in the configured final D3 commands was skipped.
- The integration module still explicitly skips when `STAGE08_RAG_DATABASE_URL` is absent and never falls back to `DATABASE_URL` or `STAGE06_LOCAL_DATABASE_URL`; the final pass used only D0's dedicated local Docker pgvector DSN.
- Full backend suite was not run because D3 brief requires the focused D1/D2/Memory/D3 and dedicated pgvector matrix; package-wide/full-backend closure remains later work.
- No real embedding/LLM/OpenRouter/Telegram/HTTP/Redis/LangGraph/browser/Mini App/staging/production/deployment call or write occurred.
- No native Stage06 PostgreSQL row was read or written by D3.

## Remaining Risks

1. D3 仍等待 fresh independent review；审查需重点攻击 event/source drift、provider output、SQL replay、cleanup replay、trace/body 泄漏与 test-provider default selection。
2. D3 只实现测试 embedding 和 unavailable default，不代表真实语义质量或 production provider 可用。
3. D4 尚未实现授权后的 hybrid retrieval、候选重读和安全 citation；本任务不宣称可对用户检索。
4. D3 没有新增 outbox scheduler/dispatcher；它只实现受控 consumer function，调度与管理 API 是后续任务。

## Temporary Cleanup

- Integration test 使用外层 transaction 并在结束时 rollback，不保留 workspace/source/chunk/outbox 测试行。
- 未创建临时脚本、dataset、credential、命名 volume 或外部 artifact。
- D0 专用 disposable pgvector container 按 Package D 计划继续保持 healthy，供 D4/D5 复用；不把它视为 staging/production。

本报告仅记录 D3 实现与本地证据。在新的独立复审通过前，不宣布 D3、Package D、Stage08、语义检索、provider integration 或 production 完成。
