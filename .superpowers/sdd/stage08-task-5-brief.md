# Stage08 Package A Task 5：Runtime API 与多 Invocation 执行

## Scope

实现既有 `POST /api/stage08/runtime/execute-plan` 合同，使其可执行已经过 PolicyGate 审核的完整 `ExecutionPlan`。这是 Package A 的收口任务；不实现 Memory、RAG、群聊持久化、LangGraph、Provider 调用、Telegram 发送或新的外部写入。

## 已确认执行语义

- `ExecutionPlan.invocations` 允许 1–7 条，且不得超过 `budget.max_tool_calls`。
- Runtime API 为整个计划创建一张 ticket；ticket 只从 `planned` 一次进入 `executing`。
- 计划按客户端请求中的 invocation 顺序执行；每个已尝试的调用只写入一条 `RedactedToolResult` 到 `tool_summary`。
- 所有调用成功才进入 `succeeded`；首个 policy/adapter 拒绝进入 `denied`、首个意外执行失败进入 `failed`，写入固定脱敏错误摘要并停止后续调用。
- `action` 是主声明动作，必须出现于 invocation 列表，但不要求等于每个 invocation。
- 客户端请求不得提交/覆盖 actor、ticket ID、ticket state、有效权限、字段白名单、Memory scope、检索过滤或审计内容。路由从 verified identity 派生 `actor="user:{identity.user_id}"`、服务端生成 ticket ID、固定 `planned` 初始状态。
- 先通过 `digital_employee.invoke` 的 workspace authorization，再调用 PolicyGate；工具 adapter 继续做 employee/caller/table/view/field 的服务端授权。
- 单调用 `Stage08ToolGateway.execute()` 的既有行为和 Task4 回归必须保持。新增多调用路径不能绕过 ticket transition lock、草稿确认、审计或服务边界。

## Required files

- Modify `backend/app/runtime/stage08_tool_gateway.py` only as needed to add an atomic sequential plan path; keep the existing single-invocation API compatible.
- Create `backend/app/schemas/stage08_runtime.py` with strict, extra-forbid request/response DTOs and no raw-text fields.
- Create `backend/app/api/routes/stage08_runtime.py` and register it from `backend/app/main.py`.
- Create `backend/tests/unit/test_stage08_runtime_api.py`; extend `backend/tests/unit/test_stage08_tool_gateway.py` only for plan-sequence behavior.
- Create `project-docs/08-implementation/STAGE_08_RUNTIME_API_BDD_AND_ACCEPTANCE.md` and `project-docs/08-implementation/evidence/stage08-runtime-api-task5.md`.
- Append implementation details, RED/GREEN commands, skipped work and risks to `.superpowers/sdd/stage08-task-5-report.md`.

## TDD required cases

1. API rejects unknown JSON fields and raw `prompt`-like nested keys before service dispatch.
2. API derives actor/ticket/state server-side; a client cannot impersonate another actor or submit terminal state.
3. Wrong-workspace caller gets 403 before `begin_execution_plan` or gateway dispatch.
4. Allowed two-invocation plan returns one ticket with `succeeded` and two redacted summaries, in order, with no raw input/output text in the HTTP response or persisted summary.
5. First denied/failed invocation returns the ticket's terminal state and does not invoke subsequent adapters.
6. Replaying the same idempotent request returns the same ticket without duplicate execution; a terminal ticket cannot be executed again.
7. Existing Task4 single-invocation gateway tests remain valid.

## Required verification

Run the new API module and the covering gateway/service tests. Use only synthetic in-memory or existing local test infrastructure; do not perform Provider, Telegram, notification, deployment or external network calls. Run a targeted scan proving no send path was introduced.

## Out of scope

- No asynchronous preemption for `max_wall_time_ms`; Task 5 retains the already implemented contract validation only.
- No change to the persistent ticket schema or migration.
- No new permission action, no direct record write and no confirmation bypass.
- No broad Stage07/Stage08 acceptance sweep.

## Fix Round 1：严格输入与验证错误脱敏

任务级复审与独立重现确认以下两项均须修复，且不得通过放宽合同或删除原有测试回避：

1. `ExecutionBudget` 必须和 Runtime request 一样拒绝隐式类型转换。`max_retrieval_chunks=false`、`0.0` 与任何其他非严格整数值都必须以 422 拒绝，且不得创建或执行 ticket。修复 Pydantic 合同而非只在路由作临时字符串过滤。
2. FastAPI 默认 `RequestValidationError` 会把失败请求的 `input` 回显至 422 body。已用 `RUNTIME_VALIDATION_SECRET` 重现：嵌套 `{ "prompt": "RUNTIME_VALIDATION_SECRET" }` 被禁止但仍出现在响应。Stage08 Runtime API 必须使用 route-scoped 或等效的最小处理机制，返回只有固定错误码、location/type 等非原始字段的 422 envelope，绝不包含 body、`input`、`ctx.error`、prompt/response/token/raw_text 或其他原始值；不得无关地改变其他 API 的验证响应。

新增 RED/Green 测试至少覆盖上述两条，并证明敏感 sentinel 不在 HTTP body、`execution_tickets` 仍为空。重新运行 Task5 API、gateway、runtime-service、runtime-contract 聚焦回归；追加 Fix Round 1 的 RED/GREEN 证据至现有 report。无 Provider、Telegram、通知或网络调用。
