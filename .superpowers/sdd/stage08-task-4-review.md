# Stage08 Package A Task 4 独立审查

审查依据：`stage08-task-4-brief.md`（唯一任务真源）、`stage08-task-4-report.md`、`stage08-task-4-working-tree-review.diff`，以及为确认调用边界、权限与锁语义而只读核对的当前源码。按要求未复跑实施者报告中的测试，也未触发 Telegram、Provider 或任何外部写入。

## Critical

### C1. Gateway 重新取得 tracked ticket 后仍使用调用者传入的 ticket 执行 adapter

- 文件/位置：`backend/app/runtime/stage08_tool_gateway.py:49-75`，`Stage08ToolGateway.execute` / `_begin`；受影响 adapter 位于 `:188-298`。
- 原因：`_begin` 通过 `_tracked_planned_ticket` 取得并校验 UoW 中的 canonical ticket，但只返回 `Actor`。`execute` 随后仍把原始入参 `ticket` 传给 adapter，并把结果 append 到该入参的 `tool_summary`。因此，只要传入一个与合法 planned ticket 同 `id` 的 detached/伪造对象，初始 policy 检查作用于 canonical ticket，而 adapter 却使用伪造对象的 `employee_id`、`workspace_id` 等字段。攻击者可借另一个 scope 更大的 employee 执行查询/建草稿，或改变 `contact.resolve` / `import.preview` 的 workspace scope；即使未扩大权限，成功摘要也可能只写入 detached 对象而没有持久化到 canonical ticket。`transition_execution_ticket` 内部重新取 tracked ticket 不能修复 adapter 已使用错误 ticket 的问题。
- 修复建议：让 `_begin` 返回 `(tracked_ticket, actor)`（或先在 `execute` 中以 ID 取得 canonical ticket），从 policy、actor、所有 adapter 参数、`tool_summary` append 到终态迁移都只使用同一个 tracked 对象；不要再读取调用者对象上除 `id` 外的任何字段。新增 forged/detached ticket 测试，至少分别篡改 `employee_id`、`workspace_id`、`actor_id`，证明 service 不执行、scope 不扩大且 canonical summary/状态一致。

### C2. create-record 草稿确认没有按确认 actor 重新校验 record.create 与字段写权限

- 文件/位置：`backend/app/services/stage06_digital_employees.py:447-489`，`confirm_record_change_draft` create 分支；相关既有服务为 `backend/app/services/stage06_platform.py:1850-1880` 的 `create_record`。
- 原因：实现仅把确认 actor 传给 `create_record`。当前 `create_record` 的 `_validate_record_values` 负责必填、类型、choice、关系等数据校验，但不执行 workspace `record.create` action 授权，也不调用 `_can_actor_write_field` 校验确认 actor 对每个目标字段的 write 权限。草稿创建阶段 `get_create_form` 对创建者做过的检查不能替代任务真源要求的“确认时按确认 actor 重验”，尤其当权限已撤销或确认者与创建者不同。结果是对目标字段已经无写权的确认 actor 仍可创建 record。
- 修复建议：在 create 分支写入前调用一个复用 Stage06 authorization/field-permission 逻辑的受控 service helper，以当前已验证 membership role 的确认 actor 检查 `record.create`、目标表和每个 proposed field；随后再调用 `create_record` 进行字段/关系校验与写入。避免在 Gateway 复制权限规则。新增测试覆盖：draft 创建后撤销字段 write、不同确认 actor、无 `record.create` role；三者都应拒绝且 record 数保持 0，draft 仍为 `pending_confirmation`。

## Important

### I1. planned ticket 的 claim 不是原子的，并发执行可重复调用 service

