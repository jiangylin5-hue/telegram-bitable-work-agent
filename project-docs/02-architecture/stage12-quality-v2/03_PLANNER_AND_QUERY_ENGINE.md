# Stage12 Planner V2 与 Authorized Query Engine

> Parent index: [README.md](README.md)

## Status

- Stage12-B implementation: local technical gate accepted on 2026-07-29; evidence in `../../08-implementation/STAGE_12_B_TASKSPEC_PLANNER_ACCEPTANCE.md`
- Stage12-C implementation: accepted locally on 2026-07-29; deterministic C diagnostic is `46/46` applicable exact and real local PostgreSQL integration passes
- Runtime authority: Stage11 V1 remains the only dispatch plan; TaskSpec V2 shadow is default-off and workspace allowlisted

## 7. Planner V2

### 7.1 两阶段解析

第一阶段是确定性 lexical/schema parser：

- 提取稳定编号：`PRJ-*`、`MT-*`、`RISK-*`。
- 识别表名、字段名、字段别名和 enum value。
- 识别比较运算：等于、不等于、包含、为空、之前、之后、最高、前 N。
- 识别聚合：数量、按项目、分别、总计、平均、最大、最小。
- 识别动作：新增、修改、创建任务、提醒、发送、删除、确认。
- 识别安全限定：只生成草稿、不要发送、等待确认、合法部分继续。

第二阶段是受约束 LLM parser，仅处理歧义、指代、多语义边界和隐含目标。LLM 输出必须通过 JSON Schema 和后端 semantic validator；不能直接形成 command。

### 7.2 TaskSpec V2

```json
{
  "version": "task-spec.v2",
  "objectives": [
    {
      "objective_id": "obj-01",
      "kind": "fact_query",
      "required": true,
      "depends_on": [],
      "query_spec_ref": "artifact:query-spec-01"
    }
  ],
  "action_slots": [],
  "conflict_groups": [],
  "output": {
    "language": "zh-Hans",
    "format": "conversational",
    "include_evidence": true
  }
}
```

允许的 Objective kind 固定为：

```text
fact_query
risk_analysis
daily_summary
record_change
task_creation
reminder_request
restricted_request
conflict_resolution
```

`risk_analysis` 只在用户要求风险识别、比较、解释或风险规则确实是完成目标所需时生成。“high”作为字段值、“blocked_reason”作为字段名、任务标题中出现“回滚”均不能单独触发 risk Objective。

### 7.3 Objective Normalization

Normalizer 依次执行：

1. 合并相同 kind、相同 entity scope 和相同输出要求的 Objective。
2. 将 risk 作为 daily 的输入依赖，而不是重复生成多个 risk 节点。
3. 为每个 ActionSlot 创建独立 action Objective，不能用一个 `requested_action` 覆盖全部动作。
4. 将权限拒绝绑定到具体 Objective，不得把整个 run 一并拒绝。
5. 将冲突绑定到具体 field assignment；独立任务或提醒仍可继续。

例如：

```text
“把 MT-017 同时改为 done 和 blocked，并创建明天之前的评审任务”
```

应生成：

```text
obj-01: query MT-017 facts                    completed
obj-02: update MT-017.status                  denied(conflicting_assignment)
obj-03: create review task due tomorrow       proposed
```

### 7.3.1 数据依赖 ActionSlot 的阶段边界

2026-07-29 用户明确确认：Planner 必须保持数据无关，不得为了在规划期展开具体动作目标而扫描记录。一个动作的目标如果取决于 Query 运行结果，Stage12-B 只生成一个逻辑 ActionSlot 模板；Stage12-C 计算授权结果集，Stage12-F 才将模板展开为具体动作候选并执行最终确认、持久化与安全验收。

规划期目标选择器固定区分两类：

```json
{
  "table_id": "authorized-table-id",
  "record_codes": ["MT-001"],
  "source_entity_codes": [],
  "query_spec_ref": null,
  "expansion_policy": "none",
  "resolution_status": "resolved"
}
```

```json
{
  "table_id": "authorized-table-id",
  "record_codes": [],
  "source_entity_codes": [],
  "query_spec_ref": "query-intent:query-01",
  "expansion_policy": "each_distinct_owner",
  "resolution_status": "deferred_query_result"
}
```

稳定规则：

1. 明确 code、明确授权实体或明确目标表使用 `expansion_policy=none`。
2. “所有 high 且 blocked 事项的负责人”“查询结果中的每个项目”等数据依赖目标必须引用 `query_spec_ref`，不得在 Planner 中读取记录或猜测具体 code。
3. `deferred_query_result` 表示计划有效但尚未解析具体目标，不等同于 `clarification_required`；只有缺少合法 QuerySpec、目标关系或授权 schema 时才要求澄清或拒绝。
4. Stage12-C 输出授权记录、关系路径、版本与 provenance；它不执行动作。
5. Stage12-F 根据 `query_spec_ref + expansion_policy + StructuredQueryResult` 生成 `ResolvedActionCandidate[]`，重新验证权限、版本、去重、数量预算与确认策略。
6. Stage12-B 不得用 Gold 中的具体目标反向注入 ActionSlot，也不得为追求 ActionSlot 分数提前实现 Record Scan。

