# Stage08 Package C Task C2：群最近窗口与历史上下文设计独立审查

## 审查结论

- Original verdict：`CONDITIONAL PASS — design only / implementation remains blocked`。
- Original finding count：`0 Critical / 2 Important / 2 Minor`。
- 结论范围：C2 的分包、默认拒绝、D1–D6 用户门禁、与 C1/B4 的隔离、无网络/无 API/无持久化正文边界均合理；它可以作为向用户征求决定的设计包，但**不是**实施授权。任何 C2 代码仍必须等待 D1–D6 全部明确确认、单独 D3 schema/data-contract 决策，以及写入最终参数的 implementation brief。
- 本审查未修改业务代码、测试、migration、路由、配置或外部状态；未运行 Telegram、Provider、HTTP、数据库写入或其他外部调用。

## 修正独立复审（2026-07-19）

- Verdict：`PASS — corrected design remains proposal-only`。
- Current finding count：`0 Critical / 0 Important / 0 Minor`。
- Remaining blockers：这不是实施许可。D1–D6 的用户明确确认、独立 D3 schema/data-contract decision、确认后的 task-level brief、migration 的 disposable local PostgreSQL 证据仍全部必需；它们是既定 product/data authority gate，不是本次文档修正遗留缺陷。

修正后的 BDD、plan 和 brief 已逐项对齐：

1. `received_at` 现在准确表述为 Telegram `message.date` 经 UTC 转换写入的初始 `event_at` **候选**，而不是纯服务端接收时间；D3 仍须决定是否批准，并补足时钟、时区、late delivery、edit/delete/version、stable tie 和旧行策略。
2. D2/D3 现明确区分 eligibility removal（`max_age`、retention）与 truncation/预算 omission（item/total/count），并给出仅待确认的 `group_context_unavailable` / `partial` / `available` matrix、空 evidence、固定安全 omission 与 renderer 行为。
3. D5 现将唯一 server-side factory、non-serializable authority construction boundary 和 re-read path 明确列为待用户确认；当前 Mini App、Telegram update、outbox/audit 均明确不可作为 producer。
4. D6 现把 `label=group_context`、`source_type=group_message_fragment`、`group_context:NN`、仅类别 scope 与 C3 独占 merge/global-budget/renderer 写成建议但未生效的待确认值；C3 前 C2 Pack 仍为 internal/non-consumable。

复核确认：所有上述 literal、profile、矩阵和 D5/D6 形状均用“推荐但未生效”或“用户必须确认/修改”限定，未将其偷设为当前配置、API、权限或实现行为。C1 v1、B4 group-Memory、D/E/F、外部网络与持久化边界均未被扩展。

## 审查范围与已读材料

已完整核对：

- `project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md`
- `docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md`
- `.superpowers/sdd/stage08-package-c-task-c2-brief.md`
- `.superpowers/sdd/stage08-package-c-task-c2-design-report.md`
- C1 brief/report/review、Package C BDD、Stage08 真源、复杂 Agent 架构、SDD、实施计划、数据/API/安全合同、测试计划、验收清单。
- 当前 `Message`、`Stage06TelegramBinding`、Stage06 UoW/binding、Stage07 identity 与 B4 group-Memory source 实现。

## 当前实现核验