- 文件/位置：`backend/app/runtime/stage08_tool_gateway.py:76-90`，`_tracked_planned_ticket` / `_begin`；`backend/app/services/stage08_runtime.py:103-129`，`transition_execution_ticket`；`backend/app/services/stage06_platform.py:1138-1142`，SQLAlchemy `get_execution_ticket`。
- 原因：Gateway 先普通读取 `status == planned`，再调用 transition；SQLAlchemy 的 `get_execution_ticket` 是 `session.get`，没有 `FOR UPDATE`、version compare 或条件 update。两个 PostgreSQL transaction 可同时读到 `planned`，都迁移为 `executing` 并执行 adapter。对 `task.create_draft` / `record_change_draft.create` 会生成重复草稿，对读工具也会重复 AgentRun/audit。现有测试只覆盖同一对象终态后的串行重跑，不能证明并发 fail-closed。
- 修复建议：增加窄的 execution-ticket claim boundary（`SELECT ... FOR UPDATE` 后检查 planned，或 `UPDATE ... WHERE status='planned' RETURNING`），并让 Gateway 只在 claim 成功后调用 service。增加真实 PostgreSQL 双 transaction 测试，断言只有一个 claimant 进入 adapter、只产生一个 draft/AgentRun，另一个请求得到固定拒绝码且不能覆盖终态。

### I2. create-record draft 确认未使用已有 transition 行锁，可并发创建两个 record

- 文件/位置：`backend/app/services/stage06_digital_employees.py:447-489`，`confirm_record_change_draft` / `_require_draft`；已有锁接口在 `backend/app/services/stage06_platform.py:1209-1216`，`lock_record_change_draft_for_transition`。
- 原因：确认路径通过普通 `get_record_change_draft` 读取 `pending_confirmation`。两个 transaction 可同时通过状态检查，各自调用 `create_record`，最终同一 draft 只保留一个 `record_id`，但数据库留下两个 records。这违反“确认后才生成一个 record”与终态不可重复的语义。仓库已有专门的 draft transition 行锁，Stage07 服务也在使用，但本路径没有使用。
- 修复建议：确认和拒绝都先使用 `lock_record_change_draft_for_transition` 取得 canonical draft，再检查状态并执行写入/终态迁移；增加真实 PostgreSQL 并发确认测试，断言一个确认成功、另一个因终态失败，且 record 总数严格为 1。另加 confirm/reject 竞争测试，证明拒绝获锁时 record 为 0、确认获锁时 record 为 1。

## Minor

### M1. 阶段计划的 Current Progress 与当前工作树状态矛盾

- 文件/位置：`project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md:6`，`Current Progress`。
- 原因：文档仍写“尚未开始任何包的代码、迁移、API 或外部操作”，但 review package 已包含 Package A Task 1-4 的合同、模型/迁移、policy/runtime 与本 Task Gateway 代码。该状态字段不再满足项目文档要求的进度透明，也会误导后续实施者。
- 修复建议：把 `Current Progress` 更新到准确的 Task 4 审查状态，并明确 Task 5/6、API 与 package-level PostgreSQL acceptance 尚未完成；不要把已有单元测试报告表述成 package 通过。

### M2. Task 4 计划示例仍使用不存在的 `field_keys` 属性

- 文件/位置：`docs/superpowers/plans/2026-07-17-stage08-runtime-foundation-implementation-plan.md:165-168`，`test_record_query_returns_visible_field_keys_and_count` 示例。
- 原因：已实现的 `RedactedToolResult` 合同字段是 `visible_field_keys`，计划示例却断言 `result.field_keys`。这不改变运行时代码，但会让后续按计划补测试或核对合同的人得到错误接口信息。
- 修复建议：统一为 `visible_field_keys`，并与 Task 1 合同、任务简报及实际测试保持一致。

## Spec compliance verdict

**不通过。** 固定 7-tool dictionary、Stage06 service boundary、输出映射、无即时 record 写入和 create-record draft 的基本形态均已实现；但 C1 允许 adapter 脱离 canonical ticket 的 employee/workspace scope，C2 未完成任务真源明确要求的确认 actor 权限/字段重验，I1/I2 也未保证重复/并发执行 fail closed 和“确认只生成一个 record”。这些问题修复并补充权限撤销、detached ticket 与 PostgreSQL 并发证据前，不能判定 Task 4 符合 spec。

