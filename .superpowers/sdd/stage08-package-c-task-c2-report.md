# Stage08 Package C2 — Task 5 PostgreSQL 收口报告

## Status

- Status：`DONE_WITH_CONCERNS`。
- Scope：Task 5 only；Task 6 independent review 尚未开始。
- Result：真实 PostgreSQL drift/privacy/concurrency 用例通过；发现并修复一个 fresh materialization 与 purge 并发时读取旧提交正文的 C2 缺陷。

## Changed files

- `backend/tests/integration/test_stage08_group_context_postgres.py`
  - 增加真实 private authority/window fixture。
  - 增加 known edit、retention expiry、authorized purge、member/binding/mapping/relation/provenance 八类独立 drift 用例。
  - 增加两个 PostgreSQL session 的 purge/read 并发用例，以 `pg_blocking_pids` 证明 reader 锁等待，不使用 sleep 作为断言机制。
  - 增加 safe view、purge result、`repr` 和测试诊断的正文/identifier carrier 负面断言。
- `backend/app/services/stage06_platform.py`
  - 对现有 fresh materialization eligible query 增加 `.with_for_update(read=True)`，使其与 lifecycle purge writer 的 `FOR UPDATE` 协调。
- `project-docs/08-implementation/evidence/stage08-package-c2-group-history.md`
  - 写入实际 RED/GREEN、最终命令、隔离、清理、风险和 C3 handoff 证据。
- `.superpowers/sdd/stage08-package-c-task-c2-report.md`
  - 本报告。

## TDD evidence

### Harness correction（不计作 RED）

首轮整文件测试在失败路径中于 writer lock 释放前退出 executor，造成 worker 等锁和 executor 等 worker 的测试 harness deadlock，工具于 124 秒终止。仅本任务启动的 pytest 进程被定向清理；改为 reader 设置 PostgreSQL `lock_timeout=3000ms`，主线程在任何断言前先 commit/rollback writer，再回收 worker。清理后 `task_pytest_processes=0`。

测试 fixture 最初还暴露两个 setup 问题：autoflush=false 时新 field 未 flush、业务 link 直接赋值未走平台 record update。二者只修正测试准备逻辑，不改变生产合同；修正后 known-edit 基线为 `1 passed, 19 deselected`。

### Valid RED

命令：

`python -m pytest -q tests/integration/test_stage08_group_context_postgres.py -k 'concurrent_purge_blocks'`

结果：exit `1`，`1 failed, 19 deselected in 4.03s`。writer 已锁定 projection、正文置空并标为 `purged` 但尚未提交时，reader `completed_before_transition=True`，证明原普通 MVCC select 会立即读取旧 committed body，而不是等待当前 lifecycle state。

### Minimal GREEN

只在原 SQL UoW eligible materialization select 增加 shared row lock。没有改 protocol、InMemory parity、service contract、schema、migration、API 或权限。

- 并发 focused：`1 passed, 19 deselected in 4.99s`。
- drift focused：`8 passed, 12 deselected in 12.39s`。
- 完整 integration file：`20 passed in 26.89s`。

## Final verification

```text
alembic heads: 20260720_0031 (head)
focused C2/C1 regression: 151 passed in 26.97s
compileall: exit 0
prohibited dependency/raw scan: zero matches (rg exit 1)
git diff --check: exit 0; only existing LF/CRLF warnings
task pytest processes after cleanup: 0
```

最终 regression 覆盖：

- `tests/unit/test_stage08_group_context_contracts.py`
- `tests/unit/test_stage08_group_context_ingestion.py`
- `tests/unit/test_stage08_group_context_service.py`
- `tests/integration/test_stage08_group_context_postgres.py`
- `tests/unit/test_stage08_context_contracts.py`
- `tests/unit/test_stage08_context_service.py`

## Scope and privacy result

- 没有 C1/C3 生产改动，没有 public API/route/response、schema/migration、Telegram network、Provider/LLM、Memory/RAG/vector、Redis、LangGraph、audit/outbox、Mini App 或部署改动。
- 旧 `Message.raw_text`、`raw_caption`、`normalized_text` 没有被读取、回填或删除。
- window 继续只持有 opaque handles；正文只在 fresh locked eligible query 后进入 private materialization，safe view/result 不携带正文或 source identifiers。
- 没有 persistent digest 或跨进程 state。normal Telegram group delete/revoke 仍遵守 `best_effort_group_deletion`，不声明实时观测。

## Concerns / handoff

- 默认数据库 orphan revision 仍是 deployment-preflight 风险；只使用 disposable `STAGE06_LOCAL_DATABASE_URL`，环境在每条命令后恢复。
- Task 6 必须独立重跑本报告命令并审查 scoped diff，才能关闭 C2 并交接 C3。
- C3 独占 C1/C2 merge、全局 budget 与 renderer；Package E 独占 Provider compressor 和 invocation-local digest。本 Task 5 不代表 Package C、Stage08、Provider evaluation 或 deployment 完成。

## Task 6 Important-findings remediation — 2026-07-20

### Status

- Status：`REMEDIATED / FRESH INDEPENDENT RE-REVIEW REQUIRED`。
- Task 6 首轮独立审查仍为 `FAIL / C3 HANDOFF BLOCKED`；本节只记录限定修复，不宣称 Task 6 或 C2 通过。

### TDD RED

命令：

`python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py`

实际结果：exit `1`，`3 failed, 33 passed in 1.68s`。三个预期失败分别证明：

1. `group_context_partial` 接受 `selected_fragments=0`；
2. private fragment 的 `scope_categories` 缺少 `group`；
3. 只有 expired count-only omission、没有安全 fragment 时 window 错误返回 partial。

### Minimal correction and focused GREEN

- `GroupContextWindowView` 现在要求 partial 同时满足 `selected_fragments > 0` 和 `omissions.total > 0`。
- window builder 在没有 selected fragment 时固定返回 `group_context_unavailable`，即使存在 count-only omission；usage 继续保持零 selected/零 raw chars。
- private fragment 的 category shape 固定为 `workspace/group/customer/project`；没有增加 category value、ID、DTO、renderer 或 persistence。
- source-chat-type decision 状态更新为已实现、Task 4 已独立复审，并明确本次修复仍等待 fresh Task 6 re-review。

同一 focused 命令实际 GREEN：`36 passed in 1.34s`。

### Scope

未修改 PostgreSQL schema/migration/UoW lock、C1/C3、API/route、Telegram network、Provider/LLM、Memory/RAG/vector、Redis、LangGraph、audit/outbox、Mini App、deployment 或默认数据库。在新的独立复审前，C3 继续 blocked。

### Final focused verification

- remediation contract/service tests after final privacy assertion tightening：`36 passed in 1.27s`。
- disposable PostgreSQL `alembic upgrade head`：exit `0`；`alembic heads` 唯一 `20260720_0031 (head)`。
- Task 6 C2/C1 focused regression：`151 passed in 29.28s`。
- allowed production files `compileall`：exit `0`。
- historical raw / prohibited dependency scan：零匹配（`rg` exit `1`）。
- allowed six-file scope `git diff --check`：exit `0`。
- 每条数据库命令在子进程内保存并恢复调用前 `DATABASE_URL`；没有触碰默认数据库。

这些结果只证明限定修复和 focused regression 通过；新的独立 Task 6 re-review 仍是解除 C3 blocker 的必要条件。
