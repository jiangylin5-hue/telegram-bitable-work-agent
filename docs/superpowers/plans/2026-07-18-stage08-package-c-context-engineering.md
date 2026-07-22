# Stage08 Package C Context Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不增加持久化、API、权限或外部调用的前提下，先交付 C1 的类型化、可解释、可重读且确定性受限的表格/Memory/通用建议上下文内核，再通过独立 C2 合同门禁处理群窗口与历史。

**Architecture:** C1 新增一个纯合同模块和一个纯内部 service。service 只复用 Stage06 的 employee/member/view/record 授权读取与 Stage08 B2/B4 的 Memory 安全读取，不读取 `Message`，不调用 Tool Gateway adapter、Provider、Telegram、RAG 或 LangGraph。`ContextPlan` 冻结选择与上限但不是读取能力；compose 时重算 authority、relation、source version 和字段可见性，最后生成不持久化的 typed evidence pack。

**Tech Stack:** Python 3.12+、Pydantic v2、既有 FastAPI 项目 service/UoW（C1 不新增 route）、SQLAlchemy 2.x/PostgreSQL（只做现有模型的集成验证）、pytest。

## Global Constraints

- 只创建/修改本计划列出的 C1 文件；不修改 migration、API router、permission matrix、Telegram ingestion/Message、Provider/LLM/RAG/LangGraph、Redis 或前端。
- C1 不 import 或查询 `app.models.telegram.Message`，不读取 `raw_text`、`raw_caption`、`normalized_text`，不创建 group-window/history fallback。
- 复用 `ExecutionBudget` 的全局硬上限语义，但 C1 使用单独的严格 `ContextBudget`；不得放宽 Package A 的 `max_retrieval_chunks=0`。
- 复用 `is_member_eligible_for_employee`、`list_view_records`、`get_view_presentation`、`read_record_for_actor`、`read_memory_projection` 与既有 UoW；不得直接读 record JSONB 绕过安全投影来生成 evidence。
- `B5` 仍为 Package B closure risk；它不阻塞 C1 task-level TDD，但 C1 不得宣称 Package B/C/Stage08 accepted。
- 不执行真实 Provider、Telegram、network 或外部写入；不进行 git stage/commit/reset/checkout/clean。
- C2 群窗口/历史必须先写独立 contract 并获确认；C1 遇到任何 group source 一律不选择。

---

## File Map

| 操作 | 文件 | 单一责任 |
| --- | --- | --- |
| Create | `backend/app/runtime/stage08_context_contracts.py` | C1 strict DTO、enum、label/type/version/scope 配对、budget 上限 |
| Create | `backend/app/services/stage08_context.py` | authority/关系 resolver、planner、table/Memory composer、budget/truncation、renderer |
| Create | `backend/tests/unit/test_stage08_context_contracts.py` | DTO、model_construct 防御、label/type、预算与 raw/group key 拒绝 |
| Create | `backend/tests/unit/test_stage08_context_service.py` | source decision corpus、关系、compose、重读、截断、general advice、no side effect |
| Create | `backend/tests/integration/test_stage08_context_postgres.py` | 真实 local PG 的 relation/field/record/Memory 撤权与版本漂移证据 |
| Create | `project-docs/08-implementation/evidence/stage08-package-c-context.md` | 实施时记录 RED/GREEN、命令、测试数、local PG、外部边界、清理 |
| Create | `.superpowers/sdd/stage08-package-c-task-c1-report.md` | C1 changed files、verification、skips、risks、cleanup |

不修改 `backend/app/main.py`，这是“C1 无 API”的可检查边界。

### Task 1: C1 strict context contracts

**Files:**

- Create: `backend/app/runtime/stage08_context_contracts.py`
- Create: `backend/tests/unit/test_stage08_context_contracts.py`

**Interfaces:**

