# Stage08 Package D / D0–D5 最终独立复审简报

## 状态与决定范围

- Status：`pending D5 implementation evidence`
- 目标：在 D5 实现报告完成后，独立判断 Package D 是否达到关闭条件。该复审不能自行关闭 Package D；仅 `0 Critical / 0 Important` 且所有本简报的本地 pgvector 证据真实通过，才可由 root 更新阶段真源并考虑进入 Package E。
- 唯一可写文件：`.superpowers/sdd/stage08-package-d-final-review-report.md`。不得修改 application、tests、contracts、models、migrations、API、Docker/config、Git state、外部系统或持久业务数据。
- 复审真源：Package D data contract、BDD/acceptance、implementation plan、D0–D5 reports、D4 fresh-state review、D5 evidence、当前生产代码与 tests。共享 worktree 已脏，不能凭空 `git diff` 推断本包的所有变更。

## 必须独立核验的 D0–D5 门槛

1. **D0/D1 database baseline。** 只使用 loopback disposable `STAGE08_RAG_DATABASE_URL`，没有 default/native fallback；`vector` extension、GIN keyword 与 HNSW index 真实存在，Alembic 为唯一 head `20260720_0032`。复审 migration upgrade/downgrade/re-upgrade 后必须回到 head，且不得把 native Stage06 PostgreSQL 当成功证据。
2. **D2/D3 source lifecycle。** 知识 source/chunk/version、scope/version composite integrity、Memory root lineage、reference-only index/cleanup event、replay/partial failure、revoke/replace/delete cleanup 都不读取 raw origin 或 Memory payload，并能在 dedicated PostgreSQL 里重新验证。embedding unavailable 必须是明确 keyword-only/worker failure 语义，不可伪造 vector 成功或调用真实 provider。
3. **D4 consumption security。** PostgreSQL 实际使用 GIN `&&` 与 pgvector cosine `<=>`，pre-filter 不被误用为授权；search 后 source revoke、employee pause、view/member/grant/business relation drift、source/chunk terminal timestamp 与 Memory root fingerprint drift 都使 held evidence/citation/safe view 不可用。局部 `populate_existing`/`no_autoflush` 可刷新当前事实但不 `expire_all()`，不隐式 flush 无关 pending state。private evidence、citation/repr/error/DTO 不泄漏正文、query、UUID、scope、score/vector、authority 或 provider detail。
4. **D5 management reindex API。** `POST /api/stage08/knowledge/reindex` 只接收严格 `workspace_id`、`knowledge_source_id`、`idempotency_key`、`trace_id`；客户端的 projection/chunk/embedding/query/filter/scope/source state/actor/role/ticket 等任何 carrier 均 422/redacted。用 server-derived verified identity + existing `member.manage`；现有 canonical role 中仅 active owner/admin 能管理，builder/operator/viewer/non-member 与所谓不存在的 manager 均 fail closed，不能修改 `ROLE_ACTIONS`。source/workspace/lifecycle/source-specific verifier 必须重验；document projection/approved summary 继续 fail closed。
5. **D5 idempotency/outbox/audit。** 同 workspace/operation/key 和相同语义请求安全重放同一仅含 `ticket_id/status=accepted` 的回执；不同行为得到 409；仅创建/复用 reference-only index event，审计一次且最小。outbox/audit/response/repr/error 中不得存 projection/chunk/embedding/keyword/query/scope UUID/message carrier/payload/provider response。HTTP 路径不得同步调用 embedding/LLM/HTTP/Telegram/Redis/LangGraph 或 worker。
6. **范围与清理。** 无 Milvus、真实 embedding/LLM/OpenRouter/Telegram/network、schema/API 以外未授权扩展、Docker production claim 或部署。测试后 dedicated database source/chunk/outbox/idempotency/audit 不留 D-package test rows；临时文件/凭据/DSN/日志不得留下。

## 必跑命令与证据

在 `backend` 执行，pytest 使用 `-W error -p no:cacheprovider`。专用 DSN 仅在 shell 中设置；不得将其值写入 report：

```powershell
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m alembic upgrade head
python -m alembic heads
python -m alembic downgrade 20260720_0031
python -m alembic upgrade head
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_retrieval_api.py tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/models/stage08_knowledge.py app/runtime/stage08_retrieval_contracts.py app/services/stage08_retrieval_chunking.py app/services/stage08_retrieval_embeddings.py app/services/stage08_retrieval.py app/services/stage08_retrieval_provider.py app/schemas/stage08_retrieval.py app/api/routes/stage08_retrieval.py
```

没有变量时的 skip 不是成功证据；此时复审必须明确停止，不回退其他数据库。还要做 production-source static scan（无 raw SQL、网络/provider/Telegram/Milvus import、direct Memory payload、默认 TestHash provider、`expire_all`），检查 router/main 注册、response/validation redaction 和 API body schema。最后读回 `vector` version、唯一 head、索引名与 source/chunk/outbox/idempotency/audit count，并说明每类是否为 0。

## 报告格式和禁止结论

报告使用中文，分别列出 Critical、Important、Minor；给出 API/权限/幂等/生命周期/fresh-state/migration/PG证据、命令结果、静态/隐私检查、skipped、cleanup 与剩余风险。不要记录 DSN、credential、UUID、正文、query、payload 或向量。

若 `0 Critical / 0 Important`，只能建议 root 关闭 Package D 并交接 Package E。无论结果如何，不得声称 Package E/F、真实 provider 质量、生产部署或 Stage08 已完成。
