# Stage08 Package A Task 4：固定 allowlist Tool Gateway

## Status

- Task status：ready for implementation
- User-confirmed decision：2026-07-18
- Scope：只实现 Package A 的受控 Tool Gateway 与其必要的 Stage06 草稿服务补齐。

## 目标与范围

新增 `Stage08ToolGateway.execute(uow, ticket, invocation) -> RedactedToolResult`。它接收已经由 Task 3 创建、并处于 `planned` 的 ticket；在执行前迁移到 `executing`，完成后只迁移到 `succeeded`、`denied`、`failed`、`cancelled` 或 `timed_out` 的合法终态。它只允许以下固定 tool 名：

1. `record.query`
2. `table.summarize`
3. `contact.resolve`
4. `import.preview`
5. `tool_catalog.inspect`
6. `task.create_draft`
7. `record_change_draft.create`

未知 tool、无效输入、非 `planned` ticket、无对应 policy 权限、重复/终态执行均必须 fail closed。不得用反射、动态 import、raw SQL 或直接操作 ORM model。

## 已确认的任务草稿合同

`task.create_draft` 输入固定为：

```json
{"table_id": "UUID", "proposed_values": {"field_key": "value"}}
```

它不是独立 Task schema，也不是即时 `create_record`。只允许在该数字员工可访问且当前 caller 可写的表上，创建：

```text
RecordChangeDraft(
  draft_type="create_record",
  record_id=null,
  status="pending_confirmation"
)
```

确认此类草稿时，`confirm_record_change_draft` 必须先以确认者 `actor` 调用既有 `create_record` 完成原有字段/关系/权限校验，再回填 `record_id` 与 `confirmed`。更新草稿仍使用原 `update_record` 路径；拒绝 create-record 草稿不得创建记录。创建和确认的 audit 均不得含 `proposed_values`。

## 其余 adapter 的最小、受控输入

| Tool | 输入 | 允许调用的既有服务边界 | 脱敏结果 |
| --- | --- | --- | --- |
| `record.query` | `view_id` | deterministic `invoke_digital_employee(..., action="query")` | view/entity ID、可见 field key、`record_count` |
| `table.summarize` | `view_id` | deterministic `invoke_digital_employee(..., action="summarize")` | view/entity ID、可见 field key、`record_count`；不产生自由文本总结 |
| `contact.resolve` | `workspace_member_id` | 一个限定的 Stage06 服务 helper，精确读取该 member 且核验同 workspace、active；不可搜索/枚举 | member ID、`resolved_count=1`，不返回 `user_id`/角色/联系人数据 |
| `import.preview` | `import_job_id` | `read_import_job`，要求 job 与 ticket workspace 一致且状态为 `awaiting_confirmation` | import-job ID、source type、行/字段计数；不返回文件名、原始行或 detected schema |
| `tool_catalog.inspect` | `{}` | 一个限定的 Stage06 服务 helper，返回固定 Tool Gateway 目录 | 允许 tool 名和 `tool_count`，不返回 Prompt 或 manifest 文本 |
| `task.create_draft` | `table_id`、`proposed_values` | 新增的受控 Stage06 create-record draft helper | draft ID、table ID、`draft_count=1`、`confirmation_required=1` |
| `record_change_draft.create` | `record_id`、`proposed_values` | deterministic `invoke_digital_employee(..., action="draft_update")` | draft ID、record ID、`draft_count=1`、`confirmation_required=1` |

所有输入 ID 都必须是 UUID 字符串；`ToolInvocation` 的既有递归敏感 key 拒绝保持不变。Gateway 的结果、ticket `tool_summary` 和 audit 都只能写 `RedactedToolResult` 的字段，尤其不得出现 `records`、`proposed_values`、`user_id`、文件行、prompt、response、secret 或 stack trace。

## 具体修改

