# Stage08 完整阶段实施计划

## Status

- Current Progress Update (2026-07-23): A–F 当前提交复核新增 `796 passed in 47.68s` 的 Unit/API 实际执行证据，且当前 `backend/` 与该轮前的 Stage08 验收代码一致。后续生产就绪动作已在 Stage09 r14 完成原生运行、公开 HTTPS health、受控真实 OpenRouter 与 Telegram 单聊天收发闭环：绑定消息提供事实 chat ID，双 allowlist 精确相同，`restricted_test` 只经 send-request → confirm → outbox bridge 投递一条测试回执；数据库证明 `sent`、`processed` 和三类审计事件均存在。未扩大收件人、未写业务表、未确认 draft 或调用 Provider 业务写入。Stage07 UI 仍独立验收。详见 `evidence/stage08-final-current-state-audit-2026-07-23.md`、`evidence/stage09-r14-real-runtime-and-provider-2026-07-23.md`。

- Current Progress Update (2026-07-23)：Stage08 A–F 已完成一次新鲜、实际执行的全量验收复跑：`796 passed in 46.80s` Unit/API、7 个真实 disposable PostgreSQL/pgvector integration 模块共 `79 passed`，以及真实 OpenRouter 12-case `12/12 passed`、0 timeout、9/9 invocation/completion。逐项 Requirement ID 映射和命令记录见 `evidence/stage08-final-current-state-audit-2026-07-23.md`；下一阶段仍为独立的生产就绪/部署，不由此自动替代 DNS/TLS、Telegram controlled smoke 或 Stage07 UI 验收。

