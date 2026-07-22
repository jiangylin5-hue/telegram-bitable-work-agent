# Stage08 Runtime Foundation 与类型化 Tool Gateway 实施计划

> **供 Agent 执行：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行；用 `- [ ]` 跟踪步骤。

**Goal：** 把已批准的 Stage06 Skill Manifest 命中转为类型化、受权限约束的工具调用；每次调用具备预算、execution ticket、幂等与审计证据。

**Architecture：** 实时表格读取和草稿创建仍在既有 Stage06 service boundary 内完成。本包新增小型 Stage08 runtime domain：校验类型化执行计划、分派 allowlist tool adapter、执行策略检查并记录脱敏工具证据。PostgreSQL 仍是真源；本包不实现 Memory、RAG、群历史持久化、协调器 LLM 路由或新的 Telegram 发送路径。

**Tech Stack：** Python 3.12、FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL JSONB、既有 LangGraph、Pydantic、pytest。

## 全局约束

- 复用既有 Stage06 scope intersection 和 service boundary；tool adapter 禁止 raw SQL 和直接操作 ORM model。
- 工具输入输出、audit state 和 AgentRun 只保存 ID、计数、动作名、脱敏错误与权限过滤 field key；不得保存原始模型 prompt/response 或密钥。
- 每个执行计划必须携带最大墙钟时间、工具次数、检索 chunk 数（本包固定为零）、图深度与重试预算。
- 本包只开放 `record.query`、`table.summarize`、`contact.resolve`、`import.preview`、`tool_catalog.inspect`、`task.create_draft`、`record_change_draft.create`；其他 Skill 必须 fail closed。
- 草稿仍为 `pending_confirmation`；不新增直接写入、通知发送或 Telegram 发送。
- 当前 worktree 已有未提交 Stage07 改动；不得 stage、commit、reset、checkout 或影响无关文件。

## 文件结构

- 新建 `backend/app/runtime/stage08_contracts.py`：执行预算、计划、ticket、调用与脱敏结果的 Pydantic 合同。
- 新建 `backend/app/runtime/stage08_policy.py`：作用域/预算/动作等级校验。
- 新建 `backend/app/runtime/stage08_tool_gateway.py`：固定 allowlist adapter registry 与 dispatcher。
- 新建 `backend/app/services/stage08_runtime.py`：trace、幂等、ticket 与审计编排。
- 新建 `backend/app/models/stage08_runtime.py`：execution ticket 持久化模型。
- 新建 `backend/alembic/versions/20260717_0028_stage08_runtime_foundation.py`：ticket 表迁移。
- 修改 `backend/app/models/__init__.py` 与 `backend/app/services/stage06_platform.py`：模型注册和 UnitOfWork 支持。
- 修改 `backend/app/services/stage06_digital_employees.py`：仅暴露 adapter 所需的受限 helper，禁止复制授权逻辑。
- 新建 `backend/tests/unit/test_stage08_runtime_contracts.py`、`test_stage08_tool_gateway.py`、`test_stage08_runtime_service.py`、`test_stage08_runtime_api.py`。
- 新建 `backend/tests/integration/test_stage08_runtime_postgres.py`。
- 新建 `project-docs/08-implementation/STAGE_08_RUNTIME_FOUNDATION_BDD_AND_ACCEPTANCE.md` 与 `evidence/stage08-runtime-foundation.md`。

---

### Task 1：定义 Runtime 合同与红灯测试

**Files：** 创建 `backend/app/runtime/stage08_contracts.py`；测试 `backend/tests/unit/test_stage08_runtime_contracts.py`。

**Produces：** `ExecutionBudget`、`ExecutionPlan`、`ToolInvocation`、`ExecutionTicketState`、`RedactedToolResult`；其中 `ExecutionPlan` 包含 `workspace_id`、`employee_id`、`Actor`、`action`、调用元组、预算、`trace_id` 与 `idempotency_key`。

- [ ] **步骤 1：先写失败测试**

```python
def test_execution_budget_rejects_invalid_limits():
    with pytest.raises(ValidationError):
        ExecutionBudget(max_tool_calls=0, max_wall_time_ms=30_000,
                        max_graph_depth=1, max_retries=0, max_retrieval_chunks=0)


def test_tool_invocation_rejects_unapproved_tool_and_raw_prompt_key():
    with pytest.raises(ValidationError):
        ToolInvocation(tool_name="provider.chat", input={"prompt": "secret"})
```

- [ ] **步骤 2：确认测试失败**

