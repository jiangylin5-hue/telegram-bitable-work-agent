# Stage08 Package D / D5：受控 Reindex API 实施报告

## Status

- Report status：`implementation and fresh verification complete; awaiting independent Package D review`
- Date：2026-07-21
- Scope：只实现 D5 brief 已批准的 reference-only reindex service、严格 API/schema、路由注册、TDD 与专用 PostgreSQL 证据。
- Closure：本报告不关闭 D5、Package D 或 Stage08，不授权开始 Package E。

## 1. Changed Files

- `backend/app/services/stage08_retrieval.py`
- `backend/app/schemas/stage08_retrieval.py`
- `backend/app/api/routes/stage08_retrieval.py`
- `backend/app/main.py`
- `backend/tests/unit/test_stage08_retrieval_service.py`
- `backend/tests/api/test_stage08_retrieval_api.py`
- `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- `project-docs/08-implementation/evidence/stage08-package-d-rag.md`
- `.superpowers/sdd/stage08-package-d-task-d5-report.md`

未修改 models、migration、Stage06 UoW/interface、identity、`ROLE_ACTIONS`、Docker/config、其他 API、Package E/F、Git state 或外部系统。

## 2. TDD 时间线

### RED 1：D5 service/API 尚不存在

先新增 service 与 API 行为测试，再运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py tests/api/test_stage08_retrieval_api.py
```

预期失败为 `request_knowledge_reindex` import 不存在。相同收集轮次还暴露本机已有 Starlette TestClient `httpx2` deprecation warning；只在新 D5 API test 模块精确忽略该 warning，未修改 production/global warning policy。

### GREEN 1：最小 service/API

新增：

- `KnowledgeReindexReceipt`，repr 只显示固定 status；
- `request_knowledge_reindex(...)` service boundary；
- strict request/response Pydantic schema；
- redacted FastAPI route 与 SQLAlchemy commit/rollback；
- main router registration。

首轮 GREEN：`109 passed in 10.17s`。

### RED 2：SQLAlchemy current membership 漂移

在 held Session 中先缓存 active owner member，再用 Core 修改数据库当前状态为 inactive。旧实现仍返回 receipt，RED 为：

```text
1 failed, 15 deselected
Failed: DID NOT RAISE PlatformValidationError
```

### GREEN 2：局部 fresh-current-state revalidation

仅在 D5 service 加入局部 `populate_existing=True`、`autoflush=False`、`session.no_autoflush`：

- workspace 使用 current row lock；
- membership current read；
- KnowledgeSource current row lock；
- Memory current item/root-lineage metadata read；
- current read/形状/lifecycle/scope/lineage 任一失败即 fail closed。

没有使用 `expire_all()`，没有 flush 无关 pending state，没有改 UoW/schema/permission matrix。最终 corrective PostgreSQL 用例为 `1 passed, 15 deselected`，随后纳入完整 16 项 matrix。

## 3. 实现结果

### API 合同

- request 仅四字段：`workspace_id`、`knowledge_source_id`、`idempotency_key`、`trace_id`。
- response 仅两字段：`ticket_id`、固定 `accepted` status。
- 422 固定为 `stage08_retrieval_request_invalid`，不回显 invalid body、嵌套字段或安全对象。
- 403 不区分 workspace/source 不存在、跨 workspace、非成员或无 `member.manage`。
- source/current-memory lifecycle 与 idempotency conflict/in-progress 为固定 409 类别。

### 权限与 source 验证

- verified identity 先由既有 `authorize_workspace_action(..., "member.manage")` 派生 Actor。
- service 再验证 current active workspace、唯一 active member、Actor/member role 一致。
- 只允许 owner/admin；仓库没有 canonical manager，manager/builder/operator/viewer 全部拒绝。
- 只允许 current active `memory_item`；读取既有 read-only projection，重算规范化 projection hash 和 `memory_lineage:<root>` fingerprint，验证完整 scope/version/source refs。
- source/Memory 的 revoked/deleted/expired/replaced、terminal timestamp、跨 workspace、漂移或 verifier 异常均不创建受理副作用。

### Ticket、幂等与 reference event

- `ticket_id` 即受理的 `stage08.knowledge.index_requested` reference event ID；不新增 execution ticket model。
- 同 source/version/hash 已有 index event 时安全复用；同语义 idempotency replay 返回同一 receipt。
- Stage06 idempotency `response_ref` 仅有 `ticket_id/status`。
- 同 key 改 source/trace 冲突；raw trace 不进入 outbox column、idempotency trace、audit 或 response。
- event/audit 仅在全部 current-state 验证成功后创建或复用；replay 不重复 audit。

## 4. Verification

Fresh mandatory commands：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py tests/api/test_stage08_retrieval_api.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_retrieval_api.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_provider.py app/schemas/stage08_retrieval.py app/api/routes/stage08_retrieval.py
```

Fresh results：

- D5 service/API：`109 passed in 11.19s`。
- D1-D5 focused：`220 passed in 12.12s`。
- dedicated pgvector：`16 passed in 7.95s`，0 skip。
- migration：唯一 head `20260720_0032`。
- extension：`vector=0.8.5`。
- compileall：exit `0`。
- `git diff --check`：exit `0`；仅共享 worktree 的 CRLF conversion warning。

Static scan：

- `expire_all=0`；
- production external provider/network/Telegram/Redis/LangGraph/Milvus import=0；
- production 默认 `TestHashEmbeddingProvider(...)` 构造=0；
- direct `Stage08MemoryItem.payload` read=0；
- route/schema request fields 与 response fields 均精确符合 brief。

## 5. PostgreSQL 事实与 Cleanup

真实 disposable PostgreSQL 覆盖：

- migration head 与 vector extension；
- owner/admin 受理、reference event 复用、idempotency replay/conflict、最小 audit；
- held-session member/source/Memory revoke 后立即拒绝且无新 event/audit/idempotency；
- 无关 pending row 不被 revalidation flush；
- source revoke 后 cleanup scrub chunk/vector/keyword/text；
- D0-D4 GIN/HNSW、keyword-only 与 current-state citation 回归继续通过。

外层 transaction rollback 后读回：source=0、chunk=0、outbox=0、idempotency=0、audit=0。

## 6. Skipped Tests / External Actions / Risks

- 未运行 full backend suite；执行了 brief 指定的完整 D1-D5 focused 与 pgvector matrix。
- 有效验证轮次无 skip；早期单独 RED/GREEN 轮次不计为最终通过证据。
- 未调用真实 embedding/LLM/OpenRouter、Telegram、HTTP、Redis、LangGraph、Milvus、浏览器、Mini App、staging、production 或部署。
- `document_projection` / `approved_summary` 继续 fail closed；真实语义召回质量尚未验证。
- 专用 pgvector container 保留供独立 Package D review；它不是 staging/production。
- 新的独立 Package D review 仍是强制门禁。本报告只提交实现与证据，不自行声明 D5/Package D/Stage08 完成。
