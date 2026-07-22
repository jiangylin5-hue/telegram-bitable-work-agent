# Stage08 Package C Task C1：类型化 Context Plan 与受限 Evidence Pack

## Status 与权限边界

- Task status：`approved / ready for task-level TDD`；用户已确认连续推进，本文件可直接作为实施边界。
- Authority：`STAGE_08_SOURCE_OF_TRUTH.md`、`STAGE_08_COMPLEX_AGENT_ARCHITECTURE.md`、`STAGE_08_SDD.md`、`STAGE_08_DATA_API_SECURITY_CONTRACT.md`、`STAGE_08_TEST_PLAN.md`、`STAGE_08_ACCEPTANCE_CHECKLIST.md` 与本 Package C BDD。
- Goal：建立 C1 的纯内部类型化 context compiler，安全组合当前表格投影、非群业务 Memory 与 `general_advice` marker；每条 evidence 具备 label/type/scope/version，且预算、截断与 reread 可确定性验证。
- Dependency：Package A runtime contracts 与 Package B B1-B4 当前接口。实施时 B5 package-level closure 尚 pending，因此不阻塞 C1；B5 已在后续独立复审中关闭，不再构成当前包级风险。
- External boundary：不调用 Provider/LLM/OpenRouter、Telegram/Bot API、HTTP client、Redis、RAG/pgvector 或 LangGraph；不创建 draft/ticket/notification，不发送消息。
- Change boundary：无 migration、无 schema 变化、无新 API、无新 permission action/role、无 `main.py` router 注册、无 Telegram ingestion/retention 变化。

## 1. 为什么 C1 采用内部 compiler

Package A 的 `RedactedToolResult` 只包含 entity refs、visible field keys 与 counts，故不能被错误当作包含业务事实的 prompt 上下文。C1 也不能扩充它为 raw tool result，因为这会改变 A 的脱敏合同。

C1 因此建立独立、纯内部 compiler：

```text
typed ContextPlanningRequest + verified Actor
-> current employee/member/view/business-scope validation
-> ContextPlan（选择与预算，不是授权 token）
-> consumption-time reread
-> bounded table projection + safe Memory projection
-> deterministic ContextPack + label renderer
```

它复用已有安全 service，不新增入口。未来 Package E 必须把它置于正式 read-only ticket/Coordinator 生命周期内；C1 本身不宣称完成 runtime API 或最终 Agent 调用。

## 2. 明确不做

- 不读 `Message` 模型或 `messages` 表，不读 `raw_text`、`raw_caption`、`normalized_text`、telegram inbox view、群 outbox 或日志。
- 不实现当前群最近窗口、历史时间衰减、群消息 edit/delete/version/order；这些属于 C2 独立合同门禁。
- 不把 B4 `group_chat_ref` Memory 混入 C1。C1 只消费当前来源为 `platform_record` 的非群 Memory。
- 不实现文件/RAG/retrieval chunk、embedding、pgvector 或 `retrieved_material`。
- 不实现 Analyst、Provider prompt、answer、citation API、draft 或 LangGraph；`analysis_from_current_material` 保留但不由 C1 生成。
- 不持久化 `ContextPlan`、`ContextPack`、renderer output 或 evidence content；不写 audit/AgentRun/log。Memory 只允许调用既有安全投影的内部 `read_only` lifecycle mode：它复用所有授权与失效验证，但不进行 lifecycle 状态迁移或 audit 写入；标准 lifecycle-aware read 的默认行为保持不变。

## 3. 精确文件范围

