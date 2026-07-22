# Stage08 真源：复杂 Agent、上下文工程与知识运行时

## Status

- Current Progress Update (2026-07-22): Stage08 A–F 已完成一次当前状态真实验收：`796 passed` Stage08 Unit/API、`79 passed` disposable PostgreSQL/pgvector integration，及受控真实 OpenRouter R4 `12/12 passed`（9 invoked / 9 completed / 8 usage-present / 0 timeout）。证据见 `evidence/stage08-final-current-state-audit-2026-07-22.md`；Telegram、公开 HTTPS、生产写入和 Stage07 UI 仍是独立后续门禁。

- Current Progress Update (2026-07-22)：Package F 的 F1–F4 质量证据范围已关闭。最终独立审查 `PASS / 0 Critical / 0 Important / 0 Minor`；R3 的单批真实 OpenRouter 合成评测为 `12/12`、0 timeout、Provider `9 invoked / 9 completed / 8 usage-present`，并以 `analysis_action` enum 证明 general-advice/read-only/deny/none 合同。初版 F3 `11/12 HOLD` 与 R2 evidence 哈希均保持不变。`STAGE_08_PACKAGE_F_OPERATIONS_SLO_AND_MILVUS_DECISION.md` 记录当前无规模触发，继续 pgvector、不引入 Milvus。A–F 的开发与非生产质量证据现已完成；生产部署、真实 Telegram controlled smoke、服务器运维与 Stage07 UI 最终验收仍是后续独立门槛。
- Current Progress Update (2026-07-22)：F3 action-verdict parent validation 已经独立复审 `PASS / 0 Critical / 0 Important / 0 Minor`；24 项聚焦、69 项 F2+F1 离线回归通过，伪造 `general_advice/read_only` 无法进入 passed batch。可运行一次版本化 F3 R3 synthetic OpenRouter batch，且新 evidence 必须保留固定 `analysis_action` enum；F3/R2 旧 evidence 不变，不重试、不扩大外部边界。
- Current Progress Update (2026-07-22)：F3 action remediation review 为 `HOLD / 0 Critical / 1 Important`：固定 `analysis_action` enum 已生成但未参与 parent/batch verdict，伪造的 `general_advice + read_only` 可假通过。F1 adapter 本体仍正确 fail closed。已批准仅 F2 evaluator parent-action mapping 修复，见 `decisions/STAGE_08_F3_ACTION_VERDICT_VALIDATION_DECISION.md`；新修复 review 前 R3 禁止执行，旧 F3/R2 evidence 不变。
- Current Progress Update (2026-07-22)：Package F final review 为 `HOLD / 0 Critical / 1 Important`。R2 的 `12/12`、F2/F1 隔离及脱敏边界均自洽，但 `general_advice` adapter 尚可接受 `read_only + []`，而受控 `deny` 未纳入该 case 预期，且 R2 未保留安全 action enum，无法事后证明实际动作。已批准仅 evaluator 内部的 action 合同+固定 enum 证据修复，见 `decisions/STAGE_08_F3_GENERAL_ADVICE_ACTION_CONTRACT_DECISION.md`；F3 R3 在新修复复审前禁止执行，历史 F3/R2 evidence 不变。
- Current Progress Update (2026-07-22)：F3 general-advice 空引用合同修复已通过独立 review `PASS / 0 Critical / 0 Important / 0 Minor`；46 项聚焦离线测试（2 个 env-mutating 专项测试按任务边界 deselected）、独立 12-case offline spawn 均通过，初版 `11/12 HOLD` evidence 的 SHA-256/mtime 已验证未变。现在可执行单次版本化 F3 R2 synthetic OpenRouter batch；不允许重试、改写旧证据或扩大 Telegram/部署行为。
- Current Progress Update (2026-07-22)：F3 的首次单批真实 OpenRouter synthetic 评测已执行并形成不可改写的脱敏 evidence：`11/12`、`0 timeout`、Provider `9 invoked / 9 completed / 8 usage-present`。独立审查确认 `general_advice -> citation_invalid` 为真实质量失败，且 F1 缺少“general advice 必须空引用”的 prompt + adapter 合同。已批准仅离线修复，详见 `decisions/STAGE_08_F3_GENERAL_ADVICE_CITATION_CONTRACT_DECISION.md`；修复复审前不启动版本化 F3 R2，Telegram 仍 dry-run。
- Current Progress Update (2026-07-22)：Package F / F2 已关闭。基础 runner 的三项 Important 证据缺口（outbound prompt gate、真实 Provider invocation 事实、F1-compatible 12-case strategy）以及其后发现的真实 fixture marker 大小写缺口均已通过最小修复与连续独立复审收口；最终 review 为 `PASS / 0 Critical / 0 Important / 0 Minor`，39 项定向离线测试通过。F3 可按用户已授权的显式 `.local` env 执行一次最多 12 个纯合成 case 的 OpenRouter 调用；Telegram 仍强制 dry-run，任何失败只记录脱敏证据、不自动调参。
- Current Progress Update (2026-07-22)：F2 首次 remediation review 为 `HOLD`（0 Critical / 1 Important）。child-local outbound guard 对 lowercase marker 作大小写敏感匹配，真实 fixture 的 uppercase 受限值可进入最终 prompt 而被误判安全；仅离线的 casefold + 四类真实 marker mutation 修复已启动。F3 继续禁止启动，未读 env、未触网或发送 Telegram。
- Current Progress Update (2026-07-22)：Package F / F2 基础 runner 的独立审查为 `HOLD`（0 Critical / 3 Important），尚未调用真实 Provider。三项问题是 outbound prompt 缺席未成为 gate、Provider 已配置被误计为实际调用、部分 offline fake/case 语义与 F1 真实输出合同不一致。已写入 `decisions/STAGE_08_F2_EVALUATION_EVIDENCE_REMEDIATION_DECISION.md` 并启动仅离线的受控修复；修复复审 `PASS` 前 F3 OpenRouter 调用禁止启动。Telegram 继续 dry-run。
- Current Progress Update (2026-07-22)：Package F / F1 已关闭：opt-in `OpenRouterStage08AnalysisProvider` 在真实 HTTP call 上使用 E5 remaining deadline/provider budget 的最小 transport timeout，严格输出且不允许模型形成 draft field/value；fresh independent review `0 Critical / 0 Important / 0 Minor`，100 focused tests、compile/diff 通过。默认 API 仍 unavailable、尚未真实网络调用。F2 12-case subprocess runner、F3 synthetic real Provider evidence、F4 review 与生产部署仍 pending。
- Current Progress Update (2026-07-22)：Package E 已关闭并交接 Package F。E1–E5 fresh final re-review 为 `0 Critical / 0 Important / 0 Minor`；compact E `218 passed`、real loopback pgvector collaboration PostgreSQL `3 passed`、compileall 与 diff check 通过。生产 Coordinator 现在真实执行 C3/D4/general fan-out，worker 不触 request session、使用 isolated read-only child sessions，取消/deadline 会在分析/Policy/Gateway 前 fail closed；E3 原子草稿/最小审计及 E4 strict API/versioned safe replay 未退化。没有真实 Provider、Telegram 或部署调用。F 必须为真实 HTTP Provider 实现 transport-level timeout/cancellation，不能把 E5 的协作式控制误称为可中断网络。
- Current Progress Update (2026-07-22)：Package E final review 发现 I-01，故 Package E `HOLD`，不得交接 F：生产 Coordinator 的 C3/D4 read node 为 no-op，真实读取被移入 `fan_in` 顺序执行，且 wall/provider budget、cancel/timeout 没有生产强制。E3 原子草稿与 E4 strict API/replay 仍通过。E5 只修复既已批准的 bounded parallel/cancel/deadline 合同，详见 `decisions/STAGE_08_E5_PRODUCTION_COORDINATOR_EXECUTION_DECISION.md`；不新增 public API/schema/权限/Provider/Telegram/部署。
- Current Progress Update (2026-07-22)：E3 已关闭。R1 的安全执行适配层与 R2/R3 的原子物化、current-state locks、hash-only idempotency replay、全 trace 最小审计投影已连续交付；用户确认的 `degraded` 终态只接受经过严格校验的 `AnalysisProviderOutcome(status="unavailable")`，不产生回答、引用、草稿或 Gateway 调用。最终独立审查为 `0 Critical / 0 Important / 0 Minor`；113 selected unit、40 Stage06 default-regression、2 real loopback pgvector PostgreSQL integration、compileall 均通过。E4 现在可实现 strict assistant query API 与 Package E 收口证据；真实 Provider、Telegram 与部署仍未开始。
- Current Progress Update (2026-07-22)：E3 安全执行适配层 R1 已关闭。sealed 单字段 JSON-safe `DraftIntent`、factory-only hash trace context，以及 ticket/Gateway/Stage06 draft 全链路安全摘要端口已实现；default ticket 与 safe trace 的 provenance replay 缺口经最小 fail-closed 修复后，fresh independent re-review `0 Critical / 0 Important`。最终 R1 证据为 90 focused unit tests 与 compileall；没有 PostgreSQL/Provider/Telegram/外部写入。R2/R3 将连续实现原子边界、current-state locks、真实 PostgreSQL 主路径和图终态。
- Current Progress Update (2026-07-22)：用户已确认 Package E/E3 的安全执行适配层。该受限内部契约扩展解决首轮 E3 独立复审发现的审计 UUID 泄露、非原子撤权/回滚、幂等 replay 和空 mutation 草稿问题；详见 `decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`。下一步先更新 E3 代码前计划、合同与 BDD，再以 TDD 实现；不新增公开 API、schema/migration、真实 Provider、Telegram、部署、直接 record 写入或草稿确认。
- Current Progress Update (2026-07-22)：Package E / E2 已关闭。E2 实现 C3/D4 controlled reads、opaque pending-group compression handoff、retrieval exception degradation 和 invocation-private group scope proof。三轮 fresh review 先后收口 target scope fallback、D4 exception、C3 后 binding/mapping drift 和 compressor shape drift；最终为 `0 Critical / 0 Important / 0 Minor`。当前证据：137 focused unit tests、loopback disposable pgvector 17 integration tests、compileall。E2 不新增 API/schema/migration、不写 AgentRun/audit/outbox/idempotency/draft，也不调用真实 Provider/Telegram/HTTP；下一项为 E3 analysis、Policy Gate 与现有 ticket/draft 路由。
- Current Progress Update (2026-07-21)：Package E / E1 private contracts 与无 checkpoint LangGraph topology 已关闭。实现严格的 opaque command/state/material/provider input、固定预算和十节点三路 read fan-out/fan-in；`checkpointer=None`、cancel→finalize、policy-gated draft route 均有测试。三轮 independent review 先后发现 reducer 的 policy/duplicate-branch fail-open 以及可伪造 sequential marker，均以最小 sealed marker/fail-closed 修复收口；最终 review 为 `0 Critical / 0 Important / 0 Minor`，39 个 E1 focused tests、compileall 与限定 diff-check 通过。E1 不接 DB、C3/D4 service、API、Provider、Telegram 或外部写入；下一项为 E2 受控 C3/D4 reads 与 process-local compression。
- Current Progress Update (2026-07-21)：Package E 已完成代码前中文设计、协作安全合同、BDD/验收合同和逐任务 TDD 实施计划；唯一设计路线是类型化 LangGraph、process-local non-checkpoint state、C3/D4 fan-out、默认 unavailable 的 compression/analysis port、Policy Gate 和现有 ticket/Tool Gateway draft 路由。E 不新增 schema/migration/UoW/global role、不会持久化 query/群摘要/RAG evidence，也不调用真实 Provider。下一项是 E1 private contracts/topology 的任务级实现和独立复审。
- Current Progress Update (2026-07-21)：Package D 已关闭并交接 Package E。D0–D5 final independent review 为 `0 Critical / 0 Important / 1 Minor`；专用 pgvector 真实完成 migration `20260720_0032 → 20260720_0031 → 20260720_0032`、唯一 head、`vector=0.8.5`、GIN/HNSW、D1–D5 `236 passed / 0 skip`。D4/D5 held-session current-state revoke、source/chunk/Memory lifecycle、reference-only outbox/audit/idempotency 均已复核，测试后相关五类行数为 0。唯一 Minor 是 D5 API test module 中既有 Starlette deprecation warning 的类别级过滤应后续进一步收窄；不影响生产代码或 D 关闭。Package E LangGraph 协作编排现可开始；Package F 的真实 LLM 质量评测、真实 provider 调用与生产部署均未完成。

