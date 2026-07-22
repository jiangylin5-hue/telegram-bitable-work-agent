# Stage08 Package E / E3-R1：私有安全模式、受控 DraftIntent 与安全审计端口

## 需求真源

完整阅读并以其为准：

1. `docs/superpowers/plans/2026-07-22-stage08-e3-safe-execution-remediation.md` 的 **Task R1**；
2. `project-docs/08-implementation/decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`；
3. `project-docs/08-implementation/decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`。

## 任务范围

- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/runtime/stage08_contracts.py`
- `backend/app/services/stage08_runtime.py`
- `backend/app/runtime/stage08_tool_gateway.py`
- `backend/app/services/stage06_digital_employees.py`
- 对应 unit tests：`test_stage08_collaboration_contracts.py`、`test_stage08_tool_gateway.py`、`test_stage08_collaboration_service.py`
- 报告：`.superpowers/sdd/stage08-package-e-task-e3-r1-report.md`

不得改动 UoW transaction/lock、E3 graph、公开 API、数据库 schema/migration、Telegram、Provider 或部署；R2 才处理原子边界。不得 stage/commit/reset/checkout/clean/push。

## 精确交付

1. `DraftIntent` 保持不可序列化、无公开 repr/JSON、只可工厂构造；改为承载**恰好一条**非空 `field_key` 与 JSON-safe `value`。不接受敏感 key（`prompt`、`response`、`api_key`、`token`、`raw_text`）或不可 JSON 值。
2. 新增不可从 `ExecutionPlan`、`ToolInvocation`、请求 JSON 或 Pydantic 输入构造的内部 `Stage08SafeExecutionContext`。唯一合法模式为 `stage08_e3_safe`，包含 hash-only trace；必须拒绝伪造、pickle、对象构造和额外 JSON 字段。
3. 在 `begin_execution_plan`、`Stage08ToolGateway.execute/execute_plan` 与 Stage06 `invoke_digital_employee` / draft 路径增加 keyword-only private context。默认值为 `None`，现有调用与现有非 E3 审计行为不变。
4. safe context 下 ticket-created/transition、gateway result、Stage06 draft audit 和 Stage06 AgentRun 使用单一白名单摘要：仅 graph/status/action/count/code/hash/latency/ticket-or-draft presence。禁止 query、answer、private material、field/value、record/draft/ticket UUID、entity refs、provider response。`RecordChangeDraft.trace_id` 可以接收 hash-only trace，但草稿主键/外键仍正常保存。
5. 不要通过“执行后清理 audit”实现；必须在各写入点直接写安全摘要。不能删除或修改默认 Stage06 审计的字段形状。
6. 先写 RED，再实现。最少包含：intent 的 field/value 合法/非法与 serialization；forged safe context；默认模式回归；E3 safe trace 扫描所有本次 AgentRun/audit/tool-summary，确认没有禁止值。

## 验证

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_service.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/runtime/stage08_contracts.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/services/stage06_digital_employees.py
```

报告必须写明 RED/GREEN 精确通过数、默认回归、trace-wide 脱敏检查、是否调用网络/Telegram/Provider（应为没有），及尚留给 R2 的风险。最终仅回复 `DONE`、测试概述和报告路径。
