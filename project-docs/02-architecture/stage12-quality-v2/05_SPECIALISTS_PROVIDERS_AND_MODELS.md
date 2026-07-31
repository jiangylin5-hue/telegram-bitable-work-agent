# Stage12 Specialist、Provider 与模型架构

> Parent index: [README.md](README.md)

## 10. Specialist V2

### 10.1 Tabular Specialist

输入：`AuthorizedQueryPlanRef + ObjectiveRef + ScopeProofRef`。

工具：`schema.resolve_authorized`、`records.query_authorized`、`links.traverse_authorized`、`records.aggregate_authorized`。

输出：`StructuredFactSet`，包含 records、groups、aggregates、relation paths、completeness 和 evidence refs。它不负责风险推断、日报文案和动作生成。

### 10.2 Risk Specialist

输入：Tabular Specialist 的 `StructuredFactSet` 与 workspace 可见的 risk policy/version。

工具：只允许读取已授权风险规则；不重新扫描整个 workspace。

输出：

```json
{
  "assessments": [
    {
      "subject_ref": "MT-001",
      "severity": "high",
      "reason_codes": ["blocked", "open_high_risk"],
      "evidence_ids": ["ev-01", "ev-04"]
    }
  ],
  "policy_version": "risk-policy.v1"
}
```

### 10.3 Daily Specialist

输入：确定性 groups/aggregates、异常记录和 RiskAssessment。不得自行重新计数。

输出：`DailyBrief`，分为事实摘要、异常、风险、建议和数据截止时间。建议必须标记为 recommendation，不得声称已执行。

### 10.4 Action Specialist

输入：`ActionSlot + AuthorizedCandidateSet + EvidenceBundle + CurrentVersionProof`。

输出：`ControlledActionProposal`。它不能自主扩大 target、field 或 workspace 范围。

### 10.5 Fan-in Composer

Supervisor 按 Objective ID 读取 typed artifacts：

1. 验证 artifact scope hash、content hash、schema version 和 data version。
2. 按 dependency DAG 判定 completed、proposed、denied、degraded。
3. 合并事实和分析，去除重复记录。
4. 对每个 ActionSlot 单独列出状态。
5. 只在必需事实不可用时阻断依赖 Objective；可选风险分析失败不能抹去可验证事实。
6. 最终只生成一个用户可见 terminal event。

### 10.6 Specialist Handler 接口与隔离

每种 capability 注册独立 handler factory，不再由 stream 名称不同但内部调用同一个 tabular handler。建议统一协议：

```python
class SpecialistHandler(Protocol):
    capability_id: str
    input_schema_version: str
    output_schema_version: str

    def execute(
        self,
        command: AuthorizedSpecialistCommand,
        context: SpecialistExecutionContext,
    ) -> SpecialistExecutionResult:
        raise NotImplementedError
```

`SpecialistExecutionContext` 只暴露受控 ports：

```text
artifact_reader
authorized_query_gateway
risk_policy_reader
model_gateway
tool_gateway (action specialist only)
clock
metrics
```

它不暴露 SQLAlchemy session、raw repository、Redis client 或 Provider key。Worker 负责 transaction、lease、retry、checkpoint 和事件；handler 负责纯业务执行。这样同一 handler 可在 embedded test 和 Redis worker 中复用，但权限与 durable 语义保持在 worker 外壳。

Registry 增加：

```text
handler_id
handler_version
input_schema_version
output_schema_version
allowed_ports
required_upstream_artifact_kinds
max_provider_calls
max_input_tokens
failure_policy
```

启动时校验 Registry 与 handler factory 一一对应；缺失 handler 直接阻止 worker readiness，不允许回退到 tabular handler。

### 10.7 Command 分发与真正并行

每个 Objective 产生独立 command，command payload 只引用 plan/objective/artifact：

```json
{
  "run_id": "uuid",
  "command_id": "uuid",
  "objective_id": "obj-02",
  "target_capability": "platform.risk.analyse",
  "input_artifact_refs": ["artifact:fact-set-01"],
  "scope_proof_ref": "scope:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "deadline_at": "2026-07-29T12:00:00Z",
  "idempotency_key_hash": "sha256"
}
```

依赖满足后由 Orchestrator 发布 outbox。Tabular 完成后，risk 和 daily 如果彼此没有依赖可并行；ActionSlot 只等待自己需要的 fact/risk artifact，不等待无关日报。

Worker 部署可以是同一进程内多个 async consumer，也可以是多个 systemd unit，但必须满足：

- 每个 capability 独立 consumer group、并发上限和 rate limit。
- Provider concurrency 使用 role/profile semaphore，不能由 Redis 消息数量无限放大。
- 同一 run 的 fan-in 使用数据库状态和 artifact，不依赖进程内共享内存。
- required command 失败触发依赖 command 取消；optional command 失败允许降级。
- terminal run 后队列中的 sibling command 在执行前检查 run status 并安全 ack/cancel。

### 10.8 Typed Fan-in 算法

Fan-in 不把 Specialist 文本直接串接。推荐步骤：

```text
load objective rows
-> verify all required terminal or deadline reached
-> load and validate typed artifacts
-> build ClaimGraph
-> deduplicate by (subject, predicate, value)
-> attach evidence IDs and objective ownership
-> resolve contradictory claims by source version/policy
-> build ActionStatusList
-> render conversational response
-> validate rendered claims against ClaimGraph
-> emit one terminal safe artifact/event
```

如果两个 artifact 对同一字段给出不同值：

1. source version 较旧的 artifact 标记 stale；
2. 相同版本仍冲突则 run degraded，显示“当前证据存在冲突”；
3. 不允许 Composer 自行选择更合理的值；
4. 依赖冲突事实的 ActionSlot 保持 denied/conflicted。

