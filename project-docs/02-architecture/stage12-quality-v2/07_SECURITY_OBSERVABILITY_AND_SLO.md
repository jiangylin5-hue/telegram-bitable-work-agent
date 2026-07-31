# Stage12 安全、可观测性与 SLO

> Parent index: [README.md](README.md)

## 14. 安全与权限审计

### 14.1 授权顺序

```text
authenticate caller
-> authorize workspace
-> intersect employee scope
-> intersect Telegram chat scope
-> resolve table/view/field permissions
-> build scope hash
-> plan query/action
-> execute
-> revalidate before artifact/action persistence
```

### 14.2 Prompt 数据最小化

- 只传完成 Objective 所需字段。
- 隐藏字段不以名称、空值、hash 或 embedding 形式泄露给 Provider。
- Recipient、chat ID、secret、token 和 raw internal IDs 默认不进入 Provider Prompt。
- EvidenceBundle 使用业务 display code 和 opaque evidence ID；真实内部 UUID 由后端映射。
- Provider 日志禁止记录 Authorization header、API key、完整 Prompt 和完整业务正文。

### 14.3 写入安全

- Planner、Specialist、Provider 均无 ORM/SQL 权限。
- Query Engine 只读；Tool Gateway 是唯一写入边界。
- 高风险动作必须确认；无法确认的外部发送保持 blocked。
- Partial success 必须逐 Objective 呈现，不能用“任务已完成”覆盖拒绝或降级。

## 15. 可观测性与 SLO

### 15.1 Trace 维度

每个 run 记录：

```text
planner_version
task_spec_hash
objective_count
query_plan_hash
candidate_count_by_source
selected_evidence_count
relation_traversal_count
provider/model/profile
provider_attempt_count
token usage
objective status counts
action slot status counts
scope revalidation count
```

### 15.2 分段延迟

```text
admission_ms
planning_ms
schema_resolution_ms
structured_query_ms
semantic_retrieval_ms
specialist_ms by capability
provider_ms by role
fan_in_ms
action_persistence_ms
total_ms
```

### 15.3 建议发布门

| Gate | Target |
| --- | ---: |
| Gold truth 人工复核 | 48/48，后续扩展到 80+ |
| Objective exact match | >= 0.90 |
| Predicate exact match | >= 0.90 |
| Retrieval candidate recall@20 | >= 0.95 |
| Final record precision | >= 0.90 |
| Final record recall | >= 0.90 |
| Join path accuracy | >= 0.95 |
| Aggregate exact match | >= 0.95 |
| Unsupported claim rate | <= 0.02 |
| ActionSlot exact match | >= 0.90 |
| Action target/field/value | 各 >= 0.95 |
| Draft persistence | >= 0.95 |
| Permission safety | 1.00 |
| External-send safety | 1.00 |
| Provider unavailable | <= 0.02 |
| P95 total latency | <= 8 s |

任一安全门失败即禁止发布。质量门不能通过 Overall score 加权抵消。

#### 15.3.1 分阶段指标归属

2026-07-29 用户确认数据依赖 ActionSlot 不在 Planner 阶段扫描记录展开。上表是最终 Stage12 发布门，不得被子阶段降级；子阶段只对其拥有的数据和职责负责：

| Stage | 本阶段必须达到的门 | 明确不在本阶段冒充完成的门 |
| --- | --- | --- |
| Stage12-B | 可静态判定的 Objective exact、Predicate exact；Action kind、静态 target、`query_spec_ref`、`expansion_policy`、confirmation、局部 deny；权限安全 1.00 | Query 结果依赖的具体 target 数量、target value、持久化 |
| Stage12-C | Filter/Join/Aggregate/Sort exact；授权结果、relation path、provenance、版本与完整性 | Action 执行、草稿持久化、外发 |
| Stage12-F | 数据依赖 ActionSlot 展开 exact；target/field/value；持久化、确认、版本冲突、外发安全 | 无 |
| Stage12 总验收 | 上表全部发布门，至少三轮真实模型均值、最差值和方差 | 无 |

Stage12-B 的分母必须只包含规划期可知事实；被排除的数据依赖项必须以 `deferred_to_stage12_c` 或 `deferred_to_stage12_f` 明示，不能记为通过，也不能记为 Planner 失败后用 Overall score 抵消。
