# Stage08 Package C Task C1 独立复审

## Status

- Review status：`FAIL / changes required`
- Review scope：仅 C1 新增 contracts、service、unit/PostgreSQL tests、实施报告与证据文档。
- Spec verdict：`FAIL`
- Code-quality verdict：`FAIL`
- Finding count：`1 Critical / 4 Important / 1 Minor`
- Boundary：未修改实现，未调用 Telegram、Provider/LLM、HTTP、Redis、RAG/pgvector、LangGraph 或任何外部系统；只执行本地静态检查、Python 复现与 focused tests。

## Critical

### C1-CR-01：`ContextPlan` 可绕过固定 intent/source matrix 与最多 3 个 view 的合同

位置：`backend/app/runtime/stage08_context_contracts.py:175-205`，消费路径 `backend/app/services/stage08_context.py:244-325`。

`ContextPlan.validate_plan_shape()` 只检查每个 intent 的必选 source 是否存在，没有拒绝 intent 外 source，也没有限制 `table_view` 数量。实测普通构造器（不需要 `model_construct`）接受了：

```text
intent=memory_lookup
sources=4 x table_view + business_memory
result=ACCEPTED
```

随后 `compose_context_pack()` 会按该 plan 消费这些额外表源。当前 composer 的全局 `max_table_records` 仍会限制最终读取条数，所以这不是总记录数上限绕过；但它已经绕过 C1-B01 的固定 source matrix、请求最多 3 个 view、以及“调用者不能通过 constructed plan 扩展来源”的策略合同。

最小修复：

1. 在 `ContextPlan` validator 中定义各 intent 的精确允许/必选 source 集合；`memory_lookup` 明确禁止 `table_view`。
2. 限制 `table_view` source 数量为 `<= 3`，保持去重与固定顺序。
3. 校验 source priority/reason 与 source kind 的固定组合，避免 plan 元数据与实际顺序不一致。
4. 同时增加普通构造器和 `model_construct -> validate_context_plan/compose` 的绕过测试。

## Important

### C1-IM-01：C1 composer 并非无副作用；Memory 重读会更新生命周期并写 audit

位置：`backend/app/services/stage08_context.py:325-369` 调用既有 `read_memory_projection()`；实际副作用位于 `backend/app/services/stage08_memory.py:469-518`。

C1 brief 声明 compiler 不持久化、不写 audit/log，但 `read_memory_projection()` 在 TTL 到期或来源失效时会把 Memory 改为 `expired`/`deleted`/`revoked` 并新增 audit。复现实测：将 Memory 的 `valid_until` 设为 `now` 后调用 `compose_context_pack()`，得到：

```text
STATUS expired
AUDIT_DELTA 1
```

composer 本身没有 commit，但它已改变共享 UoW；外层事务后续提交会持久化这些变化。现有 PostgreSQL 测试依赖测试结束 rollback，未证明生产调用无副作用。

建议修复：这是当前 C1 文件范围内无法诚实消除的合同冲突。应在以下二者中明确选择并写入设计：

1. 提供既有 Memory service 的授权、只读、无生命周期写入 projection 接口，再由 C1 使用；这会修改 `stage08_memory.py`，按 brief 属于独立 gate。
2. 明确接受 Memory 生命周期重读的既有受控写入语义，修订“纯 compiler / 不写 audit”声明，并补充事务、audit 脱敏和幂等证据。

在完成该设计决议前，不应把 C1 标记为 spec-complete。

### C1-IM-02：ID-free renderer 只处理“完整 UUID 字符串”，嵌入式 UUID 会真实泄露

位置：`backend/app/services/stage08_context.py:705-744`、`397-422`。

`_normalize_json()` 仅在整个字符串能被 `UUID(value)` 解析时替换。可见表格文本为 `record:<uuid>` 时，真实 `build -> compose -> render` 路径仍原样输出 UUID。复现实测：

```text
ACTUAL_COMPOSE_UUID_LEAK True
{"title":"record:<完整 UUID>"}
```

此外，内部 metadata 过滤仅匹配少数精确 snake_case key；constructed pack 中的 `token`、`permissions` 等字段也会通过 revalidation 并被 renderer 输出。后续 Package E 把 renderer 接入模型时，这会违反 Review Package 的 UUID/source/identity/token/permission 脱敏保证。