- 2026-07-20 update：Package C 已关闭并可交接 Package D。C3 首轮包级复审发现 direct composite 在当前 C2 变为 `group_compression_pending` 时错误输出空字符串并调用 materializer；限定修复后只输出当前 C1、不会 materialize 群正文，修复独立复审为 `PASS / 0 Critical / 0 Important / 0 Minor`。fresh Package C re-review 为 `PASS / 0 Critical / 0 Important / 1 non-blocking Minor`，可丢弃 PostgreSQL 组合回归 `213 passed`，唯一 migration head `20260720_0031`。非阻断 Minor 是既有 Starlette/httpx 在全套 `-W error` 下的环境告警；默认 `DATABASE_URL` 孤儿 revision 仍是部署前置风险。D/E/F、真实 Provider 与部署尚未开始。
- 2026-07-20 update：Package C C3 Tasks 1–4 已完成并通过独立复审。C3 将 C1/C2 合成为内容级 36,000 总预算；真实 `49 × 500 = 24,500` 字符 C2 窗口只产生 `group_compression_pending`，不会 materialize、截断、压缩或输出群正文，只有 Package E 可压缩。Task 4 的 disposable PostgreSQL 组合重读覆盖 C1 relation/field/Memory 与 C2 mapping/relation/provenance/expiry/purge 漂移，当前 12 integration `passed`、C1/C2/C3 聚焦回归 `211 passed`；初始 10 项 RED、12 项扩展覆盖与新鲜复跑时间线已独立复审。C3 Task 5 包级独立复审正在开始。默认 `DATABASE_URL` 的历史 orphan revision 仍是独立部署前置风险。
- 2026-07-18 update：Package B 已关闭。B5 在真实 disposable local PostgreSQL 复现并修复 confirmed draft 的 outbox 并发唯一键竞态：已持久化 draft 在 idempotency lookup 前以 transition row lock 串行化；`pg_blocking_pids` 证明第二会话确实被 `FOR UPDATE` 阻塞，释放后两会话复用同一 reference-only event、仅保留一条 outbox。120 项 Package B 模块回归、单一 Alembic head `20260718_0029`、compile/static/diff 通过，且无 Provider、Telegram、网络或部署调用。该关闭仅覆盖 Package B，不覆盖 Package C、Stage08、真实 LLM 评测或生产部署。
- 2026-07-18 update：Package C C1 已完成 task-level TDD、两轮最小修复与 Fix Round 3 独立复审（`PASS / 0 Critical / 0 Important`）。C1 提供不持久化的类型化 ContextPlan/ContextPack、授权表格投影、非群业务 Memory 只读重读、general advice marker、确定性预算与证据标签；内部 `read_only` Memory 模式复用现有 TTL/source/scope 验证但不写 lifecycle/audit，默认 lifecycle-aware 行为保持。74 个 C1 unit、84 个 Memory unit、6 个真实 disposable local PostgreSQL 与 196 个 A/B/C1 聚焦回归通过。C2 群窗口/原文历史、C3 包级收口、真实 Provider 评测及部署均未完成。
- 2026-07-18 update：Package B Task B4 已完成任务级 TDD、真实 local PostgreSQL 证据与两轮独立复审。受控群聊 path 仅接受 active binding/member 的短命 opaque source；候选最低置信度固定为 `0.85`，原文及 Telegram/transport/source 载体在 DTO、服务、持久化和 API 边界均拒绝。candidate promote/revoke 的 fingerprint、TTL、version 和 `autoflush=False` 事务内可见性已收口。101 项 B4 测试及 134 项 B3/B2/runtime 回归通过。B5 已在后续更新中完成 Package B 最终 PostgreSQL/生命周期收口。
- 2026-07-18 update：Package B Task B3 已完成任务级实现与两轮独立复审。确认草稿在既有 audit 后创建精确六字段的 reference-only outbox；materializer 重读记录、policy、字段可见性和 scope，并用专用 HMAC token 兑现 `identity_field_keys`。processed event replay 及零/多规则 policy 均 fail closed。81 项 B3/B2/runtime 聚焦测试通过；PostgreSQL outbox 并发与生命周期证据已在后续 B5 收口。Task B4 的详细 SDD 已就绪并开始实施。
- 2026-07-18 update：用户已明确确认 Task B3 仅使用既有 `PlatformTable.settings["memory_policy"]` 作为表格到 Memory 的映射，并确认 Task B4 的部署候选最低置信度为 `0.85`。用户已确认 B3 的内部 `identity_token` 与专用 `STAGE08_MEMORY_IDENTITY_HMAC_KEY` 方案；该 token 使 `identity_field_keys` 参与 same-identity 判定而不保存、返回或记录原始值。B3 现按 task-level TDD 实施。该对齐不触发 Telegram、Provider、通知或部署调用。
- Document status：proposed and user-approved planning boundary
- Scope：在既有多维表格、权限、数字员工、草稿和审计之上，建立受控 Tool Gateway、业务 Memory、上下文工程、RAG、LangGraph 协作与运行质量体系。
- Current Progress：2026-07-21 Package A Runtime Foundation、Package B Business Memory（B1-B5）及 Package C Context Engineering 已完成任务级实施、真实 local PostgreSQL 证据与独立复审。C2 已关闭 D1–D6、受控 ingress、source provenance、private authority/window、retention/purge、真实 PostgreSQL drift/privacy/concurrency 和 C3/E handoff；C3 已关闭 strict safe view、direct composition、compression-pending/renderer、消费期重读及 disposable PostgreSQL 组合证据。Task 5 的 direct→pending renderer 缺陷保留为已修复审计记录；fresh package re-review 后 C 已关闭。Package D 的 RAG/pgvector data/security contract、BDD 与 task-level plan 已记录；D0 专用 Docker pgvector environment 已独立复审通过（`vector=0.8.5`、无 default/native fallback），D1 strict contracts/ORM/migration 也已通过 fresh review。D1 initial composite-FK defect 已修复，真实 cross-workspace/wrong-version cases 均被数据库拒绝。D2 已关闭：root lineage、同 `memory_type`/规范化 scope（含 identity token）完整性、replacement/cleanup 和 SHA-256 trace reference 均由第三次独立复审验证（`0 Critical / 0 Important / 0 Minor`；40/96/124 focused regressions）。D3 已关闭：indexed replay drift、chunk list 异常透传、embedding overflow 均已最小修复并经 fresh independent review 验证（`0 Critical / 0 Important / 0 Minor`；77/133/161 focused + 7 dedicated pgvector）。D4 已关闭：首轮 identity-map stale、terminal timestamp、Memory root fingerprint 三项缺口经局部 fresh-current-state 读取、专用 PostgreSQL held-result 回归及独立复审全部收口（`0 Critical / 0 Important / 0 Minor`；112 provider/service、178 D1-D4、15 dedicated pgvector；cleanup=0）。D5 的受控 reindex 管理 API 与 Package D 最终证据实施中；初轮 real pgvector 已发现 held-session membership revoke 的 identity-map stale 缺口，已按 D4 同款局部 fresh-current-state correction 写入 D5 brief，D5 未关闭。native `STAGE06_LOCAL_DATABASE_URL` 未提供 vector extension。Package E/F 协作/评测、真实 Provider 实测与生产部署均未完成。

