# Stage08 Package C：Context Engineering BDD 与验收合同

## Status

- Document status：`Package C closed; approved development boundary retained`；用户已确认连续推进。C1、C2 与 C3 已完成各自独立门禁和 Package C fresh re-review；Package E 的 Provider 压缩仍不在本 BDD 的实现范围内。
- Scope：类型化 `ContextPlan`、证据 label/type/scope/version、策略安全的数据源选择、客户/项目关系解析、受限表格/Memory/通用建议上下文、确定性预算与截断、消费前 fail-closed 重读，以及后续群窗口/历史的独立合同门禁。
- Current Progress：Package A 已完成任务级实现；Package B B1-B5 已关闭。Package C 已关闭：C1 完成 task-level TDD、两轮修复与 Fix Round 3 独立复审；C2 Tasks 1–6 完成 D1–D6、受控 ingress、provenance、lifecycle 与真实 PostgreSQL 漂移/并发证据；C3 完成私有合成、36,000 内容级总预算、compression pending 与 renderer。Task 5 首轮复审发现 direct→pending renderer 丢失 C1 evidence 并调用 materializer 的 Important 缺陷；限定 C3 修复经真实 RED/GREEN 与独立复审后，fresh package re-review 为 `PASS / 0 Critical / 0 Important / 1 non-blocking Minor`，disposable PostgreSQL 组合回归 `213 passed`。Minor 是既有 Starlette/httpx 严格 warning 环境问题；不影响 C 合同闭合，但必须保留为部署前置风险。Package D 尚未开始。
- C1 boundary：只编译和组装当前授权的表格投影、既有非群作用域 `MemoryItem` 安全投影与 `general_advice` 标记；不读取 `Message.raw_text`、`raw_caption`、`normalized_text` 或群历史，不新增 API、migration、权限、Telegram/Provider/LLM/RAG/LangGraph 调用。C1 读取 Memory 时必须使用既有投影服务的内部 `read_only` 生命周期模式：复用 membership、TTL、source/version 与 scope 的 fail-closed 验证，但不得更新 Memory lifecycle、写 audit 或造成任何可提交副作用；既有默认受控生命周期读取语义不变。
- C2 gate：最近群窗口与时间衰减历史必须作为独立 C2 合同设计并单独确认；C1 不预埋对 `Message` 原文的读取旁路。

## 1. 包内分解与完成边界

| Task | 交付 | 状态/门禁 |
| --- | --- | --- |
| C1 | 纯内部类型化计划、关系解析、表格/Memory/通用建议 evidence pack、预算/截断、重读 | 任务级 TDD 与三轮独立审查完成；Fix Round 3 PASS；不等于 Package C 完成 |
| C2 | 群最近窗口、历史时间衰减、排序/版本、retention 与短命原文适配器合同 | Tasks 1–6 已关闭；D1–D6、D3 data contract/provenance 与真实 PostgreSQL 漂移/并发证据已独立复审通过 |
| C3 | Package C 组合回归、真实 local PostgreSQL 证据、包级安全扫描与验收报告 | C1/C2 均已完成；按 `2026-07-20-stage08-c3-context-composition-design.md` 与对应逐任务计划开始，Package E 压缩仍被隔离 |

C1 的完成不等于 C-01 至 C-03 全部完成。C1 可为 `business_data`、`confirmed_memory` 与 `general_advice` 提供可测试基础；群窗口/历史相关分支必须等 C2，Package C 的最终 `evidenced-pending` 必须等 C3。

## 2. 固定术语与标签合同

### 2.1 Source kind 与 evidence label

| C1 source kind | Evidence type | Evidence label | 说明 |
| --- | --- | --- | --- |
| `table_view` | `platform_record` | `business_data` | 由既有 `list_view_records` 与字段权限投影取得的当前记录切片 |
| `business_memory` | `memory_item` | `confirmed_memory` | 由既有 `read_memory_projection` 完成状态、TTL、source/version/field/scope 重读后的投影 |
| `general_advice` | `policy_marker` | `general_advice` | 只表示“后续回答不得声称基于内部资料”，不包含模型生成文本 |

`retrieved_material` 与 `analysis_from_current_material` 保留为 Stage08 全局 label，但 C1 不生成；前者属于 Package D，后者属于 Package E 的 Analyst。任何 label 与 source type 不匹配均在合同层拒绝。

### 2.2 Evidence 必备元数据

每个 evidence item 必须有：

