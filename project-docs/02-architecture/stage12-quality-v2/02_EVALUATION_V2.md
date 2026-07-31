# Stage12 Evaluation V2

> Parent index: [README.md](README.md)

## 6. Evaluation V2

### 6.1 Truth Case 契约

每个 Case 使用结构化真源，不再只保存一个扁平编号集合：

```json
{
  "case_id": "join_07",
  "query": "哪些 active 项目同时存在 blocked 工作项和 high 风险？",
  "expected_task_spec": {
    "objective_kinds": ["fact", "risk"],
    "entities": [],
    "predicates": [
      ["projects.delivery_state", "eq", "active"],
      ["work_items.status", "eq", "blocked"],
      ["risks.level", "eq", "high"]
    ],
    "group_by": ["projects.project_code"]
  },
  "expected_query_result": {
    "required_result_records": ["PRJ-ATLAS", "PRJ-BEACON"],
    "allowed_evidence_records": ["MT-001", "MT-004", "RISK-001", "RISK-004"],
    "forbidden_result_records": ["PRJ-EMBER"],
    "aggregates": {}
  },
  "expected_actions": [],
  "expected_permission_outcome": "allowed"
}
```

`required_result_records` 用于结果精确率和召回率；`allowed_evidence_records` 可出现在解释中但不降低 precision；`forbidden_result_records` 用于检测错误结论。

### 6.2 Gold truth 生成与审计

1. Fixture 使用固定 seed、固定 schema version、固定 record version。
2. Gold result 由确定性 Table Query Engine 执行并固化，不由 LLM 生成。
3. 每个 Case 保存 QueryPlan、预期 relation path、聚合结果和权限结论。
4. 现有 48 Case 逐条人工复核，首先修正 `risk_02`，再检查聚合类 Case 的结果/证据边界。
5. Gold 变更必须记录 reason、reviewer、before/after hash；不得静默覆盖历史报告。
6. r75 报告保持只读历史证据；V2 生成新的版本化报告，不重写 r75。

### 6.3 指标定义

| 层 | Metric | 定义 |
| --- | --- | --- |
| Planner | Objective exact / P / R | 比较 normalized objective kind 与 dependency edge |
| Planner | Predicate exact | field、operator、value 三元组完全匹配 |
| Planner | ActionSlot exact | action kind、target selector、assignments、deadline、confirmation policy 完全匹配 |
| Retrieval | Candidate recall@K | Gold required/evidence records 在授权 candidate set 中的比例 |
| Retrieval | Precision@K | Candidate 中与 Objective 相关的记录比例 |
| Retrieval | Join path accuracy | 实际 table/field traversal 与 Gold path 一致 |
| Query | Filter accuracy | 返回记录集合与确定性 Gold 集合比较 |
| Query | Aggregate exact | count/sum/group 等值完全匹配 |
| Answer | Grounded claim precision | 每个事实 claim 能映射到 EvidenceBundle node |
| Answer | Required fact recall | Gold required facts 被覆盖的比例 |
| Answer | Unsupported claim rate | 无 evidence claim 占比 |
| Action | Target/field/value accuracy | 分别评价，不合并掩盖错误 |
| Safety | Permission / external send | 必须始终为 1.0 |
| Runtime | Terminal / recovery / idempotency | durable 行为验证 |
| Latency | P50/P95/P99 | 按 Planner、Query、Provider、Fan-in 分段记录 |

总体分不得用“答案非空”代替回答质量。Overall score 只用于趋势展示，发布门必须逐项通过，不允许高分抵消安全或召回失败。

### 6.4 运行策略

- Deterministic layer 每个 Case 运行一次；任何不一致直接失败。
- Real LLM layer 至少运行三轮，报告 mean、minimum、standard deviation 和 provider failure rate。
- Action end-to-end Case 不允许注入 expected target/fields；只提供真实 Query、授权 scope 和 fixture。
- 另保留 component mode，用于单独测试 Provider 在已知 candidate 下的 schema 合规率，但不得与 end-to-end accuracy 混算。
- 报告保存 query、TaskSpec、QueryPlan hash、candidate IDs、selected evidence IDs、answer、ActionSlot、proposal、持久化状态和安全 delta。

### 6.5 指标计算公式与判分边界

Planner、Retrieval、Answer 和 Action 必须分别计分，不能从最终回答文本反推整个链路。

#### Objective 指标

设 Gold Objective 集合为 `G_o`，实际集合为 `A_o`，元素使用以下 canonical key：

```text
(kind, normalized_entity_scope, normalized_output_contract)
```

计算：

```text
objective_precision = |G_o ∩ A_o| / |A_o|
objective_recall    = |G_o ∩ A_o| / |G_o|
objective_exact     = 1 if G_o == A_o and gold_edges == actual_edges else 0
```

Dependency edge 单独比较 `(from_objective_key, to_objective_key, required)`，避免 Objective 集合正确但 DAG 顺序错误仍被判为通过。

#### Retrieval 指标

Candidate 评价使用 Query Engine/Retrieval trace 中的 record identity，不解析答案正文：

```text
candidate_recall@K = |gold_candidate_records ∩ top_k_candidates| / |gold_candidate_records|
candidate_precision@K = |gold_relevant_records ∩ top_k_candidates| / K
```

`allowed_evidence_records` 计入 relevant，但不计入 required result recall。跨表 Case 还要分别报告每张表的 recall，防止一个表的高召回掩盖另一个表完全缺失。

#### Answer 指标

Composer 输出内部 `claims[]`，再渲染为中文答案：

```json
{
  "claim_id": "claim-01",
  "claim_type": "record_fact",
  "subject": "MT-001",
  "predicate": "status",
  "value": "blocked",
  "evidence_ids": ["ev-01"]
}
```

后端先验证 evidence 是否支持 claim，再计算：

```text
grounded_claim_precision = supported_claims / emitted_claims
required_fact_recall     = covered_gold_facts / gold_required_facts
unsupported_claim_rate   = unsupported_claims / emitted_claims
aggregate_exact          = exact_match(actual_typed_value, gold_typed_value)
```

自然语言风格、可读性和中文表达可使用独立 LLM judge 或人工评分，但不得替代上述确定性事实指标。

#### Action 指标

ActionSlot、Candidate、Proposal 和 Persistence 分四层评价：

```text
slot_exact
target_resolution_accuracy
field_selection_accuracy
value_accuracy
confirmation_policy_accuracy
proposal_schema_accuracy
persistence_accuracy
external_effect_accuracy
```

如果 Slot 解析错误但 Gold target 被 evaluator 注入后 proposal 正确，只能算 component proposal 通过，end-to-end action 必须失败。

### 6.6 Case 分层与隐藏集

公开回归集保留可读、可审计 Case；另维护不进入 Prompt、代码注释和实现文档的隐藏集。Case 分为：

```text
L1: 单表精确编号、简单过滤
L2: 单表复合条件、否定条件、排序和 Top N
L3: 两跳/三跳 linked-record traversal
L4: Group By、Count、跨表聚合和空集合
L5: 多 Objective、多 ActionSlot、局部权限拒绝
L6: 版本漂移、Provider 故障、超时、恢复和幂等
```

每层至少包含同义改写、中文/英文业务值混用、无关噪声、顺序变化和 fixture 扰动。实现不能依赖固定 record code 或固定 Case 顺序。


