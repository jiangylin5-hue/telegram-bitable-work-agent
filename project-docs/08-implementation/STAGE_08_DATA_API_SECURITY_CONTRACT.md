# Stage08 数据、API 与安全合同

## Status

- Current Progress Update (2026-07-22)：Package E 已关闭，`POST /api/stage08/assistant/query` 已实现为唯一 E4 public route：strict body、服务端 identity/scope 派生、E1–E5 coordinator、safe-view-only response、versioned safe replay projection 与固定脱敏错误映射。E final re-review `0 Critical / 0 Important / 0 Minor`；没有新增 schema/权限/Provider/Telegram/部署。真实 Provider transport timeout/cancellation 与质量评测属于 F。
- Current Progress Update (2026-07-22)：E3 已实现内部 Policy Gate、safe ticket/Gateway/draft 路由、hash-only idempotency 和最小审计投影；合法 Analysis Provider unavailable 仅返回无 payload 的 `degraded` safe view。最终独立审查 `0 Critical / 0 Important / 0 Minor`，但 `POST /api/stage08/assistant/query` 仍不存在，E4 将按既有 strict API 合同实现该唯一入口。
- Current Progress Update (2026-07-22)：E2 已实现内部 C3/D4 read service，但仍没有 `POST /api/stage08/assistant/query`。它不写 AgentRun/audit/outbox/idempotency/draft；safe result 仅含 count/status/degradation，且群摘要、query、RAG evidence 均为 process-local。E3/E4 才会按本合同实现 Policy Gate、draft 及 API。
- Current Progress Update (2026-07-21)：E1 仅实现 private graph contract/topology，并已通过最终独立复审；规划中的 `POST /api/stage08/assistant/query` 仍不存在。E1 不会读取 C3/D4 数据、写入 AgentRun/audit、调用 Provider 或产生外部写入；后续 E2-E4 仍须按本合同逐项实现与取证。
- Current Progress Update (2026-07-21)：Package E 对 `POST /api/stage08/assistant/query`、private graph state、C3/D4 material、provider port、Policy Gate、draft/idempotency 和 AgentRun/audit redaction 的唯一详细合同已写入 `decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`。本文件的全局 API/permission 红线仍优先；E 代码尚未开始，不能将规划中的 query API 视为已可用。
- Scope：定义所有 Stage08 持久化对象、API 边界、权限计算、数据留存与安全行为。
- Status：planning contract；schema/API/permission 实现需按包获得独立确认。
- Current Progress：2026-07-19 C2 Task 1 中文 D3 合同与 Stage08 文档一致性正在 review；D1–D6 与 `best_effort_group_deletion` 已确认。C2 生产代码、schema、migration、UoW、测试、API 和外部调用均未实现。

## 1. 持久化对象

| 对象 | 关键字段 | 生命周期 | 安全要求 |
| --- | --- | --- | --- |
| `Stage08ExecutionTicket` | workspace/employee/actor、action、trace、budget、request fingerprint、status、tool summary | `planned → executing → succeeded\|denied\|failed\|cancelled\|timed_out\|expired` | trace 在 workspace 内唯一；`budget` 必为 JSON object，`tool_summary` 必为脱敏 JSON array，数据库约束拒绝其他 JSON 形状 |
| `MemoryItem` | type、scope、payload、source refs、confidence、version、supersedes、valid_until、deleted_at | active/conflicted/superseded/revoked/expired/deleted | payload 不含完整聊天/隐藏字段；保留 provenance |
| `KnowledgeSource` | type、workspace、source entity、content version、hash、validity | active/replaced/revoked/deleted | 真源指针、删除可追踪 |
| `KnowledgeChunk` | source、ordinal、text projection、embedding version、filters、status | pending/indexed/stale/deleted | 只索引可检索投影；可重建 |
| `MemoryExtractionCandidate` | source refs、candidate type、confidence、normalized payload、review/status | candidate/accepted/rejected/expired | 群聊自动提取仍需审计与冲突识别 |
| `AgentRun` 扩展 | graph version、plan summary、budget usage、retrieval/tool/memory refs | run 生命周期 | 不保存原始 prompt/response/CoT |
| `Stage08GroupBusinessContextBinding` | workspace、Stage06 chat-user binding、customer/project record、mapping version、status | `active\|inactive`；每个 binding 同时最多一个 active mapping | record 必须当前属于同 workspace；null/歧义/drift fail closed |
| `Stage08GroupMessageProjection` | source Message ref、mapping ref、`content_fragment`、content version、event/edit/retention time、lifecycle | `active\|superseded\|purged`；30 天过期后不可读 | 只对 new/edited authorized ingress 写入；fragment 最多 500 code points；purge/expiry 擦除正文 |

