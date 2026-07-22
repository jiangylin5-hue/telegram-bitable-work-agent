# Stage08 Package E / E5 独立修复审查报告

## 结论

- 审查日期：2026-07-22
- 审查范围：仅 E5 production coordinator remediation，即生产 read node、I/O-free `fan_in`、SQLAlchemy read session 隔离、runtime cancel/deadline 和既有 E3/E4 主链路回归。
- 分级：**0 Critical / 1 Important / 0 Minor**。
- 建议：**HOLD**。修复 I-01 并做定向复审后，再进行 Package E 最终复审。
- 本轮未修改业务代码、测试或合同；仅新增本中文 review report。

## Important

### I-01：并发 SQLAlchemy 分支仍在 worker 内共享访问 request `Session`

**证据**

1. `backend/app/services/stage08_collaboration.py:718-720` 的 `_isolated_read_uow` 在每个 LangGraph read worker 内从同一 `source_uow.session` 调用 `get_bind()`，然后才创建新 `Session`。
2. `read_composite_context` 和 `read_retrieval` 并发调用该函数，因此两个 worker 会同时触碰同一 request `Session`。SQLAlchemy `Session` 是可变的事务对象，不应跨并发线程共享；“只调用 `get_bind()`”也没有形成不触碰 request session 的封闭边界。
3. 新 PostgreSQL barrier 用例能证明两个子 `Session` 同时打开且 identity 不同，但不能证明并发 worker 没有访问 request `Session`。该用例目前也没有对 request session 访问做任何探针或断言。

**影响**

- 这违反 E5 决定中“SQLAlchemy 并发分支不共享 request session/UoW”的明确边界，也使当前的并发安全依赖 `Session.get_bind()` 在特定 SQLAlchemy 实现中恰好不修改状态，而不是由架构隔离保证。
- 子 `Session` 本身的 read-only transaction、rollback 和 close 语义没有被否定；缺口发生在创建子 `Session` 之前的 Engine/bind 获取方式。

**必需修复**

- 在进入 graph fan-out 前、仍处于 request 调用线程时，从 request UoW 一次性提取 Engine/bind 并构建进程内部 session factory；并发 node 只接收该 factory/Engine，不得再访问 `source_uow.session`。
- 保持每分支独立 `Session`、PostgreSQL `SET TRANSACTION READ ONLY`、`finally` rollback/close；InMemory 继续使用串行 lock fallback。
- 补一个定向证据：在 fan-out 之后，任何 worker 内对 request `Session`/request UoW 的访问都必须使测试失败；保留现有 PostgreSQL barrier/distinct-session 真实证据。

## 已通过的 E5 审查项

1. **真实 read node / I/O-free `fan_in`：PASS**
   - `read_composite_context` 真实调用 C3 compose/render/pending-material；`read_retrieval` 真实调用 D4 authority/search/render/safe-view；`mark_general_advice` 生成受限 marker。
   - `fan_in` 仅读 runtime terminal 并返回 reducer 合并状态，没有 C3/D4 I/O。定向用例把旧 `execute_collaboration_reads` 替换为必然抛错函数后，生产主路径仍完成。
2. **子 `Session` 资源边界：PASS（不包含 I-01 的创建前 bind 获取）**
   - 每个 SQLAlchemy 分支创建不同 `Session`；PostgreSQL transaction 设为 read-only，结束时回滚并由 context manager 关闭。
   - InMemory 路径由 `_INMEMORY_READ_LOCK` 串行，没有被当作生产并发证据。
3. **cancel/deadline 和后续 side effect：PASS**
   - runtime control 是 issuer/seal 保护、不可 JSON/pickle 序列化的进程内 carrier。
   - plan/read/compression/analysis/policy/draft/finalize 边界均有前后终止检查；provider 超过固定预算后返回 `timed_out`，且不再进入 Policy/Gateway/draft。
   - Gateway 内触发 cancel 时，E3 safe execution boundary 回滚 ticket、idempotency、draft 及内部 audit。
4. **降级、脱敏和 E3/E4 回归：PASS**
   - C3/D4 异常转换为既有 safe degradation；provider shape drift/forged/exception 依旧 fail closed。
   - runtime control、collector、branch result、query、provider private output 没有进入 safe view、AgentRun、audit、outbox 或 replay projection。
   - C3/D4 consumption-time proof、E3 current-state locks/savepoint/safe audit 和 E4 strict API/replay 未被放宽。

## Fresh verification

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k "runtime_control or production_read_nodes or production_cancellation or slow_analysis or cancellation_during_gateway"
```

结果：`6 passed / 24 deselected in 1.47s`。

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py
```

结果：`30 passed in 2.70s`。

从已有 compose 配置临时组装、未输出凭据的 loopback DSN，在 healthy `pgvector/pgvector:pg17` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

结果：`3 passed in 3.09s`。新用例用 `Barrier(2)` 强制 C3/D4 两个真实 read-only 分支重叠，并断言两个子 session identity 不同；其余用例保留 E3 draft/replay/rollback/revoke/lock 证据。

## Skipped / cleanup / remaining risk

- 按 brief 未运行 full backend/repository suite、Stage07/UI 或 Package F 真实 LLM 评测。
- 未调用 OpenRouter、Telegram/Bot API、webhook、Milvus、部署或任何生产外部系统。
- 未执行 Git stage/commit/reset/checkout/clean/push，未创建新容器或持久测试资源。
- 当前唯一阻塞风险是 I-01；修复应仅调整内部 bind/session-factory 获取位置，不需要改 public API、schema/migration、permission、Provider、Telegram 或部署合同。

## Final verdict

E5 已把真实 C3/D4 工作移入生产 graph branch，且 cancel/deadline、safe rollback 与脱敏主链路有新鲜证据；但并发 worker 仍在创建子 session 前共享访问 request `Session`。因 E5 review brief 要求分支不使用 request session，本轮结论是 **HOLD**。
