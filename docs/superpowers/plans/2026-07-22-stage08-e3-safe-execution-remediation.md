# Stage08 E3 安全执行适配层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for one fresh implementer and one independent review per task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 E3 首轮复审发现的审计泄露、非原子执行、幂等 replay 和空草稿问题，并使“分析 → Policy Gate → `pending_confirmation` 草稿”在真实 PostgreSQL 上可证明安全。

**Architecture:** 在已有 `ExecutionPlan`、`begin_execution_plan`、`Stage08ToolGateway` 与 `RecordChangeDraft` 外围建立仅服务端可构造的 `stage08_e3_safe` 执行模式。该模式将 current-state locks、savepoint、revalidation、ticket/idempotency、Gateway、草稿和安全 terminal summary 放入同一边界；默认 Stage06/Stage08 行为不变。draft intent 仍为不可序列化的 process-local sealed carrier，但可承载一条需二次验证的字段和值。

**Tech Stack:** Python 3.12、Pydantic v2、SQLAlchemy 2.x、PostgreSQL 17/pgvector disposable loopback、pytest、LangGraph（仍 `checkpointer=None`）。

## Global Constraints

- Execution update (2026-07-22): 用户要求以阶段功能完成度为主，避免无意义确认、重复验证和纯假设极端情形。R1 仍独立收口；R2/R3 合并为一个连续实现包和一次独立收口复审。保留的验证仅限首轮复审已复现的 transaction rollback、scope revoke、idempotency replay、全 trace 脱敏，以及主成功路径的真实 PostgreSQL 证据。
- 用户于 2026-07-22 已确认 `STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`；它与 `STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`、BDD、TDR-016 共同构成此次修复真源。
- 不新增公开 API、migration/schema、全局 role/permission 模型、真实 Provider、Telegram、部署、直接 record 写入或草稿确认。
- 只有 E3 服务端可启用 `stage08_e3_safe`；客户端、LLM、API body、checkpoint、Redis、DB JSON、log 和 DTO 均不能传入或重建安全模式、private intent 或 authority。
- query、answer、C3/D4 material、provider response、field key/value、record/draft/ticket UUID 不得进入本 E3 trace 的 `AgentRun`、audit、tool summary、outbox、log 或 API-safe DTO。
- 业务表及草稿/ticket 主键、外键仍由 PostgreSQL 保存；限制的是 E3 观测/摘要载体，不是破坏业务实体标识。
- 不 stage、commit、reset、checkout、clean、push；共享 worktree 为 dirty-safe。

---

### Task R1: 私有安全模式、受控 draft intent 与安全审计端口

**Files:**

- Modify: `backend/app/runtime/stage08_collaboration_contracts.py`
- Modify: `backend/app/runtime/stage08_contracts.py`
- Modify: `backend/app/services/stage08_runtime.py`
- Modify: `backend/app/runtime/stage08_tool_gateway.py`
- Modify: `backend/app/services/stage06_digital_employees.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_contracts.py`
- Modify: `backend/tests/unit/test_stage08_tool_gateway.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_service.py`
- Create: `.superpowers/sdd/stage08-package-e-task-e3-r1-report.md`

**Consumes:** E1 sealed carrier factory、existing `ExecutionPlan`/`ToolInvocation`、existing Stage06 draft service.

**Produces:** server-only `Stage08SafeExecutionMode` / invocation context, one-field sealed `DraftIntent`, safe ticket/Gateway/draft-service audit plumbing. Normal callers keep their current audit and tool behavior.

- [ ] **Step 1: 写 RED 合同测试**

```python
def test_e3_draft_intent_is_nonserializable_and_carries_exactly_one_json_safe_field_value() -> None:
    intent = Stage08CollaborationContractFactory.draft_intent(
        field_key="next_action", value="安排演示"
    )
    assert _private_intent_payload(intent) == ("next_action", "安排演示")
    with pytest.raises(TypeError):
        pickle.dumps(intent)

def test_safe_execution_mode_cannot_be_supplied_by_plan_or_tool_json() -> None:
    with pytest.raises(ValidationError):
        ExecutionPlan.model_validate({**_plan_json(), "safe_execution_mode": "stage08_e3_safe"})
```