| 操作 | 文件 | 内容 |
| --- | --- | --- |
| Create | `backend/app/runtime/stage08_context_contracts.py` | strict C1 contracts、固定 enum、label/type/version/scope、budget validator |
| Create | `backend/app/services/stage08_context.py` | relation resolver、planner、composer、normalizer、budget、renderer |
| Create | `backend/tests/unit/test_stage08_context_contracts.py` | contract RED/GREEN |
| Create | `backend/tests/unit/test_stage08_context_service.py` | planner/resolver/composer/renderer RED/GREEN |
| Create | `backend/tests/integration/test_stage08_context_postgres.py` | disposable local PG reread evidence |
| Create | `project-docs/08-implementation/evidence/stage08-package-c-context.md` | 实施证据（实施阶段） |
| Create | `.superpowers/sdd/stage08-package-c-task-c1-report.md` | C1 报告（实施阶段） |

Review-correction exception: `backend/app/services/stage08_memory.py` may be changed solely to add the documented internal `read_only` lifecycle mode to `read_memory_projection`. It must retain all authorization/TTL/source validation, make no lifecycle/audit write, preserve the default lifecycle-aware behavior, and add no public API, schema, migration, permission or other caller change.

不得修改任何现有 production/doc 文件。若实现必须修改 `stage08_memory.py`、Stage06 authorization/table read、`Message`、API、migration 或 permission，停止扩展并报告独立 gate。

## 4. 精确合同

### 4.1 Planning request 与 budget

```python
ContextIntent = Literal[
    "business_fact",
    "memory_lookup",
    "mixed",
    "general_advice",
]

class ContextBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    max_table_records: StrictInt = Field(ge=0, le=20)
    max_memory_items: StrictInt = Field(ge=0, le=12)
    max_evidence_items: StrictInt = Field(ge=1, le=24)
    max_item_chars: StrictInt = Field(ge=128, le=2000)
    max_total_chars: StrictInt = Field(ge=256, le=12000)

class ContextPlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    workspace_id: UUID
    employee_id: UUID
    intent: ContextIntent
    view_ids: tuple[UUID, ...] = ()
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None
    allow_general_advice: StrictBool
    budget: ContextBudget
```

请求没有 `actor`、ticket state、prompt/query text、source ref、field allowlist、group、Message、retrieval 或 output 字段。Actor 只能作为 service keyword argument 从可信调用栈传入。

### 4.2 Resolved scope 与 plan

```python
class ResolvedBusinessScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    workspace_id: UUID
    customer_record_id: UUID | None = None
    customer_version: StrictInt | None = Field(default=None, ge=1)
    project_record_id: UUID | None = None
    project_version: StrictInt | None = Field(default=None, ge=1)
    relation_kind: Literal["none", "single_record", "visible_linked_record"]

class ContextSourcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_kind: Literal["table_view", "business_memory", "general_advice"]
    priority: StrictInt = Field(ge=1, le=3)
    view_id: UUID | None = None
    source_version: StrictInt | None = Field(default=None, ge=1)
    max_items: StrictInt = Field(ge=0, le=20)
    reason_code: Literal[
        "business_fact_requested",
        "memory_requested",
        "general_advice_requested",
        "general_advice_fallback_allowed",
    ]

class ContextPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    contract_version: Literal["stage08-context-plan.v1"]
    workspace_id: UUID
    employee_id: UUID
    actor_user_id: StrictStr
    intent: ContextIntent
    business_scope: ResolvedBusinessScope
    budget: ContextBudget
    sources: tuple[ContextSourcePlan, ...]
```

`ContextSourcePlan` 的 table source 保存 `view_id`、当前 view version、上限与固定 reason；Memory/general source 不保存 item ID 或内容。Plan 不保存 record/Memory candidate list，也不保存任何文本。
`ContextSourcePlan` validator 还必须约束：`table_view` 需要 view/version 且 `max_items <= 20`；`business_memory` 禁止 view/version 且 `max_items <= 12`；`general_advice` 禁止 view/version 且 `max_items == 1`。reason 必须与 source kind 精确配对。

### 4.3 Evidence contract

