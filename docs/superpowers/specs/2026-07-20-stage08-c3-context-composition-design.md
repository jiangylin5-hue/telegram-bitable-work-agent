# Stage08 C3：C1/C2 上下文合成、总预算与私有 Renderer 设计

## Status

- Document status：`approved implementation boundary derived from confirmed C1/C2 contracts`。
- Scope：只实现 Package C 的 C3 私有合成层：C1 `ContextPack` 与 C2 `GroupContextWindow` 的当前状态重读、内容级全局预算、压缩信号传递、统一私有 renderer、local PostgreSQL 回归与包级安全收口。
- Preconditions：C1 已独立复审通过；C2 Tasks 1–6 已最终复审通过；本设计不改变 C1/C2 已确认的 schema、API、权限、retention 或 D1–D6 语义。
- Out of scope：`ContextCompressor`、Provider/LLM、Telegram 网络、Memory/RAG/vector/Redis、LangGraph、公开 API、Mini App、持久化 digest、部署和生产定时任务。

## 1. 目标与非目标

C3 把两类已受限来源编排成同一次调用可用的、可重新验证的私有 Context：

```text
C1 ContextPlan -> current authorized table/Memory/general-advice pack
                                      \
                                       C3 private composite -> Package E only
                                      /
C2 authority -> current group window / compression signal
```

它不是新的读取权限、执行票据、公开 DTO 或持久化对象。任何调用结束后，组合包、渲染文本、group fragment 与未来 digest 都必须丢弃。

## 2. 固定数据与预算合同

| 项目 | 固定规则 |
| --- | --- |
| C1 内容预算 | 沿用已确认 `ContextBudget.max_total_chars <= 12,000`，只计 C1 evidence canonical JSON content。 |
| C2 直接群内容预算 | 沿用 D2：无压缩路径最多 24,000 code points；C2 原始选择最多 60,000 code points，120 fragments，单片段 500。 |
| C3 全局内容预算 | `36,000` code points，等于已确认 C1 12,000 与已确认的直接群内容 24,000 之和；计入 evidence content 与 group fragment text，不计私有 renderer 的固定结构头。C3 不可超出此值。 |
| C3 item 上限 | 继承 C1 最多 24 条 evidence；无压缩群路径最多 120 条 C2 fragment，合计最多 144 条私有渲染 block。 |
| 压缩门槛 | 只信任 C2 的 `compression_required = raw_selected_chars > 24,000`；C3 不自行重新解释 60,000/24,000 边界。 |
| C3 压缩行为 | 若 C2 要求压缩，C3 不读取/渲染其原始正文，不创建 digest；只持有不可序列化的 group window 与 `compression_pending` 私有状态，供 Package E 的唯一 `ContextCompressor` 使用。 |

`36,000` 是内容预算，不是模型 token 限额，也不授权 Package E 绕过其执行预算。Package E 在将 renderer 文本放进最终模型调用前仍须叠加自己的 token/provider/timeout 预算。

## 3. 数据形状和可见性

### 3.1 Private composite

`_Stage08CompositeContext` 仅由 C3 service 创建，必须满足：

- 使用普通私有 Python object 与 `__slots__`；不是 Pydantic，不可 JSON 序列化，`repr` 不含正文、UUID、chat/message/source 标识。
- 仅保存已验证的 C1 plan、server-derived actor、C1 private pack、C2 opaque authority/window 和安全 view；不得保存原始 Telegram update、`Message` 或历史 raw 字段。
- 只可由 C3 renderer / Package E 内部调用使用；HTTP、Mini App、audit、outbox、cache、Memory、RAG/vector、AgentRun、checkpoint 和日志都不能消费该对象。

### 3.2 Safe view

可公开给内部观测代码的 `CompositeContextView` 只包含：

- 固定 contract version；
- `internal_evidence`、`group_compression_pending`、`general_advice_only` 或 `no_evidence` 状态；
- C1 evidence count/content char count；
- C2 group status、selected fragment count、raw selected chars 和 `compression_required`；
- 合计内容字符数和 `within_global_budget` 布尔值。

它不得包含正文、scope 值、任何 UUID、chat/message/update/binding/mapping/source identifier、plan actor 或异常诊断文本。

### 3.3 Group evidence 形状

无压缩路径经 C2 fresh materialization 后，每条群内容在私有 renderer 中固定为：

```text
[group_context:01 label=group_context type=group_message_fragment scope=workspace/group/customer/project]
<controlled fragment>
```

`group_context:NN`、label、type 和 scope 仅是已确认 D6 类别；不输出 group/chat/customer/project 的实际 ID 或名称。C3 不把它们转为 C1 `EvidenceItem`，从而不放宽 C1 的 Pydantic public evidence contract。

