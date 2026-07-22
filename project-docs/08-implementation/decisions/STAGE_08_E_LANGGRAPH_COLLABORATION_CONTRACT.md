# Stage08 Package E：LangGraph 协作、私有状态与行动闸门合同

## Status

- Current Progress Update (2026-07-22)：E3 已按本合同完成；用户确认 `degraded` 仅表示经严格校验的分析 Provider unavailable，绝不携带 answer、citation、draft 或 Gateway side effect。E4 strict API 是下一项。
- Current Progress Update (2026-07-22)：用户已确认扩展 E1 `AssistantTerminalStatus`，增加 `degraded` 终态。该终态只表示 Analysis Provider unavailable 的安全降级，不允许草稿、Gateway 或外部调用；shape invalid/forged output 仍为 `failed`，Policy deny 仍为 `denied`。本次修改不扩 API、schema、权限、Provider 或 Telegram。
- Current Progress Update (2026-07-22)：E3-R1 safe context/intent/audit port 已实现并经独立复审关闭（`0 Critical / 0 Important`）；safe context 遇到既有 default ticket replay 一律 fail closed。该状态不等于 E3 关闭，尚缺 E3 atomic boundary/current-state lock/real PostgreSQL evidence 与 graph terminal integration。
- Current Progress Update (2026-07-22)：E3 首轮实现未通过独立复审，且用户已确认安全执行适配层。E3 现在允许仅服务端、默认关闭的 transaction/savepoint、共同 current-state locks、安全 audit mode 与 sealed field/value draft intent；默认 Stage06 runtime 行为不变。具体边界以 `STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md` 为准；E3 尚未关闭。
- Document status：`approved implementation boundary derived from the user-approved Stage08 architecture`
- Scope：Coordinator graph、私有 state、C3/D4 read fan-out、ContextCompressor/AnalysisProvider internal port、Policy Gate、draft routing、safe AgentRun/audit、assistant query API。
- Current Progress Update (2026-07-22)：E2 已关闭：C3 pending group handoff 与 D4 evidence 保持 invocation-private；binding/mapping/source/current-scope 证明在 C3 和 D4 各消费点重验；target 未经唯一 current mapping 证明时 fail closed；compressor/D4 errors 仅产生固定 degradation。最终 review `0 Critical / 0 Important / 0 Minor`，137 focused unit/17 local pgvector integration。E3 Policy Gate、ticket/draft、AgentRun/audit 与 API 仍未开始。

## 1. 不变的真源和禁止跨越的边界

1. PostgreSQL 仍是 workspace、成员、employee、view/field、record、Memory、KnowledgeSource/Chunk、ticket、draft 和 audit 的唯一真源；pgvector 仅是可重建 index。
2. C3 composite、D4 private evidence、群窗口、压缩 digest、query 和 Provider 输入/输出都是本次进程私有数据；禁止 checkpoint、Redis、database、AgentRun、audit、outbox、log、DTO 和 exception carrier。
3. Coordinator 不能调用 ORM/raw SQL、绕过 C1/C2/C3/D4、构造 authority、直接写 record、确认 draft、发送 Telegram 或调用外部 provider。
4. `document_projection` 与 `approved_summary` 继续因缺少 origin verifier fail closed。Package E 不能通过 graph 或 API 放宽该规则。
5. Provider 默认 unavailable；Package E 只定义可注入端口和 deterministic test adapter。真实 Provider 和质量证据只在 Package F。

## 2. 内部类型

| 类型 | 生命周期 | 允许字段/行为 |
| --- | --- | --- |
| `AssistantQueryCommand` | process-local | 服务端验证后的 workspace/employee/actor、intent、query、requested action、目标 record、idempotency；不可从 JSON 反序列化为 authority |
| `CollaborationBudget` | process-local | 固定深度 3、fan-out 3、retrieval 12、wall 30s、provider 20s、retry 2；客户端不能覆盖 |
| `Stage08CollaborationState` | process-local/non-serializable | command、actor、private composite/retrieval/digest、节点结果、取消和安全 terminal view；图无 checkpointer |
| `ReadOutcome` | process-local | `available/degraded/unavailable`、固定 reason、私有 evidence handle；没有 raw-to-safe 隐式转换 |
| `AnalysisDecision` | process-local validated | answer、citation ordinals、`read_only/draft_update/general_advice/deny`、可选 sealed draft intent；intent 可在 E3 内部承载一个受控 field/value，但不进入 DTO、日志、AgentRun/audit、checkpoint 或持久化 |
| `AssistantQuerySafeView` | API/AgentRun safe summary | status、answer、safe citations、降级码、可选 draft ref；没有 evidence/provider/authority/internal exception |