- Current Progress Update (2026-07-22)：Package F 已完成 F1–F4 质量证据收口。R3 final evidence 为单批真实 OpenRouter `12/12 passed`、0 timeout、9/9 Provider invocation/completion、8 usage presence，并含每 case 固定 action enum；最终 Package F review 为 `PASS / 0 Critical / 0 Important / 0 Minor`，152 项离线 F1/F2/E 聚焦回归（2 env-selector 专项测试按禁令 deselected）与 compile/diff 通过。Milvus decision 为 no-go：当前无生产规模触发，维持 pgvector。A–F 开发与非生产质量证据已完成；下一阶段是独立生产就绪/部署，不由本阶段自动开启。
- Current Progress Update (2026-07-22)：Package F 终审发现 general-advice action 合同仍有一项 Important 缺口：`read_only + []` 可假通过、合法 `deny` 未纳入该 case terminal，且 R2 evidence 没有固定 action enum。`STAGE_08_F3_GENERAL_ADVICE_ACTION_CONTRACT_DECISION.md` 已授权最小 evaluator-only 修复；旧 F3/R2 evidence 不变，修复独立审查通过后才创建 F3 R3 single batch。
- Current Progress Update (2026-07-22)：F3 初次真实 synthetic batch 已完成但为 `HOLD`：11/12 passed，唯一真实质量失败是 `general_advice` 非空 citation ordinal。独立 review 确认为 F1 prompt + adapter contract 缺口而非 evaluator defect；只读修复计划已记录于 `STAGE_08_F3_GENERAL_ADVICE_CITATION_CONTRACT_DECISION.md` 与 `2026-07-22-stage08-package-f-general-advice-citation-remediation.md`。旧 evidence 保留，修复复审通过后才运行一个版本化 F3 R2 批次。
- Current Progress Update (2026-07-22)：Package F / F2 已完成并通过最终独立审查。连续修复了 outbound prompt 缺席、真实 invocation telemetry、F1-compatible case strategy 和真实 fixture marker casefold；最终 `PASS / 0 Critical / 0 Important / 0 Minor`，39 项定向离线测试通过。下一项为 F3：载入显式 ignored local env 的一次 bounded synthetic OpenRouter 评测，Telegram/通知/Provider-write/原始留存仍强制禁用；结果失败时只写脱敏 evidence，不自动修改代码或 prompt。
- Current Progress Update (2026-07-22)：Package F / F2 的独立审查发现 3 项 Important 评测证据缺口，F3 真实调用暂时阻断。已批准 evaluator-only 修复：child-local 最终 prompt guard、真实 Provider invocation telemetry、F1-compatible case strategy；详见 `decisions/STAGE_08_F2_EVALUATION_EVIDENCE_REMEDIATION_DECISION.md` 和 `2026-07-22-stage08-package-f-f2-evidence-remediation.md`。该修复不读 env、不触网、不改变 API/schema/权限/默认 Provider。
- Current Progress Update (2026-07-22)：Package F / F1 已开始：先交付 opt-in OpenRouter analysis adapter 的真实 `httpx` transport timeout、strict output mapping 与无 raw persistence 单测；默认请求路径不启用该 adapter。本任务不发网络；F2 12-case isolation runner 与 F3 synthetic real-call evidence 必须在 F1 review 后才开始，详见 `STAGE_08_PACKAGE_F_QUALITY_BDD_AND_ACCEPTANCE.md` 和 `2026-07-22-stage08-package-f-real-provider-evaluation.md`。
- Current Progress Update (2026-07-22)：Package E 已关闭。E5 修复了 final review I-01：production read nodes 承载真实 C3/D4/general 分支，`fan_in` 无业务 I/O；fan-out 前主线程构造 opaque read-session factory，worker 以 isolated read-only child sessions 运行且零 request-session touch；internal runtime control 在 read/compress/analyse/policy/draft 边界 fail closed。E5 task/review/review-remediation 均 PASS，fresh package re-review `0 Critical / 0 Important / 0 Minor`，compact E `218 passed`、real loopback pgvector `3 passed`、compileall/diff check 通过。下一项是 F：真实 Provider transport timeout/cancellation、multi-case quality evaluation 与上线准备；不代表生产上线。
- Current Progress Update (2026-07-22)：Package E final review 为 `0 Critical / 1 Important`，状态 `HOLD`。唯一 I-01 是生产 Coordinator 没有实际承载已承诺的 C3/D4 parallel read、cancel 和 deadline：graph read nodes 为 no-op，`fan_in` 顺序读取，budget 仅为 DTO。E5 remediation 将以 isolated read UoW、真实 branch、process-local runtime control 和消费期 fail-closed checks 修复；不改 API/schema/权限/Provider/Telegram/部署。详见 `decisions/STAGE_08_E5_PRODUCTION_COORDINATOR_EXECUTION_DECISION.md` 与 `2026-07-22-stage08-e5-production-coordinator-remediation.md`。
- Current Progress Update (2026-07-22)：E3 已关闭并交接 E4。安全执行适配层的 R1 与合并 R2/R3 已通过最终独立审查（`0 Critical / 0 Important / 0 Minor`）：113 selected unit、40 Stage06 default-regression、2 real loopback pgvector PostgreSQL integration、compileall 通过。严格校验的分析 Provider unavailable 现在安全映射为 `degraded`，没有 answer/citation/draft/Gateway；shape drift、伪造结果和运行异常仍为 `failed`。下一项为既定 E4 strict query API、Package E PostgreSQL evidence 与包级复审；不新增 schema/migration/权限或外部调用。
- Current Progress Update (2026-07-22)：E3 remediation R1 已关闭：factory-only `stage08_e3_safe` context、sealed 单字段/value `DraftIntent`、safe ticket/Gateway/Stage06 draft audit ports 已以 90 focused tests、compileall 与 independent re-review `0 Critical / 0 Important` 收口。首轮发现的 safe/default ticket replay provenance 缺口已 fail closed；未运行 PostgreSQL、Provider、Telegram 或部署。用户要求阶段完成度优先，R2/R3 合并为一次连续实现：只保留已复现的事务 rollback、scope revoke、idempotency replay、全 trace 脱敏和真实 PostgreSQL 主路径证据。
- Current Progress Update (2026-07-22)：E3 首轮独立复审为 `3 Critical / 4 Important`，未关闭。用户已确认受限的“安全执行适配层”方案：仅 E3 内部以 transaction/savepoint、共同 current-state locks、hash-only replay、安全 audit mode 和 process-local 受控 `field_key + JSON-safe value` intent 复用既有 ticket/Gateway/draft；Stage06 默认路径不变。该决定不新增公开 API/schema/migration/真实 Provider/Telegram/部署，详见 `decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`。E3 修复必须先完成新的 task-level TDD 计划，再补真 PostgreSQL rollback/lock/replay 证据与 fresh review。
- Current Progress Update (2026-07-22)：E2 已关闭：C3/D4 process-local controlled read service、pending group compression handoff、source/binding/mapping consumption-time revalidation、D4 fixed degradation 与 general-advice no-retrieval gate 已完成。最终 fresh review 为 `0 Critical / 0 Important / 0 Minor`；137 focused unit、17 disposable pgvector integration、compileall 通过。复审发现并修复 target scope fallback、retrieval exception、post-C3 group drift 和 compressor shape drift。E3 可开始；E4 strict API、真实 Provider、Telegram 与部署仍未实现。
- Current Progress Update (2026-07-21)：E1 已完成并通过三轮独立复审后的最终收口（`0 Critical / 0 Important / 0 Minor`）。39 个 contracts/graph tests 验证 sealed private carrier、fixed budget、十节点 topology、3-way fan-out/fan-in、cancel、draft gate、`checkpointer=None` 与 reducer conflict fail-closed；前两轮发现的 policy false/true、重复 branch 与可伪造 sequential marker 均已补 RED/GREEN 回归。E1 仅为 process-local anti-misuse boundary，不是对同一解释器任意恶意代码的安全沙箱；无 DB/API/C3/D4/Provider/Telegram/外部写入。E2 现在可以开始。
- Current Progress Update (2026-07-21)：Package E 的详细设计、数据/安全合同、BDD 和 `2026-07-21-stage08-package-e-langgraph-collaboration.md` 已完成并自检。实施顺序固定为 E1 private contract/topology、E2 C3/D4 fan-out 与 process-local compression、E3 analysis/policy/draft、E4 strict query API 与包级 PostgreSQL evidence；当前仅 E1 可开始。未实现或调用真实 Provider、Telegram、Milvus 或生产部署。
- Current Progress Update (2026-07-21)：Package D 已正式关闭。D0–D5 最终独立 review `0 Critical / 0 Important / 1 Minor`；专用可丢弃 pgvector 完成 `0032 → 0031 → 0032`、唯一 head、`vector=0.8.5`、GIN/HNSW、D1–D5 `236 passed / 0 skip` 与零残留证据。Minor 仅限 D5 API 测试模块的 Starlette warning filter 粒度，已记录为后续测试卫生项，不扩展生产 scope。交接目标改为 Package E：LangGraph 多员工协作编排；F 的真实 LLM 评测与生产部署均仍 pending。

