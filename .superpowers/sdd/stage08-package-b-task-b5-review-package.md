# Stage08 Package B Task B5：独立复审包

## Review Scope

审查以下精确变更，确认它们仅为 B5 PostgreSQL 证据与并发 idempotency 修复：

1. `backend/app/services/stage08_memory.py` 的 confirmed-record enqueue draft row lock。
2. `backend/tests/integration/test_stage08_memory_postgres.py` 的 B5 PG tests。
3. B5 brief、evidence、report 文档的事实准确性与不夸大表述。

## 必查不变量

- row lock 在 idempotency lookup **之前**，并只对已持久化 draft 生效；不破坏 in-memory UoW 和正常 confirmation hook。
- 没有新增 migration、schema、API、role/action 或任何外部系统调用。
- event payload 仍严格是六个 reference-only key，不能包含 record values、identity token、隐藏字段或 raw 内容。
- 两 session PG race 后第二调用复用同一 event，而不是接受 `IntegrityError`、重复行或隐式重试。
- field revoke/TTL/source delete/cross-workspace 的测试确实操作真实 PostgreSQL 路径而不是 mock/in-memory 替代。
- evidence 正确区分 local PostgreSQL、unit route 和 production/Provider/Telegram 未测内容。

## Fresh Evidence Available

- Fix Round 1 focused PG：`test_confirmed_record_outbox_enqueue_is_idempotent_across_competing_postgres_sessions` 通过；其使用 `pg_blocking_pids` 证明第二 session 在第一 draft row lock 上阻塞。完整模块 suite：`120 passed in 20.67s`。
- `alembic heads`：`20260718_0029 (head)`。
- `compileall` 与 B5 scoped `git diff --check`：exit 0。

## Out of Scope

不得因复审顺手扩展到 Package C、RAG、LangGraph、Telegram API/ingestion、Provider、Redis、Milvus、部署、前端，或改变任何 Stage08 source-of-truth/plan 完成状态。
