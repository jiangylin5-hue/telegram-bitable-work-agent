# Stage08 Package A · Task 3 独立审查包

## 只读范围

阅读下列绝对路径及其任务简报/报告；不得改文件，不得运行 Provider、Telegram、API、迁移、数据库或外部调用，不得 stage/commit：

- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\.superpowers\sdd\stage08-task-3-brief.md`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\.superpowers\sdd\stage08-task-3-report.md`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\app\runtime\stage08_policy.py`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\app\services\stage08_runtime.py`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\tests\unit\test_stage08_runtime_service.py`

可只读查看被这些文件直接调用的既有 Stage06/07 helper，以确认没有绕过 service/permission boundary。

## 审查重点

1. Policy 是否 fail-closed 地交集 employee active/workspace、`user:<id>`、active workspace membership、已有 `is_member_eligible_for_employee` 和逐工具的**精确**高层 action 映射；是否错误接受 caller role 或任意 manifest action。
2. action 必须是本次 invocation 内的 allowlist tool；预算即便 Pydantic 被绕过也要拒绝；deny 时不创建 ticket/idempotency/audit。
3. idempotency fingerprint 是否排除 ticket_id/trace/idempotency key，是否复用已有 helper，replay response 是否严密验证，trace conflict 是否不会遗留 in-progress idempotency record。
4. ticket 初始状态/JSON shape/response_ref/audit 是否不带 invocation input、prompt、response、secret 或自由文本。
5. 状态迁移是否只能 `planned -> executing -> terminal`，终态不可复活，completed_at 正确。确认最终采用 `transition_execution_ticket(uow, ticket, target_state)`，没有反射 session 或不兼容 InMemory/SQLAlchemy 的审计写法。
6. tests 是否确实覆盖 permission deny、assigned grant、top-level action 注入、防御预算、key replay/conflict、状态机和 audit/idempotency 脱敏；未混入 Gateway/API/Provider/Telegram/DB migration。

## 输出

按 `Critical`、`Important`、`Minor`、`Spec compliance verdict`、`Task quality verdict` 返回，注明文件/行号。区分“报告声称已跑”与“你实际复跑”。
