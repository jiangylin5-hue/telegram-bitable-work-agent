# Stage08 Package D / Task D3 独立复审报告

## Review Result

- Result：`FAIL`
- Closure eligibility：D3 **暂不具备** root closure consideration 条件。
- Findings：`0 Critical / 3 Important / 0 Minor`
- Review boundary：只读审查 D3 brief/report、Package D 数据合同与 BDD、D1 model/contracts、D2/D3 service、unit/integration tests；唯一写入为本报告。
- External boundary：未调用或写入真实 embedding/LLM/OpenRouter/Telegram/HTTP/Redis/LangGraph、staging、production 或 native Stage06 PostgreSQL。

## Findings

### Critical

无。

### Important

#### I-01：冲突重放不会同步令既有 `indexed` chunk 不可读，并且不校验向量值是否漂移

- 位置：`backend/app/services/stage08_retrieval.py:193-204`、`backend/app/services/stage08_retrieval.py:837-855`。
- 现状：已有 chunk 时，`_existing_index_matches(...)` 返回 `False` 后 worker 仅返回 `knowledge_index_failed`，不会把已有 `indexed` chunk 改为 `stale`、清空正文/向量，或令 source 进入不可检索状态。现有 conflict 测试在 `backend/tests/unit/test_stage08_retrieval_service.py:916-918` 创建的是默认 `pending` chunk，因此没有覆盖“已可读 indexed 行发生冲突”的情况。
- 另一个同路径缺口：`_existing_index_matches(...)` 只验证 embedding 是 8 维有限数，不把已持久化向量与当前 TestHash provider 对相同 chunk 的确定性输出比较。任意另一组 8 维有限数会被当作合法重放，事件仍会被标记 processed。
- 影响：违反 D3 brief 的“replay 不产生 mutable divergence”“duplicate/conflict 不留下 readable partial chunk”，也违反数据合同中 `chunk/hash/profile mismatch -> source failed 或 chunk stale，不返回 partial stale evidence`。未来 D4 只要读取 `indexed` 状态，这类冲突行仍可能作为候选。
- Required fix：重放必须验证完整不可变索引事实（含 source/workspace/version、ordinal、text/hash/terms、profile/version 和向量值或等价的稳定 embedding fingerprint）。任一冲突须在同一事务内同步把相关 chunk 变为不可读，再返回固定错误码；补充至少一个 `indexed` metadata conflict 和一个 8 维有限但值漂移的回归。

#### I-02：source 锁后读取 chunk 的数据库异常未收敛，会原样越过 worker 边界

- 位置：index 路径 `backend/app/services/stage08_retrieval.py:193`；cleanup 路径 `backend/app/services/stage08_retrieval.py:323`。
- 现状：两处 `uow.list_knowledge_chunks(...)` 均在异常收敛边界之外。若正常数据库读取遇到连接、游标或事务错误，原始异常会直接抛给调用方；现有测试只覆盖 `lock_knowledge_source_for_lifecycle` 异常（`backend/tests/unit/test_stage08_retrieval_service.py:865-899`）。
- 影响：违反 D3 对固定错误码和正文/引用/底层错误文本不回显的要求；cleanup consumer 也不能稳定返回 `knowledge_index_failed`，调度方可能接收到数据库错误内容。
- Required fix：对 index/cleanup 的 chunk list/read 路径建立与 source lock 相同的固定错误收敛，失败时不改 event、source 或 chunk，并增加包含 sentinel 的 index/cleanup 读取异常回归，断言 sentinel 不进入 result/repr/event/chunk。

#### I-03：非法 embedding 数值可在输出验证阶段抛出未收敛的 `OverflowError`

- 位置：`backend/app/services/stage08_retrieval.py:235`、`backend/app/services/stage08_retrieval.py:826-833`。
- 现状：provider 返回的值只要是 `int`/`float` 就进入 `float(value)`；该转换不在 `try/except` 中。超出 float 范围的 Python 整数会抛出 `OverflowError`，而 `_validated_embeddings(...)` 又在 provider 调用的异常收敛块之外，因此异常越过 worker；现有 provider-invalid 测试仅覆盖 raises、partial、7 维和 NaN。
- 影响：不满足“所有 provider output 均先完整验证，非法输出只返回固定 `embedding_output_invalid` 且不创建 partial chunk”的要求，也破坏错误脱敏边界。
- Required fix：让所有数值转换/迭代异常收敛为 `embedding_output_invalid`，不得保留 provider/值/异常原文；增加 overflow 数值及异常型 iterable/元素的回归，确认 event 保持 pending 且无 readable chunk。

