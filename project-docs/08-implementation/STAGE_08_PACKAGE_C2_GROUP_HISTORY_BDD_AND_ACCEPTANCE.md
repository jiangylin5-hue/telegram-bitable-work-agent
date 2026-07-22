# Stage08 Package C2：群长窗口与历史 Context BDD、数据治理门禁与验收合同

## Status

- Document status：implemented / C2 Tasks 1–6 independently reviewed complete。
- Scope：为后续 C3/Package E 提供内部、短命、受权、最多 120 片段的群长窗口与压缩信号；C2 自身不调用 Provider，不持久化 digest。
- Current Progress：2026-07-20 C2 Tasks 1–6 已完成任务级 TDD、真实 disposable PostgreSQL drift/privacy/concurrency 收口与最终独立复审。首轮 Task 6 发现的 partial 零片段和 D6 `group` scope category 两个 Important 已限定修复；新一轮复审为 `PASS / 0 Critical / 0 Important / 0 Minor`。唯一 Alembic head 为 `20260720_0031`，C2/C1 指定回归 `151 passed`。C2 现已关闭并允许 C3 开始；C3、Package D–F、真实 Provider 评测和部署仍未完成。
- Decision authority：`decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`。

## 1. 已确认门禁

| Decision | Binding value |
| --- | --- |
| D1 | 仅新到达的授权 group/supergroup 消息与 known edit 创建受控投影；历史 `Message.raw_text`、`raw_caption`、`normalized_text` 不读取、不回填，也不由 C2 删除。 |
| D2 | 30 天 retention；最多 120 fragments；每片段 500 Unicode code points；raw window 最多 60,000 code points；最终群 Context 最多 24,000 code points；最新 24 fragments 最多 12,000；临时 digest 最多 12,000；history half-life 7 天。 |
| D3 | `best_effort_group_deletion`：known edit、server-authorized purge 和 retention expiry 是可靠失效事实；普通群远端 delete/revoke 无通用可信 Bot API event，不承诺自动立即失效。 |
| D4 | 一个 active Stage06 `chat_user` binding 只能对应一个同 workspace customer `PlatformRecord` 和一个 project `PlatformRecord`；null、多值、歧义或 drift 均 fail closed。 |
| D5 | 仅内部 `Stage08GroupContextAuthorityFactory` 可从 verified actor/employee/current workspace 创建非 Pydantic、非 JSON 的 private authority；任何外部 carrier 均无资格。 |
| D6 | `label=group_context`，`source_type=group_message_fragment`，display id `group_context:NN`；scope 只暴露 `workspace/group/customer/project` 维度类别，不暴露值。C3 前 C2 不可被消费；C3 独占 merge、全局预算与 renderer。 |

任一 authority、binding、mapping、workspace、member、employee、business relation 或 lifecycle 不可证明时，必须在查询正文前返回 `group_context_unavailable`。

## 2. Scope 与非目标

### C2 做什么

- 允许既有 verified local ingress transaction 在同一本地事务内，为 new/edited authorized group/supergroup update 写入最多 500 code points 的 `content_fragment`。
- 只从当前受控投影读取，并在 employee/caller/member scope、active binding、D4 mapping、business scope、lifecycle 和 retention 交集内选择单一群源。
- 按 `event_at DESC, internal_tiebreak DESC` 保留最新 24 片段，history 仅用 7 天 half-life 时间衰减；最多选择 120 片段和 60,000 code points。
- 输出 internal-only `GroupContextWindow` 及 `compression_required = raw_selected_chars > 24000`。

### C2 不做什么

- 不新增 Telegram 网络、webhook endpoint、polling、outgoing request、历史 raw read、公开 API、permission/action 或前端。
- 不回填历史消息，不读取完整群或跨群/跨 workspace/private/channel 内容。
- 不调用 Provider，不生成 digest，不改 C1，不实现 C3 merge/global budget/renderer。
- 不将 fragment、window、digest 或 source-version set 写入 `MemoryItem`、candidate、database（受控 projection 除外）、Redis、RAG/pgvector、`AgentRun`、audit、log 或 LangGraph checkpoint。

## 3. 内部合同

```text
verified actor + employee + current workspace
 -> Stage08GroupContextAuthorityFactory
 -> private _GroupContextAuthority
 -> active binding/mapping/business/lifecycle re-read
 -> private GroupContextWindow + compression_required
 -> C3 merge/global budget
 -> Package E ContextCompressor (future, only when required)
 -> one-invocation group Context
```

| Type | 最小安全形状 | 禁止 |
| --- | --- | --- |
| `_GroupContextAuthority` | verified actor/employee/current workspace 解析结果 | BaseModel、JSON、HTTP/Telegram/outbox/audit/client construction |
| `GroupContextBudget` | 30 天、120 fragments、500/item、60,000 raw、24,000 final、24 newest、12,000 newest、12,000 digest、7-day half-life | client override |
| `GroupContextWindow` | private fragments/source-version handles；可验证投影仅 status/count/budget/compression signal | 对外序列化 text、ID、source ref、scope value |
| `GroupMessageEvidence` | `group_context:NN`、`group_context`、`group_message_fragment`、scope dimension categories | UUID、Telegram/binding/message/source ID |