所有 scope 至少包含 `workspace_id`；客户、项目、群聊、base/table/view 为可选的收窄维度，绝不能用于扩大权限。

### 1.1 C2 D3 群 Context 数据合同（2026-07-19 confirmed）

C2 D2/D3 的唯一详细合同权威为 `decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`。其约束摘要如下：

- `Stage08GroupBusinessContextBinding` 含 `id`、`workspace_id`、`telegram_binding_id`、非空 `customer_record_id`、非空 `project_record_id`、`mapping_version`、`status`、`created_at`、`updated_at`；一个 Stage06 active `chat_user` binding 同时最多一个 active mapping。
- `Stage08GroupMessageProjection` 含 `id`、`source_message_id`、`business_context_binding_id`、`content_fragment`、`content_version`、`event_at`、可选 `edited_at`、`retention_expires_at`、`lifecycle_status`、`created_at`、`updated_at`。`(source_message_id, content_version)` 唯一；只有未过期 `active` 版本可读。
- `event_at` 只来自 Telegram `message.date` 转 UTC，`retention_expires_at = event_at + 30 days`。late delivery 不改变事件顺序；known edit 创建新 version 并 supersede 旧版本。
- `best_effort_group_deletion` 只把 known edit、server-authorized purge 和 retention expiry 视为可靠失效事实。普通群远端 delete/revoke 无通用可信 Bot API event，不承诺自动立即失效。
- 既有 verified local ingress transaction 可在同一本地事务中写 new/edited controlled projection；不新增 Telegram 网络、webhook endpoint、polling、outgoing request 或历史 raw read。
- 历史 `Message.raw_text`、`raw_caption`、`normalized_text` 不是 C2 input，不迁移、不回填，也不由 C2 删除。

### 1.2 C2 长窗口与不持久化压缩边界

- C2 仅从一个当前授权 group/supergroup 选择 30 天内最多 120 个片段；单片段 500 code points，raw window 最多 60,000 code points，history half-life 7 天。
- 最新 24 个 raw fragments 最多 12,000 code points；最终 group Context 最多 24,000 code points；未来 ephemeral digest 最多 12,000 code points。
- C2 只计算 `compression_required = raw_selected_chars > 24000`，不调用 Provider、不生成 digest。C3 负责 C1/C2 merge 与全局预算；Package E 是唯一未来 `ContextCompressor` Provider 调用所有者。
- `GroupContextWindow`、`GroupContextDigest` 和 private source-version set 均只在当前 invocation 的 process-local Context 中存活；不得进入 `MemoryItem`、candidate、database、Redis、RAG/pgvector、`AgentRun`、audit、log 或 LangGraph checkpoint。任何长期结论必须走既有 Package B 门槛。
- 内部 `Stage08GroupContextAuthorityFactory` 是 D5 authority 的唯一生产者；HTTP、Mini App、Telegram update、outbox、audit 与客户端 JSON 均不能构造非 Pydantic/非 JSON private authority。

## 2. API 合同

