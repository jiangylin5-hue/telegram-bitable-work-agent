# Stage08 Package E / E5 I-01 修复独立复审报告

## 结论

- 复审日期：2026-07-22
- 范围：仅 E5 review I-01 request-session isolation 修复，以及直接受影响的 cancel/deadline、E3 draft rollback 和 E4 strict API 回归。
- 分级：**0 Critical / 0 Important / 0 Minor**。
- 建议：**PASS**。I-01 已关闭，可进入 Package E 最终复审。
- 本轮未修改业务代码或测试；仅新增本中文 remediation review report。

## I-01 关闭证据

1. **bind/session factory 在 fan-out 前生成：PASS**
   - `backend/app/services/stage08_collaboration.py:420-450` 的 `_create_stage08_read_uow_factory` 仅在 coordinator 边界读取一次 request `Session.get_bind()`，将 Engine 封装为内部 `sessionmaker`。
   - `run_stage08_collaboration` 在 `graph.invoke` 与 read fan-out 之前调用该 factory；后续 graph closure 不需要为 SQLAlchemy read branch 再解引 request session。

2. **worker 不再触碰 request Session/UoW：PASS**
   - `_isolated_read_uow` 参数已由 request UoW 改为 sealed `_Stage08ReadUowFactory`；SQLAlchemy worker 只调用 factory 中的 `sessionmaker` 创建 child `Session`。
   - C3、D4 和 compression digest revalidation 全部使用同一内部 factory，没有再从 request UoW 获取 bind。
   - factory 有 issuer/seal 保护，carrier 拒绝 pickle；未进入 graph state、DTO、audit、AgentRun 或 replay projection。

3. **PostgreSQL no-touch + barrier + distinct sessions：PASS**
   - 真实 loopback pgvector 用例使用 thread-aware request-session proxy；任何非 coordinator 线程的 session method access 都会抛出 `read_worker_touched_request_session`。
   - 实测中 `request_session_worker_touches == []`；C3/D4 两个 read-only branch 依然通过 `Barrier(2)` 重叠执行，两个 child session identity 不同。
   - child transaction 仍执行 PostgreSQL `SET TRANSACTION READ ONLY`，并在 `finally` 回滚、关闭；InMemory 仍由锁串行，没有被用作生产并发证据。

4. **cancel/deadline、E3/E4 未退化：PASS**
   - before/during-read cancel 仍在 analysis、Policy Gate、Gateway 之前终止；slow analysis 超过 provider budget 返回 `timed_out`。
   - Gateway 期间 cancel 仍通过 E3 safe execution boundary 回滚 ticket、idempotency、draft 与内部 audit。
   - 完整 PostgreSQL collaboration 用例仍覆盖 E3 draft/replay/rollback/revoke/lock；service + strict API 用例保持 E4 safe response/replay 语义。

## Fresh verification

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k "runtime_control or production_read_nodes or production_cancellation or slow_analysis or cancellation_during_gateway"
```

结果：`6 passed / 24 deselected in 1.84s`。

从已有 compose 配置临时组装、未输出凭据的 loopback DSN，执行 no-touch + barrier 定向用例：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py -k "production_read_branches_overlap"
```

结果：`1 passed / 2 deselected in 2.29s`。

执行完整 PostgreSQL collaboration 文件：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

结果：`3 passed in 3.55s`。

执行 service + E4 strict API 定向回归：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py tests/api/test_stage08_collaboration_api.py
```

结果：`60 passed in 8.75s`。

`python -m compileall -q app/services/stage08_collaboration.py` 结果为退出码 `0`；service/integration 行尾空白扫描无命中。

## Skipped / cleanup / remaining risk

- 按 remediation brief 未运行 full backend/repository suite、Stage07/UI 或 Package F 真实 LLM 评测。
- 未调用 OpenRouter、Telegram/Bot API、webhook、Milvus、部署或任何生产外部系统。
- 未执行 Git stage/commit/reset/checkout/clean/push，未创建新容器或持久测试资源。
- 本轮范围内没有 Critical、Important 或 Minor 遗留；Package E 是否整体关闭由随后最终复审决定。

## Final verdict

I-01 所指的 request `Session` 并发共享已被架构性移出 worker，且真实 PostgreSQL no-touch 探针、barrier 重叠和 distinct child sessions 证据同时成立。现有 cancel/deadline、E3 safe execution 与 E4 strict API 无定向退化，因此本轮建议 **PASS**。
