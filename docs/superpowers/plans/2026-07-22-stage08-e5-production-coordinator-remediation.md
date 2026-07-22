# Stage08 E5 生产 Coordinator 修复实施计划

## Goal

修复 E final review I-01：使实际 Coordinator（而非 fake graph）执行真实 bounded
parallel C3/D4 reads、cancel 和 deadline。该任务是 Package E 的 remediation，不是新的
产品包；E5 完成并独立复审后 Package E 才能关闭。

## Constraints

- 完整遵守 `STAGE_08_E5_PRODUCTION_COORDINATOR_EXECUTION_DECISION.md`；
- 不新增公开 API、schema/migration、权限、Provider、Telegram 或部署；
- 仅 SQLAlchemy request path 可以作为真正并行证据；InMemory fallback 仅维持单元测试；
- 所有 branch private material、session factory、runtime control 均 process-local、不可
  JSON/pickle/DTO/audit/log；
- 先 RED 再 GREEN；只测试此次真实缺口及既有 E 主链路回归。

## Task E5.1：Runtime control 与生产 read branch 架构

### Files

- Modify `backend/app/services/stage08_collaboration.py`
- Modify `backend/app/agents/stage08_collaboration.py` only if node boundary/
  reducer needs a sealed branch carrier
- Modify `backend/app/runtime/stage08_collaboration_contracts.py` only for
  process-local runtime/branch carrier validation
- Modify focused service/graph tests
- Create `.superpowers/sdd/stage08-package-e-task-e5-report.md`

### RED cases

1. 在生产 `run_stage08_collaboration` 中，三个 read node 不再允许全部 `unchanged`；
   要能证明 composite/retrieval branches 真正执行，`fan_in` 不执行 C3/D4 I/O。
2. 用 barrier/clock 注入证明 SQLAlchemy 分支有重叠、session identity 不同；InMemory
   同路径不宣称并行。
3. 取消或 wall deadline 在每个阶段触发时，result 是 `cancelled/timed_out`，analysis、
   policy、Gateway/draft 计数均为零。
4. slow compressor/analysis provider 超过固定剩余 deadline 后不进入后继 stage；请求
   仅产生允许的 minimal terminal audit。
5. branch result、runtime control、isolated UoW/session 不能进入 safe view、AgentRun、
   audit、outbox、idempotency 或 exception message。

### GREEN implementation

1. 定义 sealed `Stage08CollaborationRuntimeControl` 和 per-run collector；它只提供
   `monotonic_now`、deadline/cancel probe、branch/session identity，不接受客户端值。
2. 将实际 C3 composite、D4 retrieval、general marker 移到三条 graph branch；每条 branch
   使用 isolated read UoW（SQLAlchemy）或锁定的 InMemory fallback。`fan_in` 只合并
   collector/state；compression node 执行 pending group 的受控压缩。
3. 在 node entry/exit 与 provider/compressor 边界调用 control；deadline/cancel 转为
   sealed terminal state，并由 graph routing 跳过所有后继 action node。
4. 保持 E3 materialize 使用原 request UoW 和当前-state locks；对 branch source/plan/proof
   的现有消费期重验不作放宽。

### Verification

Run focused E service/graph/contracts/API tests, existing E PostgreSQL file and new SQLAlchemy
parallel/cancel/deadline cases on disposable loopback pgvector, then compileall/diff check.

## Task E5.2：Independent review and Package E re-review

Fresh reviewer confirms no no-op production fan-out, isolated SQLAlchemy session behavior,
cancel/deadline fail-closed behavior, no E3/E4 regression and no public/external expansion.
Then a compact E package re-review decides closure.