| API | 动作 | 请求限制 | 返回限制 |
| --- | --- | --- | --- |
| `POST /api/stage08/runtime/execute-plan` | 启动受控计划 | 类型化 tool/intent、idempotency key、无 raw prompt | ticket、脱敏工具摘要、固定错误码 |
| `GET /api/stage08/runtime/tickets/{id}` | 读取 ticket | 当前 workspace + ticket read 权限 | 不返回输入 payload 或原始输出 |
| `POST /api/stage08/memory/extractions/{id}/revoke` | 撤销自动记忆 | owner/manager + expected version | 新状态、审计引用 |
| `GET /api/stage08/memory` | 读取 Memory | workspace 与 relation scope | 仅返回当前 actor 可见 payload 投影 |
| `POST /api/stage08/knowledge/reindex` | 受控重建 | operator/manager、source allowlist、idempotency | job/ticket，不同步暴露文本 |
| `POST /api/stage08/assistant/query` | 面向用户的协调器入口 | employee/context intent、无客户端 scope 覆盖 | 标签化 answer、可访问引用、可选 draft ref |

API 不接受客户端提供的有效权限、字段白名单、Memory scope、retrieval filter、ticket 终态或审计内容；这些必须在服务端从身份与资源重新计算。

### Runtime API 的受控计划投影（2026-07-18 confirmed）

`POST /api/stage08/runtime/execute-plan` 的请求只可提供 `workspace_id`、`employee_id`、主 `action`、`trace_id`、`idempotency_key`、`budget` 和 1–7 条 `invocations`。服务端从已验证身份生成 `actor="user:{identity.user_id}"`、新的 `ticket_id` 和 `state=planned`；客户端不得提交或覆盖这三项。路由先验证调用者的 `digital_employee.invoke` 工作区权限，再交给 PolicyGate 和 Tool Gateway 重算员工、调用者、表/视图/字段交集。

同一计划只使用一张 ticket，按 invocation 原顺序执行并逐条持久化 `RedactedToolResult`。首个拒绝或失败会写入固定错误码、停止剩余调用并进入对应终态；所有调用成功才进入 `succeeded`。响应只返回 ticket 标识、终态与脱敏摘要，绝不返回输入 payload、原始模型内容、权限投影、字段白名单、审计状态或任意 raw 内容。

## 3. 权限算法

有效权限：

```text
employee configured scope
∩ caller workspace/base/table/view/field permission
∩ current Telegram chat binding scope (如果入口来自 Telegram)
∩ source relation scope (customer/project/group)
∩ source validity/deletion/retention state
```

检索前：先从 PostgreSQL 构造可读取 source/chunk 集合。检索后：再次核验每个结果的记录、字段、关系、版本和删除状态。任一步不确定均 fail closed。引用生成也复用同一投影；用户不能由 citation 得到不可读 ID、field key 或正文。

## 4. Memory 与留存

- 表格确认事件可自动写入 Memory；群聊提取必须属于允许类型、来源完整、置信度达到部署配置阈值且通过 conflict detection。
- 文件只作为 `KnowledgeSource`，不自动转 Memory。
- Memory deletion、source deletion、权限撤销、TTL 过期必须使对应 chunk/index 失效；异步删除允许短暂队列态，但读取路径必须同步拒绝失效内容。
- `MemoryItem` 不可静默覆盖；新事实创建新版本，旧项标记 `superseded` 或 `conflicted`。
- 所有创建、替代、撤销、过期、删除、reindex 记入 audit，且审计自身不保存敏感正文。

## 5. Action tier 与执行票据

| Tier | 允许动作 | ticket | 确认 |
| --- | --- | --- | --- |
| `read_only` | 查表、检索、分析、引用 | 要求 | 不要求 |
| `draft_only` | 创建任务/记录/通知草稿 | 要求 | 草稿后要求 |
| `low_risk_auto` | 明确批准的内部状态更新 | 要求 | 按动作策略 |
| `restricted_test_chat` | allowlist 测试群自动回复/建任务 | 要求 | 配置与执行均要求 |
| `external_high_risk` | 群发、账户、资金、外部 provider 写 | 默认拒绝 | 单独架构与用户授权 |

