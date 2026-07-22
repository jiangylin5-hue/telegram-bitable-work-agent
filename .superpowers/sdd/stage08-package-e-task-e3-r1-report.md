# Stage08 Package E / E3-R1 实施报告

## Status

- Status: DONE
- Scope: 私有 `stage08_e3_safe` context、单字段 `DraftIntent`、ticket/Gateway/Stage06 draft 与 AgentRun/audit 的白名单摘要端口。
- Out of scope: UoW transaction/savepoint、锁、幂等 replay、E3 graph 接线、公开 API、schema/migration、Telegram、Provider、部署。

## Changed files

- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/services/stage08_runtime.py`
- `backend/app/runtime/stage08_tool_gateway.py`
- `backend/app/services/stage06_digital_employees.py`
- `backend/tests/unit/test_stage08_collaboration_contracts.py`
- `backend/tests/unit/test_stage08_tool_gateway.py`
- `backend/tests/unit/test_stage08_collaboration_service.py`
- `.superpowers/sdd/stage08-package-e-task-e3-r1-report.md`

`backend/app/runtime/stage08_contracts.py` 已核对；其 `ExecutionPlan`、`ToolInvocation` 均已采用 `extra="forbid"`，无需生产代码改动。新增合同测试证明请求/Pydantic payload 不能注入 safe mode/context。

## What changed

1. `DraftIntent` 继续使用 factory-issued opaque carrier：无公开 payload/repr/JSON、不可直接构造、不可 pickle。其 sealed snapshot 现在只承载一条 `field_key + value`；字段必须非空且不能是 `prompt`、`response`、`api_key`、`token`、`raw_text`，值必须为有限、递归 JSON-safe 数据，嵌套敏感 key 同样拒绝。
2. 新增 factory-issued `Stage08SafeExecutionContext`。唯一 mode 为 `stage08_e3_safe`；trace 只接受固定 E3 前缀的 hex hash 或纯 hex hash。直接构造、`object.__new__` 伪造、pickle、JSON、非法 mode、UUID/private trace 均拒绝。
3. 新增单一 `_stage08_safe_execution_summary` 白名单构造器，输出键精确为 `graph/status/action/counts/code/trace_hash/latency_ms/ticket_present/draft_present`；count key/value、token、latency 和 presence 均做严格校验。
4. `begin_execution_plan`、ticket transition、`Stage08ToolGateway.execute/execute_plan`、Stage06 `invoke_digital_employee`、update/create draft 路径新增 keyword-only `safe_context=None`。context trace 必须与 ticket/plan trace 一致。
5. safe mode 下，各 ticket-created/transition、Gateway tool summary、Stage06 draft-created/invoked audit 与 Stage06 AgentRun 在写入点直接使用统一摘要；audit `entity_id=None`、固定 system actor，AgentRun/tool summary 不写实体引用、字段 key/value 或业务 UUID。`RecordChangeDraft.trace_id` 使用 context 的 hash-only trace，草稿主键/外键与 `proposed_values` 仍正常保存。
6. Gateway safe result 清空 `entity_refs` 与 `visible_field_keys`，只保留 action/status/count/code。默认分支继续写原 `RedactedToolResult` 和原 Stage06 audit/AgentRun 形状；默认 registry adapter 仍按原四参数调用。

## TDD evidence

### Baseline before RED

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_service.py
```

Output:

```text
73 passed in 1.80s
```

### RED

