# Stage08 Package E / E5 生产 Coordinator 修复实施报告

## Status

- Task：`E5 production coordinator remediation`
- Result：`IMPLEMENTED + I-01 SESSION-FACTORY REMEDIATED — pending independent re-review`
- Date：2026-07-22
- Boundary：仅修改 Stage08 collaboration service 与定向测试；没有新增 public API、schema/migration、permission role、真实 Provider、Telegram、Milvus、部署或 Git 写操作。
- Closure：本报告不宣布 Package E 关闭；依 brief 仍需 fresh independent review。

## Changed files

| 文件 | 改动 |
| --- | --- |
| `backend/app/services/stage08_collaboration.py` | 新增不可序列化的 `Stage08CollaborationRuntimeControl`、per-run opaque collector 和 coordinator-issued read-session factory；主线程在 fan-out 前一次性从 request session 解析 bind，worker 仅使用 factory 创建 isolated read-only session；将 C3/D4/general marker 真实读取移入三个生产 graph node，`fan_in` 只合并；在 read/compression/analysis/policy/draft 边界实施 cancel、wall deadline 与 provider deadline。 |
| `backend/tests/unit/test_stage08_collaboration_service.py` | 新增生产 node/fan-in、before/during-read cancel、provider timeout、Gateway 期间 cancel rollback、runtime-control opaque/non-serializable 证据及 trace 脱敏断言。 |
| `backend/tests/integration/test_stage08_collaboration_postgres.py` | 新增真实 loopback pgvector PostgreSQL barrier 证据：C3/D4 两个生产读分支同时打开、重叠执行且 child session identity 不同；I-01 修复后再用 thread-aware request-session proxy 证明任何 worker session method access 都为零；增加精确清理。 |
| `.superpowers/sdd/stage08-package-e-task-e5-report.md` | 本中文实施报告。 |

## 实现结果

### 0. I-01 request-session isolation 修复

- 首轮独立审查发现：子 `Session` 虽然不同，但旧 `_isolated_read_uow` 在每个 worker 内仍调用同一 request `Session.get_bind()`，违反 SQLAlchemy Session 不可并发共享的边界。
- 现在 `run_stage08_collaboration` 在 graph 构建/调用和 fan-out 之前，仅由 coordinator 线程调用一次 request `Session.get_bind()`，将 Engine 封装成 opaque、不可序列化的 `_Stage08ReadUowFactory`。
- SQLAlchemy worker 只能从该 factory 创建 child `Session`；`_isolated_read_uow` 的参数已从 request UoW 改为 factory carrier，C3、D4 与 compression revalidation 均不再触碰 request session/UoW 以获取 bind。
- InMemory factory 只保留原 UoW 并继续由 `_INMEMORY_READ_LOCK` 串行，未修改 Stage06 UoW protocol、public API 或任何 schema。
- PostgreSQL 用例将 request session 包装为 thread-aware proxy：主线程可以完成 plan/terminal 事务，任何 worker 读取任意 session method 都会记录并抛错。最终断言 worker touch 列表为空，同时保留 `Barrier(2)` 重叠和两个不同 child session identity 证据。

### 1. 生产 fan-out 不再是 no-op

- `plan_request` 仅在 request UoW 中构建当前计划与 group proof。
- `read_composite_context` 真实调用既有 C3 compose/render/controlled pending-material service。
- `read_retrieval` 真实调用既有 D4 authority/search/render/safe-view service，保留 consumption-time group/source proof。
- `mark_general_advice` 只产生既有受限 marker，不进行业务 I/O。
- `fan_in` 只检查 runtime terminal 并返回 reducer 已合并的 sealed state；单元测将旧 `execute_collaboration_reads` 替换为必然抛错函数，生产路径仍完成，证明 fan-in 不再执行旧的 C3/D4 I/O。
- pending group compression 由 `compress_group_context` node 执行，返回后再通过新的 isolated read UoW 验证 digest lineage。

### 2. SQLAlchemy 读分支真正隔离

- SQLAlchemy request UoW 仍仅拥有 E3 Policy/ticket/Gateway/draft 写事务。
- 每个 C3/D4 node 从 request session 的 engine 新建独立 `Session`，PostgreSQL 事务执行 `SET TRANSACTION READ ONLY`，调用完成立即 rollback/close；不在并行 node 共享 request session。
- InMemory 仅使用进程内 lock 串行 fallback，不作为生产并行证据。
- 真实 PostgreSQL 用例在两个 read-only session 已打开后用 `Barrier(2)` 强制会合，因此不依赖时间猜测；然后继续执行真实 C3/D4 branch，断言 session identity 不同。

### 3. cancel / deadline 在真实 service 生效

