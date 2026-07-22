# Stage08 Package E：LangGraph 协作 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for one fresh implementer and one independent review per task. Steps use checkbox syntax for tracking.

**Goal:** 在不调用真实 Provider、不过度持久化私有上下文、也不改变 A-D 真源的前提下，交付可并行读取、可降级、可取消、可审计并能受控创建草稿的 LangGraph 多数字员工协作层。

**Architecture:** `Stage08CollaborationCoordinator` 使用 LangGraph `StateGraph` 管理 process-local private state。它通过既有 C3 和 D4 读取受控材料，利用可注入的 unavailable/deterministic provider ports 进行压缩与分析，随后由 Policy Gate 决定是否复用既有 Stage08 ticket/Tool Gateway 创建 `pending_confirmation` 草稿。`AgentRun` 和 audit 只记录安全摘要。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、LangGraph、SQLAlchemy 2.x、Alembic（本包不新增 migration）、PostgreSQL/pgvector、pytest。

## 全局约束

- Package D 已关闭；只使用 D0 loopback/disposable pgvector 作为 RAG 组合 PostgreSQL 证据，不能回退 native/default 数据库。
- `checkpointer=None`；query、C3 group text/digest、D4 private evidence、Memory payload、raw prompt/response、UUID/field/score/vector/authority/provider error 不得进入 checkpoint、Redis、DB、AgentRun、audit、outbox、log 或 API DTO。
- 不改 models、migrations、Stage06 UoW/interfaces、全局 role matrix、Telegram、Docker/configuration、Milvus 或真实 Provider。真实模型仅 Package F。
- 只复用 `build_context_plan`、C3 composition、D4 authority/provider、Stage08 Tool Gateway、ticket/idempotency/audit 和 draft service；Coordinator 不直连 ORM/SQL。
- 所有 read/draft 路径都要在消费期重验成员、employee、view/field、record relation、group binding 和 source lifecycle；不确定即 fail closed。
- 共享 worktree 已脏：不得 stage、commit、reset、checkout、clean、push 或改动本计划以外文件。每任务更新自身报告，不宣布 Package E 完成。

---

## 文件责任图

| 文件 | 职责 |
| --- | --- |
| `backend/app/runtime/stage08_collaboration_contracts.py` | 私有 command/budget/analysis/safe view 的严格类型、固定状态和 redaction validator |
| `backend/app/agents/stage08_collaboration.py` | LangGraph topology、fan-out/fan-in、node boundary 与 private state reducer |
| `backend/app/services/stage08_collaboration.py` | 服务端 command 派生、C3/D4 adapter、provider ports、policy/draft、idempotency、AgentRun/audit |
| `backend/app/services/stage08_context_composition.py` | 仅增加 E 可调用的 opaque group-compression handoff；不暴露群正文或 private authority |
| `backend/app/schemas/stage08_collaboration.py` | strict assistant query request/response JSON schema |
| `backend/app/api/routes/stage08_collaboration.py` | redacted `POST /api/stage08/assistant/query` route、identity 与 commit/rollback mapping |
| `backend/app/main.py` | 注册唯一 E router |
| `backend/tests/unit/test_stage08_collaboration_contracts.py` | strict state/DTO/private carrier/forged input corpus |
| `backend/tests/unit/test_stage08_collaboration_graph.py` | topology、parallel reads、budget/cancel/degrade/private checkpoint corpus |
| `backend/tests/unit/test_stage08_collaboration_service.py` | policy-before-draft、idempotency、AgentRun/audit/outbox redaction、provider unavailable corpus |
| `backend/tests/api/test_stage08_collaboration_api.py` | API identity/role/body/response/redaction/idempotency corpus |
| `backend/tests/integration/test_stage08_collaboration_postgres.py` | disposable pgvector PostgreSQL current-state/cancel/transaction/cleanup evidence |
| `project-docs/08-implementation/evidence/stage08-package-e-collaboration.md` | Package E evidence ledger |

## Task E1：私有协作合同、Provider 端口和无 checkpoint 图骨架

**Files:**

- Create: `backend/app/runtime/stage08_collaboration_contracts.py`
- Create: `backend/app/agents/stage08_collaboration.py`
- Create: `backend/tests/unit/test_stage08_collaboration_contracts.py`
- Create: `backend/tests/unit/test_stage08_collaboration_graph.py`
- Create: `.superpowers/sdd/stage08-package-e-task-e1-report.md`

**Consumes:** `ContextIntent`、C3/D4 opaque result design、既有 `ExecutionTicketState`；不消费数据库或外部 Provider。

**Produces:** `AssistantRequestedAction`、`AssistantQueryCommand`、`CollaborationBudget`、`AnalysisDecision`、`AssistantQuerySafeView`、`UnavailableContextCompressor`、`UnavailableAnalysisProvider`、`build_stage08_collaboration_graph(nodes)`；E2-E4 只通过这些类型连接。

