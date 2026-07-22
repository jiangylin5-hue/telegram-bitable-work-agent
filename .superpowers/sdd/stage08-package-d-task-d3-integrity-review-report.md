# Stage08 Package D / D3 Integrity Remediation 独立复审报告

## Review Result

- Result：`PASS`
- Findings：`0 Critical / 0 Important / 0 Minor`
- Closure eligibility：D3 integrity remediation 满足 **root closure consideration** 条件；本报告不直接宣布 D3、Package D 或 Stage08 完成。
- Review scope：完整读取 integrity remediation brief、原 D3 brief、原 review report、更新后的 D3 report、Package D 数据合同/BDD、当前 worker、embedding adapter、unit/integration tests，并运行本轮 fresh evidence。
- Write boundary：唯一写入为本报告；未修改 application/test/contract/model/migration/UoW/API/Docker/configuration/database/Git 或外部系统。

## Findings

### Critical

无。

### Important

无。

### Minor

无。

## Original Findings Closure

### I-01：indexed replay metadata/vector drift

状态：`closed`

- `process_knowledge_index_event` 在 source 锁定、来源重读和确定性切片后读取精确 source/version chunk 集合。
- `_existing_index_matches` 重新核对 workspace/source/version、ordinal、text/hash/terms、profile/version，并使用纯 `deterministic_test_hash_embedding` 对八个 float32 值做精确比较；另一组有限 8 维向量不再被视为等价。
- 任一冲突会同步清空相关非 deleted chunk 的 text、terms、embedding/profile/version，并标为 `stale`；event 保持 pending，source projection 保持 active，不新增行。
- UoW 的 chunk 查询按精确 source ID/version 收窄，scrub 再次核对 source/workspace/version，因此不修改其他 source/version。
- Unit 覆盖 metadata drift 与 finite-vector drift；dedicated PostgreSQL 覆盖实际 pgvector 持久化后的 finite-vector drift、flush、stale/scrub 和后续 cleanup/replay。

### I-02：post-lock chunk read exception convergence

状态：`closed`

- index 与 cleanup 的 `list_knowledge_chunks(...)` 均在独立异常收敛边界中。
- 读取失败只返回零计数、`status="failed"`、`error_code="knowledge_index_failed"`；不改变 source/chunk/event，也不携带异常类、sentinel、正文、trace 或底层错误。
- Unit 对 index/cleanup 两条路径分别保存完整状态快照并比较，结果和 event carrier 中均无 sentinel。

### I-03：embedding output conversion exception convergence

状态：`closed`

- `_validated_embeddings` 将 batch shape、迭代、元素类型、float 转换、维度和 finiteness 置于同一收敛边界；包括超大整数的 `OverflowError` 和异常 iterable/element。
- 任一非法输出只形成 `embedding_output_invalid`，event 保持 pending；pending/readable/failed partial chunk 在创建前即被阻止。
- Unit 覆盖 oversized integer、exceptional iterable、partial batch、维度错误、NaN、provider exception 和 unavailable provider。

## Functional Check Matrix