验收归属同时固定：Stage12-B 评价动作意图、静态目标、`query_spec_ref`、展开策略、确认策略和局部拒绝；Stage12-F 才评价数据依赖动作的具体 target/field/value、展开数量、持久化和外发安全。最终 Stage12 全链路门槛保持不变。

### 7.4 Planner 详细处理流程

Planner 必须按固定顺序运行，任何阶段都不允许扩大前一阶段得到的权限范围：

```text
1. Canonicalize
   - Unicode NFKC
   - 保留原始大小写标识符副本
   - 标准化中文标点、空白和日期表达
2. Lexical Extraction
   - 编号、日期、数值、比较词、动作词、否定词、确认词
3. Schema Binding
   - 表/字段名称与别名匹配
   - enum option 和 typed value 解析
4. Clause Segmentation
   - 按“并且/同时/然后/但/若/只/不要”等逻辑连接词分句
5. Candidate Objective Construction
   - 每个子句产生候选 Objective 或 ActionSlot
6. Ambiguity Resolution
   - 只有多个合法绑定或隐含指代时调用 Planner Provider
7. Normalize/Merge
   - 合并重复 Objective，建立 dependency/conflict edge
8. Semantic Validation
   - schema、operator、scope、action、required field、deadline 验证
9. Cost Estimation
   - 估算 scan、traversal、provider 和总 deadline
10. Persist Plan Artifact
   - 保存 version/hash/ref，随后才允许 dispatch command
```

Planner Provider 返回的字段只能从后端提供的 enum/identifier 列表中选择。对于未知表、未知字段、无法解析日期或歧义 target，Planner 必须生成 `clarification_required` 或 objective-level deny，不得猜测。

### 7.5 Predicate 和时间语义

字段类型决定可用 operator：

| Field type | Operators |
| --- | --- |
| text | `eq`, `contains`, `starts_with`, `is_empty`, `is_not_empty` |
| number | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `between` |
| date/datetime | `on`, `before`, `after`, `between`, `relative_range` |
| single_select/status | `eq`, `ne`, `in`, `not_in` |
| multi_select | `contains_any`, `contains_all`, `is_empty` |
| checkbox | `is_true`, `is_false` |
| linked_record | `contains_record`, `is_empty`, `is_not_empty` |

“今天”“明天之前”“本周”必须使用 workspace timezone 转换成闭开区间，并把解析后的 UTC boundary 写入 QueryPlan/ActionSlot。评测 fixture 固定 `Asia/Shanghai` 和 evaluation clock，避免运行日期导致 Gold 漂移。

### 7.6 Planner 决策示例

Query：

```text
找出 Atlas 和 Beacon 的阻塞原因，比较风险，并为每个项目生成一个跟进任务草稿。
```

规范化结果：

```text
obj-01 fact_query:
  entities = [PRJ-ATLAS, PRJ-BEACON]
  traversal = projects <- work_items.project_link
  predicate = work_items.status == blocked

obj-02 risk_analysis:
  depends_on = [obj-01]
  comparison_group = project

act-01 task.create for PRJ-ATLAS:
  depends_on = [obj-01, obj-02]
  confirmation = required

act-02 task.create for PRJ-BEACON:
  depends_on = [obj-01, obj-02]
  confirmation = required
```

Planner 不应生成第三个通用 task slot，也不应把两个项目合并为群组 target。

## 8. Authorized Query Engine

### 8.1 为什么不能直接 Text-to-SQL

任意 SQL 会绕过服务层权限、字段隐藏、视图范围、版本校验和审计。V2 只允许 Planner 生成受限 QueryPlan AST，执行器将 AST 映射为已有 Platform service/repository 调用或受控 SQLAlchemy expression。

### 8.2 QueryPlan 操作符

```text
ResolveEntity(table, identifiers, aliases)
ScanTable(table_id, authorized_view_ids)
Filter(field_key, operator, typed_value)
TraverseLink(source_table, link_field, target_table, direction)
Project(field_keys)
GroupBy(field_keys)
Aggregate(function, field_key)
Sort(field_key, direction)
Limit(count)
```

禁止操作符：raw SQL、任意函数、跨 workspace scan、未注册字段、未授权反向 link、Provider 自定义工具调用。

### 8.3 QuerySpec 示例

```json
{
  "root_table": "projects",
  "filters": [
    {"field": "delivery_state", "op": "eq", "value": "active"}
  ],
  "traversals": [
    {
      "field": "work_items.project_link",
      "direction": "reverse",
      "filters": [{"field": "status", "op": "eq", "value": "blocked"}]
    },
    {
      "field": "risks.affected_work_items",
      "direction": "reverse",
      "filters": [
        {"field": "level", "op": "eq", "value": "high"},
        {"field": "status", "op": "eq", "value": "open"}
      ]
    }
  ],
  "group_by": ["project_code"],
  "projection": ["project_code"]
}
```