- 2026-07-20 update：Package C 已关闭。C3 Task 5 首轮复审发现 direct→pending 消费迁移会返回空字符串并调用 materializer、丢失仍有效 C1 evidence；限定修复以真实 `2 failed` RED、`2 passed` GREEN 建立回归，独立修复复审 `PASS`。fresh Package C re-review 为 `PASS / 0 Critical / 0 Important / 1 non-blocking Minor`；可丢弃 PostgreSQL C1/C2/C3 组合回归 `213 passed`、唯一 Alembic head `20260720_0031`、严格 C3 unit `65 passed`。Minor 为既有 Starlette/httpx strict-warning 环境兼容性，不能作为部署通过证据。C 已可交接 Package D；D/E/F、真实 Provider 与部署仍未开始。
- 2026-07-20 update：Package C C3 Tasks 1–4 已完成并通过独立复审。Task 3 使用真实 `49 × 500 = 24,500` 字符的 C2 高窗口证明 C3 只产生 `group_compression_pending`、不 materialize/压缩/输出群正文；复审额外复现 versioned-edit 漂移，旧 pending composite fail-closed。Task 4 在 disposable PostgreSQL 覆盖 C1 relation/field/Memory 与 C2 mapping/relation/provenance/expiry/purge 漂移；当前 12 integration `passed`、C1/C2/C3 聚焦回归 `211 passed`，首轮 10 项 RED 与后续扩为 12 项的证据时间线已补齐并复审通过。C3 Task 5 包级独立复审正在开始。C3 仍独占 merge/总预算/renderer，Package E 仍独占 `ContextCompressor`。
- 2026-07-18 update：Package B B5 已完成并通过 Fix Round 2 独立复审，Package B 现已关闭。B5 的真实 local PostgreSQL 并发验证以 `pg_blocking_pids` 确认 second session 被 confirmed-draft `FOR UPDATE` 阻塞；释放后同一 reference-only outbox event 被复用且数据库只有一行。完整 Package B 模块回归 `120 passed`，Alembic head 为 `20260718_0029`。此更新不改变 Package C C2/C3、Package D/E/F、真实 LLM 评测或部署的 pending 状态。
- 2026-07-18 update：Package C C1 已完成任务级交付与 Fix Round 3 独立复审。它实现纯内部的 ContextPlan/ContextPack、业务关系收窄、授权 table/非群 Memory/general advice 编排、证据 label/type/scope/version、预算/截断与消费时重读；未添加 API、migration、权限、群原文、Provider、RAG 或 LangGraph。审查期间发现并修复了 source 扩源、Memory 副作用、UUID/内部 ID 泄露、Pack 计划绑定和 scope 对齐问题。74 C1 unit、84 Memory unit、6 local PostgreSQL、196 A/B/C1 focused regression 通过。C2、C3 和后续真实 LLM/部署门禁仍 pending；B5 已关闭。
- 2026-07-18 update：Package B Task B4 已完成。实现了精确 `Decimal("0.85")` 群聊候选门槛、无原文短命 source adapter、candidate→Memory 生命周期、最小安全 list/revoke API 与 local PostgreSQL 事务内证据。两轮独立复审关闭了通用 group materializer 旁路、transport/source 载体、错误关联撤销、TTL/version 优先级、workspace lifecycle 分类和 `autoflush=False` 可见性问题；101 项 B4 与 134 项 B3/B2/runtime 聚焦回归通过。B5 的 package-level 收口证据已在后续更新中完成；Package B 已关闭，但 Stage08 整体仍未完成。
- 2026-07-18 update：Package B Task B3 已完成。它复用既有 `OutboxEvent` 和 table `memory_policy`，不新增 migration/API/权限；在既有 confirmed audit 后才产生包含 workspace/table/record/version/policy/rule reference 的 event。HMAC identity token 不含原始值且从安全读取投影排除；重放、权限/字段/来源漂移、HMAC 缺失与零/多规则均 fail closed。两轮独立复审收口，81 个聚焦测试通过。B5 保留 PostgreSQL outbox 并发与 lifecycle package evidence；B4 的 0.85 阈值、群聊 source adapter、candidate 生命周期及受控 API 已有详细 SDD，现进入实施。
- 2026-07-18 update：用户已确认 B3 使用既有 `PlatformTable.settings["memory_policy"]`，以及 B4 部署候选最低置信度 `0.85`。用户随后确认最小内部契约对齐：以专用 `STAGE08_MEMORY_IDENTITY_HMAC_KEY` 生成不含原始值的 `identity_token`，使 `identity_field_keys` 参与 same-identity 判定；不新增数据库、公开 API 或权限模型。B3 现进入 task-level TDD。实施计划中的 B3 示例 payload 与 BDD 对 table reference 的要求也将以 BDD 为准统一为含 `table_id` 的 reference-only event。
- Scope：Stage08 从 Runtime Foundation 到复杂协作运行时的完整实施顺序、交付物和包间门禁。
- Current Progress：Package A Runtime Foundation、Package B B1-B5 与 Package C Context Engineering 均已关闭并通过独立复审。C3 的 direct→pending renderer 缺陷已由首轮 Package C review 发现、限定修复、独立复审和 fresh package re-review 收口；最终本地 PostgreSQL C1/C2/C3 组合回归 `213 passed`。Package D 的 RAG/pgvector 数据安全合同、BDD 与逐任务 TDD 计划已写入；D0 专用 disposable pgvector 环境已通过独立复审（`vector=0.8.5`、无 default/native fallback），D1 strict contracts/ORM/migration 也已通过 fresh review（62 D1 tests、composite scope/version FK、downgrade/re-upgrade evidence）。D2 source projection/chunking/reference-only index request 已关闭：两轮修复分别收口真实 Memory 新 UUID lineage、raw trace 持久化、type/scope identity collision，第三次独立复审为 `0 Critical / 0 Important / 0 Minor`（40/96/124 focused regressions）。D3 已关闭：first-review 的 replay drift、list read exception redaction、embedding overflow 以最小修复收口，fresh independent review 为 `0 Critical / 0 Important / 0 Minor`（77/133/161 focused + 7 dedicated pgvector）。D4 已关闭：原 source revoke/employee pause identity-map stale、lifecycle timestamp 与 Memory root fingerprint 漂移均由不扩 schema/API/UoW 的局部 fresh read 收口；fresh independent review 为 `0 Critical / 0 Important / 0 Minor`（112/178 focused、15 dedicated pgvector、清理为 0）。D5 受控 reindex 管理 API 与 Package D 最终 PostgreSQL evidence 已开始。native `STAGE06_LOCAL_DATABASE_URL` 的 `vector` extension 仍不可用，不能作为 D 成功证据。Package E/F、真实 Provider 评测与生产部署均尚未开始。
- 2026-07-18 update：Task 6（评测隔离）已完成。该任务仅实现 case 子进程隔离、父进程脱敏 DTO 重验证、有限超时清理和最多 2 路批处理；33 个聚焦单元测试通过，独立窄范围复审无 Critical/Important，未触发 Provider、Telegram、通知或网络调用。Task 5 仍等待已提出的多 invocation ticket 执行语义确认。
- 2026-07-18 update：用户已确认 Task 5 的多 invocation ticket 语义；Runtime API 实施开始。一张 ticket 将顺序执行计划内调用、逐步追加脱敏摘要，并在首个拒绝/失败时停止后续调用进入终态。该任务不扩展 Provider、Telegram、通知、Memory/RAG 或权限模型。
- 2026-07-18 update：Task 5（Runtime API）已完成任务级实现与独立复审。API 从 verified identity 派生 actor/ticket/state；一张 ticket 串行执行完整 invocation 列表、逐步持久化脱敏摘要，并在首个拒绝/失败时停止。严格嵌套预算与 422 验证错误均 fail-closed 且不回显 raw request；86 个聚焦测试通过，未触发任何外部调用。Package A 的六项实现任务均已完成；Package 级完整验收与真实 Provider 评测仍按后续阶段执行。
- 2026-07-18 update：Package B Business Memory 的详细实施计划、BDD 与 Task B1 SDD brief 已完成；Task B1 正在实施。Task B3 使用既有 `PlatformTable.settings.memory_policy` 承载已确认表格到记忆的映射，开始该任务前必须取得单独确认。该包尚未进行真实 Telegram 或 LLM 调用。
- 2026-07-18 update：Package B Task B1 已完成。`20260718_0029` 已建立 Memory 与 Candidate 的 JSONB/生命周期/唯一性持久化边界及 UoW；任务级 TDD、真实 local PostgreSQL 约束/排序/双会话 `FOR UPDATE` 阻塞证据和独立复审均已收口（8 项聚焦测试通过）。Task B2 的类型化投影与安全生命周期服务开始；该状态不等于 Package B 完成、真实 Telegram/LLM 评测或生产部署。
- 2026-07-18 update：Package B Task B2 已完成。严格类型化投影、来源与状态再校验、TTL/撤销、脱敏审计、same-identity 生命周期及 workspace-row serialization 已在 task-level TDD 和独立复审后收口；51 项聚焦 unit/local PostgreSQL 测试通过，包含 `pg_blocking_pids` 双会话证据。B3 仍等待 `PlatformTable.settings.memory_policy` 形状的单独确认；未进行 Telegram、Provider 或真实外部写入。