最小修复：对字符串内 UUID 片段做确定性替换；对 source/identity/token/permission 元数据采用稳定 canonical key 规则或 fail-closed 检查；补实际 composer 路径和 constructed pack 路径的泄露回归测试。

### C1-IM-03：`ContextPack` validator 未把 evidence 与 plan、usage 精确绑定

位置：`backend/app/runtime/stage08_context_contracts.py:289-339`。

当前 validator 只校验 selected `<=` considered、evidence 总数、content chars 与 status。它没有验证：

- evidence 的 source/label 是否在 plan sources 中；
- `table_records_selected` / `memory_items_selected` 是否等于实际 evidence 类型计数；
- `truncated_items` 是否等于实际 `truncated=True` 项数。

实测一个仅含 `general_advice` source 的 plan 可以携带 `platform_record/business_data` evidence 并通过；同时 `table_records_selected=0` 也通过，renderer 会把该未计划 evidence 当作有效内部证据输出。这削弱了 service 边界重新验证 constructed model 的目标。

最小修复：在 `ContextPack` validator 中按 plan source 集合约束 evidence 类型，并把 selected/truncated/omitted/content/evidence counts 与实际 tuple 精确对齐；增加 constructed pack 负向测试。

### C1-IM-04：`memory_lookup` 被错误禁止客户/项目 scope，且 Memory scope 只做单向匹配

位置：`backend/app/runtime/stage08_context_contracts.py:79-84`、`backend/app/services/stage08_context.py:609-616`。

BDD C1-B02/C1-B04 允许请求携带客户/项目 scope，并要求 Memory scope 逐维精确匹配。当前 request validator 却拒绝 `memory_lookup + customer_record_id/project_record_id`，导致无法做客户/项目范围内的 Memory 查询。与此同时，Memory 比较只在请求维度非空时检查，不能保证 customer/project 两个维度整体精确相等。

最小修复：仅禁止 `memory_lookup` 的 table-only `view_ids`，允许 customer/project scope；当 business scope 非空时，对 customer/project 两个维度做精确相等比较，拒绝缺维、跨维和额外维度；增加单客户、单项目、双维、缺维、错维测试。

## Minor

### C1-MI-01：测试名称声称覆盖 budget/truncation，但缺少核心规范化断言

当前 C1 unit 没有直接覆盖长字符串 `255 + …`、list 20、depth 4、NaN/Infinity、`truncated_paths` 稳定性，以及 item/total budget 的固定 omission 行为。实现肉眼检查与 focused tests 未发现这些路径的即时错误，但 Review Package 要求这些安全边界有真实证据。

建议补充一组纯 unit table-driven 测试，并在修复后更新实施报告中的测试计数与证据状态。

## 已通过的边界检查

- 生产 C1 文件未命中 `Message`、raw message columns、Telegram、OpenRouter/HTTP、LangGraph、pgvector、Redis、`APIRouter` 或 route registration。
- C1 没有新增 API/router、migration、schema/role/permission action、agent execution、draft/ticket/notification。
- 表格正文通过 `list_view_records` 与 `read_record_for_actor` 交集生成；未发现直接读取 `record.values` 生成 evidence。
- 关系解析使用当前可见 linked-record 投影，并检查 active workspace/member/employee/record/table/base 与 employee table scope。
- group Memory 在调用 projection 前被 defer；生产 C1 未 import/query `Message`。
- general-advice intent 不列举 table/Memory，marker 内容固定为 `{"internal_evidence":false}`。
- composer 保留全局 table/evidence/item/total budget 上限，ordering 与 canonical JSON 路径整体为确定性实现。

## Fresh verification

```text
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py
32 passed in 1.16s

python -m pytest -q tests/integration/test_stage08_context_postgres.py
5 passed in 8.55s

python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py
152 passed in 8.57s

python -m compileall -q <C1 source/tests>
exit 0

forbidden production dependency scan
NO_FORBIDDEN_PRODUCTION_MATCHES

scoped git diff --check
SCOPED_DIFF_CHECK_OK
```

测试计数与实施报告一致。测试全绿不改变本次 verdict，因为现有用例没有覆盖上述合同绕过和副作用。

## 复审结论

C1 的基本结构、授权投影复用、群聊/外部依赖隔离和本地 PostgreSQL 基线是成立的，但当前不能通过独立复审。先修复 C1-CR-01、C1-IM-02、C1-IM-03、C1-IM-04；C1-IM-01 需要明确的 Memory 只读/生命周期语义决议。完成修复、补测并更新证据后再做一轮 scoped re-review。