- [ ] **Step 1：先写 RED 合同与 graph topology 测试**

```python
def test_private_command_and_state_cannot_be_json_or_pickle_serialized() -> None:
    command = _server_command(query="预算是什么")
    with pytest.raises(TypeError):
        pickle.dumps(command)
    assert "预算是什么" not in repr(command)

def test_graph_has_no_checkpointer_and_only_allowed_nodes() -> None:
    graph = build_stage08_collaboration_graph(_fake_nodes())
    assert graph.checkpointer is None
    assert _node_names(graph) == {
        "plan_request", "read_composite_context", "read_retrieval",
        "mark_general_advice", "fan_in", "compress_group_context",
        "analyse", "policy_gate", "materialize_draft", "finalize",
    }
```

- [ ] **Step 2：运行 RED**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

Expected: import/contract failure，因为 E1 files 不存在。

- [ ] **Step 3：实现严格 contract 与 topology**

实现下列最小接口，不引入数据库模型：

```python
class CollaborationBudget(BaseModel):
    max_graph_depth: StrictInt = Field(default=3, ge=1, le=3)
    max_parallel_reads: StrictInt = Field(default=3, ge=1, le=3)
    max_retrieval_chunks: StrictInt = Field(default=12, ge=0, le=12)
    max_wall_time_ms: StrictInt = Field(default=30_000, ge=100, le=30_000)
    max_provider_time_ms: StrictInt = Field(default=20_000, ge=100, le=20_000)
    max_retries: StrictInt = Field(default=2, ge=0, le=2)

class ContextCompressor(Protocol):
    def compress(self, material: object, *, budget: CollaborationBudget) -> object:
        pass

class AnalysisProvider(Protocol):
    def analyse(self, material: object, command: object, *, budget: CollaborationBudget) -> AnalysisDecision:
        pass

def build_stage08_collaboration_graph(nodes: Stage08CollaborationNodes) -> Any:
    """Compile the fixed E topology with checkpointer=None."""
```

`AssistantQueryCommand`、私有 state/material 与 private port input 必须 opaque、slots-only、`repr` redacted、pickle/JSON 不可用；public `AssistantQuerySafeView` 要用 frozen Pydantic 重建来拒绝 `model_construct` 夹带字段。图条件边只允许既定状态机，编译时明确 `checkpointer=None`。

- [ ] **Step 4：运行 GREEN 和静态边界**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
```

Expected: private carrier/forged model/topology/budget/terminal tests all pass；没有 `requests`、`httpx`、OpenRouter、Telegram、Redis、Milvus import。

- [ ] **Step 5：写 E1 报告并独立复审**

报告写 RED/GREEN、没有数据库/Provider 调用、`checkpointer=None`、static privacy scan；独立审查必须确认 Coordinator 节点没有 ORM/Tool Gateway/Provider key 直接依赖。

## Task E2：C3/D4 并行读取、短暂群压缩与受控降级

**Files:**

- Modify: `backend/app/agents/stage08_collaboration.py`
- Create: `backend/app/services/stage08_collaboration.py`
- Modify: `backend/app/services/stage08_context_composition.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_graph.py`
- Create: `backend/tests/unit/test_stage08_collaboration_service.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Create: `.superpowers/sdd/stage08-package-e-task-e2-report.md`

**Consumes:** E1 contract；C3 `compose_stage08_context`/private render boundary；D4 `Stage08RetrievalAuthorityFactory`、`PostgresRetrievalProvider`、private evidence/safe citations。

**Produces:** `execute_collaboration_reads(uow, command, actor, deps, now)`，返回 private aggregate + safe omission/degradation metadata；E3 仅消费 aggregate。

- [ ] **Step 1：编写 fan-out、current-state、压缩 RED 用例**

```python
def test_reads_fan_out_within_three_child_budget_and_fan_in_stable_order() -> None:
    outcome = execute_collaboration_reads(_uow(), _command(), _actor(), _barrier_deps(), NOW)
    assert outcome.safe_view.read_child_count == 3
    assert outcome.safe_view.degradation_codes == ()

def test_revoked_member_or_source_after_plan_drops_only_that_material() -> None:
    outcome = _held_plan_then_revoke_member_or_source()
    assert outcome.private_material is None or outcome.safe_view.status != "internal_evidence"
    assert "private text" not in repr(outcome)

def test_pending_group_context_never_persists_digest_when_compressor_unavailable() -> None:
    outcome = execute_collaboration_reads(
        _uow(), _command(), _actor(), _unavailable_compressor_deps(), NOW
    )
    assert outcome.safe_view.group_status == "compression_unavailable"
    assert _all_persistent_sinks_are_empty()
```

- [ ] **Step 2：运行 RED**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

