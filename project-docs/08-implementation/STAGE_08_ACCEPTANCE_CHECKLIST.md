# Stage08 验收矩阵

## Status

- Current Acceptance Audit (2026-07-23): 本轮再次实际执行当前提交的 26 个 Stage08 Unit/API 文件，结果为 `796 passed in 47.68s`，且 `backend/` 未偏离本轮前的 Stage08 验收代码。A–F 的本地开发验收结论维持；Stage09 r14 已提供原生运行、公开 HTTPS、受控真实 Provider，以及一条经过事实绑定、双 allowlist、请求确认、outbox `processed` 与审计闭环的 Telegram 测试回执。该结论仅覆盖单聊天受控 Telegram smoke，未扩大接收人、未确认业务 draft；Stage07 UI 仍不在本矩阵结论内。

- Current Acceptance Audit (2026-07-23): Stage08 A–F 的新鲜真实验收已执行通过：`796 passed in 46.80s` Unit/API、`79 passed` disposable PostgreSQL/pgvector、真实 OpenRouter `12/12`。逐项 Requirement ID 当前结论、命令、边界见 `evidence/stage08-final-current-state-audit-2026-07-23.md`；该条是当前状态，以下早期 `Current Progress Update` 保留为开发历史。

- Current Acceptance Audit (2026-07-22): A–F 的初始 `planned` 单元已由 `evidence/stage08-final-current-state-audit-2026-07-22.md` 的逐项映射取代；新鲜证据为 `796 passed` Unit/API、`79 passed` disposable PostgreSQL/pgvector 和真实 OpenRouter 12/12 R4。该结论仅为 Stage08 本地非生产验收，不替代 Telegram、公开部署或 Stage07 UI 验收。

- Current Progress Update (2026-07-22)：E-01 至 E-05 已由 Package E final re-review 标记为 `accepted`：`0 Critical / 0 Important / 0 Minor`、compact E `218 passed`、real loopback pgvector collaboration PostgreSQL `3 passed`、compileall/diff check 通过。E5 额外闭合 production fan-out、isolated-session/no-touch、cancel/deadline 实际执行；真实 Provider、Telegram 与部署不在本次 acceptance 内。
- Current Progress Update (2026-07-22)：E-03 已 `implemented`：E3 safe-execution adapter、Policy Gate/ticket/idempotency/audit 与受限 `degraded` terminal 已经最终独立复审 `0 Critical / 0 Important / 0 Minor`；113 selected unit、40 Stage06 default-regression、2 real loopback pgvector PostgreSQL integration、compileall 通过。E-04/E-05 仍待 E4 API 与 Package E 收口，不以 E-03 替代。
- Current Progress Update (2026-07-22)：E-02 已由 E2 final independent review 标为 `implemented`：C3/D4 controlled reads、consumer-time group proof、compressor/retrieval degrade、137 focused unit 与 17 disposable pgvector integration，结论 `0 Critical / 0 Important / 0 Minor`。E-03 及后续仍为 `planned`，E2 不可替代 Policy Gate/ticket/draft/API 证据。
- Current Progress Update (2026-07-21)：E-01 已由 E1 private-contract/topology 交付标为 `implemented`：39 focused tests 与 final independent review `0 Critical / 0 Important / 0 Minor` 证明 private state、fixed topology、no-checkpoint 与 reducer fail-closed。E-02 至 E-05 仍为 `planned`；不得将 E1 单元测试视为 C3/D4/PostgreSQL/API/Provider 证据。
- Current Progress Update (2026-07-21)：D-01 至 D-04 已由 Package D D0–D5 final independent review 作为 `accepted` 收口（`0 Critical / 0 Important / 1 non-blocking test-hygiene Minor`；migration downgrade/re-upgrade、236 focused tests、dedicated pgvector、cleanup 证据齐全）。E-01 至 E-05 的中文合同和任务计划已完成，状态仍为 `planned`，不得用 D 的证据替代 E graph/API/PostgreSQL 证据。
- Scope：以 Requirement ID 管理 Stage08 包级验收；初始状态均为 `planned`。
- Rule：`implemented`、`evidenced-pending` 和 `accepted` 不可混用；任何包不得用后续包或总测试数替代本行证据。