- [ ] **Step 2: 运行 RED**

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_collaboration_service.py -k "draft_intent or safe_execution"
```

Expected: FAIL because the private field/value carrier and internal-only execution context do not exist.

- [ ] **Step 3: 实现最小私有合同与审计模式**

```python
@dataclass(frozen=True, slots=True)
class Stage08SafeExecutionContext:
    trace_hash: str
    mode: Literal["stage08_e3_safe"]

def begin_execution_plan(
    uow: Stage06PlatformUnitOfWork,
    plan: ExecutionPlan,
    *,
    safe_context: Stage08SafeExecutionContext | None = None,
) -> Stage08ExecutionTicket: ...

def execute(
    self, uow, ticket, invocation, *, safe_context: Stage08SafeExecutionContext | None = None
) -> RedactedToolResult: ...
```

The context must be a sealed/factory-issued Python object, not a Pydantic field. In safe mode, ticket-created/transition audit, Tool Gateway result summary and Stage06 `invoke_digital_employee` draft audit/AgentRun use a shared helper which emits only the contract whitelist and never writes entity ids or field/value. `RecordChangeDraft.trace_id` receives the hash-only trace supplied by E3. Outside safe mode existing payloads must remain byte-for-byte behaviorally compatible.

- [ ] **Step 4: 写 GREEN 覆盖**

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_service.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/runtime/stage08_contracts.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/services/stage06_digital_employees.py
```

Expected: default Runtime regressions and safe-mode scans pass; a complete safe-mode trace contains no query/answer/UUID/field/value in any summary.

- [ ] **Step 5: 写报告**

Report exact RED/GREEN counts, default-mode compatibility evidence, rejected forged mode/intent corpus and confirmation that no network/Telegram/Provider was called.

### Task R2: 原子执行边界、current-state 锁与 replay

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/services/stage08_collaboration.py`
- Modify: `backend/app/services/stage08_runtime.py`
- Modify: `backend/app/runtime/stage08_tool_gateway.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_service.py`
- Create: `backend/tests/integration/test_stage08_collaboration_postgres.py`
- Create: `.superpowers/sdd/stage08-package-e-task-e3-r2-report.md`

**Consumes:** R1 safe context; existing workspace/member/employee/group lifecycle locks; E2 `_build_current_plan` and current scope proof.

**Produces:** `run_stage08_collaboration` uses an explicit safe execution boundary and returns a stable safe view for same-key replay.

- [ ] **Step 1: 写 RED 服务与 PostgreSQL案例**

```python
def test_gateway_exception_rolls_back_ticket_idempotency_draft_and_internal_audit() -> None:
    result = _run_with_gateway_exception()
    assert result.status == "failed"
    assert _e3_side_effect_counts() == {"tickets": 0, "idempotency": 0, "drafts": 0, "audits": 1}

def test_same_key_revalidates_then_replays_same_pending_draft() -> None:
    first = _run_valid_draft(key="k")
    replay = _run_valid_draft(key="k")
    assert replay == first

def test_revocation_after_scope_lock_before_gateway_is_denied_without_side_effect() -> None:
    assert _held_execution_then_revoke("mapping").status == "denied"
    assert _counts_after_commit() == {"tickets": 0, "drafts": 0, "idempotency": 0}
```

The PostgreSQL file must construct real `SqlAlchemyStage06PlatformUnitOfWork` fixtures and contain tests for successful pending draft, same-key replay, different-key behavior, Gateway exception rollback, cancel/timeout rollback, record/source/member/employee revoke and two-session `pg_blocking_pids` evidence for the shared lock.

- [ ] **Step 2: 运行 RED**

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k "rollback or replay or revoke"
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

Expected: at least one service case and the real transaction cases fail before the boundary exists; no test may be only `SELECT 1`.

- [ ] **Step 3: 实现边界和锁顺序**

```python
with begin_stage08_e3_safe_execution(
    uow,
    workspace_id=command.workspace_id,
    employee_id=command.employee_id,
    actor_user_id=command.actor_user_id,
    target_record_id=command.target_record_id,
) as boundary:
    scope = boundary.lock_and_revalidate(command, actor, intent)
    ticket_or_replay = boundary.begin_or_replay(plan)
    result = gateway.execute(..., safe_context=boundary.safe_context)
    boundary.complete_pending_draft(result)
