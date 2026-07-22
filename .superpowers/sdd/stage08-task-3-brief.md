# Stage08 Package A · Task 3：Policy Gate、幂等与 Execution Ticket 生命周期

## 目标

实现执行计划的纯后端策略门、ticket 创建幂等及不可逆状态迁移。必须复用既有 Stage06 workspace membership、digital employee access mode/grant、idempotency 与 audit 基础设施；不得创建 Tool Gateway、route、LLM/Provider、Telegram、Memory/RAG 或直接记录写入。

## 已确认边界

- Execution ticket 的唯一状态：`planned`、`executing`、`succeeded`、`failed`、`denied`、`cancelled`、`timed_out`、`expired`。
- 合法迁移严格为 `planned -> executing`，以及 `executing -> succeeded|failed|denied|cancelled|timed_out|expired`。任何终态不可复活；`planned` 不能直接到终态。
- `pending_confirmation`/`confirmed` 仅属于既有 `RecordChangeDraft`，绝不可用于 ticket。
- 首批 tool 仍仅限 Task 1 的七项 Literal；没有发送、通知确认、外部 provider write 或直接 record write。
- ticket 仅在 Policy Gate allow 后创建为 `planned`；deny 不得创建 ticket 或 idempotency record。
- idempotency 使用既有 `fingerprint_request`、`begin_idempotent_operation` 与 `complete_idempotent_operation`。同 workspace + 同 key + 同语义请求须重放同一 ticket；同 key + 异语义请求必须以既有 `idempotency_conflict` fail closed。
- `request_fingerprint` 可从原始 typed input 短暂计算 hash，但不得把 input/prompt/response/secret 持久化或写入 audit。

## 允许变更文件

- 新建 `backend/app/runtime/stage08_policy.py`
- 新建 `backend/app/services/stage08_runtime.py`
- 修改 `backend/app/services/stage06_platform.py`
- 新建 `backend/tests/unit/test_stage08_runtime_service.py`
- 修改 `backend/tests/integration/test_stage08_runtime_postgres.py`
- 新建/追加 `.superpowers/sdd/stage08-task-3-report.md`

不得修改其他文件，不得 stage、commit、reset 或 checkout。

### 已确认的并发一致性补充

在 Task 3 首轮独立审查中发现，单纯的 trace 预查询不能覆盖两个 SQLAlchemy transaction 同时创建同一 workspace ticket 的竞态，并可能遗留 `in_progress` idempotency record。用户已确认采用最小方案：扩展 `Stage06PlatformUnitOfWork`、`InMemoryStage06PlatformUnitOfWork` 与 `SqlAlchemyStage06PlatformUnitOfWork` 一个窄方法：

```python
def lock_workspace_for_stage08_execution(
    self,
    workspace_id: UUID,
) -> Workspace | None: ...
```

- SQLAlchemy 实现必须是受条件限制的 `SELECT Workspace ... FOR UPDATE`；不使用 raw SQL、advisory lock、反射 session 或全局锁。
- InMemory 实现只返回对应 workspace，供语义和单元测试使用。
- `begin_execution_plan` 必须在 policy allow 后、trace/idempotency 检查前取得锁，并在锁内完成这些检查和 ticket/idempotency 创建。
- 这只串行化同一 workspace 的 ticket 创建，不改变 caller/employee/table/view/field 权限交集；不同 workspace 不应被此锁串行化。

## 1. Policy Gate 合同

在 `stage08_policy.py` 定义最小可测试 API：

```python
@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str | None
    effective_tool_names: tuple[ToolName, ...]

def evaluate_execution_plan(
    uow: Stage06PlatformUnitOfWork,
    plan: ExecutionPlan,
) -> PolicyDecision: ...
```

仅返回固定 reason code，不能拼入输入内容或异常详情。拒绝时 `effective_tool_names == ()`。

按下列顺序、fail closed 计算交集：