| ID | 包 | 需求 | 初始状态 | 必须证据 |
| --- | --- | --- | --- | --- |
| A-01 | A | ExecutionPlan/ToolInvocation 合同拒绝未知 tool、raw content 与无效预算 | planned | unit red/green |
| A-02 | A | employee/caller/chat/field scope 交集在 dispatch 前强制 | planned | unit/API deny matrix |
| A-03 | A | ticket 的迁移、唯一 trace、幂等重放/冲突和终态不可逆 | planned | local PostgreSQL |
| A-04 | A | allowlist adapter 只调用既有 service boundary | planned | adapter spies/contract tests |
| A-05 | A | 任何 draft 保持 pending_confirmation 且源记录不变 | planned | service/PostgreSQL |
| A-06 | A | Tool Gateway/API/audit 不暴露 raw prompt/response/hidden payload | planned | redaction scans/tests |
| A-07 | A | Provider evaluator 每 case 隔离、超时不阻塞后续 case | planned | unit runner tests |
| B-01 | B | Memory 具有 source、scope、version、confidence、TTL 与 audit | planned | migration/unit |
| B-02 | B | 表格事件自动 Memory 幂等且可追溯 | planned | service/PostgreSQL |
| B-03 | B | 群聊高置信提取不保存完整原文且跨群隔离 | planned | fixture/security tests |
| B-04 | B | conflict 生成新版本，不覆盖旧事实 | planned | concurrency/unit |
| B-05 | B | revoke/delete/TTL 同步使 Memory 与索引不可读 | planned | service/PG |
| C-01 | C | Context Planner 能区分实时事实、检索、群窗口与通用建议 | planned | unit decision corpus |
| C-02 | C | 无完整表/群注入，窗口、chunk 和预算受限 | planned | prompt projection tests |
| C-03 | C | 回答有证据标签并在资料不足时正确标记 general_advice | planned | graph/API |
| D-01 | D | source/chunk/version/reindex/delete 可重建且可恢复 | design/BDD complete; D0 environment in progress | migration/worker tests |
| D-02 | D | pgvector + structured/keyword filter 检索前后权限一致 | design/BDD complete; D0 environment in progress | PG integration |
| D-03 | D | citation 指向当前可访问的 source/version/field | design/BDD complete; D0 environment in progress | API/security |
| D-04 | D | RetrievalProvider 可替换但 PostgreSQL 仍是权限真源 | design/BDD complete; D0 environment in progress | provider contract tests |
| E-01 | E | Coordinator 只分解/汇总，专长节点不越权 | accepted — E1–E5 final review 0C/0I/0M; sealed state/no checkpoint/actual branch ownership | graph state tests |
| E-02 | E | 并行 read、预算、取消、失败降级与终态映射正确 | accepted — E5 production fan-out, cancel/deadline, 218 compact E + 3 PostgreSQL | graph/integration |
| E-03 | E | Draft 必经 Policy Gate、ticket、幂等和 audit | accepted — E3 safe adapter retained through E5 final review | service/PostgreSQL |
| E-04 | E | strict API/DTO/errors/AgentRun audit redaction | accepted — E4 single POST, redacted errors and versioned safe replay retained through final review | API/security |
| E-05 | E | provider unavailable 不网络调用，compressor private retention | accepted — unavailable ports, private retention and no external-call boundary reviewed in E1–E5 | provider/security tests |
| F-01 | F | 标注评测覆盖权限、引用、Memory、群时效、草稿与降级 | accepted — fixed 12-case synthetic matrix and versioned F3/R2/R3 evidence cover scope/revoke, citation, group/RAG lifecycle, general advice, policy/draft, cancel/replay and multilingual paths | F2/F3 evidence |
| F-02 | F | 合成 live provider 结果完全脱敏且可重复 | accepted — spawn isolation, strict parent DTO, prompt guard and versioned redacted real-provider evidence; R3 12/12 | F1/F2/R3 evidence |
| F-03 | F | token/成本/延迟/召回/错误指标可审计 | accepted — privacy-limited telemetry records invocation/completion/usage presence, latency buckets, terminal/failure and safe action enum; raw token/cost values intentionally prohibited | F3 R3/F4 review |
| F-04 | F | Milvus 只在量化门槛满足后进入技术决策 | accepted — no current scale/SLO trigger; retain pgvector and defer Milvus integration under documented future gate | Package F operations decision |

## 阶段验收限制

- A-F 的开发与非生产证据均已完成；Stage08 阶段级开发收口不等于生产部署、真实 Telegram 或 Stage07 UI 验收。
- Stage08 验收不替代 Stage07 现有 Browser/UI 验收缺口。
- 任何真实 Telegram、生产部署、Milvus 集群或外部写入都需新的显式授权与独立证据。