## 11. Provider V2

### 11.1 Provider 分工

| Provider | 输入 | 输出 | 不允许做的事 |
| --- | --- | --- | --- |
| Planner Provider | 脱敏 Query + Authorized Schema Summary | TaskSpec candidate | 执行查询、决定权限 |
| Embedding Provider | 已授权、脱敏文本 | Fixed-profile vector | 返回业务答案 |
| Analysis Provider | EvidenceBundle | Typed analysis/answer claims | 扩大证据、重新计数 |
| Action Provider | ActionSlot + authorized candidates | Controlled proposal | 直接写入或发送 |
| Composer Provider | typed objective results | Conversational answer | 新增无证据事实 |

### 11.2 Strict Output 与语义校验

JSON Schema 通过后仍必须执行 semantic validation：

- enum/value 与字段类型一致；
- citation/evidence ID 存在；
- target/field 在 authorized candidate 中；
- action name 使用平台 canonical enum；
- required assignments 完整；
- answer claim 不引用未提供 evidence；
- 中文 Query 的用户可见结果必须为中文；
- deny 不得携带 proposal payload；
- proposed 不得包含“已经完成/已经发送”等完成性声明。

### 11.3 错误分类

统一错误码：

```text
provider_timeout
provider_rate_limited
provider_quota_exhausted
provider_http_error
provider_schema_invalid
provider_semantic_invalid
provider_language_invalid
provider_citation_invalid
insufficient_evidence
ambiguous_target
action_not_allowed
field_not_allowed
deadline_exhausted
```

用户安全事件只暴露稳定 error class；详细 Provider status、attempt、latency、usage、validation path 写入受控观测记录，不保存 secret 或完整 Prompt。

### 11.4 重试规则

- timeout、429、可恢复 5xx：在总 deadline 内指数退避，最多两次 Provider attempt。
- Schema/semantic invalid：返回精确 validation path 进行一次 repair attempt。
- permission denied、ambiguous target、insufficient evidence：不重试，返回可解释结果。
- deadline 剩余不足：不发起新请求，直接进入 degraded fan-in。
- 不允许用 deterministic fallback 冒充真实模型调用成功。

### 11.5 Model Gateway 与角色路由

所有 LLM 调用通过统一 Model Gateway，业务服务不直接拼接 Provider URL。Gateway 根据 role 读取版本化 `ModelProfile`：

```json
{
  "profile_id": "planner.zh.structured.v1",
  "provider": "openrouter-compatible",
  "model_id": "google/gemini-2.5-flash",
  "allowed_roles": ["planner"],
  "supports_strict_json_schema": true,
  "response_language": "zh-Hans",
  "temperature": 0,
  "max_output_tokens": 1400,
  "request_timeout_seconds": 25,
  "max_attempts": 2,
  "data_policy": "permission-filtered-only"
}
```

`model_id` 不是从用户 Query 动态选择，也不由 Agent 自己切换。生产配置加载时校验 profile；报告必须记录真实 provider/model/profile，不只写显示名称。

建议角色策略：

| Role | 主要能力 | Temperature | 输出预算 | 选择原则 |
| --- | --- | ---: | ---: | --- |
| Planner | 中文语义拆解、严格 JSON | 0 | 1,400 | Schema adherence 和 ActionSlot exact 优先 |
| Risk | 证据归纳、规则解释 | 0–0.1 | 1,600 | Grounded claim precision 优先 |
| Daily | 长上下文压缩、中文写作 | 0.1–0.2 | 2,200 | 完整性、稳定格式、成本平衡 |
| Action | 严格字段和值生成 | 0 | 1,200 | Safety、schema、target accuracy 优先 |
| Composer | 多结果合并、自然对话 | 0.1 | 2,000 | 不新增事实、中文可读性优先 |

当前 `google/gemini-2.5-flash` 只保留为 r75 baseline profile。Stage12 模型选择通过 V2 Case 对当前 profile 和候选 profile 做盲测；在结果出来前不预设“更贵模型必然更好”。允许不同角色选择不同 profile，但同一角色在一个评测 round 内必须固定。

### 11.6 Prompt 组成与 Token 预算

Prompt 分层且可版本化：

```text
System Policy
-> Role Contract
-> Output JSON Schema
-> Objective
-> Authorized Schema Summary
-> EvidenceBundle
-> Explicit Deny/Degrade Rules
```

不得把完整聊天历史、完整 workspace 或其他 Objective 的无关 evidence 注入每个 Specialist。Token budget 先分配给 required evidence，再分配给 allowed supporting evidence；不得按字符串尾部粗暴截断 JSON。

预算超限时按以下顺序压缩：

1. 删除重复 display text，保留 typed facts。
2. 用确定性 aggregate 替代全量 record 正文。
3. 删除低 rank 的 supporting evidence，不删除 required evidence。
4. 将长文本替换为有 source ref 的 extract。
5. required evidence 仍超限时转后台任务或明确拒绝完整回答。

### 11.7 Provider 响应验证和 Repair

Provider 返回后依次执行：

```text
HTTP/usage validation
-> JSON parse
-> JSON Schema validation
-> canonical enum normalization
-> evidence/citation validation
-> permission/candidate validation
-> field type validation
-> forbidden completion-claim validation
-> language validation
```

Repair request只发送：原 schema、原目标、validation path 和上一次受限输出，不附加新的业务证据。示例 validation path：

```text
$.action_type: value "update_record" is not canonical; allowed=["record.update"]
$.citations[1]: evidence_id "ev-99" not present
$.assignments.priority: value "urgent" not in allowed enum
```

Repair 仍失败时保留具体失败类并进入 degraded/denied，不再进行第三次“碰运气”调用。