```python
class EvidenceScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    workspace_id: UUID
    base_id: UUID | None = None
    table_id: UUID | None = None
    view_id: UUID | None = None
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None

class EvidenceVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    kind: Literal["record", "memory", "contract"]
    value: StrictInt = Field(ge=1)

class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    evidence_id: StrictStr
    label: EvidenceLabel
    source_type: Literal["platform_record", "memory_item", "policy_marker"]
    scope: EvidenceScope
    version: EvidenceVersion
    content: dict[str, JsonValue]
    truncated: StrictBool
    truncated_paths: tuple[StrictStr, ...]
```

固定配对：

```text
platform_record + record version -> business_data
memory_item + memory version      -> confirmed_memory
policy_marker + contract version  -> general_advice
```

任何其它配对，包括 reserved labels `retrieved_material` / `analysis_from_current_material`，在 C1 fail closed。

其余输出合同固定为：

```python
class ContextOmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_kind: ContextSourceKind
    reason_code: Literal[
        "authority_changed",
        "business_scope_changed",
        "view_version_changed",
        "source_revalidation_failed",
        "scope_mismatch",
        "group_source_deferred",
        "source_limit_reached",
        "item_budget_exceeded",
        "total_budget_exceeded",
    ]
    count: StrictInt = Field(ge=1)

class ContextBudgetUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    table_records_considered: StrictInt = Field(ge=0)
    table_records_selected: StrictInt = Field(ge=0)
    memory_items_considered: StrictInt = Field(ge=0)
    memory_items_selected: StrictInt = Field(ge=0)
    evidence_items: StrictInt = Field(ge=0, le=24)
    content_chars: StrictInt = Field(ge=0, le=12000)
    truncated_items: StrictInt = Field(ge=0)
    omitted_items: StrictInt = Field(ge=0)

class ContextPack(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    plan: ContextPlan
    status: Literal["internal_evidence", "general_advice_only", "no_evidence"]
    evidence: tuple[EvidenceItem, ...]
    omissions: tuple[ContextOmission, ...]
    usage: ContextBudgetUsage
```

`ContextPack` 不包含 raw source IDs 列表、permission snapshot、prompt 或 answer。validator 必须检查 selected/considered、evidence count 与实际 tuple、`content_chars` 与 plan budget、status 与 label 集合保持一致。

## 5. Service 接口与算法

### 5.1 关系解析

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

必须验证 active workspace/employee/member、assigned grant、employee table scope、record/table/base/workspace/status 与 `read_record_for_actor`。两记录同时存在时，只能通过安全投影中当前 actor 可见的 `linked_record` cell 精确匹配另一 record ID；不得查看 raw `record.values` 来绕过 relation field visibility。返回 record version 用于 compose 时重读。

### 5.2 Planner

```python
def build_context_plan(
    uow: Stage06PlatformUnitOfWork,
    request: ContextPlanningRequest,
    *,
    actor: Actor,
) -> ContextPlan: ...
```

Planner 先重新 `model_validate(model_dump)` 防止 constructed model 绕过，再调用 relation resolver。Table source 必须同时满足 employee action `query|summarize`、accessible view/table、same workspace/base、当前 view access。`general_advice` intent 不读取任何内部源。Plan source 顺序固定且去重。

### 5.3 Composer 与 renderer

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

Compose 前重新验证 plan、actor、employee、member、business scope 与 view version。Table 只用 `list_view_records(..., limit=...)`，每条 record 再 `read_record_for_actor`；Memory 逐项 `read_memory_projection(..., lifecycle_mode="read_only")`，只收 exact non-group scope/source。读取失败不返回旧内容；C1 不得使该重读留下 lifecycle 或 audit 副作用。

排序：view request order → view record order → Memory repository order → general marker。预算 canonicalization 使用 sorted key、compact separators、`ensure_ascii=False`、`allow_nan=False`；字符串 256 code points、列表 20、深度 4。单 item 和总预算都只接受完整 JSON evidence；所有裁剪/丢弃写固定 path/reason，不写源内容。