| Required check | Fresh conclusion |
| --- | --- |
| 正常显式 TestHash index/replay | PASS；固定 profile/version、8 个有限 float，重放无重复行，event 首次处理时间稳定。 |
| indexed metadata drift | PASS；返回固定 `knowledge_index_failed`，event pending，相关 chunk stale 且正文/terms/vector/profile/version 清空。 |
| finite 8-vector drift | PASS；unit 与真实 pgvector 均拒绝，仅“有限且 8 维”不能通过等价校验。 |
| unrelated source/version | PASS；读取和 scrub 均按 exact source/version 收窄，并再次核对 workspace/source/version。 |
| index post-lock chunk-read failure | PASS；固定失败码、零计数、状态快照不变、无 sentinel。 |
| cleanup post-lock chunk-read failure | PASS；固定失败码、零计数、状态快照不变、无 sentinel。 |
| oversized/abnormal embedding output | PASS；固定 `embedding_output_invalid`、event pending、无 partial row。 |
| valid cleanup/replay | PASS；terminal source 可清理，正文/terms/vector/profile/version 被清空，deleted tombstone 和首次 `deleted_at` 保留，重放不回填。 |
| active/hash-mismatch cleanup | PASS；均被 deny/discard，不删除 active material。 |
| TestHash isolation | PASS；worker 默认仍为 `UnavailableEmbeddingProvider`；production runtime 无 `TestHashEmbeddingProvider(...)` 实例化。新增 deterministic helper 是固定 test-profile 的纯函数，不含 provider/network/environment 选择。 |
| dedicated pgvector | PASS；仅 `STAGE08_RAG_DATABASE_URL`，无 native/default fallback；真实 vector、HNSW、GIN、FK、replay、drift scrub、cleanup 均通过。 |
| raw-data/external boundary | PASS；无外部 provider/network/Telegram/LLM/API/Milvus import 或调用，无 raw body/trace/provider output 的新增持久化或日志路径。 |

## Fresh Verification Evidence

工作目录：`backend`。所有 pytest 使用 `-W error -p no:cacheprovider`。

1. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py`
   - Exit：`0`
   - Result：`77 passed in 2.00s`
2. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py`
   - Exit：`0`
   - Result：`133 passed in 2.09s`
3. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py`
   - Exit：`0`
   - Result：`161 passed in 2.26s`
4. `$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py`
   - 本轮显式配置唯一 dedicated loopback `STAGE08_RAG_DATABASE_URL` 后执行。
   - Exit：`0`
   - Result：`7 passed in 1.36s`，无 skip。
5. `python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py`
   - Exit：`0`
   - Result：无输出。

附加定向回归：

- `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py -k "replay_conflict or post_lock_chunk_read or embedding_failure"`
- Exit：`0`
- Result：`11 passed, 56 deselected in 0.86s`

专用环境只读证据：

- Docker image：`pgvector/pgvector:pg17`
- Container：`healthy`
- `vector` extension：`0.8.5`
- Alembic database version：`20260720_0032`
- 集成回滚后：`stage08_knowledge_sources=0`、`stage08_knowledge_chunks=0`、Stage08 knowledge outbox rows `=0`
- `git diff --check`：exit `0`；仅共享 dirty worktree 的既有 LF/CRLF conversion warnings。

## Skipped Evidence and Open Scope

- 本轮 required/targeted tests 无 skip。
- 未运行 full backend suite；本轮范围是 D3 integrity remediation 的 D1/D2/Memory/D3 focused matrix 与 dedicated pgvector evidence。
- 未运行真实 embedding/LLM/OpenRouter/Telegram/HTTP/Redis/LangGraph、browser/Mini App、staging、production 或 deployment。
- D3 仍只证明 test deterministic embedding、unavailable default、index/cleanup consumer 与本地 pgvector 数据完整性，不代表真实语义质量或 production provider 可用。
- Package D 仍未关闭；D4 hybrid retrieval、pre/post authorization、source-specific revalidation、safe citation 和 D5 management/API/integration 仍为 open scope。
- Stage08 和 production deployment 仍为 open scope。

## Cleanup and State

- Integration tests 在外层 transaction 中执行并 rollback；本轮只读复核确认未保留 source/chunk/outbox 测试行。
- D0 disposable pgvector container 保持原有 healthy 状态，供后续 Package D 工作使用；本轮未修改 Docker 状态。
- 未创建临时脚本、dataset、credential、volume 或外部 artifact。
- 未执行 Git stage/commit/reset/checkout/clean/push/PR。

结论：D3 integrity remediation 已通过本轮 fresh independent review，`0 Critical / 0 Important / 0 Minor`，可提交 root 进行 D3 closure consideration。Package D、D4、D5、真实 provider、语义质量与 production 仍未完成。
