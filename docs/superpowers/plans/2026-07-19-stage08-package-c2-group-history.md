# Stage08 Package C2 Group History Plan（长 Context 合同对齐版）

## Status

- Plan status：superseded execution sequence / Task 1 documentation in review。
- Scope：保留 C2 群历史计划入口，并将其合同对齐到已确认的长 Context 方案。
- Current Progress：2026-07-19 Task 1 中文 D3 决策记录与 Stage08 文档一致性正在 review；C2 生产代码、schema、migration、UoW、测试、API 和外部调用均未实现。
- Execution authority：`docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`。本文不得作为旧短窗口实施依据。
- Decision authority：`project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`。

## Goal

在既有 verified Telegram ingress transaction 中，仅为 new/edited authorized group/supergroup message 写入最小受控投影；C2 重读当前 authority、mapping、business scope、lifecycle 与 retention，构建最多 120 片段的私有长窗口，并只输出压缩信号。该窗口是 Context，不是 Memory。

## Confirmed Contract

| Key | Confirmed value | Fail-closed behavior |
| --- | --- | --- |
| D1 | 新到达的授权 group/supergroup 消息和 known edit 可建受控投影；历史 `Message.raw_text`、`raw_caption`、`normalized_text` 不读、不回填，本任务不删旧行 | 无新投影时 unavailable，不查 raw column |
| D2 | 30 天 retention；120 fragments；500 code points/item；60,000 raw；24,000 final；最新 24 项/12,000；digest 12,000；7-day half-life | 超过 count/char/age/budget 只产生安全 omission |
| D3 | `best_effort_group_deletion`；known edit、authorized purge、expiry 可靠；普通群远端 delete/revoke 不可靠观测 | 不虚构删除事实；只按已知 lifecycle 与 30 天 retention 收窄 |
| D4 | 一个 active Stage06 `chat_user` binding 唯一映射一个同 workspace customer record 和一个 project record | null/多值/歧义/drift/wrong workspace 全部 unavailable |
| D5 | 仅 `Stage08GroupContextAuthorityFactory` 从 verified actor/employee/current workspace 产生非 Pydantic、非 JSON private authority | 客户端、HTTP、Mini App、Telegram update、outbox/audit carrier 全部拒绝 |
| D6 | `group_context`、`group_message_fragment`、`group_context:NN`；scope 只暴露维度类别；C3 拥有 merge/global budget/renderer | C3 前 C2 window 不可消费 |

`event_at` 精确来自 Telegram `message.date` 转 UTC。late delivery 只影响入库时间，不改变源事件顺序。known edit 创建新 `content_version` 并使旧版本 `superseded`；server-authorized purge 与 expiry 擦除 `content_fragment` 并标记 `purged`。

## Permitted Ingress Exception

C2 不新增 Telegram network、webhook endpoint、polling、outgoing request 或 historical raw read。唯一允许的入站变更是：既有 verified local ingress transaction 可在同一本地事务中，为 new/edited authorized update 写入最多 500 code points 的 controlled projection。该例外不授权历史回填、Telegram 发送、Provider 调用、Memory 写入或新 API。

## Long-Window and Compression Boundary

1. C2 只从一个当前受权 group/supergroup 选择 30 天内 active fragments。
2. 每片段最多 500 code points，最多 120 片段，raw work window 最多 60,000 code points。
3. 最新 24 片段按 `event_at DESC, internal_tiebreak DESC` 保留，最多 12,000 code points；其余 history 仅按 7 天 half-life 时间衰减。
4. C2 只设置 `compression_required = raw_selected_chars > 24000`，不调用 Provider 也不生成 digest。
5. C3 负责 C1/C2 merge 与全局预算；仅未来 Package E 可调用 `ContextCompressor`，生成最多 12,000 code points 的 process-local digest，与最新 raw fragments 组成最多 24,000 code points 的群 Context。
6. window/digest/source-version set 不得写入 `MemoryItem`、candidate、database、Redis、RAG/pgvector、`AgentRun`、audit、log 或 LangGraph checkpoint。任何长期结论必须走 Package B。

## Status and Omission

| Status | Exact rule |
| --- | --- |
| `group_context_unavailable` | invalid authority/scope/mapping、private/channel、no eligible source 或 all-source re-read drift；空 fragments，只输出安全 status/count |
| `group_context_partial` | 至少一个 safe fragment，但存在 count/char/age/budget omission；仅 count-only omission |
| `group_context_available` | 至少一个 safe fragment，且无 eligibility/age/count/char/budget omission |

## Current Task Sequence

| Task | 产物 | Gate |
| --- | --- | --- |
| Task 1 | D3 decision record 与 Stage08 文档合同一致性 | 当前正在 review；仅文档 |
| Task 2 | mapping/projection schema、migration 与 UoW parity | Task 1 review clean 后才可开始 |
| Task 3 | trusted local ingress projection 与 best-effort lifecycle | Task 2 schema/UoW |
| Task 4 | opaque authority、window contracts、selector 与 purge service | Task 2–3 |
| Task 5 | real local PostgreSQL drift/privacy/package evidence | Task 2–4 |
| Task 6 | independent review 与 C3/E 交接 | Task 5 focused verification |

逐文件、逐步命令和未来 RED/GREEN 期望只以 `2026-07-19-stage08-package-c2-long-context-implementation.md` 为准。本 Task 1 不执行 schema、migration、测试、Provider、Telegram 或任何外部调用，也不宣称实现或生产就绪。
