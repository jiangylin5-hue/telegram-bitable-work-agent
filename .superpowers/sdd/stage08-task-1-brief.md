# Stage08 Package A / Task 1：Runtime 合同与红灯测试

## 目标

创建 `backend/app/runtime/stage08_contracts.py` 与 `backend/tests/unit/test_stage08_runtime_contracts.py`，为后续 Tool Gateway 提供严格、脱敏的 Pydantic 合同。

## 必须产出

- `JSONScalar = str | int | float | bool | None`。
- `ExecutionBudget`：`max_tool_calls` 1..7，`max_wall_time_ms` 100..30000，`max_graph_depth` 1..3，`max_retries` 0..2，`max_retrieval_chunks` 仅允许 0。
- `ToolInvocation`：`tool_name` 仅允许：`record.query`、`table.summarize`、`contact.resolve`、`import.preview`、`tool_catalog.inspect`、`task.create_draft`、`record_change_draft.create`。
- `ToolInvocation.input` 只接受 JSON 标量或嵌套 JSON 结构；递归拒绝 key：`prompt`、`response`、`api_key`、`token`、`raw_text`。
- `ExecutionTicketState`、`ExecutionPlan`、`RedactedToolResult` 均为后续 task 可导入的类型。`RedactedToolResult` 只能包含 tool 名、状态、实体引用、可见 field key、计数、固定错误码；禁止自由文本内容。

## TDD

先在测试中证明：无效预算被拒绝、未知 tool 被拒绝、包含 `prompt` 的嵌套 input 被拒绝、允许 tool/input 可通过、结果 DTO 没有自由 `answer`/`content` 字段。运行测试，确认在实现前因模块缺失失败；再写最小实现，运行同一测试为绿。

## 约束

- 不修改既有 Stage06/Stage07 文件，不创建数据库模型、迁移、API 或 Provider 调用。
- 不保存/打印密钥、prompt、模型回复或任何业务正文。
- 使用项目既有 Pydantic 风格；仅改本任务两个文件与任务报告。
- 当前 worktree 已有用户未提交改动：不得 stage、commit、reset、checkout、删除或格式化无关文件。

## 验证

从 `backend` 运行：

`python -m pytest -q tests/unit/test_stage08_runtime_contracts.py`

并运行：

`git diff --check -- backend/app/runtime/stage08_contracts.py backend/tests/unit/test_stage08_runtime_contracts.py`

报告必须记录 RED/GREEN 命令与结果、修改文件、自查和 concern。