| 设计前提 | 当前证据 | 审查判断 |
| --- | --- | --- |
| `Message` 没有可供 C2 直接依赖的 lifecycle/retention 事实 | `backend/app/models/telegram.py` 仅有 Telegram 标识、raw/normalized 文本、`received_at` 与处理状态；没有 content version、edit/delete/revoke 时间、retention 或持久化 chat type | 属实；D3 必须先于任何正文读取落地 |
| `received_at` 不是完整 C2 生命周期排序合同 | `backend/app/services/telegram_update_parser.py` 将 Telegram `message.date` 写入 `received_at`，但没有版本、编辑、删除、保留、chat type 或可审计的 C2 `event_at` 合同 | 需要更精确表述，见 I-01 |
| Stage06 binding 不足以推出客户/项目 PlatformRecord 映射 | `backend/app/models/stage06_platform.py` 的 binding 只有 workspace/member/chat/user/type/default base/employee/scope JSON/status；没有 version、group type 或 customer/project record 关系 | 属实；D4 不能把历史 `Message.customer_id` 当成 C1 record |
| 现有 UoW 没有安全的 message history projection | `Stage06PlatformUnitOfWork` 只暴露 binding 列表，不提供 Message lifecycle/read projection | 属实；D3/D5 必须定义新的受限 repository/service surface，而不能让 C2 直接查询 ORM |
| B4 group Memory 不可作为 C2 history adapter | `stage08_group_memory_source.py` 只接受短命 `TrustedGroupMessageInput`，生成 candidate 的 opaque source/scope，未读取历史 `Message` | 设计正确地隔离了 B4，不存在复用旁路 |
| C1 v1 不接受群 source/evidence | `stage08_context_contracts.py` 仅允许 table/Memory/general advice；C1 service 显式隔离 group Memory 与 Message | C2 的独立 Pack、C3 后合并安排正确 |

## 已满足的关键边界

1. D1–D6 缺任一项即 `group_context_unavailable`，并在 raw-column query 前拒绝，符合 fail-closed 要求。
2. recent 与 history 都有数量、年龄、字符、稳定排序和总预算门槛；history 禁止 query、关键词、embedding、LLM 与客户端相关性，未提前进入 D/E。
3. plan 不携带正文或 source list，compose 时重新读取 binding/member/relation/lifecycle/version；跨 workspace、ambiguous、private/channel、relation 漂移和旧行均拒绝。
4. 正文只允许短命 fragment；禁止持久化到 Memory、candidate、outbox、AgentRun、audit、cache、RAG/vector 与日志。B4 的 0.85 candidate path 未被错误复用。
5. 未引入 API、权限角色/action、Telegram 网络读写、Provider、Redis、RAG/pgvector、LangGraph、Package D/E/F 或 C1 v1 改动。
6. 推荐 profile 被明确标为 inactive，未被偷设为生效配置。

## Findings

### I-01：`received_at` 的事实表述过度，D3 必须明确其可否作为 event-time 候选

`STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md` 第 84 行称当前 `received_at` “仅是接收时间”。当前 parser 实际把 webhook payload 的 `message.date` 转为 UTC 后写入该字段。它仍不足以证明 C2 所需的编辑/删除/版本/留存、也未形成已批准的 `event_at` 数据合同，但不宜误述为纯服务端接收时刻。

**Required correction before implementation brief：** D3 应明确写明 `received_at` 是否可在受控 projection 中作为初始 Telegram message event time；若可，仍须规定时钟、时区、late delivery、edit/delete/version、stable tiebreak 与旧行的处理。若不可，则 migration/projection 必须提供新的 approved event-time fact。不得通过这项文字修正放宽 raw 读取门禁。

### I-02：不可用结果与 D2 的期满动作尚未形成可测试的精确合同

设计多处要求固定 `group_context_unavailable`，但 `GroupContextPack` 的拟议 `status`/omission 形状没有列出精确 literal、全失效时的状态、是否允许只返回 omission、以及 renderer 对 unavailable 的固定输出。D2 要求“期满动作”，推荐 profile 仅给出了 max age/half-life/字符数，并没有指定窗口期满、retention 到期、总预算耗尽与全项 omission 各自是 `unavailable`、普通 omission 还是交给 C3 的行为。

**Required correction before implementation brief：** 在 D2/D3 确认记录中固定无 source-carrier 的 unavailable DTO/status/omission matrix，并把 `max_age`、retention expiry 与 budget omission 分开定义。测试必须证明未确认、无 eligible source、全部 compose drift、单项超预算和正常 partial pack 不会被混为同一行为，更不能回退到其它群或全历史。