## 1. 规划文档关系

| 文档 | 职责 |
| --- | --- |
| `STAGE_08_SOURCE_OF_TRUTH.md` | 阶段目标、确认决策、边界、完成定义 |
| `STAGE_08_COMPLEX_AGENT_ARCHITECTURE.md` | 分层架构、节点职责、状态机、预算、基础设施 |
| `STAGE_08_DATA_API_SECURITY_CONTRACT.md` | schema、API、权限、留存、action tier、数据红线 |
| `STAGE_08_SDD.md` | A-F 包的设计单元、测试重点和退出条件 |
| `STAGE_08_TEST_PLAN.md` | 分层测试、真实 Provider 规则与质量门槛 |
| `STAGE_08_ACCEPTANCE_CHECKLIST.md` | Requirement ID 账本 |
| `docs/superpowers/plans/2026-07-17-stage08-runtime-foundation-implementation-plan.md` | Package A 的逐任务 TDD 实施计划 |
| `decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md` | C2 D1–D6、D3 投影/mapping/lifecycle、长窗口与 C3/E 交接的唯一合同权威 |
| `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md` | C2 长 Context 逐任务实施计划；Task 1 review 通过后才可执行 Task 2 |
| `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md` | C3 私有合成、36,000 内容级总预算、压缩 pending 与 renderer 合同权威 |
| `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md` | C3 逐任务 TDD、真实 PostgreSQL 与独立复审计划 |