---

## Fix Round 2 独立复审

### Round 2 Status

- Review status：`FAIL / changes required`
- Spec verdict：`FAIL`
- Code-quality verdict：`FAIL`
- Round 2 finding count：`0 Critical / 2 Important / 1 Minor`
- Scope：重审首轮 `1 Critical / 4 Important / 1 Minor` 的修复；仅运行本地攻击式构造、focused tests、disposable PostgreSQL 与静态检查，未修改实现，未调用任何外部系统。

### 首轮问题关闭情况

| 首轮 Finding | Round 2 结论 | 证据 |
| --- | --- | --- |
| C1-CR-01 intent/source 扩源 | 已关闭 | 普通构造与 `model_construct -> validate_context_plan` 均拒绝 `memory_lookup + 4 table_view`；intent/source、priority/reason、最多 3 view 与总 source budget 已进入 validator。 |
| C1-IM-01 Memory 重读副作用 | 已关闭 | TTL：`read_only -> active / audit +0`，默认模式 `expired / audit +1`；source drift：`read_only -> active / audit +0`，默认模式 `deleted / audit +1`。C1 composer 明确调用 `lifecycle_mode="read_only"`。 |
| C1-IM-02 嵌入 UUID / sensitive metadata | 部分关闭 | 真实 compose/render 已把 `record:<uuid>:current` 转为 `record:[internal-reference]:current`；UUID、token、permission、identity、source-ref 变体会被拒绝。但 constructed pack 的 `id/record_id/memory_id` 仍可绕过，见 C1-R2-IM-02。 |
| C1-IM-03 Pack 与 plan/usage 绑定 | 部分关闭 | advice-only plan 已不能携带 business evidence，selected/truncated/content/omission 总计已精确校验；但 per-view scope 与 per-source count 尚未绑定，见 C1-R2-IM-01。 |
| C1-IM-04 scoped memory lookup | 已关闭 | `memory_lookup` 接受 customer/project；无 scope、customer-only、project-only、customer+project 四种相等组合均选中，缺维、错维、额外维度均 fail closed。 |
| C1-MI-01 normalization/budget 覆盖 | 已关闭 | 新增 string/list/depth/changed-path、NaN/Infinity、item/total budget、multi-view 分配测试，当前行为与固定规则一致。 |

## Round 2 Important

### C1-R2-IM-01：`ContextPack` 仍未与具体 plan source 的 view scope 和 `max_items` 精确绑定

位置：`backend/app/runtime/stage08_context_contracts.py:339-410`。

Round 1 修复新增了 source type、workspace、ordinal 与 usage 总数检查，但只把 plan sources 映射成一个 source-type 集合。它没有检查：

- `platform_record` evidence 的 `scope.view_id` 是否属于 plan 中的具体 `table_view`；
- platform evidence 是否具备 table/base/view 的来源形状；
- 每个 view 的 evidence 数是否不超过对应 `ContextSourcePlan.max_items`；
- Memory evidence 数是否不超过 `business_memory.max_items`；
- evidence customer/project scope 是否与 `plan.business_scope` 精确一致；
- policy marker 是否保持仅 workspace scope 与固定 marker content。

攻击式普通构造已被接受：plan 只有 view `V1`、唯一 table source 的 `max_items=1`，但 pack 携带两条 scope 为另一个 view `V2` 的 `business_data` evidence；usage 与 content chars 自洽后 validator 返回成功：

```text
PACK_ATTACK_ACCEPTED 2
PLANNED_MAX 1
VIEW_MISMATCH True
```

这不绕过 composer 的真实授权读取路径，但会让 `validate_context_pack()` / renderer 把 constructed、未计划来源当作已验证 evidence，违反 Fix Round 2 的 plan/evidence/usage exact binding 目标。

最小修复：

1. 对 `platform_record` 要求 `scope.view_id` 精确属于 plan table sources，并按 view 统计 evidence 数 `<= source.max_items`；至少要求 base/table/view 均存在。
2. 对 `memory_item` 统计数量 `<= business_memory.max_items`，并要求 customer/project scope 与 plan business scope 精确相等。
3. 对 `policy_marker` 要求仅 workspace scope、contract version 与 `{"internal_evidence": false}` 固定内容。
4. 增加 constructed pack 负向测试：wrong view、missing view/table/base、per-view over-count、Memory over-count、business-scope mismatch、非固定 marker。

