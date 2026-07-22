# Stage08 Package D / D5：受控 Reindex API 与最终 PostgreSQL 证据实施简报

## 状态、目标与已确认边界

- Status：`implementation approved by existing Stage08 Package D plan`
- 前置：D0–D4 已关闭；D4 fresh-current-state independent review 为 `0 Critical / 0 Important / 0 Minor`。D5 是 Package D 的最后一个实现任务，但 D5 完成和复审前不得宣称 Package D 或 Stage08 完成。
- 目标：新增一个**仅管理者可调用**的 `POST /api/stage08/knowledge/reindex`，为服务器已经验证的知识 source 创建或复用 reference-only reindex 事件，并以一个安全的受理回执返回。它不查询知识、不上传文档、不接受投影/正文/embedding/query/filter/scope，也不调用任何外部 provider。
- 这是已批准的 Package D API 合同落地，不新增 schema/migration、权限角色、Telegram、LLM/embedding provider、Milvus、文档传输或部署。

## 唯一允许的改动文件

- Modify：`backend/app/services/stage08_retrieval.py`
- Create：`backend/app/schemas/stage08_retrieval.py`
- Create：`backend/app/api/routes/stage08_retrieval.py`
- Modify：`backend/app/main.py`
- Create：`backend/tests/api/test_stage08_retrieval_api.py`
- Modify：`backend/tests/unit/test_stage08_retrieval_service.py`
- Modify：`backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Create：`project-docs/08-implementation/evidence/stage08-package-d-rag.md`
- Create：`.superpowers/sdd/stage08-package-d-task-d5-report.md`

禁止修改 models、migrations、Stage06 UoW/interface、身份机制、全局角色矩阵、其他 API、Docker/configuration、Package E/F 文件、Git state 或外部系统。

## API 合同与权限

1. 路由只接受一个严格 Pydantic body，字段精确为 `workspace_id`、`knowledge_source_id`、`idempotency_key`、`trace_id`；拒绝任何额外字段。所有 ID 在服务端解析；不可从客户端接受 `projection_text`、`chunk_text`、`embedding`、`query`、`filter`、`scope`、`source_type`、`source_status`、`ticket_status`、actor/role 或任何 source 内容。
2. 回应 JSON 仅有 `ticket_id`、`status`。`ticket_id` 是本次受理的内部 reference event/ticket 标识；不得返回 source/chunk/record/field UUID、正文、query、scope、hash、embedding、profile、actor、authority、审计状态或错误细节。
3. 先用已验证 API identity 派生 actor，再用既有 `member.manage` 行为授权；当前 canonical roles 中它只允许 active `owner`/`admin`。仓库并不存在可新增的 `manager` 角色：D5 必须 fail closed，而不是创建 role、扩展 `ROLE_ACTIONS` 或把 builder/operator/viewer 当 manager。身份、workspace、membership、source、active lifecycle 或 source/workspace 不匹配均拒绝。
4. 所有 source selector 与权限、source-specific 可读性/lifecycle、trace 格式和 idempotency 均由服务端再次验证。D4 的 `document_projection` 与 `approved_summary` 仍因缺少 approved origin verifier 而 fail closed；当前实现不得借 D5 放宽它们。`memory_item` 只能通过既有 read-only projection/lineage 规则，不得直接读 payload。
5. 在 service boundary 使用既有 Stage06 idempotency record 机制；同 workspace/operation/key 与相同语义请求重放同一安全回执，不同语义请求得到 `409 idempotency_conflict`。trace 不得由客户端任意覆盖服务端 idempotency trace 绑定；不引入 execution ticket model 或新的 schema。
6. 仅在验证成功后创建或复用既有 reference-only `stage08.knowledge.index_requested` outbox event，并写入最小审计。outbox/audit 不得包含 projection/chunk/embedding/keyword/query/scope UUID、文件名、Memory payload、group/Message carrier 或 provider 回应。这个端点只“请求重建”，不在 HTTP 请求中调用 embedding、LLM、HTTP、Telegram、Redis、LangGraph 或 worker。
7. 采用与相邻 Stage08 routes 相同的 redacted validation/error envelope：额外字段或无效 body 为 422；权限失败 403（不存在 workspace/source 不泄漏为 404）；idempotency conflict/in-progress 和无效 source lifecycle 为 409；响应和 `repr`/exception 不泄密。所有 SQLAlchemy request path 正常 commit；失败 rollback；InMemory 不产生隐式外部副作用。
8. **消费期当前态重验（D5 corrective requirement）。** 真实 PostgreSQL RED 已证明：同一 SQLAlchemy session 先缓存 active member，再以 Core/current database operation 将成员改为 inactive，普通 getter 会继续允许 reindex。D5 必须像 D4 一样只在本 service 的 authorization/source revalidation 使用窄范围 `select(...).execution_options(populate_existing=True, autoflush=False)` 与 `session.no_autoflush`，重读 workspace、membership、knowledge source 和 `memory_item` 所需 metadata；不得使用 `expire_all()`、不得 flush 无关 pending state、不得扩 UoW 或角色矩阵。任何 current-read failure、membership/source/lifecycle/scope drift 必须 403/409 或 fail closed，不能创建 event/audit/idempotency 记录或输出 receipt。

## TDD 证据

必须先写 RED、记录预期失败，再最小 GREEN。至少覆盖：

1. anonymous/invalid identity、owner/admin 正向、builder/operator/viewer/非成员拒绝，source 跨 workspace、不存在、replaced/revoked/deleted/expired 及 `document_projection`/`approved_summary` 拒绝；不能用 client-provided role 绕过。
2. 禁止字段、嵌套 carrier、错误 UUID/trace/idempotency、源状态/投影/正文/embedding/query/filter/scope/ticket 字段均为 redacted 422；DTO 与错误/repr 不泄漏安全对象。
3. 同 key+相同语义的 replay 只得到同一 `ticket_id/status`、只有一条 reference-only index event 和一条最小审计；同 key+不同 source 或 trace 409；不以 client trace 生成可冲突的服务端 trace。
4. outbox payload/审计字段只含允许的 reference metadata；没有 raw projection/chunk/embedding/keyword/query/scope/message/payload。没有同步 embedding/provider/network 调用，也没有外部写入。
5. dedicated pgvector PostgreSQL 覆盖 migration head、source lifecycle 与 API/service reindex 的事务/idempotency/cleanup，并保留 D0-D4 的 GIN/HNSW、keyword-only、current-state redaction 回归。必须在同一 held SQLAlchemy session 中以 Core/current database operation 撤销 membership、source 或 Memory lifecycle，再调用 D5 service/route；请求必须被拒绝且数据库中不得新增 event/audit/idempotency。另验证无关 pending row 在 current-state revalidation 后仍未 flush。

## 必跑命令

从 `backend` 执行，pytest 禁用 cache 且 warnings 为 error：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py tests/api/test_stage08_retrieval_api.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_retrieval_api.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m alembic upgrade head; python -m alembic heads; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_provider.py app/schemas/stage08_retrieval.py app/api/routes/stage08_retrieval.py
```

还必须运行 production-code privacy/external dependency scan 与 `git diff --check`；记录专用 pgvector 的 `vector` 版本、唯一 migration head、测试后 source/chunk/outbox/idempotency/audit 清理读回。不得把 skip 计为通过。

## 报告、清理与复审门禁

`stage08-package-d-task-d5-report.md` 和 Package D evidence 需为中文，记录 RED/GREEN、精确命令、数据库事实、允许字段、拒绝类别、权限矩阵、idempotency、审计/outbox redaction、静态边界、跳过项、cleanup 与风险。不得写入 credential、DSN、UUID、正文、query 或 payload。

完成后必须进行一轮新的独立 Package D review，涵盖 D0–D5；在该 review 之前不得更新 Package D 为 closed，也不得开始 Package E。