本文件不复制它们的合同细节；实施者必须按上表顺序阅读，后文的每个阶段只说明何时可以开始、必须实现什么、必须留下哪些证据。

## 2. 总体依赖图

```text
A Runtime Foundation
  -> B Business Memory
  -> C Context Engineering
  -> D RAG / pgvector Indexing
  -> E LangGraph Collaboration
  -> F Quality / Operations / Milvus Decision
```

其中 F 的评测器隔离基础可在 A 中先行实现；F 的完整质量门禁必须等到 E 的 graph 路径稳定后完成。

## 3. Package A：Runtime Foundation

### 功能范围

- `ExecutionBudget`、`ExecutionPlan`、`ToolInvocation`、`RedactedToolResult` 等类型化合同；
- 运行票据 `Stage08ExecutionTicket`、状态机、预算、取消、幂等和审计；
- 固定 allowlist Tool Gateway，连接实时查表、汇总、联系人解析、导入预览、工具目录、任务草稿和记录草稿；
- `PolicyGate` 在 dispatch 前计算 authority intersection；
- API 只能接受服务端可重新计算的输入；
- 将长时间卡住的真实 Provider 评测改成 case 隔离、硬超时和受限并发。

### 不做什么

不做 Memory、向量检索、群聊历史持久化、Coordinator、多 Agent loop、直接写入或发送。

