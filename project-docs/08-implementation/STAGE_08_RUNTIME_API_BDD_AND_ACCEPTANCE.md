# Stage08 Runtime API BDD and Acceptance

## Status

- Scope: Package A Task 5 的受控 `POST /api/stage08/runtime/execute-plan` 与多 invocation 顺序执行。
- Boundary: 仅执行既有 allowlist adapter；不引入 Memory、RAG、LangGraph、Provider、Telegram、通知或其他外部写入。

## Behaviour

### Request and identity

- Given 一个经过验证的请求身份，When 请求包含 workspace、employee、action、trace、idempotency、budget 和 invocation，Then 服务端派生 actor、ticket ID 与 `planned` 初始状态。
- Given 客户端提交未知字段、actor、ticket ID、ticket state 或任意嵌套 `prompt`-like key，When DTO 校验，Then 在 service dispatch 前以 `422` 拒绝。
- Given 调用者不是目标 workspace 的有效 `digital_employee.invoke` 成员，When 请求执行，Then 在创建 ticket 或 gateway dispatch 前以 `403` 拒绝。

### Execution ticket

- Given PolicyGate 允许的 1–7 条 invocation 计划，When Runtime API 执行，Then 仅创建一张 ticket，并只进行一次 `planned -> executing` 转换。
- Given 所有 adapter 成功，When 调用按请求顺序完成，Then ticket 进入 `succeeded`，并按相同顺序持久化一条 `RedactedToolResult` / 已尝试调用。
- Given 首个 adapter 拒绝，When 后续调用仍在计划内，Then ticket 进入 `denied`、写入固定脱敏错误摘要且不调用后续 adapter。
- Given 首个 adapter 出现未预期错误，When 后续调用仍在计划内，Then ticket 进入 `failed`、写入 `tool_execution_failed` 且不调用后续 adapter。
- Given 相同语义的重放请求，When ticket 已终态，Then 返回同一 ticket 与安全摘要，状态为 HTTP `200`，不重复执行。

## Acceptance criteria

- 请求与响应 DTO 均 `extra=forbid`，响应没有 raw input/output、权限投影、字段白名单、Memory/retrieval 或 audit 内容。
- 授权先使用既有 `digital_employee.invoke` workspace authorization；再由既有 PolicyGate 与 adapter 权限继续收敛。
- `Stage08ToolGateway.execute()` 的单 invocation 行为不变；多 invocation 使用独立 `execute_plan()` 路径，且同一 ticket 只持有一次 transition lock。
- 新增 API 与 gateway 聚焦用例，以及覆盖的 Runtime service/contract 回归全部通过。

## Verification

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py backend/tests/unit/test_stage08_runtime_service.py backend/tests/unit/test_stage08_runtime_contracts.py -q
```

Expected result: `77 passed`.
