# Stage08 Package A · Task 3 实施报告

## Status

- Status: READY_FOR_REVIEW
- Scope: Policy Gate、Execution Ticket 幂等创建与状态生命周期
- External Calls: 未执行 Provider、Telegram、HTTP API、数据库迁移或任何外部系统调用。
- Git: 未执行 stage、commit、reset 或 checkout。

## 改动文件

- `backend/app/runtime/stage08_policy.py`：实现 fail-closed Policy Gate、固定拒绝码、actor/member/access-mode/grant、精确 tool-to-action 映射与防御性预算复核。
- `backend/app/services/stage08_runtime.py`：实现创建前策略门、语义指纹、受控幂等重放、trace 冲突保护、最小 response ref、状态机和脱敏审计。
- `backend/tests/unit/test_stage08_runtime_service.py`：覆盖 allow/deny、member/grant、模型构造绕过、幂等、trace 冲突、状态机与输入不持久化。

## TDD 证据

- RED：`python -m pytest -q tests/unit/test_stage08_runtime_service.py -k "policy or idempotency or transition"` 在模块尚不存在时失败，错误为 `ModuleNotFoundError: No module named 'app.runtime.stage08_policy'`。
- GREEN（聚焦）：同一命令在实现后通过，`10 passed, 1 deselected`。
- GREEN（完整指定回归）：`python -m pytest -q tests/unit/test_stage08_runtime_service.py tests/unit/test_stage06_audit_redaction.py tests/unit/test_stage08_runtime_contracts.py`，结果 `51 passed in 2.53s`。
- 格式：`git diff --check -- backend/app/runtime/stage08_policy.py backend/app/services/stage08_runtime.py backend/tests/unit/test_stage08_runtime_service.py` 无输出。

## 覆盖与边界

- deny：未授权 tool、workspace/actor 错误、inactive member、assigned employee 无 grant、注入 action、预算/检索绕过均 fail closed；deny 前不创建 ticket、idempotency 或 audit。
- 幂等：同 workspace/key/语义请求重放同一 ticket；语义变更触发既有 `idempotency_conflict`；trace 冲突在开始幂等记录前拒绝。
- 状态机：只允许 `planned -> executing -> terminal`；终态不可复活；`completed_at` 只在进入 terminal 时写入。
- 脱敏：invocation input 仅用于瞬时请求指纹；审计与 `response_ref` 不写 input、prompt、response 或 key 值。

## 处理过的接口冲突

原任务简报的 `transition_execution_ticket(ticket, target_state)` 与“必须写审计并读取成员角色”要求不兼容。经主控确认，文档优先收紧为 `transition_execution_ticket(uow, ticket, target_state)`，因而能在 InMemory 与 SQLAlchemy UoW 上通过服务边界写审计，未使用 ORM session 反射。

## 风险

- 本任务只实现 backend service；尚未提供 Tool Gateway、路由或外部调用入口，符合 Package A 范围。
- SQLAlchemy/PostgreSQL 的 ticket 持久化由 Task 2 覆盖；本任务的回归使用 InMemory UoW，以验证策略和生命周期服务逻辑。

## 审查回修：workspace 行锁、replay 绑定与受跟踪状态迁移

### 改动文件

- `backend/app/services/stage06_platform.py`：在 protocol、InMemory 和 SQLAlchemy UoW 增加 `lock_workspace_for_stage08_execution`；SQLAlchemy 使用带 `Workspace.id == workspace_id` 条件的 `SELECT ... FOR UPDATE`。
- `backend/app/services/stage08_runtime.py`：策略通过后先取得 workspace 行锁，再在该锁范围内执行 trace/idempotency 预检与创建；重放 ticket 同时校验 workspace 和语义指纹；状态迁移仅修改从 UoW 重新取得的受跟踪 ticket。
- `backend/tests/unit/test_stage08_runtime_service.py`：新增 workspace lock、污染 replay response（workspace 与 fingerprint 两种污染）与脱离 UoW ticket 的回归。
- `backend/tests/integration/test_stage08_runtime_postgres.py`：新增两个 SQLAlchemy session/线程的真实本地 PostgreSQL 竞争回归，使用 PostgreSQL backend PID 与锁等待观测，并设置 future 15 秒安全超时。

### TDD 与验证证据