`event_at` 固定来自 Telegram `message.date` 转 UTC；late delivery 仅影响入库时间，不改变事件顺序。known edit 写入新 `content_version`、将旧版本标记 `superseded`。server-authorized purge 与 expiry 必须幂等擦除 `content_fragment`并标记 `purged`。

## 4. Status 与 omission

| `GroupContextWindow.status` | 触发条件 | 输出边界 |
| --- | --- | --- |
| `group_context_unavailable` | authority/scope/mapping 无效；private/channel；无 eligible source；全部 re-read drift | 空 fragments；仅固定安全 status/count omission |
| `group_context_partial` | 至少一个安全 fragment，但有 count、char、age 或 budget omission | 仅当前选中 fragment 与 count-only omission |
| `group_context_available` | 至少一个安全 fragment，且无 eligibility/age/count/char/budget omission | 仅当前重读通过的 fragment |

`group_context_available` 不表示普通群远端 delete/revoke 已被可靠观测。所有 omission 只能暴露计数或固定类别，不得暴露 identity/text。

## 5. BDD

### C2-B01：旧 raw 永不是 C2 source

Given 数据库中存在历史 `Message` raw 字段
When C2 构建群 Context
Then 不枚举、不读取、不回填这些字段
And 只使用功能启用后 new/edited authorized ingress 创建的受控投影。

### C2-B02：scope 只收窄

Given server-created private authority
When 解析群源
Then 仅接受 single active `chat_user` binding、same-workspace active member/employee/caller 和当前 D4 mapping
And 任一 null、歧义、workspace 不同、relation drift、private 或 channel 在正文读取前 fail closed。

### C2-B03：窗口有界且确定

Given 30 天内的合格 active projections
When C2 选择窗口
Then 每项最多 500 code points，总数最多 120，raw window 最多 60,000 code points
And 最新 24 项按 `event_at DESC, internal_tiebreak DESC` 保留，最多 12,000 code points
And history 仅按 7 天 half-life、`event_at DESC` 与内部 tiebreak 排序，不使用 query、正文、embedding 或 LLM。

### C2-B04：压缩信号不是压缩执行

Given 已选 raw fragments
When C2 完成 window
Then 精确计算 `compression_required = raw_selected_chars > 24000`
And C2 不调用 Provider、不生成 digest、不合并 C1
And 仅未来 Package E 可在 C3 全局预算后生成最多 12,000 code points 的 process-local digest。

### C2-B05：version、purge、retention 与 authority drift fail closed

Given plan/window 构建后任一 version、mapping、member、scope、purge 或 retention 状态变化
When 下游准备消费
Then 重读当前状态，丢弃旧 window/digest 并从当前投影重建
And 不把 stale text 降级为 Memory 或 general advice。

### C2-B06：`best_effort_group_deletion` 语义诚实

Given 普通群远端 delete/revoke 没有可信通用 Bot API event
When C2 评估 lifecycle
Then 只把 known edit、server-authorized purge 和 retention expiry 当作可靠失效事实
And 不声称未知远端删除已被观测。

### C2-B07：Context / Memory 隔离

Given fragment、window 或未来 digest 包含可复用的结论
When 当前 invocation 结束
Then 该 Context 被丢弃，不写 `MemoryItem`、candidate、database、Redis、RAG/pgvector、`AgentRun`、audit、log 或 checkpoint
And 任何长期结论只能通过既有 Package B 门槛。

## 6. Acceptance Matrix

| Requirement | 已证明 | 最低证据 |
| --- | --- | --- |
| C2-A01 governance | D1–D6、受控 ingress 例外、旧 raw 拒绝 | decision record + unit negative |
| C2-A02 mapping/authority | inactive/ambiguous/wrong workspace/private/channel/relation drift 拒绝 | unit + disposable local PostgreSQL re-read |
| C2-A03 budget/order | 30/120/500/60,000/24,000/24/12,000/7-day 边界、排序、status/omission | table-driven unit |
| C2-A04 lifecycle | edit version、expiry、authorized purge、binding/relation drift 不泄漏；不伪造普通群远端删除事实 | real local PostgreSQL |
| C2-A05 privacy | 公开投影/renderer/audit/log/error 无 text/identity carrier；digest 无持久化 | negative serialization + static scan |
| C2-A06 isolation | 无 Provider/Telegram network/API/Memory/RAG/Redis/LangGraph/C1 mutation | scoped diff + regressions |

C2-A01–C2-A06 均已由 Tasks 1–6 的 decision/unit/disposable PostgreSQL/negative serialization/static/diff 证据与最终独立复审关闭。该结论仅关闭 C2；C3 尚未实施，Package C、Stage08、真实 Provider 评测与生产部署均不因此通过。