## Task quality verdict

**不通过。** 实现结构清晰，7 个 adapter 与主要串行 happy/fail-closed 路径有单元测试，脱敏结果未直接返回 raw records/proposed values；但测试全部基于 in-memory UoW，且遗漏最关键的 canonical ticket 完整性、确认时权限变化与两个并发状态机。实现报告中的 `20 passed` 只能支持已覆盖的串行场景，不能支撑本任务的安全与幂等质量门槛。

## Fix Round 1 Re-review

复审依据：更新后的 `stage08-task-4-brief.md`、`stage08-task-4-report.md`、`stage08-task-4-fix-round-1-review.diff`，以及为核对当前 membership role、字段权限和 UoW 锁语义而只读打开的对应源码。按要求未复跑实施者报告的 unit/PostgreSQL 测试，未触发 Telegram、notification、Provider 或其他外部写入。

### Critical

无。

### Important

#### FR1-I1. create-record 确认仍信任可能过期的 `Actor.role`，未完成“当前 membership 权限”重验

- 文件/函数：`backend/app/services/stage06_digital_employees.py:1001-1015`，`_require_active_actor_member`；`:1048-1070`，`_assert_create_record_confirmation_allowed`；调用点 `confirm_record_change_draft`。
- 依据：`_require_active_actor_member` 只查到同 `user_id` 且 `status == "active"` 的 member，随后丢弃该 member，既不核对 `member.role == actor.role`，也不以当前 `member.role` 重建 canonical actor。`get_create_form`、`can_actor_write_record_fields` 以及后续 `create_record` 继续使用调用方传入的 `actor.role`。因此 member 已从 `operator` 降为 `viewer`、但调用持有旧 `Actor(role="operator")` 时，确认仍按 operator 字段权限创建 record，不符合 Fix Round brief 的“确认 actor 当时权限”重验。新增测试覆盖了 field policy 撤销、显式 viewer Actor 和 membership inactive，但没有覆盖“数据库 role 已降级 + stale Actor role”。
- 修复建议：让 active-member helper 返回当前 member，并在锁内基于 `member.user_id/member.role` 构造 canonical actor；用该 actor 完成 `get_create_form`、`can_actor_write_record_fields`、`create_record` 和确认 audit。至少新增 role downgrade 回归：draft 创建后把 member role 从 operator 改为 viewer，仍传旧 operator Actor，确认必须拒绝、draft 保持 `pending_confirmation`、record 数为 0。

### Minor

#### FR1-M1. `Current Progress` 仍停留在“正在修复”，未记录 Fix Round 1 已实现并等待复审

- 文件/位置：`project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md:6`，`Current Progress`。
- 依据：实现报告已声明 Fix Round 1 完成并给出 unit/PostgreSQL 证据，但阶段文档仍写 Task 4“正在按既有安全合同修复”。
- 修复建议：更新为“Fix Round 1 已实现并完成复审；仍有 FR1-I1 待修复”，同时继续明确 Task 5/6 与生产门禁未开始。

#### FR1-M2. 合同说明仍残留不存在的 `field_keys` 字段

- 文件/位置：`docs/superpowers/plans/2026-07-17-stage08-runtime-foundation-implementation-plan.md:74`，Task 1 合同说明。
- 依据：Task 4 示例已修正为 `visible_field_keys`，但合同说明仍列为 `field_keys`；实际 `RedactedToolResult` 与代码使用 `visible_field_keys`。
- 修复建议：将该处同步为 `visible_field_keys`。

### 上一轮硬性 findings 复核