`ContextCompressor.compress(private_group_context, budget)` 与 `AnalysisProvider.analyse(private_material, command)` 必须只接受 private sealed object、返回严格内部 DTO；任何 object 构造、反序列化、shape drift 或 provider error 都视为 unavailable。

## 3. 状态机和动作

```text
queued -> planning -> reading -> analysing -> policy_check
       -> completed | draft_pending | degraded | denied | failed | cancelled | timed_out
```

- terminal state 不可逆；每个 terminal state 写一条最小 AgentRun/audit 摘要。
- `read_only` 只可进入 `completed/denied/failed/cancelled/timed_out`。
- `degraded` 只可由不可用的 Analysis Provider 产生，必须携带 `analysis_unavailable`，不得包含 answer、citation 或 draft ref，也不得调用 Gateway。
- `draft_update` 只能在 `policy_check` 通过后创建现有 ticket 和 `pending_confirmation` draft，进入 `draft_pending`；不得确认或写源 record。
- 取消、预算/超时、permission/source drift、private state failure 和 idempotency conflict 无副作用；已有 ticket 必须进入对应 terminal state，不留 running/planned orphan。
- E3 draft 路径必须在单一安全执行边界内完成：锁定并消费期重验 scope → reservation/ticket → Gateway → pending draft → safe terminal summary；任一失败回滚该边界。相同 idempotency key 在重验后重放原安全结果；不得以 record 的全局 pending-draft 数量识别结果。

## 4. API、权限和幂等

`POST /api/stage08/assistant/query` 的 body 精确包含 `workspace_id`、`employee_id`、`intent`、`query`、`requested_action`、可选 `target_record_id`、`idempotency_key`；extra field 一律 redacted 422。

调用者必须是 active workspace member，且拥有既有 `digital_employee.invoke` 权限；employee 必须 active、属于 workspace、成员 grant/employee scope 当前有效。views 只从 employee 当前 configured views 以稳定顺序选取最多三项；customer/project/group/retrieval/field scope 均由 C1/C2/D4 重新计算。target record 只是待验证资源选择，不构成有效 scope 或 draft values。

idempotency fingerprint 使用 hash-only normalized query。相同语义 replay 不重新运行 graph，但必须返回同一个严格 `AssistantQuerySafeView`；response reference 只能保存 versioned safe replay projection（status、已验证且有界的 answer、citation ordinal/label、degradation code、可选 draft ref），不得保存 query 或任何 private material/provider output/internal ID。不同语义 409。权威状态改变后 replay 必须重新验证 actor/employee/target read scope，失败则拒绝而不泄露旧结果；projection shape/version 无效时 409。详见 `STAGE_08_E4_SAFE_REPLAY_PROJECTION_DECISION.md`。

## 5. 审计、API 与错误脱敏

`AgentRun.input_summary/output_summary/tool_calls` 与 `OpsAuditEvent` 可记录：graph version、terminal state、action、计数、citation count、degradation/error code、hash/trace、ticket/draft 是否生成、聚合时延。不得记录 query、answer、群片段/digest、table/Memory/RAG 正文、hidden field、source/chunk/record UUID、field key、vector/score、provider response、secret、authority 或 CoT。

E3 的安全执行模式还适用于其复用的 ticket、Gateway 和 Stage06 draft-service 内部 AgentRun/audit：它们不得使用默认的实体 UUID/record audit payload，而须产出同一白名单摘要。业务表、ticket 和 draft 的 PostgreSQL 主键/外键不是 audit/API payload，仍按既有 schema 保存。

API 只返回安全 answer、稳定 ordinal citation label、降级码和可选 draft ref。权限错误 403；不存在的 workspace/employee/target 不泄露为 404；invalid input 为 422；幂等冲突/运行冲突为 409；Provider/读取失败映射为固定 safe terminal code。

## 6. 验收门槛

E-01：Coordinator 仅分解和汇总、专长节点无越权；E-02：fan-out/fan-in、budget、cancel、degrade、terminal mapper 正确；E-03：draft 先 policy、再既有 ticket/idempotency/audit，源 record 不变，且安全执行边界无 orphan/UUID audit 泄露。每项都需 unit + service/API + real local PostgreSQL evidence 和 fresh independent review。