运行：`python -m pytest -q tests/unit/test_stage08_runtime_contracts.py`  
预期：因模块不存在而失败。

- [ ] **步骤 3：最小实现**

```python
JSONScalar = str | int | float | bool | None

class ExecutionBudget(BaseModel):
    max_tool_calls: Annotated[int, Field(ge=1, le=7)]
    max_wall_time_ms: Annotated[int, Field(ge=100, le=30_000)]
    max_graph_depth: Annotated[int, Field(ge=1, le=3)]
    max_retries: Annotated[int, Field(ge=0, le=2)]
    max_retrieval_chunks: Literal[0] = 0
```

`ToolInvocation.tool_name` 必须是全局约束中的 Literal；递归拒绝 `prompt`、`response`、`api_key`、`token`、`raw_text`。`RedactedToolResult` 只允许 `tool_name`、`status`、`entity_refs`、`visible_field_keys`、`counts`、`error_code`，不含自由文本内容。

- [ ] **步骤 4：确认通过并检查 diff**

运行：`python -m pytest -q tests/unit/test_stage08_runtime_contracts.py`  
预期：PASS。  
运行：`git diff --check -- backend/app/runtime/stage08_contracts.py backend/tests/unit/test_stage08_runtime_contracts.py`  
预期：exit 0。

### Task 2：持久化 execution ticket 并扩展 UnitOfWork

**Files：** 创建 `backend/app/models/stage08_runtime.py`、迁移 `backend/alembic/versions/20260717_0028_stage08_runtime_foundation.py`；修改 models registry 与 `stage06_platform.py`；测试 `backend/tests/integration/test_stage08_runtime_postgres.py`。

**Produces：** `Stage08ExecutionTicket(id, workspace_id, employee_id, actor_id, action, trace_id, request_fingerprint, status, budget, tool_summary, created_at, completed_at)`；UoW 增加 `add_execution_ticket`、`get_execution_ticket`、`get_execution_ticket_by_trace`。

- [ ] **步骤 1：写失败的 round-trip/唯一约束测试**

```python
def test_execution_ticket_round_trip_and_trace_uniqueness(postgres_uow, workspace):
    ticket = Stage08ExecutionTicket(..., status="planned",
        budget={"max_tool_calls": 1}, tool_summary=[])
    postgres_uow.add_execution_ticket(ticket)
    postgres_uow.commit()
    assert postgres_uow.get_execution_ticket(ticket.id).status == "planned"
```

同一 `(workspace_id, trace_id)` 需触发数据库唯一约束。

- [ ] **步骤 2：确认失败**

运行：`python -m pytest -q tests/integration/test_stage08_runtime_postgres.py -k execution_ticket`  
预期：missing model/table。

- [ ] **步骤 3：实现模型、迁移与两种 UoW**

使用 `UuidPrimaryKeyMixin`、时区时间戳、JSONB `budget/tool_summary`、`(workspace_id, status, created_at)` 索引与 `(workspace_id, trace_id)` 唯一约束。数据库还必须通过 `jsonb_typeof` 约束 `budget` 是 object、`tool_summary` 是 array；`tool_summary` 必须由合同保障脱敏。状态 check 必须严格列出 canonical 白名单，并在测试中验证任一非白名单状态被拒绝。

- [ ] **步骤 4：运行迁移和测试**

运行：`python -m pytest -q tests/integration/test_stage08_runtime_postgres.py -k execution_ticket`  
预期：PASS。  
运行：`alembic heads`  
预期：只有一个 head，末尾是 `20260717_0028`。

### Task 3：实现 Policy 与 ticket 生命周期

**Files：** 创建 `backend/app/runtime/stage08_policy.py`、`backend/app/services/stage08_runtime.py`；测试 `backend/tests/unit/test_stage08_runtime_service.py`。

**Produces：** `evaluate_execution_plan(uow, plan) -> PolicyDecision` 与 `begin_execution_plan(uow, plan) -> Stage08ExecutionTicket`；`PolicyDecision` 包含 `allowed`、`reason_code`、`effective_tool_names`。

- [ ] **步骤 1：写失败测试**

```python
def test_policy_denies_tool_not_allowed_by_employee_scope(uow, employee, actor):
    plan = plan_for(employee=employee, actor=actor, tool_name="import.preview")
    assert evaluate_execution_plan(uow, plan).reason_code == "tool_not_allowed_by_employee"

def test_same_idempotency_key_replays_without_second_ticket(uow, plan):
    assert begin_execution_plan(uow, plan).id == begin_execution_plan(uow, plan).id
```