Expected: `execute_collaboration_reads`/opaque compression handoff missing。

- [ ] **Step 3：实现受控读取与 compression handoff**

服务层只从 command 派生 actor/employee 的前 3 个稳定可访问 view；调用 C1 plan、C3 composition、D4 factory/search/`render_private_evidence`，并在每个 consumer 时使用已有 current-state validator。使用 LangGraph `Send` 或等价明确 fan-out reducer，读子图最大 3。

在 `stage08_context_composition.py` 增加**内部** opaque handoff：它只在 `group_compression_pending` 且调用者来自 E private port 时 materialize 当前 group projection，并在同一次调用把 compressor 结果重新校验为 bounded digest；任何异常/timeout/shape drift 返回 no-group degradation。E 选择并调用 compressor；C3 不保存 digest、不暴露 raw fragment、也不修改 C3 public safe view 合同。

`UnavailableContextCompressor` 不网络调用，返回固定 unavailable；partial read failure 保留其余合法材料，只有无材料时才按 command 的 `allow_general_advice` 降级。禁止将任何 private result 放入 graph public state、日志或持久化。

- [ ] **Step 4：运行 GREEN、C3/D4 回归与专用 pgvector**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
```

Expected: fan-out budget、held revoke、source/chunk/Memory drift、compression unavailable、no persistence、D4 safe citation 和 keyword-only regression all pass。

- [ ] **Step 5：写 E2 报告并独立复审**

独立审查必须检查 C3 raw group material/digest 没有离开 process-local handoff，D4 private evidence 没有进入 safe state，且没有真实 Provider/HTTP/Telegram 调用。

## Task E3：分析、Policy Gate 与既有 ticket/draft 路由

**Files:**

- Modify: `backend/app/services/stage08_collaboration.py`
- Modify: `backend/app/agents/stage08_collaboration.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_service.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_graph.py`
- Create: `backend/tests/integration/test_stage08_collaboration_postgres.py`
- Create: `.superpowers/sdd/stage08-package-e-task-e3-report.md`

**Consumes:** E1-E2 private aggregate、existing `begin_execution_plan`、`Stage08ToolGateway`、`RecordChangeDraft`、Stage06 idempotency/audit。

**Produces:** `run_stage08_collaboration(uow, command, actor, deps, now) -> AssistantQuerySafeView`，并且仅在 pass policy 的 `draft_update` 下创建现有 ticket 和 pending draft。

- [ ] **Step 1：先写分析/草稿 RED corpus**

```python
def test_analysis_provider_cannot_cite_ordinal_not_in_current_safe_material() -> None:
    result = run_stage08_collaboration(
        _uow(), _command(), _actor(), _decision_with_unknown_citation_deps(), NOW
    )
    assert result.status == "denied"
    assert result.draft_id is None

def test_draft_is_created_only_after_policy_rereads_current_scope() -> None:
    result = _plan_then_revoke_target_record_or_employee_grant()
    assert result.status in {"denied", "failed"}
    assert _draft_count() == 0
    assert _orphan_ticket_count() == 0

def test_unavailable_analysis_is_safe_degraded_and_never_calls_network() -> None:
    result = run_stage08_collaboration(
        _uow(), _command(), _actor(), _unavailable_analysis_deps(), NOW
    )
    assert result.status == "degraded"
    assert _network_calls == 0