1. employee 必须存在、`status == "active"`，且 `employee.workspace_id == UUID(plan.workspace_id)`；UUID 不合法一律 deny。
2. `plan.actor` 只接受 `user:<non-empty-user-id>` 格式。该 user 必须是目标 workspace 的 `active` `WorkspaceMember`。从该成员取得 role；不得相信调用方自己声称的 role。
3. 必须复用 `is_member_eligible_for_employee(uow, employee, actor_user_id)`，从而强制既有 `access_mode == workspace|assigned` 与 member grant；不合格 deny。
4. `plan.state` 必须是 `ExecutionTicketState.planned`；`plan.action` 必须是本次 invocation 中出现的 Stage08 allowlist tool name，不能注入 `telegram.send`、`record.update` 等顶层 action。
5. 每个 invocation 的 tool 必须映射到 employee 配置过的现有高层 action：

   | Tool | 已有 `DigitalEmployee.allowed_actions` 要求 |
   | --- | --- |
   | `record.query` | `query` |
   | `table.summarize` | `summarize` |
   | `contact.resolve` | `contact.resolve` |
   | `import.preview` | `import.preview` |
   | `tool_catalog.inspect` | `tool_catalog.inspect` |
   | `task.create_draft` | `draft_create` |
   | `record_change_draft.create` | `draft_update` |

   这是到已有授权模型的单向映射；不得将任意配置 action 自动转换为工具名，也不得因 manifest 命中而越权。
6. 防御性复核预算：调用数不超过 `max_tool_calls`、`max_graph_depth` 在 1..3、`max_retries` 在 0..2、`max_wall_time_ms` 在 100..30000、`max_retrieval_chunks == 0`。即使外层 Pydantic 被 `model_construct` 绕过也要 deny。

建议 reason code 使用固定值：`employee_not_found`、`employee_inactive`、`workspace_mismatch`、`actor_invalid`、`actor_not_workspace_member`、`employee_caller_scope_denied`、`plan_state_invalid`、`plan_action_invalid`、`tool_not_allowed_by_employee`、`execution_budget_invalid`。如实现需要额外固定码，测试要写明且不能暴露输入。

## 2. Runtime service 与生命周期

在 `backend/app/services/stage08_runtime.py` 提供：

```python
def begin_execution_plan(
    uow: Stage06PlatformUnitOfWork,
    plan: ExecutionPlan,
) -> Stage08ExecutionTicket: ...

def transition_execution_ticket(
    uow: Stage06PlatformUnitOfWork,
    ticket: Stage08ExecutionTicket,
    target_state: ExecutionTicketState,
) -> Stage08ExecutionTicket: ...
```

### `begin_execution_plan`

- 先执行 Policy Gate。deny 时抛出 `PlatformValidationError`，code 固定为 `stage08_policy_denied`，message 只包含 reason code；不得创建 ticket/idempotency record/audit。
- 对允许计划计算稳定语义 fingerprint。payload 至少包括 workspace、employee、actor、action、budget 与 invocation tool/input；**排除** `ticket_id`、`trace_id`、`idempotency_key`，这样同 key 的重放不因请求关联 ID 改变而产生伪冲突。
- 取得 `lock_workspace_for_stage08_execution(workspace_id)` 后才使用 operation 常量 `stage08.execution_plan` 及 `plan.trace_id` 调用既有 idempotency helper。锁不到 workspace 一律 fail closed，且不得创建 ticket/idempotency/audit。
- helper 返回 replay 时，只读取其受控 `response_ref["ticket_id"]` 并通过 UoW 取回 ticket；缺失、不是字符串 UUID、ticket 不存在、ticket 的 `workspace_id` 不等于当前 workspace，或 ticket 的 `request_fingerprint` 不等于当前 fingerprint，一律 `PlatformValidationError("stage08_idempotency_replay_invalid", ...)`，不得新建 ticket。
- 在 workspace 锁内，started 前先检查 `(workspace_id, trace_id)` 是否已有 ticket：同指纹可返回既有 ticket；不同指纹必须 `PlatformValidationError("stage08_trace_conflict", ...)`。因为同 workspace 创建均走同一锁，trace 冲突不会在 `begin_idempotent_operation` 之后才暴露，也不会遗留未完成 idempotency record。
- 创建状态 `planned` 的 ticket，`budget` 只保存结构化 `plan.budget.model_dump()`，`tool_summary` 初始为空 list，`actor_id=plan.actor`，并调用 UoW `add_execution_ticket`。
- 立即以最小受控 response ref（`ticket_id`、`status`）完成 idempotency record。不得把 invocation input、prompt 或工具输出写入 record。
- 对真正新建的 ticket 写一条审计事件 `stage08.execution_ticket_created`，只含 ticket ID、状态、action、tool names、预算数值和 workspace membership role；不得包含 `ToolInvocation.input`、fingerprint 原文、prompt/response 或其他自由文本。可使用 `record_audit_event(getattr(uow, "session", uow), ...)` 与 `sanitize_stage06_audit_state`，保持 InMemory/SQLAlchemy 两种 UoW 兼容。

