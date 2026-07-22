# Stage08 Package D / D0–D5 最终独立复审报告

## Review Result

- Review date：2026-07-21
- Result：`PASS`
- Findings：`0 Critical / 0 Important / 1 Minor`
- Closure eligibility：Package D 当前满足交由 root agent 关闭并交接 Package E 的条件。本报告不自行关闭 Package D，也不声称 Package E/F、真实 Provider 质量、生产部署或 Stage08 已完成。
- Review boundary：完整对照 final-review brief、Package D data contract、BDD/acceptance、implementation plan、D0–D5 实施/纠正/独立复审证据及当前生产代码和 tests。唯一写入为本报告；未修改 application、tests、contracts、models、migration、API、Docker/config、Git 或外部系统。

## Findings

### Critical

无。

### Important

无。

### Minor

#### M-01：D5 API 测试对 Starlette deprecation warning 使用了类别级忽略

`tests/api/test_stage08_retrieval_api.py` 在测试模块中执行 `warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)`。它没有修改 production 或全局 pytest 配置，范围也只针对一个 Starlette warning 类别，因此不影响 D0–D5 生产行为和当前关闭判断；但 Python warning filter 在同一 pytest 进程内是进程级状态，API 模块收集后可能掩盖后续测试产生的同类别 warning。建议 Package E 开始前或测试基础设施整理时，改为精确 message/module filter 或局部 context/pytest marker，并单独跟踪 Starlette/httpx2 兼容升级。此项不阻断 Package D。

## D0/D1 Migration 与 pgvector 基线

- 仅使用 final-review brief 指定的 loopback disposable Stage08 RAG PostgreSQL；未回退 native Stage06 PostgreSQL、默认 `DATABASE_URL` 或外部数据库。
- 独立执行 `alembic upgrade head -> heads -> downgrade 20260720_0031 -> upgrade head -> current` 全部 exit `0`；最终 current/head 均为唯一 `20260720_0032`。
- 数据库直接读回 `vector=0.8.5`。
- `stage08_knowledge_chunks` 上真实存在：
  - `ix_stage08_knowledge_chunk_keyword_terms_gin`
  - `ix_stage08_knowledge_chunk_hnsw_test_profile`
  - source/status、workspace/status/source/version、唯一 source/version/ordinal 及主键索引。
- 当前 approved compose 静态声明 `pgvector/pgvector:pg17`、loopback port、tmpfs 数据目录；reviewer 沙箱不能读取本机 Docker pipe，因此未把 `docker compose ps` 当本轮成功证据。真实迁移、extension/catalog、索引和 16 项 PostgreSQL integration 均由数据库连接独立验证，且 D0 独立复审已有容器隔离证据。

## D2/D3 Source Lifecycle 与 Worker

- D2 contract、chunking、source/version/scope composite integrity、Memory root lineage、reference-only index/cleanup event、trace reference redaction 均在本轮 focused matrix 中回归通过。
- D3 index/cleanup worker 的 replay、partial failure、source drift、chunk read failure、embedding unavailable/invalid output、revoke/replace/delete cleanup 均通过。
- 未注入 provider 时维持明确的 `embedding_provider_unavailable` / keyword-only 语义；production 没有默认构造 deterministic test provider，也没有调用真实 embedding 服务。
- 生产路径不直接读取 `Stage08MemoryItem.payload`；Memory 文本只经既有 read-only safe projection 进入 source adapter。outbox 仍为 reference-only，清理会 scrub source/chunk text、keyword 和 vector。

## D4 Retrieval、Fresh State 与隐私

- PostgreSQL integration 捕获到真实 keyword `&&` 与 pgvector cosine `<=>` SQL；GIN/HNSW 不是仅凭 migration 名称推断。
- structured pre-filter 只缩小候选，最终 evidence/citation/safe view 仍经过 authority、source、chunk、Memory lineage 与业务关系重验。
- search 后 source revoke、employee pause、view/member/grant/business relation drift、source/chunk terminal timestamp 与 Memory root fingerprint drift 会使 held evidence、citation 和 safe view 立即不可用。
- SQLAlchemy 路径只使用局部 `populate_existing=True`、`autoflush=False` 和 `session.no_autoflush`；production static scan 的 `expire_all=0`。无关 pending state 回归证明未被隐式 flush。
- safe citation/DTO/repr/error 不包含正文、检索输入、内部 UUID、scope、score/vector、authority 或 provider detail。

## D5 API、权限、幂等与无副作用重验