```

- [ ] **Step 2：运行 RED**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

Expected: `run_stage08_collaboration`/Policy Gate missing。

- [ ] **Step 3：实现 analyse、policy 和 draft**

`AnalysisProvider` 的结果只可包含 answer、已存在 safe ordinal、requested action 和受限 draft intent。服务验证 ordinals、answer size、action；不可用/invalid/timeout 映射固定 `degraded/failed`，不存 raw answer。

`PolicyGate` 在 action 前重新计算 active member、employee、target record/view/field、business/source lifecycle、预算与 idempotency。只允许 `draft_update` 通过现有 `ExecutionPlan` 生成一个 `record_change_draft.create` invocation，调用 `begin_execution_plan` 后再经 `Stage08ToolGateway`；其结果必须是既有 `pending_confirmation` draft。禁止 direct ORM record write、draft confirm、Telegram send 或 provider call。取消、deny、异常要回滚刚创建的 reservation/ticket，保持无 orphan。

为每个 terminal run 使用 `uow.add_agent_run` 和 `record_audit_event` 写入白名单 summary；摘要只含 graph/status/count/code/action/ticket-or-draft-presence/hash trace/latency，不能含 query/answer/private materials/UUID/field/provider response。

- [ ] **Step 4：运行 GREEN 与 PostgreSQL transaction evidence**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

Expected: malformed provider、unknown citation、policy revoke、cancel、budget exceed、same/different idempotency、draft pending、audit redaction、rollback cleanup 都 pass。

- [ ] **Step 5：写 E3 报告并独立复审**

复审要证明 Analyst/Draft 没有 tool/ORM bypass，Policy Gate 发生在 draft 前，所有 write 都通过既有 ticket/idempotency/audit，且无外部系统调用。

## Task E4：Assistant Query API、Package E PostgreSQL 证据与包级复审

**Files:**

- Create: `backend/app/schemas/stage08_collaboration.py`
- Create: `backend/app/api/routes/stage08_collaboration.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/stage08_collaboration.py`
- Create: `backend/tests/api/test_stage08_collaboration_api.py`
- Modify: `backend/tests/integration/test_stage08_collaboration_postgres.py`
- Create: `project-docs/08-implementation/evidence/stage08-package-e-collaboration.md`
- Create: `.superpowers/sdd/stage08-package-e-task-e4-report.md`
- Create: `.superpowers/sdd/stage08-package-e-final-review-report.md`

**Consumes:** E1-E3 `run_stage08_collaboration` and safe view；existing Stage06 identity/authorization/UoW transaction patterns。

**Produces:** strict `POST /api/stage08/assistant/query` plus final E evidence; no other public API.

- [ ] **Step 1：先写 API 与完整 Package E RED tests**

```python
def test_assistant_query_rejects_client_scope_provider_budget_tool_and_draft_values(client) -> None:
    response = client.post(PATH, json={**_valid_body(), "scope": {"workspace_id": "x"}})
    assert response.status_code == 422
    assert "workspace_id" not in response.text

def test_assistant_query_active_member_gets_safe_response_and_idempotent_replay(client) -> None:
    first = client.post(PATH, json=_valid_body(), headers=_identity_headers())
    replay = client.post(PATH, json=_valid_body(), headers=_identity_headers())
    assert set(first.json()) <= {"status", "answer", "citations", "degradation_codes", "draft_id"}
    assert replay.json() == first.json()
```

- [ ] **Step 2：运行 RED**

Run:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/api/test_stage08_collaboration_api.py
```

Expected: route/schema missing。

- [ ] **Step 3：实现窄 API 和安全错误映射**

使用同类 Stage08 route 的 `APIRoute` validation wrapper、verified identity、`digital_employee.invoke` authorization、commit/rollback。Pydantic request 仅声明 contract 字段，`query` 仅在 request 生命周期传入 service，API 不把 exception input 回显。响应使用 `AssistantQuerySafeView` 重建，idempotency replay 在返回前重验当前 member/employee/target 可读性。

注册 router 后不新增 GET/list、管理 API、Provider 配置或 webhook。错误映射固定：invalid 422、member/employee scope 403、not found 404、idempotency/run conflict 409、provider/read failure 安全 terminal response；任何异常不泄露 private carrier。

- [ ] **Step 4：执行完整 Package E evidence**

Run from `backend`:

```powershell
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py tests/api/test_stage08_collaboration_api.py tests/integration/test_stage08_collaboration_postgres.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_tool_gateway.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py app/schemas/stage08_collaboration.py app/api/routes/stage08_collaboration.py
```

同时记录 dedicated pgvector extension/head、AgentRun/audit/ticket/draft/idempotency/source/chunk/outbox cleanup、`checkpointer=None`、raw/private/provider/network/Milvus/Telegram/static scan 和 `git diff --check`。无 DSN 时 skip 不能计为通过。

- [ ] **Step 5：写 E4 evidence 并做 fresh Package E independent review**

报告以中文记录 API matrix、graph matrix、PostgreSQL evidence、无外部调用、cleanup、跳过项和风险。独立复审需达到 `0 Critical / 0 Important` 才能建议 root 更新 Stage08 source/plan/acceptance 并交接 Package F；不能把 real Provider/production/UI 宣称为完成。

## Plan Self-Review

- **Spec coverage：** E1 实现私有 state/topology；E2 实现 C3/D4 fan-out 和压缩降级；E3 实现 analysis/policy/draft/ticket；E4 实现 strict API、数据库证据和包级复审。覆盖 E-B01 至 E-B06 与 E-01 至 E-05。
- **No-placeholder scan：** 每项都有精确文件、接口、RED/GREEN 命令和验收边界；不存在未填充标记或“以后实现”步骤。
- **Type consistency：** E1 是唯一 contract producer；E2 只消费 private command/ports；E3 只消费 E2 aggregate 并复用既有 ticket gateway；E4 只暴露 E1 safe view。没有以 API JSON 代替 opaque authority。

## Execution Handoff

以用户已确认的 Stage08 协作方向为基础，按 E1→E4 顺序执行；每任务均需要 fresh implementer + independent reviewer。任何 schema/API/permission 变更超出本计划、真实 Provider、Telegram/外部写入、Milvus 或生产部署都必须先暂停并取得新的明确授权。