- 运行内稳定 `evidence_id`，格式为 `<label>:<两位序号>`，不得包含数据库 ID；
- 固定 `label` 与 `source_type`；
- `scope`：至少 `workspace_id`，并可收窄到 base/table/view/customer/project；C1 合同不接受 `group_chat_ref`；
- `version`：表格记录使用 record version，Memory 使用 Memory version，通用建议 marker 使用 context contract version；
- 已授权、已投影且受限的 `content`；
- `truncated` 与 `truncated_paths`，使截断可解释；
- 不持久化、不中转 raw source、prompt、response、Telegram identity、hidden field 或 chain-of-thought。

## 3. BDD

### C1-B01：严格类型化计划与策略安全 source selection

**Given** 一个由服务端传入的已验证 `Actor`、active workspace、active digital employee 与类型化 `ContextPlanningRequest`  
**When** `build_context_plan(...)` 选择来源  
**Then** 只可按固定 intent 矩阵选择 `table_view`、`business_memory`、`general_advice`；计划不得包含 raw query/prompt、任意 adapter、任意 SQL、群窗口或 retrieval source。  
**And** employee workspace、member eligibility、allowed action、accessible view/table、view access 与业务 scope 任一不成立时 fail closed。  
**And** 客户端或调用者不能通过 `model_construct`、重复 source、超限 budget 或额外字段扩展来源。

固定 intent 矩阵：

| Intent | 必选/可选来源 |
| --- | --- |
| `business_fact` | 至少一个 `table_view`；可选 `business_memory`；允许失败后 `general_advice` marker |
| `memory_lookup` | `business_memory`；允许空结果后 `general_advice` marker |
| `mixed` | 至少一个 `table_view` + `business_memory`；允许失败后 `general_advice` marker |
| `general_advice` | 仅 `general_advice`，不得借机读取表或 Memory |

### C1-B02：客户/项目关系解析只收窄、不扩权

**Given** 请求携带可选 `customer_record_id` / `project_record_id`  
**When** `resolve_business_scope(...)` 解析业务作用域  
**Then** 每个记录必须 active、位于同一 workspace、位于 employee 可访问 table，且 `read_record_for_actor` 当前可读。  
**And** 两个 ID 同时存在时，至少一个方向必须有当前 actor 可见的 `linked_record` 单跳关系；无关系、隐藏关系、跨 workspace、失效记录或 relation target 漂移均拒绝。  
**And** resolver 只返回 ID、record version 与固定 relation kind，不返回记录正文或隐藏 field key。

### C1-B03：受限表格上下文

**Given** 一个计划中已授权、版本冻结的 view source  
**When** `compose_context_pack(...)` 读取表格证据  
**Then** 必须再次执行当前 employee/member/view/table/field 权限检查，并通过既有 `list_view_records(..., limit=...)` 获取受限切片。  
**And** 每条记录在进入 evidence 前再次用 `read_record_for_actor` 检查当前 record version 与字段可见性；不一致即丢弃该 item 并记录固定 omission reason。  
**And** 整表不得进入 pack；单 view 最多 20 条、C1 最多 3 个 view、最终仍受总 evidence/字符预算约束。

### C1-B04：受限业务 Memory 上下文

**Given** workspace 内 active Memory 列表  
**When** C1 选择 Memory evidence  
**Then** 逐项调用既有 `read_memory_projection` 的内部 `read_only` 生命周期模式，复用其 membership、TTL、source version、field visibility、relation scope 与删除/撤权 fail-closed 行为，同时不得变更 lifecycle 或写 audit。  
**And** 只接收无 `group_chat_ref` 且 source 为当前 `platform_record` 的投影；B4 群来源 Memory 留给 C2 的关系/群 scope 合同，不在 C1 静默混入。  
**And** customer/project 请求存在时，Memory scope 必须逐维相等；缺维、跨维或 identity-only 模糊命中均不得扩大范围。  
**And** C1 最多选择 12 条 Memory，顺序为既有 UoW 的 `created_at DESC, id DESC`，随后受总预算约束。

### C1-B05：确定性预算、规范化与截断

**Given** 相同计划、相同授权数据与相同 budget  
**When** 重复 compose  
**Then** evidence 顺序、canonical JSON、字符使用、truncated path、omission 计数与 renderer 输出完全一致。  
**And** 字符计数以 canonical UTF-8/Unicode code point 字符串为准：key 排序、无多余空白、`ensure_ascii=False`。  
**And** 单字符串先按 256 code points 截断并加 `…`；列表最多 20 项、嵌套最多 4 层；单 item 超预算时按稳定 key 顺序裁剪并显式标记，仍无法容纳则整体 omission。  
**And** 全局预算只加入完整、有效的 evidence item；不得在 JSON token 中间截断，也不得因超限隐式扩大 budget。

