# Stage08 Package B Task B5：实施报告

## 交付范围

- 新建 B5 task brief、真实 PostgreSQL acceptance tests、Package B evidence 和本报告/复审包。
- 对 `enqueue_confirmed_record_memory_event` 做一处最小服务修复：已持久化 confirmed draft 在 outbox idempotency lookup 前取得既有 transition row lock。
- 未修改 migration、模型 schema、API、权限、Telegram/webhook、Provider、Redis、RAG、LangGraph 或部署配置。

## TDD 记录

1. **RED**：并发 PostgreSQL 测试使两个 session 对同一 confirmed draft enqueue。第二 commit 在唯一约束 `uq_outbox_events_idempotency_key` 失败，确认了真实 race。
2. **GREEN**：复用 draft transition row lock；两个 session 返回同一 event、数据库仅一条 outbox 行，并捕获到 `FOR UPDATE`。
3. 新增真实 PG 生命周期验收：独立 worker transaction materialize、reference-only event、隐藏字段/audit redaction、字段撤权、TTL、foreign workspace、source delete 的 fail-closed 行为。
4. 初次 aggregate suite 发现两项回归：未注册 in-memory draft 被新 lock 错误拒绝，以及 PG evidence 不应把 producer 和 worker 压进同一 `autoflush=False` transaction。前者改为“有 lock 即使用，无 lock 保持既有安全输入校验”，后者改为实际 outbox producer/worker 两事务；随后完整套件 fresh green。

## Fix Round 1：独立复审 I-01

- 初审结论不是生产缺陷，而是 confirmed-record 双会话测试没有直接证明第二 session 曾被 draft `FOR UPDATE` 阻塞。
- 测试现使用 two-phase Event coordination 与 PostgreSQL `pg_blocking_pids(second_pid)`：在第一 session 仍持有 draft lock 时，必须先观测第二 backend 被第一 backend 阻塞，之后才 commit/释放锁。
- 测试继续断言第二 session 复用相同 event、最终仅一条 outbox，并用 SQL capture 验证 draft lock 查询发生在 outbox idempotency lookup 前。
- `finally` 对 timeout/assertion 的未关闭第一事务 rollback，并 `executor.shutdown(wait=True)`；未新增生产代码、schema/API/permission 或外部调用。

## Changed Files

- `backend/app/services/stage08_memory.py`：并发 enqueue 的 draft row-lock/idempotency 修复。
- `backend/tests/integration/test_stage08_memory_postgres.py`：B5 confirmed outbox 并发、redaction/field-revocation、TTL/cross-workspace/source-deletion 证据。
- `.superpowers/sdd/stage08-package-b-task-b5-brief.md`：实施前范围与 B-01~B-05 映射。
- `project-docs/08-implementation/evidence/stage08-package-b-memory.md`：命令、RED/GREEN、边界、风险与清理记录。
- `.superpowers/sdd/stage08-package-b-task-b5-review-package.md`：独立复审输入。

## Verification

- Targeted concurrent PG RED：真实 `IntegrityError`，已记录于 evidence。
- Targeted concurrent PG GREEN：pass。
- Fix Round 1 fresh Package B module suite：`120 passed in 20.67s`。
- `python -m alembic heads`：单一 `20260718_0029 (head)`。
- `python -m compileall -q ...`：exit 0。
- B5 范围 `git diff --check`：exit 0。

## Skipped / Remaining Risks

- 未跑完整 backend suite、production DB、真实 Telegram/LLM 或部署。
- 未声称 Package B/Stage08 完成；需要独立 task review 后才由父任务决定是否更新进度真源。