### C1-R2-IM-02：constructed pack 仍可通过内部 identifier key 并由 renderer 输出

位置：`backend/app/runtime/stage08_context_contracts.py:437-472`、`backend/app/services/stage08_context.py:400-425`。

正常 composer 的 `_normalize_json()` 会删除 `id`、`record_id`、`memory_id`，但 `EvidenceItem` 的 `_validate_evidence_content()` 没有拒绝这三个内部 key。攻击式构造一个结构和 usage 均合法的 `general_advice` pack，content 为 `{"record_id":"opaque-internal-id"}`，随后 `render_evidence_pack()` 重校验仍成功并原样输出：

```text
CONSTRUCTED_RECORD_ID_ACCEPTED True
```

因此“constructed pack 不能泄露内部 identifier”的修复尚未闭环；即使值不是标准 UUID，也仍是被正常 composer 明确移除的内部记录标识。

最小修复：让 contract validator 与 normalizer 共享同一套 canonical identifier-key 禁止规则，至少覆盖 `id`、`record_id`、`memory_id` 及大小写/分隔符变体；补 constructed `EvidenceItem` / `ContextPack` / renderer 三层负向测试。

## Round 2 Minor

### C1-R2-MI-01：持久测试未直接保留“无 business scope”成功组合

当前参数化 scope 测试覆盖 customer-only、project-only、双维成功，以及缺维/错维/额外维度失败，但没有 `(request=none, memory=none, selected=True)`。本轮攻击式实测该组合成功，代码行为正确；建议把它加入参数表，避免后续把 workspace-wide Memory lookup 错误回归为全拒绝。

## Round 2 Fresh verification

```text
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py
56 passed in 1.32s

python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py
140 passed in 1.41s

python -m pytest -q tests/integration/test_stage08_context_postgres.py
5 passed in 8.37s

python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py
177 passed in 8.09s

compileall
COMPILE_OK

forbidden C1 production dependency scan
NO_FORBIDDEN_C1_PRODUCTION_MATCHES

C1 API/router/migration registration scan
NO_C1_API_OR_MIGRATION_REGISTRATION

scoped git diff --check
SCOPED_DIFF_CHECK_OK
```

未运行 full backend suite、staging/production、Telegram、Provider/LLM、HTTP/network、Redis、RAG/pgvector 或 LangGraph；因此不作相应验收声明。

## Round 2 结论

首轮 Critical、Memory read-only 生命周期、UUID fragment、scoped Memory 与 normalization/budget 主体修复均成立，现有 focused regression 与 PostgreSQL 证据可信。C1 仍不能 PASS，因为 constructed `ContextPack` 的来源级精确绑定和 internal identifier 脱敏尚有两个 Important。修复 C1-R2-IM-01/02、补充 C1-R2-MI-01 后，可进行一次窄范围 Round 3 re-review。

---

## Fix Round 3 独立复审

### Round 3 Status

- Review status：`PASS / non-blocking documentation freshness follow-up`
- Spec verdict：`PASS`
- Code-quality verdict：`PASS`
- Round 3 finding count：`0 Critical / 0 Important / 1 Minor`
- Scope：重新阅读 C1 brief、Package C BDD、实施报告、Package C evidence 与前两轮复审；只审查 C1 contracts/service/tests，以及为 C1 加入的 `stage08_memory.py` 内部 `read_only` correction。未修改实现，未调用 Telegram、Provider/LLM、HTTP、Redis、RAG/pgvector、LangGraph 或外部系统，未提交。

### 前两轮 finding 关闭复验