- Produces: `ContextPlanningRequest`, `ContextBudget`, `ContextPlan`, `ContextSourcePlan`, `ResolvedBusinessScope`, `EvidenceScope`, `EvidenceVersion`, `EvidenceItem`, `ContextBudgetUsage`, `ContextOmission`, `ContextPack`。
- Stable literals:
  - `ContextIntent = Literal["business_fact", "memory_lookup", "mixed", "general_advice"]`
  - `ContextSourceKind = Literal["table_view", "business_memory", "general_advice"]`
  - `EvidenceLabel = Literal["business_data", "confirmed_memory", "retrieved_material", "analysis_from_current_material", "general_advice"]`
  - C1 source/type mapping only: `platform_record -> business_data`、`memory_item -> confirmed_memory`、`policy_marker -> general_advice`。
- All models use `ConfigDict(extra="forbid", strict=True, frozen=True)` unless a mutable local accumulator is strictly internal and not exported.

- [ ] **Step 1: Write RED contract tests**

```python
def test_context_budget_enforces_c1_hard_limits():
    with pytest.raises(ValidationError):
        ContextBudget(
            max_table_records=21,
            max_memory_items=12,
            max_evidence_items=24,
            max_item_chars=2000,
            max_total_chars=12000,
        )

def test_context_request_rejects_raw_group_and_retrieval_inputs():
    base = _request_dict()
    for forbidden in ("prompt", "raw_text", "group_chat_ref", "message_ids", "retrieval_query"):
        with pytest.raises(ValidationError):
            ContextPlanningRequest.model_validate({**base, forbidden: "secret"})

def test_evidence_label_type_scope_and_version_must_match():
    with pytest.raises(ValidationError, match="context_evidence_label_mismatch"):
        _evidence(source_type="memory_item", label="business_data")
    with pytest.raises(ValidationError):
        _evidence(scope={"workspace_id": str(uuid4()), "group_chat_ref": "x"})
```

- [ ] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: collection FAIL because `app.runtime.stage08_context_contracts` does not exist.

- [ ] **Step 3: Implement the exact C1 model bounds**

Required shapes:

```python
class ContextBudget(BaseModel):
    max_table_records: StrictInt = Field(ge=0, le=20)
    max_memory_items: StrictInt = Field(ge=0, le=12)
    max_evidence_items: StrictInt = Field(ge=1, le=24)
    max_item_chars: StrictInt = Field(ge=128, le=2000)
    max_total_chars: StrictInt = Field(ge=256, le=12000)

class ContextPlanningRequest(BaseModel):
    workspace_id: UUID
    employee_id: UUID
    intent: ContextIntent
    view_ids: tuple[UUID, ...] = ()
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None
    allow_general_advice: StrictBool
    budget: ContextBudget

class ContextSourcePlan(BaseModel):
    source_kind: ContextSourceKind
    priority: StrictInt = Field(ge=1, le=3)
    view_id: UUID | None = None
    source_version: StrictInt | None = Field(default=None, ge=1)
    max_items: StrictInt = Field(ge=0, le=20)
    reason_code: Literal[
        "business_fact_requested", "memory_requested", "general_advice_requested",
        "general_advice_fallback_allowed"
    ]
```

`ContextPlanningRequest` validator requirements:

- at most 3 unique `view_ids`;
- `business_fact`/`mixed` require at least one view；`general_advice` requires no view/customer/project；
- `memory_lookup` cannot set table-only options；
- no actor, ticket, source refs, raw text, group or retrieval fields exist in the model.

`EvidenceScope` only contains workspace/base/table/view/customer/project UUIDs. `EvidenceVersion(kind, value)` uses positive integer values. `EvidenceItem` validates exact label/type pairs and `evidence_id` pattern `^(business_data|confirmed_memory|general_advice):[0-9]{2}$`; C1 rejects the two reserved labels at construction.

`EvidenceItem.content` is `dict[str, JsonValue]`. `ContextOmission` has only `source_kind`、fixed `reason_code` and positive `count`; `ContextBudgetUsage` has considered/selected counts、evidence count、content chars、truncated/omitted counts；`ContextPack` has only `plan`、`status`、`evidence`、`omissions`、`usage`. Use the exact shapes and fixed reason codes in `.superpowers/sdd/stage08-package-c-task-c1-brief.md`; do not add free-text diagnostics.

- [ ] **Step 4: Run GREEN and bypass tests**