Renderer 只输出运行内 evidence ID、label/type/version、scope 的维度名称和 canonical content；不得输出 scope UUID 值、record/Memory UUID、source refs、field keys 之外的权限元数据或 identity token。

## 6. RED → GREEN 测试清单

### RED-1：contracts

必测：

- hard budget 上限/下限、bool 冒充 int、NaN/Infinity；
- raw/prompt/group/retrieval/actor/permission extra fields；
- duplicate/超过 3 view、intent/source 形状；
- evidence label/type/version mismatch、group scope、非法 evidence ID；
- `model_construct` 后在 service 边界重新验证失败。

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

RED 预期：module import/接口缺失 FAIL。GREEN 预期：全 PASS。

### RED-2：resolver/planner

必测：

- owner/viewer 当前可见单向 relation 成功；
- hidden relation、foreign workspace、inactive record/table/base、employee table/view out-of-scope 拒绝；
- assigned employee grant 撤销拒绝；
- 四种 intent 的固定 source matrix；
- general advice 不触发 table/Memory UoW list；
- private/restricted view 当前 actor 不可读时 fail closed；
- plan 无 raw content/item list。

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "resolver or business_scope or planner or source_matrix"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

RED 预期：函数缺失 FAIL。GREEN 预期：全 PASS。

### RED-3：compose/reread/budget/renderer

必测：

- full table 不会进入 pack，view limit 生效、hidden field 缺失；
- Memory 仅通过 `read_memory_projection`，TTL/source version/field revoke 后立即 omission；
- group Memory 不进入 C1；历史 `Message` sentinel 不进入任何 pack/renderer；
- relation/version/employee/member/view drift 后重读失败；
- 相同输入两次 `model_dump_json` 与 renderer byte-identical；
- string/list/depth/item/total 上限、有效 JSON、truncated path 与 omission count；
- 内部证据全失效后只出现 `general_advice` marker，marker 为 `{"internal_evidence":false}`；
- renderer 不含 UUID/source ref/permission/identity token/raw sentinel。

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_service.py -k "compose or reread or budget or renderer or advice"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

RED 预期：函数/行为缺失 FAIL。GREEN 预期：全 PASS。

### RED-4：local PostgreSQL

必测：

- visible linked relation + bounded pack；
- plan 后 field permission 撤销；
- plan 后 record version/relation target 漂移；
- Memory TTL/source version drift；
- group Memory 与 historical Message row 存在但 C1 不选择；
- 事务 rollback 后无 C1 新持久化对象。

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

GREEN 必须是实际 local PostgreSQL PASS；SQLite 或 skip 不能替代。

## 7. Final verification

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

```powershell
Push-Location backend; python -m compileall -q app/runtime/stage08_context_contracts.py app/services/stage08_context.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

```powershell
rg -n "Message|raw_text|raw_caption|normalized_text|TelegramBot|OpenRouter|httpx|requests|LangGraph|pgvector|Redis|APIRouter|add_api_route" backend/app/runtime/stage08_context_contracts.py backend/app/services/stage08_context.py
```

最后一个命令预期生产文件零命中。实施报告必须记录 fresh 数量、local PG 边界、未运行 full suite/Provider/Telegram、B5/C2 风险与 temporary cleanup。

## 8. C2 明确停线点

任何以下需求一出现，C1 停止而不是扩展：

- 读取当前群消息文字或历史 `Message`；
- 引入群窗口排序、时间衰减、消息 edit/delete/version；
- 增加 `group_chat_ref` 到 C1 evidence scope；
- 新增 group context API/schema/permission；
- 修改 Telegram webhook/parser/ingestion 或 raw retention。

C2 必须先解决可信短命窗口输入、binding/member scope、消息版本/排序/删除、retention、历史 raw 数据治理、预算、审计脱敏与 local PostgreSQL 证据，并获得用户独立确认。
