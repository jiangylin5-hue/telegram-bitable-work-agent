# Stage08 E5：生产 Coordinator 并行、取消与 deadline 修复决定

## Status

- Decision status：`implementation correction for an approved Package E contract`
- Date：2026-07-22
- Trigger：Package E final independent review I-01（`0 Critical / 1 Important`）
- Scope：`run_stage08_collaboration` 的实际 C3/D4 读取、deadline 与取消执行；不改变 public API/schema/permission/provider/Telegram/deployment。
- Outcome：E5 与 request-session factory remediation 已由 task review、remediation review 和 fresh Package E re-review 收口（最终 `0 Critical / 0 Important / 0 Minor`）；compact E `218 passed`、real loopback pgvector PostgreSQL `3 passed`。Package E 可关闭。

## 已确认缺口

现有 LangGraph 只有形式上的三路 fan-out：生产 Coordinator 把三个 read node
注入为 no-op，并在 `fan_in` 顺序执行全部 C3/D4 读取；`CollaborationBudget`
虽含 wall/provider 限额，实际没有 deadline 或 server-side cancellation 检查。

因此 E1 topology 的 unit 通过不等于 E2/E-02 的生产 bounded
parallel/cancel/timeout 已交付。Package E 在此修复前保持 `HOLD`。

## 决定

不降低已批准的“bounded parallel read、可取消、可降级”合同。新增一个仅进程内、
不可序列化的生产执行边界：

1. `read_composite_context`、`read_retrieval` 和 `mark_general_advice` 必须承载真实
   分支逻辑；`fan_in` 只能合并 sealed branch result，不得再承载全部业务读。
2. SQLAlchemy 分支使用独立、只读、调用结束即关闭的 session/UoW，避免多个线程共享
   request transaction/session。原 request UoW 仍只拥有 E3 policy/ticket/draft 写事务；
   E3 已有消费期 current-state lock/revalidation 继续是写前真源。
3. InMemory UoW 只允许串行测试 fallback，不能作为“生产并行”证据；真实 loopback
   PostgreSQL integration 必须证明两个 read branch 有重叠执行且不共享 session。
4. `Stage08CollaborationRuntimeControl` 仅内部注入：固定 monotonic deadline、取消 probe
   和每节点检查。取消或 deadline 到达后直接进入 `cancelled/timed_out`，不进入
   analyser、Policy Gate、Gateway 或 draft。
5. 所有 read、compression、analysis、policy、draft 前后检查 remaining budget；provider
   继续接收固定 `CollaborationBudget`。E5 不接真实 Provider；Package F 必须让真实
   HTTP adapter 使用同一 deadline 配置其 transport timeout。
6. Branch 失败只产生合同已有的 degradation；branch/cancel/deadline private carrier 不得
   进入 API、AgentRun、audit、outbox、log 或 idempotency projection。

## 不变项

- 不新增 migration/model/global role/public route/request/response 字段；
- 不在 Agent 节点直连 ORM/raw SQL；实际 read 仍经既有 C3/D4 service；
- 不允许取消/超时路径产生 ticket、draft、outbox 或外部 side effect；
- 无真实 OpenRouter、Telegram、Milvus、部署调用；
- Stage06 默认路径和 E3 `stage08_e3_safe` adapter 语义不变。

## 验收

1. 生产 node 不再是 no-op；SQLAlchemy 两个真实 read branch 用独立 session 重叠执行，
   fan-in 后只有 sealed aggregate；
2. cancel/deadline 在 read/compression/analysis/policy/draft 各边界 fail closed，并且
   不产生 ticket/draft/idempotency/audit orphan；
3. 读取/Provider 延迟超过 budget 返回固定 `timed_out`，其后的 policy/Gateway 不调用；
4. C3/D4 scope/source/mapping 当前态验证、E3 原子草稿和 E4 safe replay 回归保持；
5. 以 focused unit/API 加真实 loopback pgvector PostgreSQL 主路径取证，随后 fresh E
   package review 为 `0 Critical / 0 Important` 才关闭。