- 路由已在 `app/main.py` 注册：`POST /api/stage08/knowledge/reindex`。
- strict request 字段精确为 `workspace_id`、`knowledge_source_id`、`idempotency_key`、`trace_id`；response 精确为 `ticket_id`、固定 `accepted`。额外字段、无效 ID/trace/idempotency 和 nested carrier 均为固定 redacted 422，不回显非法字段或值。
- actor 来自 verified request identity 与既有 `authorize_workspace_action(..., "member.manage")`；production `ROLE_ACTIONS` 未改。当前 canonical role 中只有 active owner/admin 通过，builder/operator/viewer/non-member 及不存在于 canonical matrix 的 manager 均 fail closed。
- workspace/source 不存在或跨 workspace 使用非披露 403；source lifecycle、Memory verifier、idempotency conflict/in-progress 使用固定 409 类别。`document_projection` / `approved_summary` 继续 fail closed。
- 同 workspace/operation/key 且相同语义 replay 返回同一安全 receipt；改变 source 或 trace 为 409。只创建/复用同一 reference-only index event，idempotency `response_ref` 仅含 ticket/status，replay 不重复 audit。
- HTTP/service 路径没有同步调用 worker、embedding、LLM、HTTP、Telegram、Redis、LangGraph 或 Milvus。

### Held-session current-state 证据

专用 PostgreSQL 用例在同一 SQLAlchemy Session 已缓存 active 数据后，以直接数据库更新改变当前事实，并先反查确认，再调用 D5 service：

- active member 改为 inactive：固定拒绝；
- active source 改为 revoked：固定拒绝；
- active Memory item 改为 revoked：固定拒绝；
- 三种拒绝后的 outbox、idempotency、audit 数量均未增加；
- Session 中无关 pending Workspace 仍在 `session.new`，数据库查无该行，证明 fresh revalidation 没有旁路 flush。

这直接关闭了 held-session identity-map 旧状态导致“撤权后仍受理”的风险。source cleanup 后再次 reindex 也拒绝，且不会留下新的 idempotency reservation。

## Mandatory Verification

所有 pytest 从 `backend` 执行，使用 `-W error -p no:cacheprovider`；有效轮次无 skip。

| Verification | Fresh result |
| --- | --- |
| Alembic upgrade / heads / downgrade / re-upgrade / current | 全部 exit `0`；最终唯一 `20260720_0032` |
| D1–D5 final focused matrix（unit + API + dedicated PostgreSQL） | `236 passed in 19.52s` |
| 其中 dedicated pgvector integration | `16 passed`，无 skip |
| Package D production `compileall` | exit `0` |
| `git diff --check` | exit `0`；仅共享 worktree 既有 LF/CRLF 提示，无 whitespace error |

## Static / Privacy / External Boundary

本轮对 Package D production files 的 scan 结果：

```text
expire_all=0
external_provider_or_network_imports=0
raw_sql_import_or_from_statement=0
default_test_hash_provider_construction=0
direct_memory_payload_read=0
synchronous_external_call_symbols_in_D5_path=0
```

- 无 OpenRouter/OpenAI/Telegram/HTTP/Redis/LangGraph/Milvus production dependency 或调用。
- Provider PostgreSQL 查询使用 SQLAlchemy expression；raw SQL 仅见于 integration/catalog reviewer evidence，不在 production。
- `repr`、validation/error envelope、receipt、idempotency、outbox 与 audit 的测试投影未发现正文、检索输入、embedding/vector、group/Telegram carrier、Memory payload 或 provider response。
- D5 audit 只保留固定事件类型、受理状态、reference event、source category/version 与 `member.manage`/server-derived role；没有 client raw trace 或业务正文。

## Cleanup、Skipped 与 Remaining Risks

测试 transaction rollback 后，数据库直接读回：

```text
stage08_knowledge_sources=0
stage08_knowledge_chunks=0
outbox_events=0
stage06_idempotency_records=0
ops_audit_events=0
```

- 无 skipped-as-pass；未运行 full backend suite，因为 final-review brief 要求的是 D1–D5 focused matrix。
- 未调用真实 embedding/LLM/OpenRouter、Telegram、HTTP、Redis、LangGraph、Milvus、浏览器、staging、production 或部署。
- 未创建临时脚本、日志、凭据、DSN 文件或业务数据；approved disposable pgvector container 保留给后续开发，不是 production evidence。
- 剩余非阻断风险：真实 embedding/LLM 的语义召回、成本、延迟与回答质量仍属于 Package F；Coordinator/LangGraph 协作属于 Package E；document/approved-summary origin verifier、生产备份/恢复、容量和部署均尚未实现或验证。

## Recommendation

本次最终独立复审为 `0 Critical / 0 Important / 1 Minor`。建议 root agent 关闭 Package D，更新阶段真源/验收矩阵，并按既定计划交接 Package E；M-01 作为测试基础设施债务继续跟踪。此结论不扩大到真实 Provider 质量、Package E/F、生产部署或 Stage08 整体完成。