Add tests that construct invalid models using `model_construct`, then pass them through exported `validate_context_*` helpers or `ContextPack.model_validate(model_dump(...))`; service boundaries must revalidate dumps rather than trust model identity.

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: PASS.

### Task 2: Authority and customer/project relationship resolver

**Files:**

- Create: `backend/app/services/stage08_context.py`
- Create: `backend/tests/unit/test_stage08_context_service.py`

**Interfaces:**

- Consumes: Task 1 DTOs; `Actor`; `Stage06PlatformUnitOfWork`; `is_member_eligible_for_employee`; `get_view_presentation`; `read_record_for_actor`.
- Produces:

```python
def resolve_business_scope(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    employee_id: UUID,
    actor: Actor,
    customer_record_id: UUID | None,
    project_record_id: UUID | None,
) -> ResolvedBusinessScope: ...
```

- [ ] **Step 1: Write RED resolver tests**

```python
def test_resolver_accepts_only_visible_one_hop_customer_project_relation():
    scope = resolve_business_scope(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=viewer,
        customer_record_id=customer.id,
        project_record_id=project.id,
    )
    assert scope.relation_kind == "visible_linked_record"
    assert scope.customer_version == customer.version
    assert scope.project_version == project.version

@pytest.mark.parametrize("drift", ["foreign_workspace", "hidden_relation", "inactive_record", "employee_table_out_of_scope"])
def test_resolver_fails_closed_for_invalid_or_invisible_relation(drift):
    apply_drift(drift)
    with pytest.raises(PlatformValidationError, match="context_business_scope_denied"):
        resolve_business_scope(...)
```

- [ ] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "resolver or business_scope"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: import/attribute FAIL.

- [ ] **Step 3: Implement minimal resolver**

Resolver order is fixed:

1. Load active workspace and active employee; require exact workspace equality.
2. Require current active member matching `actor.actor_id` and `is_member_eligible_for_employee(...)`.
3. Parse `employee.accessible_tables` into UUID set; malformed values fail closed.
4. For each supplied record, require active record/table/base in workspace and table in employee scope; call `read_record_for_actor`.
5. If both IDs exist, inspect only visible `linked_record` cells returned by `read_record_for_actor` in either direction; accept exact ID match. Do not inspect raw `record.values` to prove the relation.
6. Return only IDs, record versions and `relation_kind`; no record values/labels/field keys.

- [ ] **Step 4: Run GREEN**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "resolver or business_scope"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: PASS.

### Task 3: Deterministic Context Planner

**Files:**

- Modify: `backend/app/services/stage08_context.py`
- Modify: `backend/tests/unit/test_stage08_context_service.py`

**Interfaces:**

```python
def build_context_plan(
    uow: Stage06PlatformUnitOfWork,
    request: ContextPlanningRequest,
    *,
    actor: Actor,
) -> ContextPlan: ...
```

- [ ] **Step 1: Write RED decision corpus**

```python
@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ("business_fact", ("table_view", "general_advice")),
        ("memory_lookup", ("business_memory", "general_advice")),
        ("mixed", ("table_view", "business_memory", "general_advice")),
        ("general_advice", ("general_advice",)),
    ],
)
def test_planner_uses_fixed_source_matrix(intent, expected):
    plan = build_context_plan(uow, request(intent=intent), actor=viewer)
    assert tuple(source.source_kind for source in plan.sources) == expected
```

Also test duplicate views, private view, wrong employee action, assigned employee without grant, malformed accessible view IDs, `model_construct` budget bypass and view version drift at plan build.

- [ ] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "planner or source_matrix"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: FAIL before `build_context_plan` exists.

- [ ] **Step 3: Implement planner without reads of evidence content**

The planner must:

- revalidate request with `ContextPlanningRequest.model_validate(request.model_dump(mode="python"))`;
- call resolver and current employee/member checks;
- require `query` or `summarize` employee action for every table source；Memory-only/general plans do not invent a new permission action and remain internal, non-executable until Package E wraps them in a read-only ticket；
- validate every view is active, in employee `accessible_views`, same workspace/base, and current actor can call `get_view_presentation`；
- freeze only view ID/version and per-source max items；it does not list records or Memory during planning；
- sort table sources by request order after duplicate rejection, then Memory, then general-advice fallback.