## 1. 阶段目标

Stage08 不是“让模型拥有更多自由”的阶段，而是把数字员工升级为可组合、可解释、可撤销的复杂协作运行时。首个目标闭环是：

```text
用户问题或 Telegram @员工
-> 识别事实查询 / 群聊上下文 / 文件与 Memory 检索 / 通用建议
-> 并行取得受权限约束的证据
-> 分析、归因与不确定性说明
-> 回答，或创建任务/记录草稿
-> Policy Gate、execution ticket、audit
```

平台仍以表格为宪法。聊天、向量结果和 Memory 均不能绕开 `workspace -> base -> table -> field -> record -> view -> permission -> draft -> audit`。

## 2. 已确认的产品决策

| 主题 | 决策 |
| --- | --- |
| 首个业务面 | 通用知识助手；回答、引用，并在需要时创建任务/记录草稿 |
| 数据源 | 已授权工作区表格、上传文件、Telegram 群聊上下文 |
| 群聊上下文 | 仅使用 new/edited authorized ingress 的受控投影；30 天内最多 120 片段、raw 最多 60,000 code points，超过 24,000 仅由 C2 发 compression signal；C3/E 分别负责合并/压缩 |
| 多 Agent | 可 `@` 专长员工；复杂请求由 Coordinator 分解为专长子图 |
| 内部数据不足 | 可回答通用建议，但必须标明未依据内部资料 |
| Memory | 表格事件自动写入；高置信群聊决策/偏好/风险/事实自动写入；文件不自动写入 |
| 写入策略 | 默认草稿确认；低风险内部状态可单独批准自动执行；仅 allowlist 测试群可自动回复/建任务 |
| 检索首发 | PostgreSQL 为真源，`pgvector` + 关键词/结构化过滤 |
| Milvus | 非首发依赖；仅在测量触发门槛满足后作为可重建索引副本评估 |