```

The UoW contract must have matching InMemory rollback and SQLAlchemy `session.begin_nested()` behavior. Lock order is workspace → workspace member → employee → target record → group binding/mapping → projections/source rows → ticket. Lifecycle writers that can invalidate a consumed row must already acquire the same row lock; if an object cannot be locked/re-read it is a denial. On exception, cancel or timeout the boundary rolls back all E3 transient persistence and adds only one safe terminal summary outside the rolled-back side effect set.

- [ ] **Step 4: 跑 GREEN 与真实 PostgreSQL**

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

Expected: exact focused pass count reported; integration proves real UoW, savepoint rollback, replay, current-state denial and `pg_blocking_pids`, with no skipped core E3 case.

- [ ] **Step 5: 写报告**

Record data cleanup counts, lock evidence, test database provenance without printing credentials, and assert no Provider/Telegram/network/deployment calls.

### Task R3: E3 graph integration、全链路脱敏与独立复审

**Files:**

- Modify: `backend/app/agents/stage08_collaboration.py`
- Modify: `backend/app/services/stage08_collaboration.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_graph.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_service.py`
- Modify: `backend/tests/integration/test_stage08_collaboration_postgres.py`
- Modify: `.superpowers/sdd/stage08-package-e-task-e3-report.md`
- Create: `.superpowers/sdd/stage08-package-e-task-e3-r3-report.md`

**Consumes:** R1/R2 boundaries; existing fixed ten-node, no-checkpoint E1 graph.

**Produces:** correct `analysing → policy_gate → materialize_draft → finalize` execution and a fresh E3 evidence package.

- [ ] **Step 1: 写 RED graph/trace 扫描**

```python
def test_full_safe_execution_trace_has_no_forbidden_value_in_any_persistent_projection() -> None:
    view, persisted = _run_real_safe_draft_trace()
    assert view.status == "draft_pending"
    assert _forbidden_trace_values_not_present(persisted)

def test_unavailable_analysis_is_degraded_without_gateway_or_network() -> None:
    view = _run_unavailable_provider()
    assert view.status == "degraded"
    assert _gateway_calls == _network_calls == 0
```

- [ ] **Step 2: 实现终态映射**

The graph must retain `checkpointer=None`, no new public state and the existing node names. `unavailable` analysis maps to `degraded`; malformed/forged output maps to fixed `failed`; policy deny maps to `denied`; cancellation/timeout map to their matching terminal status. A draft is materialized only if the R2 boundary returns an authenticated pending draft. `latency_ms` must use measured monotonic elapsed time rather than a constant.

- [ ] **Step 3: 运行全 E3 验证**

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py tests/integration/test_stage08_collaboration_postgres.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/runtime/stage08_contracts.py app/services/stage08_collaboration.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/services/stage06_digital_employees.py app/services/stage06_platform.py app/agents/stage08_collaboration.py
```

- [ ] **Step 4: 独立复审门禁**

Reviewer must inspect the entire trace, not merely the last audit row; report separate spec-compliance and code-quality verdicts. E3 is not closed unless both pass with no open Critical/Important finding. Package E/E4, Package F, real LLM and deployment remain pending after this task.

## Plan Self-Review

- Coverage: R1 addresses C3/I4; R2 addresses C1/C2/I1/I2; R3 addresses I3/M1, graph integration and trace-wide redaction.
- No scope expansion: no endpoint/migration/real Provider/Telegram/deployment task appears.
- Evidence: every prior failed audit item has a RED case, GREEN command and an explicit local PostgreSQL acceptance requirement.