Document in code docstring: `ContextPlan is a bounded internal compilation artifact, not an authorization token or execution ticket`.

- [ ] **Step 4: Run GREEN**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "planner or source_matrix"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: PASS.

### Task 4: Bounded evidence composition, fail-closed reread and renderer

**Files:**

- Modify: `backend/app/services/stage08_context.py`
- Modify: `backend/tests/unit/test_stage08_context_service.py`

**Interfaces:**

```python
def compose_context_pack(
    uow: Stage06PlatformUnitOfWork,
    plan: ContextPlan,
    *,
    actor: Actor,
    now: datetime,
) -> ContextPack: ...

def render_evidence_pack(pack: ContextPack) -> str: ...
```

- [ ] **Step 1: Write RED composition tests**

```python
def test_compose_uses_only_visible_bounded_table_and_platform_memory_projection():
    pack = compose_context_pack(uow, plan, actor=viewer, now=NOW)
    assert [item.label for item in pack.evidence] == ["business_data", "confirmed_memory"]
    assert len([item for item in pack.evidence if item.source_type == "platform_record"]) <= plan.budget.max_table_records
    assert all("hidden_field" not in json.dumps(item.content) for item in pack.evidence)
    assert all("group_chat_ref" not in item.scope.model_dump() for item in pack.evidence)

def test_compose_rereads_and_omits_revoked_or_version_drifted_sources():
    revoke_field_and_change_memory_source_version()
    pack = compose_context_pack(uow, plan, actor=viewer, now=NOW)
    assert pack.status == "general_advice_only"
    assert [item.label for item in pack.evidence] == ["general_advice"]
    assert {o.reason_code for o in pack.omissions} >= {"source_revalidation_failed"}

def test_budget_and_renderer_are_deterministic_and_never_cut_invalid_json():
    first = compose_context_pack(uow, tiny_budget_plan, actor=viewer, now=NOW)
    second = compose_context_pack(uow, tiny_budget_plan, actor=viewer, now=NOW)
    assert first.model_dump_json() == second.model_dump_json()
    assert render_evidence_pack(first) == render_evidence_pack(second)
    assert first.usage.content_chars <= first.plan.budget.max_total_chars
```

- [ ] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "compose or budget or renderer or reread"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: FAIL before composer/renderer exists.

- [ ] **Step 3: Implement fixed read and ordering algorithm**

Table path:

1. Revalidate plan dump, employee/member/business scope and view version.
2. Call `list_view_records(uow, view_id, actor=actor, limit=source.max_items)`.
3. Preserve view record order. For each result, load current record only for ID/version, then call `read_record_for_actor`; include only the intersection matching the view's already safe fields. Version/access mismatch produces omission.
4. Never call `uow.list_records` for context composition.

Memory path:

1. Iterate `uow.list_memory_items(workspace_id)` in repository order.
2. Ignore non-active rows before reading；then call `read_memory_projection(..., lifecycle_mode="read_only")` for each candidate. This internal mode must apply the same authorization/TTL/source validation but make no lifecycle or audit write; the default lifecycle-aware read behavior remains unchanged for existing callers.
3. Reject any projection containing `group_chat_ref`, group source, identity token, missing requested customer/project dimension, or mismatched base/table scope.
4. Include at most `max_memory_items` safe payloads with Memory version.

Budget path:

- recursively sort dict keys；max depth 4；lists first 20 items；strings first 255 code points + `…`；record every JSON path changed；
- canonical encoding: `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`；
- source order is table views/request order → records/view order → Memory repository order → policy marker；
- add a full item only if both item and total caps permit；otherwise add/update fixed `ContextOmission` counts；
- evidence ordinal is assigned only after accepted ordering, so repeat composition is byte-stable.

Renderer format is exact and ID-free:

```text
[business_data:01 label=business_data type=platform_record version=3 scope=workspace/base/table/view]
{"field_a":"value"}
```

Scope displays only dimension names, never UUID values. General marker content is exactly `{"internal_evidence":false}`.