Stage12-C 最终实现采用等价的 typed contract，并为多目标关系增加显式 Join intent：

```text
QueryExecutionIntentV1.join_intents[]
  target_table_id
  purpose: project | filter | exists | aggregate
  requirement: required | optional

AuthorizedQueryPlanV1.traversal_paths[]
  path_id
  target_table_id
  purpose
  join_mode: inner | left | semi
  steps[]
  predicate
```

该增量 contract 已于 2026-07-29 获得用户确认。每个 target 独立解析唯一授权最短路径；`inner` 表示必需 Join，`left` 保留无匹配的主记录，`semi` 只做存在性筛选。仅承担上下文说明且没有被 projection/filter/aggregate/sort 消费的 optional path 可以惰性跳过物化，以避免无关记录进入 evidence；路径本身仍需通过 schema、relation 和权限验证。

### 8.4 执行与权限

每个操作符执行前必须同时验证：

```text
workspace membership
base/table/view access
field visibility
record scope
linked target table access
employee configured scope
telegram chat scope
data version
```

反向关联不能通过读取 link ID 后绕开目标表权限。不可见目标只返回“存在不可见关联”的安全计数或完全省略，具体行为由字段权限策略确定。

### 8.5 确定性结果

Query Engine 输出 `StructuredQueryResult`：

```json
{
  "query_plan_version": "authorized-query-plan.v1",
  "records": [],
  "groups": [],
  "aggregates": [],
  "relation_paths": [],
  "source_versions": [],
  "scope_hash": "sha256",
  "result_hash": "sha256",
  "truncated": false
}
```

Count、Group、Join 和排序答案必须来自该结果，LLM 不得重新计算。

### 8.6 操作符执行语义

#### `ResolveEntity`

解析顺序为精确 code、精确 display value、授权别名、语义候选。精确 code 命中后不得被向量结果覆盖。多个同名记录必须返回 ambiguous，不默认选择最新或第一条。

#### `ScanTable`

只接收已授权 table/view ID，不接收自然语言表名。执行器应用 view filter、record scope 和 soft-delete 条件，并强制稳定排序键，确保分页和重放一致。

#### `Filter`

Value 先通过 field type validator 转为 canonical typed value。不同字段之间默认 `AND`；同一 `in` predicate 内部是集合语义。复杂 `OR` 必须显式 AST：

```json
{"op":"or","children":[{"field":"status","op":"eq","value":"planned"},{"field":"status","op":"eq","value":"in_progress"}]}
```

#### `TraverseLink`

每次 traversal 保存 source table、field、direction、target table 和最大 expansion。默认最大深度为 2；三跳 Query 只有 Gold Case 和 cost budget 明确允许时执行。执行器维护 visited `(table_id, record_id, field_id)`，防止循环关联。

#### `Aggregate`

聚合在数据库或服务层完成，输入必须是已授权 QuerySet。`count` 明确区分 record count、non-null value count 和 distinct count。Group key 不可见时不能以 hash、空字符串或内部 ID泄露分组存在。

Stage12-C 已支持跨已授权 Join row 的分组聚合。Aggregate 的目标记录表与 Group field 所在表可以不同，但二者必须位于同一个已验证 traversal path 中；聚合按目标 record ID 去重，并只保留实际贡献到 filter/HAVING 结果的 source version 和 relation proof。

#### `Limit`

用户未要求 Top N 时，Limit 仅用于安全分页，不能改变 aggregate 输入集合。回答“全部”前必须遍历所有分页或由数据库聚合确认完整结果。

### 8.7 成本与预算控制

QueryPlan Validator 计算：

```text
estimated_scan_rows
estimated_relation_expansions
estimated_result_rows
estimated_evidence_tokens
estimated_provider_calls
```

建议初始硬限制：

- 单 Objective 扫描上限 5,000 条授权记录；超过时要求增加过滤条件或走后台分析任务。
- relation expansion 上限 1,000 edges。
- 同步 API 最多 8 个 Objective、8 个 ActionSlot、4 次 Provider 调用。
- 超过同步预算的任务生成 durable background run，并通过 SSE 报告进度，不能静默截断后仍声称完整。

执行器不使用数据库统计结果作为权限判断；统计只用于拒绝超预算计划。实际权限仍逐操作符验证。

### 8.8 Stage12-C 本地实现结论

2026-07-29 本地技术门已通过：C 适用 Query `46/46 exact`、Join `8/8`、Aggregate `11/11`、Sort `2/2`、Safety `48/48`；focused `288 passed`、真实 PostgreSQL `1 passed`、全后端 `1928 passed, 133 skipped`。验收见 `../../08-implementation/STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md`。

该结论只证明事实计算底座。Stage12-D Retrieval/Embedding、Stage12-E Specialist/Provider、Stage12-F Action/UI 以及生产切换尚未实现。