先只修改测试并运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_collaboration_service.py -k "draft_intent or safe_execution"
```

Output:

```text
17 failed, 1 passed, 56 deselected in 2.05s
```

失败原因符合预期：旧 `draft_intent(summary=...)` 不接受 `field_key/value`；factory 没有 safe context；runtime/Gateway 没有 private context 参数；safe trace 无白名单写入端口。

### Focused GREEN

同一命令在最小实现后：

```text
18 passed, 56 deselected in 1.53s
```

### Full required GREEN

最终 fresh 输出记录在下方 `Verification`。

## Default-mode compatibility

- 修复前指定四文件基线：73 passed。
- 修复后同一四文件测试全部通过，包含既有 default ticket audit、transition、Gateway result/tool summary、Stage06 AgentRun/audit、query/summarize/create/update draft 行为。
- 所有新增参数均为 keyword-only 且默认 `None`。
- default Gateway registry handler 仍按原四参数调用；只有显式 safe context 才传入私有 keyword。
- default audit payload、entity id、permission snapshot、Stage06 trace 与 `RedactedToolResult` 字段形状未删除或改写。

## Trace-wide redaction evidence

`test_e3_safe_execution_redacts_the_complete_ticket_gateway_and_draft_trace` 不再使用创建前切片，而是按 `trace_id == trace_hash` 扫描 UoW 中该 trace 的全部：

- ticket-created 与两次 transition audit；
- Stage06 draft-created 与 invoked audit；
- Stage06 AgentRun 的 `input_summary`、`output_summary`、`tool_calls`、`trace_id`、`created_entity_refs`；
- ticket `tool_summary`。

扫描禁止 corpus 包含 field key、field value、actor id、workspace/base/table/record/employee/ticket/draft UUID。断言所有禁止值均不出现，所有本次 audit `entity_id is None`；同时断言草稿业务行仍保存一条 field/value，且 `draft.trace_id == trace_hash`。

## Rejected corpus

- Intent field: empty、whitespace、`prompt`、case-variant `Response`、`token`。
- Intent value: arbitrary object、tuple、nested `api_key`、nested `raw_text`、NaN、Infinity。
- Safe context: direct construction、forged `object.__new__`、pickle、JSON、invalid mode、UUID trace。
- Request/Pydantic: `ExecutionPlan.safe_execution_mode` extra field、`ToolInvocation.safe_context` extra field。

## External calls

- Network: none.
- Telegram: none.
- Provider/OpenRouter: none.
- Deployment: none.
- Database integration: none; R1 使用 InMemory UoW 单元测试，不宣称 PostgreSQL 事务证据。

## Verification

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_service.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/runtime/stage08_contracts.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/services/stage06_digital_employees.py
```

Final output:

```text
90 passed in 2.22s
compileall: exit code 0, no output
```

## Independent-review remediation: I-1 safe/default ticket provenance

独立复审发现 safe `begin_execution_plan` 可静默返回同 trace 或同 idempotency 的既有 default ticket；该 ticket 的历史 default audit 已含 ticket UUID，违反完整 trace 脱敏。

### Remediation RED

先新增真实 InMemory UoW 回归：用合法 hash trace 在 default mode 创建 ticket 并确认 default UUID audit 存在，再以同 plan 和 factory-issued safe context 调用。

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py -k "safe_execution_rejects_default_ticket_with_the_same_hash_trace"
```

Output:

```text
1 failed, 18 deselected in 1.98s
Failed: DID NOT RAISE PlatformValidationError
```

### Minimal GREEN

`begin_execution_plan` 的两个 replay return（same-trace 与 idempotency）现在共用 `_return_replayed_ticket`。R2 provenance 尚不存在时，显式 safe context 遇到任何既有 ticket 一律 fail closed，稳定错误码为 `stage08_safe_execution_ticket_provenance_unavailable`；default replay 仍原样返回。

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py -k "safe_execution"
```

Output:

```text
2 passed, 17 deselected in 1.53s
```

最终 fresh 四文件测试与 compileall 输出见上方 `Verification`：`90 passed in 2.22s`，compileall exit 0。remediation 未调用 network、Telegram、Provider 或 deployment。

## Skipped tests

- 未运行真实 PostgreSQL、E3 graph、API、Telegram、Provider 或部署测试；均不在 R1 指定验证范围。
- 未修改或验证 UoW rollback/savepoint/lock/replay；由 R2 负责。

## Remaining risks for R2/R3

1. R1 只建立安全端口，不提供原子边界。Gateway exception、cancel、timeout、deny 时 ticket/idempotency/draft/audit 的 rollback 与 orphan cleanup 尚未证明。
2. current-state workspace/member/employee/record/group mapping/source locks、统一锁顺序和撤权 drift fail-closed 尚未实现。
3. same-key revalidation/replay 与 different-key 行为尚未实现。
4. 当前 E3 collaboration service/graph 尚未接入 safe context 和单字段 intent materialization；R2/R3 必须在边界内接线，不能把 R1 端口存在误报为完整 E3 安全执行。
5. 本报告不声称 real PostgreSQL 原子性、Package E 完成或生产 readiness。

## Temporary cleanup and Git

- 未创建临时脚本、测试数据、数据库数据或外部资源，无需清理。
- 未执行 stage、commit、reset、checkout、clean、push。