### 已确认的 Package A 任务草稿落点（2026-07-18）

`task.create_draft` 以已有任务表中的 `RecordChangeDraft(draft_type="create_record")` 表达“待确认的新任务记录”，不新建独立 Task schema。Tool Gateway 只能生成 `pending_confirmation` 草稿；确认服务在确认者权限校验后才创建记录，拒绝不会创建记录。该决定只补齐既有草稿合同的创建记录分支，不扩展 Telegram、通知、Provider、Memory 或直接写入权限。

### 开始门槛

用户确认 Package A 的逐任务计划；工作区保持 dirty-safe；existing Stage06/07 authorization/draft/audit 回归可运行。

### 退出门槛

满足 A-01 至 A-07，迁移在 disposable local PostgreSQL 通过，且没有新发送路径或 raw provider 内容持久化。

## 4. Package B：Business Memory

### 功能范围

- 建立 `MemoryItem`、`MemoryExtractionCandidate`、source reference/version、TTL/删除/撤权状态；
- 对已确认表格事件自动写入结构化 Memory；
- 使用受控群聊提取器识别高置信决策、偏好、风险、客户事实和项目事实；
- conflict detector 以版本链而非覆盖处理矛盾；
- 管理端可查询、撤销、删除、导出 Memory 的安全投影；
- source 删除或权限撤销触发 Memory/索引失效。

### 底层架构

写入采用 outbox/queue 风格：业务事件先提交原事实与 audit，再产生幂等 Memory job；job 只能生成类型化 payload。群聊提取先生成 candidate，再由 policy/confidence/冲突器决定 active、conflicted 或 discarded；不保存群全文。

### 退出门槛

满足 B-01 至 B-05；包含并发/幂等、TTL、删除、跨 scope、脱敏和 local PostgreSQL 证据。

## 5. Package C：Context Engineering

### 功能范围

- 建立 `ContextPlan`：问题分类、读取源、最大窗口/chunk、预算和回答标签；
- 当前群最近消息窗口、客户/项目关联表、按时间衰减的历史选择器；
- 实时结构化查表、Memory、RAG 与通用建议的上下文合并与截断；
- evidence pack：每条内容都带 source/type/scope/version/label；
- 资料不足时的 `general_advice` 安全降级。