表格仍是可审计的实时业务事实真源；Context 只是当前调用的受权现场信息；Memory 只保留通过既有 Package B 门槛的跨任务协作经验；知识库承载稳定资料。C2 窗口与未来的临时 digest 只能属于 Context，不得进入 Memory 或知识库。

## 3. 绝对边界

- 禁止 raw SQL、直接 ORM 写入、任意工具 import、任意 tool loop、模型自确认高风险动作。
- 禁止将完整表、完整群聊、原始 prompt/response、密钥、隐藏字段或思维链写入 Memory、AgentRun、日志或向量索引。
- 禁止把 Telegram 身份、群聊存在或向量命中当作系统权限。
- 禁止本阶段默认为生产群发送、群发、付款、账号操作、外部 provider 写入或无授权 webhook 改动。
- Stage08 不自动关闭 Stage07 验收缺口，不代表生产部署就绪。

## 4. 交付包与依赖

| 包 | 名称 | 核心产物 | 前置条件 |
| --- | --- | --- | --- |
| A | Runtime Foundation | Tool Gateway、budget、ticket、Policy Gate、审计、幂等、评测隔离 | 既有 Stage06/07 授权、草稿、审计 |
| B | Business Memory | `MemoryItem`、版本、冲突、TTL、撤权、自动事件/群聊提取 | A |
| C | Context Engineering | source planner、上下文压缩、群窗口/历史、证据标签 | A、B |
| D | RAG and Indexing | 文件/chunk/version/reindex/delete、pgvector 混合检索 | B、C |
| E | LangGraph Collaboration | Coordinator 与专长子图、并行、降级、草稿路由 | A-D |
| F | Quality and Operations | 评测集、超时隔离、遥测、成本、Milvus 决策 | A-E |

每个包必须先完成自己的 BDD/SDD、数据/API/安全合同、TDD 和 local PostgreSQL 证据，才可进入下一包。

## 5. 阶段完成定义

只有同时满足以下条件，Stage08 才能进入“implemented-local”讨论：

1. 所有 Tool Gateway 动作具备类型合同、权限交集、预算、ticket、幂等和审计；
2. Memory 具备来源、版本、冲突、TTL、删除、撤权和索引失效闭环；
3. 检索前后都执行权限核验，且引用可被当前调用者访问；
4. Coordinator 的并行、失败降级、草稿与 Policy Gate 有覆盖性自动化和 PostgreSQL 证据；
5. 真实 Provider 评测采用合成数据、单 case 隔离和脱敏指标；
6. 不存在绕过草稿确认、字段权限、chat scope 或审计的写入路径。