| 先前 finding | Round 3 结论 | 独立复验 |
| --- | --- | --- |
| C1-CR-01 intent/source 扩源、超过 3 view、metadata 不精确 | 已关闭 | 普通构造拒绝 4 个 table view；`model_construct -> validate_context_plan` 拒绝 `memory_lookup + 4 table_view + business_memory`。`ContextPlan` 对 intent source-set、source 顺序、唯一 view、budget 总额执行 fail-closed；`ContextSourcePlan` 固定 kind 对应的 priority/reason。 |
| C1-IM-01 Memory reread 副作用 | 已关闭 | C1 composer 固定调用 `read_memory_projection(..., lifecycle_mode="read_only")`。Memory 单测实际覆盖 TTL 与 source drift：返回 `None`、item 保持 `active`、audit 数不变；默认 `lifecycle_aware` 路径仍将 TTL 设为 `expired`、source stale 设为 `deleted`。 |
| C1-IM-02 UUID fragment / sensitive metadata | 已关闭 | 真实 composer 路径把嵌入 UUID 替换为 `[internal-reference]`；contract 对 value/key 中 UUID、`token`、permission、identity、source-ref 及 canonicalized `id`/`record_id`/`memory_id` 变体 fail-closed。攻击式 constructed item 同时携带非计划 view 与 `record_id`，在 `validate_context_pack` 与 `render_evidence_pack` 均被拒绝。 |
| C1-IM-03 plan/evidence/usage 绑定 | 已关闭 | `ContextPack` 逐条绑定 planned view、base/table/view 形状、view source version、per-view `max_items`、Memory `max_items` 与 customer/project 双维 scope；policy marker 只能是 workspace scope、contract v1、`{"internal_evidence": false}`、未截断。constructed wrong-view 与同一 view 超过 max-items 均被拒绝。 |
| C1-IM-04 Memory customer/project scope | 已关闭 | unit 参数化覆盖 `(none, none)`、customer-only、project-only、双维成功，以及缺维、错维、额外维拒绝；local PostgreSQL 覆盖持久 workspace-wide `(none, none)` Memory 成功。 |
| C1-MI-01 normalization/budget | 已关闭 | table-driven unit 覆盖 255+ellipsis、list 20、depth 4、NaN/Infinity、stable `truncated_paths`、单 item 与总 budget omission；结果为 valid canonical JSON。 |
| C1-R2-IM-01 source-level scope/count | 已关闭 | contracts 单测覆盖 wrong view、缺少 base/table/view、per-view over-count、Memory over-count、scope mismatch 与非固定 policy marker；`model_construct` 后 service-boundary revalidation 仍执行。 |
| C1-R2-IM-02 constructed internal identifier | 已关闭 | `record_id`、`Memory-ID`、`ID` constructed evidence 都无法通过 renderer 的 revalidation。 |
| C1-R2-MI-01 workspace-wide Memory | 已关闭 | unit 的 `(request=none, memory=none, selected=True)` 和本地 PostgreSQL `test_context_postgres_workspace_wide_memory_scope_is_selected` 均保留成功证据。 |

### 本轮直接命令与结果

```text
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py
74 passed in 1.79s

python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py
84 passed in 1.19s

python -m pytest -q tests/integration/test_stage08_context_postgres.py
6 passed in 11.13s

python -m compileall -q <C1 contracts/service/read_only Memory/tests>
exit 0

forbidden C1 production dependency scan
NO_FORBIDDEN_C1_PRODUCTION_MATCHES

C1 API/router/migration registration scan
NO_C1_API_OR_MIGRATION_REGISTRATION

raw-record/Message dependency scan
NO_RAW_RECORD_OR_MESSAGE_DEPENDENCY

scoped git diff --check
exit 0
```

上列数量为本轮直接运行所得，未采用实施报告中的旧数量。未运行 full backend suite、staging/production、Telegram、Provider/LLM、HTTP/network、Redis、RAG/pgvector 或 LangGraph，因此不作这些范围的验收声明。

### Minor

#### C1-R3-MI-01：实施报告与 Package C evidence 的 fresh 测试计数仍停留在 Fix Round 1

`.superpowers/sdd/stage08-package-c-task-c1-report.md` 与 `project-docs/08-implementation/evidence/stage08-package-c-context.md` 仍记录 `56` C1 unit / `5` PostgreSQL tests 和 “Fix Round 1 ready-for-independent-re-review”，而本轮独立执行的当前数为 `74` / `6`。这不影响已复验的合同或运行时安全边界，但会降低阶段审阅的证据可追溯性。

建议：实施方在不修改实现的前提下，把这两份 evidence 文档更新为 Round 3 的实际状态、命令和计数，并明确 C1 PASS 不等于 Package C/C2/C3 或 Stage08 完成。

### Round 3 结论

C1 的 strict context plan、read-only Memory reread、证据来源级绑定、renderer fail-closed 与预算规范化在本轮 normal-construction 和 `model_construct` 攻击路径中均成立；未发现 Critical 或 Important 问题。代码与 C1 BDD/brief 的实现边界通过独立复审。唯一 Minor 是证据文档的测试计数和状态未随 Fix Round 3 刷新；应在后续文档更新中关闭，但不阻断 C1 的 task-level PASS。
