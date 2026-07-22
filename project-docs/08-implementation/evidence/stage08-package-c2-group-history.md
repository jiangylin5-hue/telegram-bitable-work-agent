# Stage08 Package C2 群长窗口 PostgreSQL 收口证据

## Status

- Evidence status：`C2 Tasks 1–6 verified / final independent review PASS`。
- Scope：仅记录 C2 受控群消息窗口的真实本地 PostgreSQL lifecycle、drift、privacy 与 purge/read concurrency 证据。
- Date：2026-07-20。
- Database：已批准的 disposable `STAGE06_LOCAL_DATABASE_URL`；所有命令完成后恢复调用前 `DATABASE_URL`，没有接触、stamp、删除或修复默认数据库。

## 1. 被证明的行为

从一个有效 workspace/member/`chat_user` binding、单一 active group-business mapping、customer/project 关联、verified `group` projection、private authority 和已构建 window 开始，真实 PostgreSQL 用例分别改变下列当前状态：

1. known edit 创建 version 2，并把旧 version 标为 `superseded`；旧 window 无法再物化旧正文，重新构建只得到当前 version 2。
2. source 超过 30 天后，旧 window 和重新构建的 window 都不能得到旧正文；authorized purge 擦除 `content_fragment` 并标记 `purged`。
3. member、Stage06 binding、group-business mapping 任一失效后，fresh materialization fail closed。
4. project→customer 可见 linked-record 关系改变后，旧 authority/window fail closed。
5. `source_chat_type` 从 `group` 漂移为 `unknown` 后，SQL eligibility 在正文选择前拒绝该行。
6. purge writer 持有 projection `FOR UPDATE` 并完成未提交生命周期更新时，fresh reader 必须等待当前行状态；purge 提交后 reader 重新判断并返回 unavailable/空 fragments。
7. safe window view 和 purge result 只含固定 contract/status/count/budget 字段；测试诊断、异常断言和对象 `repr` 不含 `content_fragment`、projection UUID 或 source message UUID。

## 2. TDD RED

最初整文件尝试因测试 harness 在断言失败时先等待 worker、后释放 writer lock，触发 124 秒工具超时；这不是可接受的产品 RED。由本任务产生的 pytest 进程已定向清理，随后把 harness 改为 reader `lock_timeout=3000ms`、主线程无论结果如何先 commit/rollback writer，再等待 worker；最终没有遗留进程或连接。

有效 RED 命令：

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m pytest -q tests/integration/test_stage08_group_context_postgres.py -k 'concurrent_purge_blocks'
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

实际结果：exit `1`，`1 failed, 19 deselected in 4.03s`。失败断言为 `completed_before_transition is False`，实际值为 `True`：writer 尚未提交 purge transition 时，fresh reader 已完成普通 MVCC 读取并取得旧提交版本，证明并发 stale read 缺陷真实存在。

## 3. Minimal GREEN correction

唯一生产修正位于现有 `SqlAlchemyStage06PlatformUnitOfWork.get_eligible_group_message_projection_for_materialization`：在原有 projection ID、mapping、provenance、active、non-empty、retention 与 event cutoff 条件之后增加 PostgreSQL shared row lock（SQLAlchemy `.with_for_update(read=True)`）。

该锁与 purge 的 `FOR UPDATE` 冲突；在 PostgreSQL `READ COMMITTED` 下，reader 等待 purge transition 结束，再针对更新后的当前版本重新判断 eligibility。没有新增接口、DTO、schema、migration、权限、route、网络或持久化载体。

GREEN 结果：

- 并发 focused：`1 passed, 19 deselected in 4.99s`。
- 八类独立 drift：`8 passed, 12 deselected in 12.39s`。
- 完整 PostgreSQL 文件：`20 passed in 26.89s`。

## 4. Final verification

指定最终命令使用 disposable PostgreSQL 执行 `alembic upgrade head`、`alembic heads` 及 C2/C1 focused regressions。