### 核心算法

`ContextPlanner` 先判定是否涉及具体业务事实。涉及事实时优先 `record.query/table.summarize`；涉及群动态时，C2 只从 new/edited authorized ingress 的受控投影中选择 30 天内最多 120 片段和 60,000 code points。`compression_required = raw_selected_chars > 24000`；C3 负责 C1/C2 merge 与全局预算，仅 Package E 可通过已批准 Provider 路径生成调用内 digest。C2 自身不能调用 provider，也不能扩展 scope。

允许的入站例外仅是：既有 verified local ingress transaction 可在同一本地事务内写 new/edited controlled projection。C2 不新增 Telegram network、webhook endpoint、polling、outgoing request 或 historical raw read。任何临时 digest 只是 Context，不得持久化或绕过 Package B 进入 Memory。

### 退出门槛

满足 C-01 至 C-03；prompt projection 证明不存在全表、全群、隐藏字段或未授权引用。

## 6. Package D：RAG 与 pgvector 索引

### 功能范围

- `KnowledgeSource` 的文件、Memory、批准摘要版本管理；
- extraction projection、chunking、content hash、embedding adapter、pgvector index；
- keyword + vector + structured filter 的混合检索；
- reindex/delete/revoke/TTL worker 与 source-version 对齐；
- `RetrievalProvider` 抽象，首发 `PostgresRetrievalProvider`；
- 引用和 rerank 在 PostgreSQL 重新授权后才可给模型。

### 索引原则

embedding 只针对可检索文本投影，不针对完整敏感内容；向量 metadata 只包含最小 scope/filter 字段。检索索引可被删掉后从 PostgreSQL 重建；PostgreSQL 本身永不从向量库回写权限或业务事实。

### 退出门槛

满足 D-01 至 D-04；删除/撤权后同步读取拒绝、异步索引清理与重建一致性均有本地 PG 证据。

## 7. Package E：LangGraph 协作运行时

### 功能范围

- `Coordinator` 管理 run 生命周期和预算；
- `ContextPlanner`、`StructuredDataAgent`、`GroupContextAgent`、`KnowledgeRetrievalAgent` 并行读取；
- `AnalystAgent` 汇总证据、结论和不确定性；
- `DraftAgent` 将许可的行动转为草稿；
- `PolicyGate` 在最终回复/草稿前校验引用、权限、预算、tier 和 ticket；
- checkpointer/resume/cancel 只保存受控状态和引用，不保存完整对话或 chain-of-thought。

### 协作约束

节点之间只传结构化 state；每个 state 字段有 owner。读节点不能写入；分析节点不能临时扩大检索；草稿节点不能确认；Coordinator 不能跳过 PolicyGate。失败节点产出固定失败标签，Coordinator 只能按降级策略继续。

### 退出门槛

满足 E-01 至 E-03；并行、取消、预算、失败、草稿与审计都可从 trace 重放解释。

## 8. Package F：质量、运维与 Milvus 决策

### 功能范围

- 维护标注评测集：表格、文件、群聊、权限、Memory、检索、草稿、通用建议与失败降级；
- 单 case 子进程、硬超时、最大并发、结果脱敏、临时文件 cleanup；
- 指标：成功率、引用正确率、权限拒绝率、超时、工具次数、token、成本、延迟、检索召回、Memory conflict；
- SLO 与容量报告；仅当触发门槛满足时撰写 Milvus 技术决策与双写/回退计划。

### 退出门槛

满足 F-01 至 F-04；报告必须区分合成 Provider 证据、local PostgreSQL 证据和生产证据，禁止混写。

## 9. 跨包变更管理

每个包开始前必须：更新 `Current Progress`、建立该包 BDD/SDD/API/安全合同、明确 migration head、写入当前风险。每个包结束后必须：更新验收矩阵、记录命令和测试数、清理临时 artifacts、执行独立代码审查。

若任一包需要新增权限动作、改变 retention、自动执行新写入、接入生产 Telegram、接入 Milvus 或引入外部知识源，必须先补技术决策并获得用户明确确认。