- `Stage08CollaborationRuntimeControl` 只能由内部 issuer 创建，repr 固定，JSON/pickle 序列化拒绝，不放入 graph state/DTO/persistence。
- 控制器使用 monotonic clock，固定执行现有 `30s wall / 20s provider` 预算，并 latch 首个 `cancelled/timed_out` 终态。
- plan/read/fan-in/compression/analysis/policy/finalize 进出口都检查控制器。Provider 返回后会用 provider-start monotonic 时间检查 20s 限额。
- draft 路径在 current-state lock/revalidation、ticket、Gateway、draft lookup 前后均检查；Gateway 内触发 cancel 时抛出内部固定 stop，使 E3 savepoint/InMemory boundary 回滚 ticket、idempotency、draft 和内部 audit，最后仅保留允许的 terminal AgentRun/audit。

### 4. 脱敏与既有 E3/E4 语义

- runtime control、collector、isolated session、branch result 都只存在 closure/process-local object，未增加 state/public response/replay projection 字段。
- cancel/timeout/Gateway-cancel 用例扫描整个 trace 的 AgentRun、audit、ticket summary 与 outbox，没有 UUID、caller actor、query、answer、field/value 或 private carrier。
- E3 仍使用原 request UoW 和已审查的 current-state locks/savepoint/safe audit；E4 request/response 与 versioned safe replay projection 没有修改。

## RED / GREEN 证据

### RED

首先新增生产 service 用例后执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_collaboration_service.py `
  -k "production_read_nodes or production_cancellation or slow_analysis"
```

结果：`4 failed / 24 deselected`；四个失败均是预期的
`AttributeError: module ... has no attribute '_create_stage08_runtime_control'`，证明旧生产路径没有 runtime control，新用例不是立即通过。

PostgreSQL barrier 用例同样在代码前已写入；首次运行因 compose service 名提取错误未正确组装临时 DSN，在 fixture 连接阶段失败，因此不把该次计为功能 RED。修正为读取 `stage08-rag-postgres` 后才执行真实证据，未输出 DSN/凭据。

I-01 复审后先扩展同一 PostgreSQL 用例，用 thread-aware proxy 包装 request session，任何 worker method access 立即抛出 `read_worker_touched_request_session`。修复前定向运行结果为 `1 failed / 2 deselected`，最终 safe view 由期望的 `completed` 变为 `failed`，证明旧 worker 确实从 request session 获取 bind。

### GREEN

1. 定向生产 service GREEN：`4 passed / 24 deselected`。
2. 完整 service 文件（加入 Gateway-cancel 和 opaque 后）：`30 passed in 1.81s`。
3. compact E suite：

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_collaboration_contracts.py `
  tests/unit/test_stage08_collaboration_graph.py `
  tests/unit/test_stage08_collaboration_service.py `
  tests/unit/test_stage08_tool_gateway.py `
  tests/unit/test_stage08_context_composition_service.py `
  tests/unit/test_stage08_retrieval_provider.py `
  tests/api/test_stage08_collaboration_api.py
```

Result：`218 passed in 10.22s`。

4. 临时进程环境从 compose 配置组装 loopback DSN，执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/integration/test_stage08_collaboration_postgres.py
```

Result：`3 passed in 4.80s`；包含新 E5 barrier/distinct-session 证据与既有 E3 draft/replay/rollback/revoke/lock 证据。数据是合成数据，专用 E5 committed fixture 在 finally 精确删除；首次 cleanup 失败留下的唯一已知 synthetic workspace 也已按明确 UUID 清除并确认不存在。

5. `python -m alembic heads`：`20260720_0032 (head)`。
6. 指定 E 源码 `compileall -q`：退出码 `0`。
7. 三个改动文件行尾空白 `rg` 扫描：无命中。`ruff` 未安装（`No module named ruff`），未把该项声称为通过。

### I-01 remediation fresh GREEN

1. E5 focused：`6 passed / 24 deselected in 1.34s`。
2. 整个 collaboration service：`30 passed in 1.75s`。
3. 真实 loopback pgvector PostgreSQL collaboration：`3 passed in 2.99s`；其中 no-touch + Barrier + distinct-session 定向用例单独为 `1 passed / 2 deselected in 1.93s`。
4. compact E regression：`218 passed in 10.80s`。
5. 指定 E 源码 `compileall -q`：退出码 `0`。
6. service/integration 行尾空白扫描：无命中。

## Skipped / external actions

- 按 brief 未运行 full repository/backend suite，未运行 Stage07/UI 验收。
- 未调用 OpenRouter/真实 Analysis Provider、Telegram/Bot API、webhook、Milvus、Redis 写入、部署或生产环境。
- 未执行 Git stage/commit/reset/checkout/clean/push。

## Remaining review points

- fresh reviewer 应重点核查：生产 node 是否真正承载 C3/D4；SQLAlchemy read-only session 是否完全与 request write session 隔离；cancel/provider timeout 是否在 Policy/Gateway 前 fail closed；Gateway 期间 cancel 是否由 E3 boundary 回滚；private runtime 是否无持久化出口。
- Package F 接入真实 HTTP Provider 时，transport timeout 仍必须使用同一预算；E5 本身没有实现真实 Provider adapter。
