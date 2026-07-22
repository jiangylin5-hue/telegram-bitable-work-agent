# Stage08 Package E — Task E3 independent review report

## Review status

- Status: `REVIEWED`
- Scope: E3 spec compliance、代码质量、现有 runtime/UoW/gateway 持久化链路与最小关键测试复核。
- Review package note: review package 包含 E1-E3 当前完整文件；本报告只把 brief/report 所标识的 E3 协调器、草稿物化和 E3 测试作为变更归因范围。
- Production/test code changes: none；本次只新增本审查报告。
- External effects: 未调用真实 provider、network、Telegram 或部署写入；未连接 PostgreSQL（环境未配置 disposable URL）。

## Verdict

- Spec compliance verdict: **FAIL / NOT ACCEPTABLE**。
- Code-quality verdict: **FAIL**。
- Gate recommendation: **不得接受 E3**。至少应修复下列 Critical/Important 项并补齐真实 PostgreSQL transaction/current-state/cancel/rollback/cleanup 证据后重新复审。

当前实现确实保留了 LangGraph 拓扑与 `checkpointer=None`，unknown citation 会 fail closed，正常 happy-path 不直写业务 record，也未发现 Telegram/network/真实 provider 调用。但这些正向点不足以抵消真实 SQLAlchemy UoW 不可工作、TOCTOU/rollback/idempotency 错误和完整持久化链路违反白名单的阻断性问题。

## Critical

### C1 — 草稿成功识别依赖 InMemory 私有属性，真实 SQLAlchemy UoW 会在已产生副作用后错误返回 `failed`

- E3 在 `backend/app/services/stage08_collaboration.py:608-615` 通过 `getattr(uow, "record_change_drafts", ())` 查找结果。`record_change_drafts` 只是 `InMemoryStage06PlatformUnitOfWork` 的列表实现细节，不属于 `Stage06PlatformUnitOfWork` contract；contract 提供的是 `list_record_change_drafts`（`backend/app/services/stage06_platform.py:592`），SQLAlchemy UoW 也只实现查询方法（`backend/app/services/stage06_platform.py:2097`），没有该列表属性。
- 因此在真实 PostgreSQL UoW 上，gateway 已创建 draft、ticket 已转为 `succeeded` 后，`draft_ids` 恒为空，E3 在 `backend/app/services/stage08_collaboration.py:614-615` 返回 `failed`。这会造成响应状态与已持久化状态相互矛盾，并直接违反“结果必须是已有 `pending_confirmation` draft”。
- `backend/tests/integration/test_stage08_collaboration_postgres.py:14-25` 只执行 `SELECT 1`，从未构造 SQLAlchemy UoW、运行 `run_stage08_collaboration` 或断言 draft/ticket/transaction；因而完全没有覆盖此缺陷。

### C2 — current-state consumption 不是原子的；ticket 创建后撤权/撤销 source lifecycle 仍可落草稿，异常又没有 rollback cleanup

- Policy Gate 在 `backend/app/services/stage08_collaboration.py:549-555` 校验一次，物化入口在 `backend/app/services/stage08_collaboration.py:574` 再校验一次；但随后 `begin_execution_plan` 与 gateway 执行（`backend/app/services/stage08_collaboration.py:604-605`）之间没有锁住/revalidate target record、group mapping/source lifecycle 或 employee member grant 的同一事务边界。
- `begin_execution_plan` 只锁 workspace（`backend/app/services/stage08_runtime.py:48`）。gateway 的 `_begin_plan`/`_authorized_employee`（`backend/app/runtime/stage08_tool_gateway.py:134-169`）只重查 active employee/allowed action，`_actor_for_ticket`（同文件 `:356`）只重查 active member；它不重查 employee member grant、group mapping/source lifecycle 或 target record lifecycle。
- 只读注入复现：在 `execute_plan` 入口将 target record 标成 inactive，结果仍为 `draft_pending`、draft 1、ticket 1/succeeded；在同一位置将 group mapping 标成 revoked，结果同样仍为 `draft_pending`、draft 1、ticket 1/succeeded。这违反 brief 要求的消费期 current-state 校验与“计划后撤销 target/source 时 draft 计数 0”。
- `backend/app/services/stage08_collaboration.py:639-640` 捕获所有异常后只把 graph 状态改为 `failed`，没有回滚刚创建的 ticket、idempotency reservation、audit 或可能已创建的 draft。只读注入 gateway exception 的复现结果是：`failed`，ticket 1（状态 `planned`），draft 0，idempotency record 1；这是明确的 orphan reservation/ticket。
- 该问题必须以真实 PostgreSQL transaction/savepoint/rollback/current-state 并发测试证明修复，不能只依赖 InMemory 列表计数。