- [ ] **步骤 2：确认失败**

运行：`python -m pytest -q tests/unit/test_stage08_runtime_service.py -k "policy or idempotency"`  
预期：模块不存在。

- [ ] **步骤 3：最小实现**

将 tool 名映射到既有 employee allowed action，并复用既有 authorization/scope helper；校验工具数、图深度、`max_retrieval_chunks == 0`，拒绝发送与写入绕过。只在 allowed 后创建 `planned` ticket，并使用 `fingerprint_request`/`begin_idempotent_operation` 处理重放与冲突。为消除同 workspace 的 trace/幂等并发竞态，新增一个窄 UnitOfWork 行锁方法：SQLAlchemy 对 `workspaces` 目标行使用 `FOR UPDATE`，内存实现只返回对应对象；锁内完成 trace 预检、幂等预检和创建，锁不改变权限语义。重放 ticket 必须复核 workspace 与 request fingerprint；状态迁移必须先由 UoW 重新取得受跟踪 ticket。

- [ ] **步骤 4：回归**

运行：`python -m pytest -q tests/unit/test_stage08_runtime_service.py tests/unit/test_stage06_audit_redaction.py`  
预期：PASS。

### Task 4：实现固定 allowlist Tool Gateway

**Files：** 创建 `backend/app/runtime/stage08_tool_gateway.py`；修改 `backend/app/services/stage06_digital_employees.py`；测试 `backend/tests/unit/test_stage08_tool_gateway.py`。

**Produces：** `Stage08ToolGateway.execute(uow, ticket, invocation) -> RedactedToolResult`；adapter 统一使用 `(uow, employee_id, actor, input)`。

#### 已确认的任务草稿语义（2026-07-18）

`task.create_draft` 不引入独立 `Task`、`TaskDraft` 表或新的业务垂类。它只接受一个调用者和数字员工都已获授权的任务表 `table_id` 与 `proposed_values`，在既有 `RecordChangeDraft` 中创建 `draft_type="create_record"`、`record_id=null`、`status="pending_confirmation"` 的草稿。草稿创建本身不得写入 `PlatformRecord`。

确认 `create_record` 草稿时，既有 Stage06 服务必须先按确认者的字段权限和表校验调用 `create_record`，再把新 record ID 回写到该草稿并把状态置为 `confirmed`，同时留下不含 `proposed_values` 的审计摘要。更新草稿继续沿用既有 `draft_type="update_record"` 路径。拒绝路径不创建记录。此为用户明确确认的实现边界；不改变 Package A 禁止直接写入和禁止发送的规则。

- [ ] **步骤 1：写失败测试**

```python
def test_record_query_returns_visible_field_keys_and_count(uow, ticket):
    result = gateway.execute(uow, ticket, ToolInvocation(
        tool_name="record.query", input={"view_id": str(view.id)}))
    assert result.visible_field_keys == ("status",)
    assert result.counts["record_count"] == 1

def test_unknown_tool_fails_closed_without_service_call(uow, ticket):
    with pytest.raises(Stage08ToolGatewayError, match="tool_not_registered"):
        gateway.execute(uow, ticket, unknown_invocation)
```

草稿 adapter 还必须证明：仅生成一个 `pending_confirmation`、源记录不变、结果不含 `proposed_values`。

- [ ] **步骤 2：确认失败；步骤 3：实现 adapter**

运行：`python -m pytest -q tests/unit/test_stage08_tool_gateway.py`  
预期：模块不存在。  
实现固定 dictionary dispatcher，禁止反射和用户控制 import path；每个 adapter 只能调用 Stage06 service boundary，并将输出映射为 `executing` 后的 `succeeded`、`denied`、`failed`、`cancelled` 或 `timed_out`。

- [ ] **步骤 4：回归与无发送扫描**

运行：`python -m pytest -q tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_skill_matching.py`  
预期：PASS。  
运行：`rg -n "sendMessage|notification_request.confirm|Telegram.*send" backend/app/runtime/stage08_tool_gateway.py backend/app/services/stage08_runtime.py`  
预期：无匹配。

### Task 5：增加 API、BDD 与证据

#### 已确认的多 invocation ticket 语义（2026-07-18）