实际结果：

- Alembic：唯一 `20260720_0031 (head)`。
- 测试：`151 passed in 26.97s`。
- `compileall`：exit `0`。
- 禁止依赖/历史 raw scan：exit `1`（代表零匹配）。扫描目标中没有 `raw_text`、`raw_caption`、`normalized_text`、Telegram client/send、HTTP client、OpenRouter、public route、Redis、pgvector、LangGraph、`MemoryItem` 或 `AgentRun`。
- `git diff --check -- backend project-docs/08-implementation docs/superpowers`：exit `0`；输出仅包含 dirty worktree 既有 LF→CRLF warning，没有 whitespace error。
- Task 5 pytest process cleanup：`task_pytest_processes=0`。

## 5. Privacy、持久化和副作用边界

- C2 只持久化已确认的受控 projection；没有 persistent digest、Memory candidate、RAG/vector、Redis、LangGraph checkpoint、AgentRun、audit 正文或日志正文。
- 测试只在 disposable local PostgreSQL 中创建数据；各非并发用例 rollback，并发用例提交 purge 只用于该 disposable fixture，fixture 结束后清理。
- 没有 Telegram/Provider/LLM/HTTP 调用，没有外部消息、Mini App、公开 API、部署或生产写入。
- normal Telegram group delete/revoke 仍不可可靠观测；本证据只兑现 known edit、server-authorized purge 和 30 天 retention 的 `best_effort_group_deletion`。

## 6. Retained risks 与 C3 handoff

- 默认 `DATABASE_URL` 的历史 orphan revision 仍是独立 deployment-preflight 风险；Task 5 没有触碰或修复它。
- shared row lock 的正确性已由双 session PostgreSQL 用例证明；未来调用方仍必须让 materialization 与受控消费保持在明确事务边界内，并在每次下游 LLM/tool invocation 前重新验证。
- C2 只交付 private long window 与 `compression_required`。C3 才能合并 C1/C2、实施全局预算和 renderer；Package E 才能调用 `ContextCompressor` 并生成不持久化的 invocation-local digest。
- Task 6 最终独立复审通过，C2 已关闭并允许 C3 开始。本证据不代表 Package C、Stage08、真实 Provider 评测、生产数据库或部署完成。

## 7. Task 6 最终独立复审

首轮 Task 6 独立审查发现两个 Important：`group_context_partial` 允许零可用片段，以及 D6 private evidence 的 scope categories 缺少 `group`。限定修复后的新一轮独立复审直接读取代码和测试，确认：

- partial 必须同时满足 `selected_fragments > 0` 和 `omissions.total > 0`；只有 expired/count omission 而无安全片段时固定 unavailable。
- private evidence categories 精确为 `workspace/group/customer/project`，repr 和 count-only safe view 仍不含正文或内部 ID。
- source-chat-type decision 状态已与 `0031` migration、Task 4/5 证据一致。
- 修复未触及 PostgreSQL schema/migration/UoW lock、C1/C3、API/route、Telegram network、Provider/LLM、Memory/RAG/vector、Redis、LangGraph、audit/outbox、Mini App 或 deployment。

本轮实际验证：

```text
contract/service focused: 36 passed in 1.19s
alembic upgrade head: exit 0
alembic heads: 20260720_0031 (head)
C2/C1 focused regression: 151 passed in 28.60s
compileall: exit 0
historical raw / prohibited dependency scan: zero matches
public/persistent carrier scan: zero matches
Telegram/Provider/Redis/vector/LangGraph/Memory boundary scan: zero matches
git diff --check: exit 0; only existing LF/CRLF warnings
```

第一次完整回归尝试被命令层 10 秒超时提前终止，不计作测试证据；定向检查确认无残留 pytest 进程后，以 120 秒上限原样重跑并完整成功。最终 verdict：`PASS / 0 Critical / 0 Important / 0 Minor`。
