# Stage08 Package E 最终独立复审报告

## 结论

- 复审日期：2026-07-22
- 范围：Package E / E1–E5，重点复核前次 final review I-01、E5 request-session isolation 修复，以及 E3/E4 主链路回归。
- 分级：**0 Critical / 0 Important / 0 Minor**。
- 决定：**CLOSE，Package E 可关闭并交接 Package F。**
- 本轮仅新增本报告；未修改业务代码或测试，未调用真实 Provider、Telegram、部署或其他外部系统。

## Findings

### Critical

无。

### Important

无。

### Minor

无。

## 前次 I-01 关闭证据

### 1. 生产 C3/D4/general read nodes 已执行真实分支

- `backend/app/services/stage08_collaboration.py:1252-1276` 的 `read_composite_context` 使用独立 read UoW 调用 C3 composite/render/pending-material 分支。
- `backend/app/services/stage08_collaboration.py:1278-1303` 的 `read_retrieval` 使用另一独立 read UoW 调用 D4 authority/search/render/safe-view 分支。
- `mark_general_advice` 仅生成既有受限 marker，不执行业务 I/O。
- `fan_in` 在 `1326-1334` 只读取 runtime terminal 并返回 reducer 已汇总 state，不再调用 C3/D4 或旧 `execute_collaboration_reads`。
- 生产 service 用例把旧 read helper 替换为必然抛错函数后仍完成，并记录到 composite/retrieval/general 三个真实 node。

### 2. request session 在 fan-out 前完成 bind/factory 交接

- `_create_stage08_read_uow_factory` 在 `420-450` 由 coordinator 一次性读取 request `Session.get_bind()`，将 Engine 封装为 process-local `sessionmaker`。
- `run_stage08_collaboration` 在 `1203-1215` 的 graph 构建和 `graph.invoke` 之前创建 factory/collector；worker closure 不再解引 request session 来创建 read session。
- `_isolated_read_uow` 在 `793-826` 只从 sealed factory 创建 child `Session`，PostgreSQL 事务显式设置 `READ ONLY`，并在 `finally` rollback/close。InMemory 依然使用进程内 lock 串行 fallback，未被当作生产并行证据。

### 3. 真实 PostgreSQL 同时证明 no-touch、overlap 与 distinct sessions

- `test_postgres_production_read_branches_overlap_with_distinct_isolated_sessions` 在 loopback `pgvector/pgvector:pg17` 上使用 `Barrier(2)`，强制 C3/D4 两个生产 read-only branch 同时到达，不依赖时间猜测。
- 该用例断言两个 child session identity 不同；thread-aware request-session proxy 会在任何 worker 触碰 request session 时立即抛错，fresh run 中 `request_session_worker_touches == []`。
- 这一证据同时保留 E3 的真实 PostgreSQL pending-draft/replay、savepoint rollback、scope revoke、outer cleanup 和双会话行锁用例。

### 4. cancel / wall / provider control 已进入生产 service

- `Stage08CollaborationRuntimeControl` 是 issuer/seal 保护的 process-local carrier，不可 JSON/pickle，未进入 graph state、API DTO、replay、AgentRun 或 audit。
- control 使用 monotonic wall deadline 和 provider budget，并 latch 首个 `cancelled/timed_out` terminal。plan/read/fan-in/compression/analysis/policy/draft/finalize 边界均检查 terminal。
- before/during-read cancel 的生产 service 用例证明 AnalysisProvider、Policy Gate、Gateway 调用数均为零，也没有 ticket/idempotency/draft。
- slow analysis 跨越 provider budget 后固定返回 `timed_out`，不进入 Policy/Gateway。Gateway 完成时触发 cancel 会由 E3 safe boundary 回滚 ticket、idempotency、draft 和内部 audit，最终仅留允许的 terminal 白名单摘要。

## E3/E4 未退化证据

1. **E3 safe execution：PASS**
   - Policy Gate 仍位于 ticket/Gateway 之前；request UoW 仍是 E3 write transaction 的唯一 owner。
   - current-state locks、single savepoint/InMemory rollback boundary、same-key safe draft replay、default/safe provenance 隔离和 trace-wide UUID/private redaction 未被 E5 改写。
   - PostgreSQL 文件 fresh 通过，保留 draft/replay、Gateway rollback、mapping revoke、root cleanup 和锁阻塞证据。
2. **E4 strict API/replay：PASS**
   - 仍只有 `POST /api/stage08/assistant/query`；client 不能提供 authority、budget、provider、tool 或 draft values。
   - request 异常仍是 redacted `422/403/404/409/500`；replay 先重验 current member/employee/target，再从 versioned six-field allowlist 投影严格重建 safe view。
   - E5 没有改动 public request/response、replay projection、API route 或 router registration。

## Fresh verification

在 `backend` 目录执行 compact E suite：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_collaboration_api.py
```

结果：`218 passed in 11.04s`。

从已有 compose 配置临时组装且未输出的 loopback DSN，执行完整 collaboration PostgreSQL 文件：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

结果：`3 passed in 3.12s`。容器为 healthy 本地 `pgvector/pgvector:pg17`；这是真实 SQLAlchemy/PostgreSQL 主路径，不是连通性烟测。

```powershell
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py app/schemas/stage08_collaboration.py app/api/routes/stage08_collaboration.py
```

结果：退出码 `0`。E5/E4 指定文件 `git diff --check` 退出码 `0`。

## 边界、跳过项与剩余风险

- 未发现 E5 新增 public API、schema/migration、permission/global role、真实 Provider、Telegram/webhook、Milvus 或部署行为；private runtime/factory/collector/session 无公开或持久化出口。
- 按 brief 未执行 full backend/repository suite、Stage07/UI、Package F 真实 LLM 质量评测、Telegram 或上线验收。
- E5 是 coordinator-level 合作式取消/超时；真实 HTTP Provider 的 transport timeout 和连接取消仍必须在 Package F adapter 使用同一 budget，不得把 E5 的返回后终止检查误称为可中断任意阻塞网络调用。
- `AgentRun.usage_summary.provider_calls` 在 Package E 仍表示真实外部 Provider 调用数，因本包仅使用 unavailable/deterministic in-process port 而为 `0`；Package F 接入真实 Provider 时必须使用真实计数/用量更新，否则会造成可观测性失真。
- PostgreSQL 用例完成 rollback/finally 精确清理；本轮没有新建容器、临时脚本、生产数据或外部资源。

## Final verdict

前次 Package E final review I-01 和随后 E5 request-session isolation I-01 均已被生产源码、生产 service 测试与真实 PostgreSQL no-touch/barrier/distinct-session 证据共同关闭。E3 原子草稿/安全审计与 E4 strict API/safe replay 无退化。本轮为 **0 Critical / 0 Important**，满足 final re-review brief 关闭条件，建议 **CLOSE Package E**。