当 `ExecutionPlan.invocations` 含有 1–7 个、且不超过 `budget.max_tool_calls` 的调用时，Runtime API 创建且只创建一张 ticket。该 ticket 仅从 `planned` 迁移一次至 `executing`，随后严格按请求中 invocation 的顺序执行；每一步只追加一条 `RedactedToolResult` 到 `tool_summary`。所有调用成功时迁移至 `succeeded`。首个 adapter 拒绝或失败时，追加该调用的固定脱敏错误摘要、停止所有后续调用，并分别迁移至 `denied` 或 `failed`。已进入终态的 ticket 绝不可重跑。`action` 仍是主声明动作，必须出现在 invocation 列表中；它不再要求等于每一步调用。该确认不改变 max wall-time 的合同校验，也不在 Task 5 引入异步抢占、Provider/Telegram 调用或新的写入路径。

**Files：** 创建 `backend/app/schemas/stage08_runtime.py`、`backend/app/api/routes/stage08_runtime.py`、BDD/证据文档；修改 `backend/app/main.py`；测试 `backend/tests/unit/test_stage08_runtime_api.py`。

**Produces：** `POST /api/stage08/runtime/execute-plan`。它接受执行计划，返回 ticket ID、终态和脱敏工具摘要，且必须先走既有 verified identity/workspace authorization。

- [ ] **步骤 1：写失败 API 测试**

```python
def test_execute_plan_returns_403_before_dispatch_for_wrong_workspace(client, identity):
    response = client.post("/api/stage08/runtime/execute-plan", json=plan_payload,
                           headers=identity.headers)
    assert response.status_code == 403

def test_execute_plan_returns_redacted_summary(client, identity):
    response = client.post("/api/stage08/runtime/execute-plan", json=allowed_query_payload,
                           headers=identity.headers)
    assert response.json()["status"] == "succeeded"
    assert "answer" not in response.text
```

- [ ] **步骤 2：确认失败；步骤 3：实现 route 和文档**

运行：`python -m pytest -q tests/unit/test_stage08_runtime_api.py`  
预期：route-not-found。  
采用项目既有 error envelope/identity dependency；Pydantic 必须在服务前拒绝 raw prompt-like input。BDD/证据文档记录验收 case、命令、合成数据边界和 no-send 保证。

- [ ] **步骤 4：API/PG 回归**

运行：`python -m pytest -q tests/unit/test_stage08_runtime_api.py tests/integration/test_stage08_runtime_postgres.py`  
预期：PASS。

### Task 6：隔离真实 Provider 评测器

**Files：** 修改 `backend/scripts/stage06_live_llm_skill_quality_eval.py`、`backend/tests/unit/test_stage06_live_llm_skill_quality_eval.py`、`project-docs/08-implementation/evidence/stage06-live-llm-skill-quality-2026-07-16.md`。

**Produces：** `run_case_isolated(case, timeout_seconds) -> RedactedCaseResult` 和 `run_batch(cases, max_parallelism, timeout_seconds) -> RedactedBatchResult`。

- [ ] **步骤 1：写失败隔离测试**

```python
def test_timed_out_case_has_static_label_without_raw_content(monkeypatch):
    result = run_case_isolated(case, timeout_seconds=1)
    assert result.failure_labels == ("case_timeout",)
    assert "prompt" not in result.model_dump_json()

def test_batch_continues_after_one_timeout(monkeypatch):
    assert run_batch((slow_case, passing_case), max_parallelism=2,
                     timeout_seconds=1).case_count == 2
```

- [ ] **步骤 2：确认失败；步骤 3：实现进程级隔离**

运行：`python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "timeout or batch"`  
预期：导入或断言失败。  
每个 case 使用子进程硬超时；子进程内部可处理原始 provider 输出，但对外只传固定 allowlist 的布尔、计数、状态和静态错误标签。默认并发最多 2；保留 Telegram dry-run/provider-write disabled；`finally` 清理临时结果。

- [ ] **步骤 4：测试与证据更新**

运行：`python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py`  
预期：PASS。  
证据只记录旧串行批次是否被中断/超时、新超时合同及“未保留原始输出”。本任务不得触发新的 Provider 调用，除非另获明确执行授权。

## 计划自检

- 覆盖范围：Package A 实现 Tool Gateway、预算、execution ticket、policy、audit、幂等和 Provider 评测隔离；Memory、群持久化、检索和协调器属于路线图 B-F，不在本包抢先实现。
- 完整性：每个任务都有精确文件、接口、红灯测试、命令和预期结果。
- 类型一致性：`ExecutionBudget`、`ExecutionPlan`、`ToolInvocation`、`RedactedToolResult`、`Stage08ExecutionTicket` 与 gateway 在使用前已定义。
- 范围检查：本包不创建 Memory/vector chunk/Milvus、直接 Telegram 发送或自治 Agent loop。