### `transition_execution_ticket`

- 必须先用 `uow.get_execution_ticket(ticket.id)` 取得受跟踪实体；不存在则以 `PlatformValidationError("stage08_ticket_not_found", ...)` fail closed。只修改该受跟踪实体并写入审计；不调用任何 Tool、Provider、Telegram 或外部服务。
- 按已确认 state machine 实施 fail-closed 迁移；不合法转移抛 `PlatformValidationError("stage08_ticket_transition_invalid", ...)`。
- 从 `executing` 进入任一终态时写 `completed_at = datetime.now(UTC)`；非终态保持 `None`。不要使已完成时间倒退或在终态后覆盖。
- 写一条最小脱敏 audit `stage08.execution_ticket_transitioned`：仅 old/new state、ticket ID、action、tool summary 的计数和 trace；不得写工具 input/output。对于本 Task 因无 gateway actor 参数，可从 `ticket.actor_id` 解析 user，并在当前 workspace 读取 active member role；缺失时 fail closed 为 audit role `unknown`，不得影响已通过的状态迁移。

## 3. TDD 测试

先创建 `backend/tests/unit/test_stage08_runtime_service.py`，运行：

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_service.py -k "policy or idempotency or transition"
```

预期在模块尚不存在时 RED。实现后至少覆盖：

1. active workspace member + active eligible employee + `record.query -> query` 获 allow，`effective_tool_names` 正确；
2. employee 未配置 `import.preview` 时 deny 为 `tool_not_allowed_by_employee`，且 `begin_execution_plan` 不创建 ticket/idempotency；
3. 错 workspace、未激活/伪造 actor、assigned employee 无 member grant 均 deny；
4. `plan.action` 注入非 allowlist 或未出现的动作时 deny；`model_construct` 绕过的超预算/非零 retrieval 仍 deny；
5. 同 workspace/key/语义请求（可换 `ticket_id` 与 trace）返回同一 ticket；同 key 不同 invocation/action 触发既有 `idempotency_conflict`；
6. 状态只可 `planned -> executing -> terminal`，终态不可复活，`completed_at` 仅在终态设置；
7. audit 与 `Stage06IdempotencyRecord.response_ref` 的序列化文本不含 invocation input 的哨兵字符串、`prompt`、`response` 或密钥键。
8. replay response 指向不同 workspace 或不同 fingerprint ticket 时必须 `stage08_idempotency_replay_invalid`；脱离 UoW 的 ticket 不能被状态迁移。
9. local PostgreSQL 两 session/线程竞态：首 transaction 持有 workspace 行锁时第二个同 workspace 请求不能越过；第一条提交后，第二条对同 trace 的不同请求得到 `stage08_trace_conflict`，且数据库中只有第一条 ticket 和第一条已完成 idempotency record。测试必须有超时保护，避免永久等待。

运行完整回归：

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_service.py tests/unit/test_stage06_audit_redaction.py tests/unit/test_stage08_runtime_contracts.py
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
git diff --check -- backend/app/runtime/stage08_policy.py backend/app/services/stage08_runtime.py backend/app/services/stage06_platform.py backend/tests/unit/test_stage08_runtime_service.py backend/tests/integration/test_stage08_runtime_postgres.py
```

若实际代码中的模块不存在导致初始 RED，即为预期。不得为了制造 RED 而修改既有产品代码。没有本任务数据库迁移；不得运行真实 Provider、Telegram 或 API。

## 完成报告

报告须列出改动文件、RED/GREEN、deny/幂等/状态机/audit 脱敏覆盖、无外部调用确认、未 stage/commit 和风险。未运行的命令要如实说明。