- [ ] **Step 4: Run full C1 unit GREEN**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: PASS.

### Task 5: Real local PostgreSQL reread evidence

**Files:**

- Create: `backend/tests/integration/test_stage08_context_postgres.py`

**Interfaces:** Uses only Task 1-4 public functions and existing SQLAlchemy Stage06 UoW/migrations.

- [ ] **Step 1: Write RED PostgreSQL tests**

Required test names:

```python
def test_context_postgres_visible_relation_and_bounded_pack(): ...
def test_context_postgres_field_revocation_after_plan_fails_closed(): ...
def test_context_postgres_record_version_and_relation_drift_after_plan_fails_closed(): ...
def test_context_postgres_memory_ttl_and_source_version_reread_fails_closed(): ...
def test_context_postgres_group_memory_and_message_rows_are_never_selected_by_c1(): ...
```

The last test may insert a historical `Message` sentinel as fixture evidence, but C1 production modules must not import/query it; assert sentinel absent from pack/renderer/audit/log capture.

- [ ] **Step 2: Run PostgreSQL RED**

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: assertion FAIL exposing any missing re-read/integration behavior; connection skip is not acceptance evidence.

- [ ] **Step 3: Make only C1 service corrections**

Do not add migration or change Stage06 semantics. A narrowly internal `read_only` mode on the existing Memory projection is permitted only to preserve C1's documented no-side-effect contract; it must retain all existing validation and leave the default lifecycle-aware read behavior unchanged. If the test reveals any other necessary schema/API/permission change, stop that branch, document it as a future gate, and keep C1 inside current contracts.

- [ ] **Step 4: Run PostgreSQL GREEN**

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: PASS against disposable local PostgreSQL; report actual test count and database boundary.

### Task 6: Regression, security scan and C1 evidence

**Files:**

- Create: `project-docs/08-implementation/evidence/stage08-package-c-context.md`
- Create: `.superpowers/sdd/stage08-package-c-task-c1-report.md`

- [ ] **Step 1: Run C1 + A/B regression**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: PASS；record fresh counts, do not copy planned numbers.

- [ ] **Step 2: Compile and scan boundaries**

```powershell
Push-Location backend; python -m compileall -q app/runtime/stage08_context_contracts.py app/services/stage08_context.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

```powershell
rg -n "Message|raw_text|raw_caption|normalized_text|TelegramBot|OpenRouter|httpx|requests|LangGraph|pgvector|Redis|APIRouter|add_api_route" backend/app/runtime/stage08_context_contracts.py backend/app/services/stage08_context.py
```

Expected: compile exit 0 and production scan no matches.

```powershell
rg -n "stage08_context|context_plan" backend/app/main.py backend/app/api backend/alembic
```

Expected: no API/router/migration registration.

- [ ] **Step 3: Write evidence/report**

Both documents must contain actual commands/results, local PG vs staging/production boundary, no Provider/Telegram/network evidence, skipped full suite, B5 risk, C2 gate, changed files and temporary cleanup. Do not include evidence content, UUIDs, group IDs, prompt/response or database credentials.

- [ ] **Step 4: Self-review**

Check the implementation against every C1-B01…B08 scenario, scan for unresolved placeholder markers, verify every exported type name matches this plan, and confirm no unlisted production file changed.

## C2 Contract Gate — explicitly not part of C1 implementation

Before C2 code, create a separate BDD/SDD/plan and obtain explicit confirmation for all of the following:

1. short-lived trusted group-window input DTO and who is allowed to create it；
2. no-raw persistence rule versus historical `Message` retention and whether a migration/retention worker is required；
3. exact current-window ordering key, duplicate handling, edit/delete semantics and source version；
4. history time-decay formula, maximum age/window/items/chars and cross-group isolation；
5. active binding/member/workspace and customer/project/group relationship intersection；
6. consumption-time reread, deletion/revocation/TTL and audit/log redaction；
7. whether any API/schema/permission addition is needed—each requires separate user confirmation；
8. local PostgreSQL evidence without Telegram Bot API, send, webhook mutation or Provider calls。

Until this gate passes, C1 must return no group-window/history evidence and must not read `Message` raw columns.