## 4. 合成与重读算法

`compose_stage08_context(uow, plan, *, actor, now)` 必须：

1. 重新验证 `ContextPlan` dump，并用既有 C1 `compose_context_pack` 重新取得当前受限表格/Memory/general-advice 内容。
2. 从 plan 的 server-derived workspace/employee/actor/customer/project scope 创建 C2 private authority；不得接受 chat、binding、message、text 或 caller 提供的 group reference。
3. 以同一个 current business scope 构建 C2 window。invalid authority、无 mapping、relation drift、unknown/private/channel/provenance/lifecycle/retention 失败都只使群来源 unavailable，不能扩大 C1 权限或读取其他群。
4. 若群窗口不可用：保留 C1 结果；只有 C1 也没有内部 evidence 时才使用 C1 的 `general_advice` marker。
5. 若 `compression_required=false`：仅通过 C2 private fresh materialization 取得当前片段；任何 handle/version/purge/expiry/source/mapping/member/scope 漂移均丢弃全部群片段，且不能回退到历史 Message 或 partial stale output。
6. 若 `compression_required=true`：不 materialize 原始群正文；生成 `group_compression_pending` safe view，并保留 opaque window 仅供 Package E 之后重新验证并压缩。
7. C1 internal evidence 与无压缩群片段按固定顺序合成：C1 existing evidence order，随后 C2 window order（最新 band，随后 C2 已确定的 decay history order）。C1 `general_advice` marker 不与任何内部 evidence/群片段同时出现。
8. 计算内容字符总数；大于 36,000 或任何来源自身超限时 fail closed，返回无可消费的 private content 和安全 status，不截断群正文来伪造可用结果。按已确认的 C1/C2 hard cap，正常实现不应触发该保护分支。

`render_stage08_composite_context(uow, composite, *, now)` 必须重新调用相同组合算法后才输出文本；它不能信任已构建 composite 的 C1 pack 或 C2 handles。render 所得字符串只可传给 Package E 的当前调用，调用结束即丢弃。

## 5. 状态、降级与压缩分层

| C1 结果 | C2 结果 | C3 safe status | 可私有渲染内容 |
| --- | --- | --- | --- |
| internal evidence | group unavailable | `internal_evidence` | C1 evidence |
| no C1 evidence | group unavailable | `general_advice_only` 或 `no_evidence` | C1 policy marker 或空 |
| 任意 C1 | direct group available/partial | `internal_evidence` | C1 internal evidence + 当前 group fragments；若 C1 只有 marker 则移除 marker |
| 任意 C1 | compression required | `group_compression_pending` | 仅 C1 internal evidence；opaque C2 window 仅留给 E |
| authority/scope/plan drift | 任意 | `no_evidence` | 空；不使用 stale C1/C2 内容 |

`group_context_partial` 仍是 C2 window 的本地状态：它只意味着至少一条群 fragment 可用且有 omission；C3 不更改该含义。C3 的 `group_compression_pending` 只代表 C2 原始工作窗口超过 24,000 并等待 E，不代表已经压缩或已经调用 Provider。

## 6. 严格边界

- C3 不导入或查询 `app.models.telegram.Message`，不读取 `raw_text`、`raw_caption`、`normalized_text`，不扫描历史消息。
- 不新增 migration、table、field、API route、permission action/role、webhook、polling 或 outgoing Telegram request。
- 不写 `MemoryItem`、candidate、database、Redis、RAG/pgvector、AgentRun、audit、outbox、log 或 checkpoint；特别是不得持久化 renderer 文本或未来 digest。
- 不调用 Provider/LLM；`ContextCompressor` 的唯一调用方仍是 Package E。
- 不改变 C1 ContextPack 或 C2 GroupContextWindow 的公开合同；C3 只在两者之上新增私有组合合同。

## 7. 验收与交接

C3 至少需要证明：

1. C1+C2 只在相同已验证 customer/project scope 下合并；任一侧漂移会在消费前重新验证。
2. 无压缩路径的内容和顺序稳定，内容总数不超过 36,000，且不泄露标识。
3. 压缩路径不读取群正文、不创建 digest、不调 Provider，只传播 private pending 状态给 E。
4. general advice 不与内部 evidence 混用；C2 unavailable 不会导致 C1 丢失或扩大读取。
5. real disposable PostgreSQL 覆盖 C1 relation/field/Memory drift 与 C2 mapping/provenance/purge/expiry drift 的组合失败关闭。
6. C3 通过不代表 Package E、真实 LLM 评测、Telegram 外部活动、部署或生产可用。

Package E 的后续输入是 C3 private composite + current revalidation，不是 C3 safe view 或 renderer 的持久化副本。