固定 C1 上限：`max_table_records <= 20`、`max_memory_items <= 12`、`max_evidence_items <= 24`、`max_item_chars <= 2000`、`max_total_chars <= 12000`。测试可使用更小值，不得构造更大值。

### C1-B06：fail-closed re-read 与授权漂移

**Given** plan 生成后 workspace/member/employee/view/field/record/Memory/source/version 发生变化  
**When** context pack 消费来源  
**Then** 必须以当前 PostgreSQL/UoW 状态重算；计划中的旧版本或旧可见性不是读取能力。  
**And** authority 或 customer/project relation 漂移使整个 plan 失效；单个 record/Memory 漂移只产生固定 omission，不暴露旧内容。  
**And** 内部证据全部失效且 `allow_general_advice=True` 时，只返回 `general_advice` marker；若为 false，则返回空 evidence pack 与固定 `internal_evidence_unavailable` 状态。

### C1-B07：证据 renderer 与资料不足降级

**Given** 一个已组成的 evidence pack  
**When** `render_evidence_pack(...)` 生成后续模型可消费的文本  
**Then** renderer 只包含 evidence ID、label、type、version、收窄后的非敏感 scope 类别与 canonical content。  
**And** 不输出 record/Memory UUID、source refs、field permission、identity token、group binding、audit、ticket、raw prompt/response。  
**And** 无内部证据时必须出现 `general_advice` label，明确后续回答不能声称“已查询内部数据”。

### C1-B08：无持久化、无 API、无外部调用

**Given** C1 focused/unit/local PostgreSQL 测试  
**When** 执行全部 C1 路径  
**Then** 不新增或写入 context schema，不创建 API route，不读取 `Message`，不发 Telegram，不调用 OpenRouter/LLM/Provider/RAG/LangGraph/Redis，不创建 draft/ticket/notification。  
**And** C1 返回值只存在于调用栈内；日志、audit、AgentRun 和 test artifact 不保存 evidence content 或 renderer 文本。

### C2-G01：群窗口/历史独立合同门禁

**Given** C1 已完成  
**When** 提议实现最近群窗口或时间衰减历史  
**Then** 必须先单独写明并获得确认：可信入站适配器、chat binding/member scope、排序键、source version、窗口上限、历史衰减、删除/撤权/retention、是否及如何替代历史 `Message` raw retention、审计脱敏与 PostgreSQL 证据。  
**And** 在该确认前，禁止从 `Message.raw_text/raw_caption/normalized_text`、telegram inbox view、outbox 或日志重建上下文；禁止新增 group context API。

## 4. 验收映射

| Stage08 requirement | Package C 行为 | 最低证据 |
| --- | --- | --- |
| C-01 | intent/source planner 区分表格、Memory、群门禁、通用建议 | C1 decision corpus + C2 合同测试 |
| C-02 | 无完整表/群注入；窗口/item/字符预算受限 | C1 projection/budget tests + C2 window tests |
| C-03 | evidence label 准确，资料不足标记 `general_advice` | C1 renderer/service tests；E/API 后续集成证据 |

## 5. C1 最低验收命令

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：C1 unit 全部通过；测试数以实施报告 fresh output 为准，不在设计阶段虚构。

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：disposable local PostgreSQL 下 relation/field/record/Memory version 与撤权重读 fail closed；这不是 staging/production 证据。

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：C1 + A/B 相关回归通过。

静态边界检查：

```powershell
rg -n "Message|raw_text|raw_caption|normalized_text|TelegramBot|OpenRouter|httpx|requests|LangGraph|pgvector|Redis|APIRouter|add_api_route" backend/app/runtime/stage08_context_contracts.py backend/app/services/stage08_context.py
```

预期：无生产依赖命中；测试中的 sentinel 字符串不计为生产依赖。

## 6. 阻断条件与剩余风险

- B5 与 C2 均已关闭，不再阻断 C3；C3 仍须证明其不改变 C1/C2 的安全边界，且不可提前调用 Package E 的 `ContextCompressor`。
- 若 C1 实现发现必须新增 schema、API、permission action/role、Telegram ingestion/retention、LLM/RAG/LangGraph 或外部调用，立即停止该扩展并请求单独确认；不得把它塞入 C1。
- 历史 `Message` 已持久化 raw 文本是已知跨阶段风险。C1 通过完全不 import/查询 `Message` 避免放大风险；真正处理该风险属于 C2 retention 合同或独立迁移任务。
- C1 的 `general_advice` 只是证据边界 marker，不是模型回答质量证明。真实 Provider、Coordinator 与最终 API 标签仍分别属于 E/F 与后续入口集成。