### C3 — 完整 draft 路径额外持久化含 UUID/record 信息的 AgentRun 与 audit；E3 只检查最后一条摘要，未满足“每个终态/完整链路严格白名单”

- E3 通过 gateway 调用 `invoke_digital_employee`（`backend/app/runtime/stage08_tool_gateway.py:336-349`）。该既有路径在创建草稿时写入 Stage06 AgentRun（`backend/app/services/stage06_digital_employees.py:842-867`）和 draft/invocation audit（同文件 `:788-835`、`:977-993`）；`begin_execution_plan`/ticket transition 也写 ticket UUID audit（`backend/app/services/stage08_runtime.py:94-99`、`:167-209`）。
- E3 在 ticket transition audit 已经写完之后才清空 `ticket.tool_summary` entity refs（`backend/app/services/stage08_collaboration.py:616-627`），不能撤销已写 audit/AgentRun 中的 UUID、`record_id`、`draft_id`、skill evidence 等数据。
- 只读扫描一个 valid draft 路径的持久化对象得到：2 条 AgentRun，其中 `stage06_digital_employee_runtime` 含 UUID，output keys 为 `action/draft_id/record_count/record_id/skill_evidence/status`；相关 5 条 ticket/draft/invocation audit 均含 UUID，只有 E3 自己的 terminal AgentRun/audit 不含 UUID。
- 现有 redaction 测试只序列化 `agent_runs[-1]` 与 `audit_events[-1]`（`backend/tests/unit/test_stage08_collaboration_service.py:504-510`），刻意漏掉前述完整持久化链路。这不能证明“不进入 AgentRun/audit”。

## Important

### I1 — idempotency/replay 与多草稿识别语义错误，并会留下与返回状态冲突的成功副作用

- `begin_execution_plan` 对相同 trace/fingerprint 返回既有 ticket，但 gateway 只接受 `planned` ticket（`backend/app/runtime/stage08_tool_gateway.py:86`、`:173-184`）。因此相同 command/idempotency 的第二次调用拿到 `succeeded` ticket 后失败。
- 只读复现：相同 idempotency 连续调用得到 `draft_pending`、`failed`；ticket 1、draft 1、idempotency record 1。正确 replay 应稳定返回同一安全结果，而不是失败。
- E3 以“该 record 当前全部 pending drafts 必须恰好为 1”识别本次结果（`backend/app/services/stage08_collaboration.py:608-615`），而不是绑定本 execution 的 draft。不同 idempotency 对同一 record 的第二次合法调用会创建第二份 draft 和第二个 succeeded ticket，然后 E3 因总数为 2 返回 `failed`。
- 只读复现：不同 idempotency 连续调用得到 `draft_pending`、`failed`；ticket 2（均 `succeeded`）、draft 2。该路径既违反 same/different idempotency 要求，也放大 C2 的 cleanup 问题。
- `backend/tests/unit/test_stage08_collaboration_service.py` 只有 unknown-citation 与单次 happy-path 两个 E3 测试（`:402-515`），没有任何 replay/conflict/different-key 覆盖。

### I2 — PostgreSQL integration test 只是连通性测试，未提供计划要求的任何 E3 集成证据

- `backend/tests/integration/test_stage08_collaboration_postgres.py:14-25` 仅创建 engine 并执行 `SELECT 1`；没有迁移/schema、SQLAlchemy UoW、事务、current-state revoke、cancel、rollback、cleanup、draft/ticket/audit/idempotency 断言。
- 本环境复跑结果为 `1 skipped`，原因是 `STAGE08_RAG_DATABASE_URL` 未配置；实现报告也明确承认这不是 PostgreSQL acceptance result。
- 因此 Task E3 的 PostgreSQL acceptance 条件完全未满足，且 C1 说明即便连接测试通过也不能代表 E3 能运行。

### I3 — brief 指定的 RED/GREEN 场景大部分既未实现也未测试

- 缺失场景包括：计划后撤销 target record、计划后撤销 employee grant、unavailable analysis 的 `degraded`、malformed provider、cancel、budget exceeded、same/different idempotency、rollback cleanup、完整 audit/AgentRun redaction。
- 默认 `UnavailableAnalysisProvider` 在 `backend/app/services/stage08_collaboration.py:523-524` 被直接映射成 graph `failed`；最小复现返回 `failed` + `analysis_unavailable`，不是 brief 明确要求测试的安全 `degraded`。
- Collaboration budget 声明了 `max_provider_time_ms`（`backend/app/runtime/stage08_collaboration_contracts.py:261`），但 E3 未实施 deadline/timeout/cancellation；只把 budget 传给 provider。terminal `latency_ms`、`completed_at` 与 `provider_calls` 又被硬编码为 0/started_at/0（`backend/app/services/stage08_collaboration.py:790`、`:805-808`），不能作为预算或时延证据。