- RED：新增回归先运行 `python -m pytest -q tests/unit/test_stage08_runtime_service.py -k "workspace_lock or replay_ticket_outside or detached_ticket"`，结果 `3 failed`；分别证明 UoW 缺锁方法、污染 replay 未被拒绝、脱离 UoW ticket 可被迁移。
- GREEN（新增 unit）：初次实现后 `3 passed, 11 deselected`；补齐 fingerprint 污染分支后为 `4 passed, 11 deselected`。
- GREEN（指定 unit 回归）：`python -m pytest -q tests/unit/test_stage08_runtime_service.py tests/unit/test_stage06_audit_redaction.py tests/unit/test_stage08_runtime_contracts.py`，最终结果 `55 passed in 2.07s`。
- GREEN（真实本地 PostgreSQL）：`python -m pytest -q tests/integration/test_stage08_runtime_postgres.py`，最终结果 `4 passed in 5.32s`。测试使用已配置且受本地 URL guard 约束的 disposable PostgreSQL schema；未连接远程数据库。
- 格式：扩展后的 `git diff --check` 无空白错误，仅有 Git 的 LF/CRLF 工作副本提示。

### 串行化范围与安全结果

- 行锁只针对 `Workspace` 的指定 ID；因此只串行化同一 workspace 的 ticket 创建，不扩大 caller/employee/table/view/field 权限，也不对不同 workspace 建立全局锁。
- 两条不同语义、同 workspace、同 trace 的并发请求中，首条成功创建并完成 idempotency；后进入锁区的请求得到 `stage08_trace_conflict`。数据库最终只有一条 ticket 和一条 `completed` idempotency record，没有 `in_progress` 残留。
- replay 现在必须同时绑定当前 workspace 与当前 request fingerprint；脱离 UoW 的 ticket 以 `stage08_ticket_not_found` fail closed，不会产生审计或状态改写。

### 外部边界

- 未执行 Provider、Telegram、HTTP API、数据库迁移或其他外部系统写入；仅运行本地测试进程和 disposable local PostgreSQL 回归。
- 未执行 stage、commit、reset 或 checkout。

## 最终复审回修：PostgreSQL 直接锁等待证据

### 测试设计

- 重写 `test_workspace_lock_serializes_conflicting_ticket_creates_without_in_progress_idempotency`，不使用同起跑同步原语。
- Session A 显式调用 `lock_workspace_for_stage08_execution(workspace_id)` 后读取 `pg_backend_pid()` 并保持事务。B 在独立 session 建立连接后读取自身 `pg_backend_pid()`，通过 Event 仅把 PID 交给主线程，随后立即调用真实 `begin_execution_plan`。
- 主线程使用独立 observer connection 有界轮询 SQLAlchemy `select(func.pg_blocking_pids(b_pid))`；只有返回值包含 `a_pid`，才确认 B 正被 A 的 PostgreSQL workspace 行锁阻塞。5 秒观察期限只使用 50ms 轮询 sleep，不承担业务同步。
- 确认 PG 锁等待后才断言 B future 未完成。随后 A 在持锁事务内创建并提交首条 ticket；B 解锁后读取已创建 trace 并严格返回 `stage08_trace_conflict`。future 使用 15 秒安全超时；所有 A/B/observer 资源均由上下文管理器与 try/finally 清理。
- 最后真实查询数据库，断言 `1` 条 ticket、`1` 条 `completed` idempotency、`0` 条 `in_progress` idempotency。

### 控制性 RED 与 GREEN

- RED：仅在测试中临时用 test-local UoW 绕过 B 的 workspace 行锁。B 不会出现在 `pg_blocking_pids(b_pid)` 的 A 阻塞者列表中，5 秒有界观察以 `Session B did not enter a PostgreSQL lock wait for Session A` 如预期失败；未改动生产代码。
- GREEN：移除临时 test-local 绕过，恢复真实 `SqlAlchemyStage06PlatformUnitOfWork` 后，`python -m pytest -q tests/integration/test_stage08_runtime_postgres.py -k "workspace_lock" --durations=5` 结果为 `1 passed, 3 deselected in 4.29s`，其中调用阶段为 `0.31s`。
- 耗时复测：全量受 guard integration 随后结果为 `4 passed in 8.23s`。锁等待观测本身由 5 秒 deadline 限制，B future 由 15 秒 deadline 限制；不存在 Provider、网络或 Executor 外部依赖。
- 本回修只改 integration 测试和本报告；生产代码、Provider、Telegram、HTTP API、迁移与 Git 状态均未被额外写入。
