# Stage08 C2：可信来源群类型持久化提案

## Status

- Document status：`approved decision / implemented / Task 4 independently reviewed`。
- Scope：仅解决 C2 在后续 authority/window 重读时，如何无需外部网络调用而可靠区分 `group`、`supergroup` 与 `channel`。
- Current Progress：用户已于 2026-07-20 确认本提案；`20260720_0031` migration、verified ingress provenance、SQL eligibility 与 fresh materialization fail-closed 已实现，C2 Task 4 独立复审通过，Task 5 真实 PostgreSQL drift/privacy/concurrency 收口完成。Task 6 首轮独立审查发现的两个 Important 规格偏差与本文档状态漂移已限定修正，新一轮独立复审为 `PASS / 0 Critical / 0 Important / 0 Minor`。C2 已关闭并允许 C3 开始。本实现没有扩大至 API、Telegram 网络、Provider、Memory 或 RAG。
- Decision：采用不可变 `source_chat_type` provenance；迁移前历史 projection 为 `unknown` 且不可读。

## 1. 触发原因

Telegram 的 `group`、`supergroup` 与 `channel` 都可能使用负数 chat ID。因此，C2 仅凭已有 Stage06 `chat_user` binding 的 `telegram_chat_id`，无法在窗口读取或清理时证明来源不是频道。

此问题不能通过下列方式解决：

| 方案 | 结论 | 原因 |
| --- | --- | --- |
| chat ID 正负号推断 | 拒绝 | 负数不能区分群与频道，违反 fail-closed。 |
| 读取历史 `Message.raw_*` | 禁止 | 违反 D1 原文治理。 |
| 调用 Telegram `getChat` | 禁止 | C2 不新增 Telegram 网络调用，也不应把远端响应当作当前窗口唯一真源。 |
| 使用 binding 的普通 `scope_policy` 值 | 拒绝 | 该值不是每条已验证入站来源的不可变 provenance，不能证明当前 source 类型。 |
| 把所有 C2 窗口一律禁用 | 不采用 | 虽然安全，但会让已确认的群聊 Context 业务能力不可用，偏离 Stage08 目标。 |

## 2. 推荐方案：不可变 `source_chat_type`

在 `stage08_group_message_projections` 增加一个仅含类型枚举的内部字段：

| 字段 | Proposed contract |
| --- | --- |
| `source_chat_type` | 非空字符串枚举：`group`、`supergroup`、`unknown`。不保存 chat ID、message ID、用户名、正文或其他身份信息。 |
| 新行写入 | 仅既有 secret-verified webhook 的 `message` / `edited_message` 已解析 `chat.type` 为 `group` 或 `supergroup` 时可创建 projection；写入后不可由 C2 修改。 |
| 历史行迁移 | 使用 `unknown`，并在 C2 authority/window 的资格查询中默认不可读。不会回填或扫描历史 `Message.raw_*`。 |
| 重读条件 | C2 仅选择 `source_chat_type IN ('group', 'supergroup')` 的 active、未过期、非空 projection。`unknown` 与任何未来非群类型均 fail closed。 |
| 数据约束 | PostgreSQL `CHECK` 只允许三个稳定值；默认 `unknown` 仅服务 migration 安全，不授权其成为可读 Context。 |

该字段是来源类别事实，不是用户可编辑配置，不进入公开 DTO、webhook 响应、审计、outbox、trace、Memory、RAG/vector、Provider、AgentRun 或 LangGraph checkpoint。

## 3. 最小实施范围（确认后）

1. 新增一份 C2 专用 Alembic migration，位于现有 `20260719_0030` 之后：增加字段、默认安全回填、`CHECK` 与 C2 source eligibility 索引调整；不改业务表、权限模型或公开 API。
2. 更新 `Stage08GroupMessageProjection` ORM 与 Task 3 ingress writer：仅使用已经验证的 parser `chat_type` 写入 `group`/`supergroup`；不新增 Telegram 请求，不触碰历史原文。
3. 更新 Task 4 UoW eligibility/count-only 查询与 authority 重读：仅读取 provenance 已证明的 group/supergroup projection；移除任何 chat ID 形状推断。
4. 增加 TDD 测试：
   - `channel` update 不创建 projection；
   - `unknown` historical projection 永远不进入窗口；
   - `group`/`supergroup` 行在重读时可用；
   - 非法枚举被数据库拒绝；
   - migration 后 source graph 只有一个 head；
   - public carriers 不含字段、正文或内部标识。
5. 重新执行 Task 4 独立复审与 C2 Task 5 package-level drift/privacy 验证。

## 4. 不做什么

- 不新建 Telegram API 调用、webhook endpoint、route、Mini App API 或权限动作。
- 不重写、删除或读取历史 `Message.raw_text`、`raw_caption`、`normalized_text`。
- 不将 `source_chat_type` 当作系统权限或业务事实；业务权限仍由 workspace/member/employee/binding/mapping/customer/project relation 共同重读。
- 不创建摘要、长期 Memory、RAG 向量、LLM 调用、外部写入或部署。

## 5. 验收标准

| Requirement | Evidence required |
| --- | --- |
| C2-CT01 | migration 的 `CHECK` 拒绝非法值，existing source graph 有唯一 head。 |
| C2-CT02 | verified `group`/`supergroup` ingress 写入对应类型；`channel` 不创建 projection。 |
| C2-CT03 | 历史 `unknown` 行不被读取，也不触发 raw 回填。 |
| C2-CT04 | authority/window 只选择 `group`/`supergroup`，任何 drift 后 fail closed。 |
| C2-CT05 | 无 source type、正文或 identity 从 C2 私有边界进入 API、audit、Memory、RAG、Provider 或日志。 |
| C2-CT06 | Task 4 修复回归、真实 local PostgreSQL 与独立复审均通过；默认遗留数据库 revision 风险仍单独记录，不混作生产通过。 |

## 6. User Confirmation

用户已确认：按本决策把 `source_chat_type` 作为 C2 projection 的内部、不可变 provenance 字段实施，并创建相应 migration。