### M-01：D5 的 server-only authority 需要在决定记录中指定创建者与不可序列化边界

`opaque_binding_pointer` 是正确方向，但当前只是接口文字；Pydantic/普通 DTO 本身不能使一个字段不可伪造。C2 没有现成 coordinator/runtime entry，Stage07 Mini App identity 只解析用户身份，不能自动成为 C2 group authority。

**Required confirmation detail：** D5 必须指定一个已验证的服务端 producer、其接收的 identity/binding scope、authority 的非 HTTP/non-persistent construction boundary、重读方法及拒绝原因。不允许由 C2 route、Mini App、Telegram update、outbox/audit 或客户端 JSON 直接构造。

### M-02：D6 需要把 “label/type” 明确为字段配对，而不是只给两个词

推荐 `group_context / group_message_fragment` 与 C1 的 `label/source_type` 命名不同；C1 v1 不能兼容此配对是已知且正确的事实。C3 前不能伪装为 C1 的 `business_data`、`confirmed_memory` 或 `general_advice`。

**Required confirmation detail：** D6 应固定哪一个是 `label`、哪一个是 `source_type`、证据 ID 格式、scope category 的公开粒度、C3 的全局预算仲裁/renderer owner 以及 C2 Pack 在 C3 前的不可消费规则。

## 面向用户的最小确认清单（不代替用户作选择）

下列每项均需明确值；推荐 profile 仅是可选基线，未确认前不生效。

| 决定 | 需要确认的最小内容 | 可选/推荐信息（不默认采用） |
| --- | --- | --- |
| D1 原文治理 | 可读取的是历史 `Message` 原文、经治理的入站投影，还是暂时全面禁用；可用主体；旧 raw 的清理/回填/删除策略 | 优先选择受控、最小正文投影；不得把历史 raw 的存在视为授权 |
| D2 有界参数 | recent 条数、history 条数、最大年龄、half-life、单消息/群字符上限，以及窗口/预算/期满的精确行为 | 可接受或替换：recent 20、history 12、30 天、7 天、500 Unicode code points、群 6000 code points；仍受 C1 24 evidence/12000 chars 上限 |
| D3 lifecycle/schema/旧行 | content version、edit/delete/revoke、retention、event-time/stable tie、chat type 可信来源、migration/backfill 与所有旧行策略；并确认 `received_at` 是否只能作为受控 initial event-time 候选 | 缺失任一 lifecycle/version 事实的旧行保持不可读；需独立 migration/data-contract 决策和 local PostgreSQL 证据 |
| D4 业务关联 | active `chat_user` binding 与 C1 customer/project `PlatformRecord` 的精确、当前、可重读 mapping；null 是否可用及何种严格条件 | 不能使用历史 `Message.customer_id` 或 binding `scope_policy` 的未定义 JSON 语义作默认映射 |
| D5 可信入口 | 唯一 server-side authority producer、输入身份、authority 创建/传递/重读边界、何时失效 | client HTTP/Mini App/Telegram update/outbox/audit 不得提供 binding/chat/message/text 或反序列化 authority |
| D6 evidence/C3 | group evidence 的准确 label/type 配对、C3 merge owner、全局预算/renderer 归属、C2 Pack 在 C3 前的消费限制 | `group_context / group_message_fragment` 只是待选名称；不得伪装为 C1 label |

## 允许的下一步

收到 D1–D6 全部确认后，先创建独立 D3 decision/schema plan，并在新的 C2 implementation brief 中填入最终值、准确数据来源和新的受限 UoW projection。随后才可按 RED → minimal GREEN → focused unit → disposable local PostgreSQL → independent review 实施。若确认引入 API、role/action、网络读取、C1 修改、B4 Memory 复用、D/E/F 功能或外部写入，必须作为新的偏差/扩展单独讨论。