### I4 — 受限 draft intent 没有形成受控 mutation；实现无条件创建空 `proposed_values` 的 no-op 草稿

- E3 只调用 `_draft_intent_snapshot` 证明 carrier 来源（`backend/app/services/stage08_collaboration.py:576-579`），完全不使用 intent 内容；invocation 固定为 `proposed_values: {}`（`:596-600`）。
- 因为空字段集，Policy Gate 无从验证“target field”或 field permission，也无法证明草稿基于已验证 intent。此行为只满足“产生一个 pending object”的表面条件，不满足“基于已验证的受限 intent 构造 invocation”及 target field current-state 校验。
- 如果当前 E1 contract 确实故意只允许 summary、无法表达安全 field/value intent，则 E3 应先停在文档/contract blocker，而不是制造可被确认的空更新草稿；按本任务约束不得擅自扩 schema/API/model。

## Minor

### M1 — 过宽异常折叠与虚假运行指标降低可审计性

- `_analyse_state` 与 `_materialize_draft_state` 以裸 `except Exception` 折叠所有 provider、policy、gateway、programming error（`backend/app/services/stage08_collaboration.py:531-532`、`:639-640`），终态只剩通用 `analysis_unavailable`/`failed`，无法区分 cancel、timeout、policy deny 或 rollback failure。
- terminal summary 又将 provider call、latency、completed time 固定为零值（`:790`、`:805-808`）。这些字段虽然没有泄露私有值，但记录并不真实，妨碍预算与异常取证。

## Verification evidence

### Required unit command

```text
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
47 passed in 1.69s
```

结论：现有测试自身通过，但测试集没有覆盖上述阻断性行为。

### Required PostgreSQL command

```text
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
1 skipped in 0.21s
```

Skip reason: `STAGE08_RAG_DATABASE_URL` 未配置。没有 PostgreSQL E3 acceptance evidence。

### Additional read-only deterministic diagnostics

全部使用 InMemory UoW 与本地注入 provider/gateway，无 network/Telegram/真实 provider：

```text
same_idempotency: draft_pending, failed; tickets=1 drafts=1 idempotency=1
different_idempotency: draft_pending, failed; tickets=2 drafts=2; ticket_statuses=succeeded,succeeded
gateway_exception: failed; tickets=1 drafts=0 idempotency=1; ticket_status=planned
revoke_after_ticket_record: draft_pending; drafts=1 tickets=1; ticket_status=succeeded
revoke_after_ticket_mapping: draft_pending; drafts=1 tickets=1; ticket_status=succeeded
unavailable_default: failed; degradation_codes=analysis_unavailable; drafts=0 tickets=0
valid persisted chain: AgentRun=2; audits include ticket-created, ticket-transitioned, draft-created, digital-employee-invoked and E3-terminal; Stage06 AgentRun and five non-E3 terminal-chain audits contain UUIDs
```

## Required remediation before re-review

1. 在不扩 schema/API/model 的前提下，设计真正原子的 E3 transaction/savepoint：Policy Gate current-state revalidation、ticket reservation、gateway execution、terminalization 与 rollback/cleanup 必须同一可验证边界；失败/取消不得吞异常后提交 orphan state。
2. 让 E3 从本 execution/replay 的受控结果取得 draft identity，不依赖 InMemory 列表或 record 全局 pending 数量；same-key replay 与 different-key 行为须明确定义并测试。
3. 解决 gateway 所触发的既有 Stage06 AgentRun/audit/ticket audit 与 E3 严格白名单冲突；测试必须扫描本次 trace 的全部 DB/Redis/checkpoint/AgentRun/audit/outbox/log/API DTO，而不是只检查最后一条。
4. 为 record/view/field、business/source lifecycle、member/employee/grant、budget/idempotency 添加消费期撤权测试，并提供真实 PostgreSQL transaction/current-state/cancel/rollback/cleanup 证据。
5. 明确无法表达 field/value 的 E1 draft-intent contract 是 blocker，或在已获批准的 contract 范围内让 invocation 真正来源于受控 intent；不要落空 mutation 草稿。

## Skipped tests and remaining risk

- Skipped: PostgreSQL E3 integration test（环境未配置 local disposable URL）。
- Not run: 全 backend test suite；本次复审按任务要求只复跑最小关键测试。
- Remaining risk: 未在真实 PostgreSQL 上触发 C1/C2；静态 UoW contract 已足以证明 C1，且缺少事务/并发测试意味着 C2 的生产风险尚未被约束。

## Temporary cleanup

- 未创建临时脚本、测试数据、数据库对象、凭据、network artifact 或 deployment artifact。
- 只新增本 review report；未修改生产/测试代码，未执行 stage/commit/reset/checkout/clean/push。