- C1 canonical ticket：已修复。`execute` 只从调用对象读取 `ticket.id`，`lock_execution_ticket_for_transition` 返回的 canonical ticket 贯穿 policy、actor、adapter、summary 与终态迁移；detached employee/workspace/actor 测试覆盖相应边界。
- C2 当前确认权限：部分修复。active membership、`get_create_form.can_create`、全部 proposed field write 检查已加入，但仍存在 FR1-I1 的 stale role 缺口。
- I1 ticket 并发 claim：已修复。SQLAlchemy UoW 使用 `SELECT ... FOR UPDATE`，测试以两个独立 session 和 `pg_blocking_pids` 证明第二 claimant 等待；最终仅一个 AgentRun、一个持久化 redacted summary，第二请求得到 `ticket_not_planned`。
- I2 draft transition 并发：已修复。confirm/reject 均使用既有 draft transition lock；double-confirm 与 confirm/reject 两种顺序均以 `pg_blocking_pids` 证明锁等待，并验证严格的 0/1 record 单一副作用。
- 固定 dispatcher 与安全边界：未发现新的 Critical/Important。registry 与 action map 均只含 7 个固定 tool；adapter 仍只经 Stage06 service boundary；结果/ticket summary 使用 `RedactedToolResult` 投影，未见 raw record、PII、`proposed_values`、secret 或 stack trace 写入；未新增 Telegram/notification/provider、Task/TaskDraft schema、migration、API、Memory/RAG、LangGraph 或即时 record 写入路径。

### Spec compliance verdict

**不通过，需再修 FR1-I1。** C1、I1、I2 已满足硬性要求，C2 的 membership active、form 与 field 检查也已落地；但确认授权仍使用可能过期的 `Actor.role`，尚未真正按数据库中的当前 membership role 重验。修复该点并补充 role downgrade 测试后，未见其他阻止 Task 4 通过的 Critical/Important。

### Task quality verdict

**暂不通过。** Fix Round 1 的 targeted unit 覆盖和 PostgreSQL `pg_blocking_pids` 并发证据较上一轮显著补强，且证明了 ticket/draft 的单一副作用；但权限撤权测试缺少最关键的 role downgrade + stale Actor 场景，当前实现仍可绕过最新角色权限。两个文档问题为 Minor，不单独阻塞代码验收。

## Fix Round 2 Re-review

本轮只核验 FR1-I1。只读检查了更新后的 brief、report Fix Round 2、`stage06_digital_employees.py` 与对应 unit test；未复跑实施者测试。

### Critical

无。

### Important

无。

FR1-I1 已关闭，依据如下：

- `backend/app/services/stage06_digital_employees.py:1001-1025`：`_require_active_actor_member` 返回当前 active `WorkspaceMember`，`_canonical_active_member_actor` 只以该 member 的当前 `user_id` 和 `role` 构造 canonical `Actor`，不再信任传入的旧 `Actor.role`。
- `create_create_record_draft`（`:513-564`）：canonical actor 贯穿 `get_create_form` 与 draft-created audit。
- `confirm_record_change_draft` / `_assert_create_record_confirmation_allowed`（`:448-490`、`:1058-1081`）：取得 draft transition lock 后，以 canonical actor 执行 `get_create_form`、`can_actor_write_record_fields`、`create_record` 和 confirmed audit；权限拒绝发生在 record 写入前。
- `backend/tests/unit/test_stage08_tool_gateway.py:373-389`：测试先以 operator 创建 draft，再把当前 active member 的 role 降为 `viewer`，确认时仍传入旧的 `fixture.operator`（role 为 `operator`）；断言抛出 `PlatformValidationError`、draft 保持 `pending_confirmation`、`record_id` 为空且 records 为零，准确覆盖 role downgrade + stale actor 场景。

### Spec compliance verdict

**通过。** 就 Fix Round 2 唯一范围 FR1-I1 而言，当前 membership role 已成为 create-record draft 创建/确认的权限真源，上一轮剩余 Important 已关闭。

### Task quality verdict

**通过。** 实现复用单一 canonical-actor helper，调用链覆盖 form、field、write 与 audit，且 targeted regression 精确验证旧 Actor role 不能绕过降级后的 member 权限。本轮没有新的 Critical 或 Important。