### Minor

无。

## Functional Review Matrix

| Review area | Evidence / conclusion |
| --- | --- |
| 正常 index | TestHash 显式注入时生成固定 profile `stage08.test-hash-v1`、version `1`、8 维有限 float；unit 与 real pgvector lifecycle 均通过。 |
| 正常 replay | 未变化路径不重复插入，unit 和 PostgreSQL 均观察到 1 个 chunk；但 I-01 阻断完整重放一致性结论。 |
| source/event drift | workspace/version/hash/status/TTL、event type/aggregate/payload/trace 走 discard/fail-closed；`_positive_version` 明确排除 `bool`。 |
| provider unavailable/invalid | unavailable、普通 provider exception、partial batch、维度和 NaN 已有固定码证据；I-03 表明输出验证仍非异常完备。 |
| cleanup | replaced/revoked/expired/deleted 正常清空 source projection 及 chunk text/terms/vector/profile/version，保留 deleted tombstone；active/hash drift cleanup 被拒绝，重放不回填。I-02 阻断数据库读取失败路径。 |
| 数据脱敏 | event 为 exact reference-only shape，trace 为 64-hex 派生引用；worker result 只含 status/count/fixed code。静态扫描未发现外部 provider/network/Telegram/LLM 导入。I-02/I-03 仍允许底层异常越界。 |
| TestHash 隔离 | production worker 未实例化 `TestHashEmbeddingProvider`；未显式传 provider 时只选择 `UnavailableEmbeddingProvider`。 |
| 专用 pgvector | 本轮使用唯一 `STAGE08_RAG_DATABASE_URL` 指向 loopback disposable Docker PostgreSQL；7 个 integration tests 无 skip，验证 extension、schema/FK、GIN/HNSW、真实 vector 持久化、worker replay 与 cleanup。代码未回退 `DATABASE_URL` 或 `STAGE06_LOCAL_DATABASE_URL`。 |

## Fresh Verification Evidence

工作目录：`backend`；pytest 均使用 `-W error -p no:cacheprovider`。

1. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py`
   - Exit `0`
   - `71 passed in 2.06s`
2. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py`
   - Exit `0`
   - `127 passed in 2.17s`
3. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py`
   - Exit `0`
   - `155 passed in 2.35s`
4. `$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py`
   - 本轮先显式设置唯一专用 `STAGE08_RAG_DATABASE_URL`，再按命令映射给 `DATABASE_URL`。
   - Exit `0`
   - `7 passed in 1.51s`，无 skip。
5. `python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py`
   - Exit `0`
   - 无输出。

附加只读环境证据：

- container image：`pgvector/pgvector:pg17`
- health：`healthy`
- `vector` extension：`0.8.5`
- Alembic head/database version：`20260720_0032`
- `git diff --check`：exit `0`；仅共享 dirty worktree 的既有 LF/CRLF warnings。
- production service 静态扫描：无 requests/httpx/OpenAI/OpenRouter/Telegram/LangGraph/Redis/Anthropic/Cohere/Milvus import；无 `TestHashEmbeddingProvider(...)` runtime call。

## Skipped Evidence

- 未运行 full backend suite；D3 brief 要求的 focused D1/D2/Memory/D3 与 dedicated pgvector 矩阵已全部运行。
- 未运行真实 embedding/LLM 质量评测、Telegram、API、LangGraph、Redis、staging、production 或 deployment；这些不属于 D3。
- 未验证 D4 hybrid retrieval、pre/post authorization、safe citation 或 D5 management API；尚未实现，不能由 D3 结果推断。

## Cleanup and State

- integration tests 使用 transaction rollback；本轮不保留测试 workspace/source/chunk/outbox 行。
- 未创建临时脚本、dataset、credential、volume 或外部 artifact。
- D0 disposable pgvector container 仍保持 healthy，供后续修复与 Package D 任务使用；它不是 staging/production。
- 未执行 Git stage/commit/reset/checkout/clean/push/PR。

结论：虽然所有规定命令均通过，I-01 至 I-03 仍属于 D3 数据完整性与失败收敛门禁。修复并经新的独立回归前，D3 不可关闭，也不能据此推进 Package D closure。