ticket 的状态转换只能是 `planned -> executing -> succeeded|denied|failed|cancelled|timed_out|expired`，不可从任意终态回到运行中。`pending_confirmation / confirmed` 只属于既有 `record_change_draft`，不属于 execution ticket。每次执行由 `idempotency_key + request_fingerprint` 保护；同键同请求重放返回既有安全结果，同键异请求拒绝。创建 ticket 时必须先对目标 workspace 取得受控的行级互斥锁，再在该锁内完成 trace 预检、幂等预检和 ticket 创建；锁的目的是把同一 workspace 内的竞态串行化，不能用它扩大 workspace 或 employee 权限。

## 6. 观测与红线

可记录：计数、耗时、模型/provider 名称、token/成本聚合、tool 名称/状态、chunk 数、Memory ID、固定错误码、hash/trace。不得记录：密钥、原始群聊、原始文件、完整 prompt/response、隐藏字段、未授权引用、模型思维链。

## 7. 已确认的 Package B 配置与 B3 契约对齐（2026-07-18）

### 7.1 表格 Memory Policy

Task B3 仅复用 `PlatformTable.settings["memory_policy"]`，不新增表、公开 API、权限角色或客户端可写入口。用户已确认 policy `version=1` 的首个规则形状：

```json
{
  "version": 1,
  "rules": [{
    "memory_type": "decision",
    "identity_field_keys": ["customer", "subject"],
    "payload_field_keys": ["decision", "status"],
    "scope_field_keys": {
      "customer_record_id": "customer",
      "project_record_id": "project"
    },
    "valid_for_days": 90
  }]
}
```

无该配置、规则版本不支持、字段不存在、字段不可读、scope 引用无效或草稿状态不是 `confirmed` 时，服务 fail closed：不创建 outbox、不创建 Memory、不触发外部调用。

### 7.2 内部 Identity Token（2026-07-18 confirmed）

`identity_field_keys` 是已确认的业务去重语义，不能被 B2 现有“仅按 scope”算法静默忽略。拟在 `MemoryScopeProjection` 加入仅服务端生成的 `identity_token`：它是规则版本、表、memory type 和 policy 列出的可读 identity 字段值的 canonical HMAC-SHA256 摘要；原始值不进入 token、outbox、audit、API 或日志。token 会随 Memory scope 持久化以支持版本链比较，但 `GET /api/stage08/memory` 及任何其他安全读取投影会强制排除该字段。该字段不接受客户端输入，不扩展 scope 权限，也不需要迁移。该设计新增一个非公开部署密钥 `STAGE08_MEMORY_IDENTITY_HMAC_KEY`：B3 materializer 启用的环境必须配置它，测试使用显式注入的固定测试值；不得复用 Telegram、provider 或 webhook 密钥。

当前批准的 B3 enqueue interface 为单事件接口，因此 `memory_policy.rules` 必须**恰好一条**有效规则；零条或多条规则均 fail closed，不创建 outbox 或 Memory。多规则策略须先单独设计并确认 multi-event contract，不能静默丢弃规则。

### 7.3 Confirmed-record Outbox

`stage08.memory.confirmed_record.v1` 的 payload 只包含 `workspace_id`、`table_id`、`record_id`、`record_version`、`policy_version` 和 `rule_index`；不含 record values、field key、identity token、聊天文本或任何 provider/Telegram 数据。幂等键由同一组 reference 字段构成。materializer 在事务内重读当前 record，按 policy 与调用者字段可见性重建受限投影，然后才调用 Memory service 与审计；成功后才把 outbox 标为 terminal。

### 7.4 Group Candidate 阈值

Task B4 的部署配置最低置信度固定为 `0.85`。低于该值的群聊提取不创建 candidate；达到阈值仍必须通过绑定、scope、字段可见性、来源完整性与冲突检测。该确认不授权真实 Telegram 发送、Provider 写入或生产部署。