- 创建 `backend/app/runtime/stage08_tool_gateway.py`：固定 dictionary registry、输入转换、ticket transition、结果映射和固定错误代码。
- 修改 `backend/app/services/stage06_digital_employees.py`：添加小型受控 helper：精准 workspace-member resolution、固定工具目录、create-record draft 创建；扩展 `confirm_record_change_draft` 以确认 `create_record` 草稿。
- 创建 `backend/tests/unit/test_stage08_tool_gateway.py`：先 RED 后 GREEN，覆盖 7 个 adapter、fail-closed、权限/终态、脱敏、create-record 草稿未写入、确认后写入、拒绝不写入。

## 首次独立审查后的必需安全修复（2026-07-18）

首次实现未通过独立审查，以下四项属于既有 Stage08 fail-closed、权限交集与状态机要求的修复，不改变已批准的产品边界：

1. `execute` 只能把调用方对象的 `ticket.id` 作为查找键。UoW 重新取得的 canonical ticket 必须贯穿 actor/employee/workspace 校验、每一个 adapter、tool summary 追加和终态迁移；不得读取 detached ticket 上的 scope 字段。
2. 在 Gateway 调用 adapter 前增加窄的 `lock_execution_ticket_for_transition(ticket_id)` UoW 边界：内存实现只返回已有对象；SQLAlchemy 对目标 `stage08_execution_tickets` 行 `FOR UPDATE`。锁内只允许从 `planned` claim 到 `executing`。并发调用中仅一个可进入 adapter，其他固定拒绝且不覆盖终态。
3. `confirm_record_change_draft` 与 `reject_record_change_draft` 必须使用既有 `lock_record_change_draft_for_transition`。create-record 确认的锁内状态检查、权限重验、record 创建与状态迁移必须同一事务完成。
4. create-record 确认必须按**确认 actor 的当时权限**重验：active workspace membership、`get_create_form(..., actor).can_create` 与 `can_actor_write_record_fields` 对全部 `proposed_values` field key 均通过，然后才调用既有 `create_record` 完成类型、必填、关系校验。active member 的当前 `user_id` 与 `role` 必须重建为 canonical actor；不可继续信任调用时携带的旧 `Actor.role`。Stage06 当前没有独立 `record.create` action contract，本修复不新造动作权限；上述既有 workspace/table/field authorization 即为该记录创建路径的权限真源。

新增/扩展测试必须覆盖 forged/detached ticket（篡改 employee/workspace/actor）、确认者权限撤销或不同确认者、ticket 并发 claim、create-record draft 双确认及 confirm/reject 竞争。PostgreSQL 并发测试必须使用受控本地数据库并直接证明锁等待或单一副作用，不得以 sleep/barrier 代替数据库锁证据。

## 明确不做

- 不创建 `Task` / `TaskDraft` ORM model、迁移或 API。
- 不创建或提交 `PlatformRecord`，除非用户以既有 confirmation 流程确认 `create_record` 草稿。
- 不发送 Telegram、通知或 Provider 请求。
- 不返回 raw record、任务字段值、联系人 PII、文件内容、prompt 或 response。
- 不实现 Memory、RAG、群聊历史、LangGraph coordinator 或 Runtime API（分别属于后续任务/Package）。

## 验收标准

1. 每个 7-tool adapter 只能经过既有 Stage06 service boundary，且未知 tool 不产生 service call。
2. `record.query` / `table.summarize` 只返回 caller 可见 field key 与计数。
3. `task.create_draft` 与 `record_change_draft.create` 都只产生一个 `pending_confirmation` 草稿；源记录/目标表在草稿阶段不变；脱敏结果不含 `proposed_values`。
4. 确认 create-record 草稿后才生成一个 record；拒绝后为零；确认权限被 Stage06 `create_record` 重新校验。
5. ticket 以 Task 3 状态机迁移，终态不可重跑；结果/审计/ticket 只保留脱敏摘要。
6. `python -m pytest -q tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_skill_matching.py` 通过；并执行 no-send `rg` 扫描。
