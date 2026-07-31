# 当前项目交接说明

## 1. 文档用途

- Status: active root handoff
- Audience: 没有历史上下文的新 Codex 对话、开发者和审计人员
- Updated: 2026-07-31
- Latest Stage12 acceptance update: Human Gold is `48/48`. The bounded deterministic-section correction is implemented locally and its one new independent real `48 × 3` campaign completed with release `FAIL`. Every Case/final-answer gate is `48/48` per round, Retrieval passed, and `mixed_02`/`mixed_08` no longer collapse; Composer unavailable is `36/48`, `47/48`, `37/48`, dominated by schema-invalid attempts, and total-latency P95 worst is `13775.8 ms`. Current bundle hash is `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`; pre-correction bundle `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6` remains immutable history. Effects are `0/0/0`. Read the bounded design/plan and current campaign audit before continuing; do not rerun the full campaign before a new focused Provider-schema decision.
- Current Stage: Stage11 仍是生产权威；Stage12 的用户可见回答完整性已在本地提升到三轮 `48/48`，但真实 Composer schema 可用性和总延迟仍未通过，因此 Stage12 未部署、未激活、未最终验收。下一步是单独设计并确认 focused Provider compatibility 或 acceptance-contract 修正，不是部署，也不是直接再跑 `48 × 3`。
- Rule: 本文只负责当前状态和下一步导航，不复制各技术专题的完整定义

新对话必须先读本文，再按任务进入对应专题。不要从 Stage02–Stage09 的历史文档推断当前生产能力，也不要把本地 Stage12-A–F 描述成已经部署的 Query/Retrieval/Specialist/Action/UI 或 dispatch 能力。

## 2. 新对话最短阅读路径

按以下顺序读取：

1. [AGENTS.md](AGENTS.md)：项目产品定位、技术基线、安全边界和确认规则。
2. [Implementation Source Of Truth](project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)：当前顶层产品和实现真源。
3. [Stage12 bounded Provider design](docs/superpowers/specs/2026-07-31-stage12-bounded-deterministic-section-provider-design.md)：当前 Composer 内部契约。
4. [Stage12 bounded Provider plan](docs/superpowers/plans/2026-07-31-stage12-bounded-deterministic-section-provider.md)：实现、local gate 和真实 campaign 执行证据。
5. [Current bounded campaign audit](project-docs/08-implementation/evidence/stage12-final-provider-campaign-v2-2026-07-31/AUDIT.md)：当前 `FAIL`、改善项与剩余阻断。
6. [Stage12 comprehensive audit](project-docs/08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md)：历史全量缺口和修复链。
7. [Stage12 Quality V2 索引](project-docs/02-architecture/stage12-quality-v2/README.md)：批准的目标架构入口。
8. [Stage11 Acceptance](project-docs/08-implementation/STAGE_11_ACCEPTANCE.md)：当前生产实现的通过项、失败项和限制。
9. [r75 真实 48 Case 报告](project-docs/08-implementation/evidence/stage11-r75-real-48case-report-2026-07-28.md)：需要逐 Case 复核时读取。
10. [Stage12-C acceptance](project-docs/08-implementation/STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md)：读取本地 Query Engine 已通过项、证据和未覆盖边界。
11. [Stage12-D acceptance](project-docs/08-implementation/STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md)：读取 D 的最终证据、跳过项和未激活边界。
12. [Stage12-E source](project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_SOURCE_OF_TRUTH.md)：读取 E 的实施边界、源码审计和验收条件。
13. [Stage12-E architecture](project-docs/02-architecture/stage12-quality-v2/05_SPECIALISTS_PROVIDERS_AND_MODELS.md)：读取 typed Specialist、Provider 与 Supervisor 设计。
14. [Stage12-E code plan](docs/superpowers/plans/2026-07-30-stage12-e-typed-specialist-provider-v2.md)：读取已完成 Tasks 1–8 的实现映射和测试命令。
15. [Stage12-E acceptance](project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_ACCEPTANCE.md)：读取 E 的逐条验收、跳过项和未激活边界。
16. [Stage12-F acceptance](project-docs/08-implementation/STAGE_12_F_DURABLE_ACTION_UI_ACCEPTANCE.md)：读取 F 的逐条验收、真实浏览器证据、跳过项和未激活边界。
17. [Stage12 delivery/acceptance architecture](project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md)：读取冻结 gate；当前全量 campaign 已执行，不得直接再跑。

只有修改 Stage11 runtime 时才继续读取：

- [Stage11 coordination middleware](project-docs/02-architecture/STAGE_11_MULTI_AGENT_COORDINATION_MIDDLEWARE.md)
- [Stage11 evaluation protocol](project-docs/08-implementation/STAGE_11_COMPLEX_CHINESE_EVALUATION_PROTOCOL.md)
- [Stage11 implementation plan](docs/superpowers/plans/2026-07-28-stage11-multi-agent-coordination.md)

## 3. Git、工作树和 PR

| Item | Current value |
| --- | --- |
| Repository workspace | repository root |
| Active worktree | `.worktrees/stage09-ai-conversation-sse` |
| Current branch | `codex/stage09-ai-conversation-sse` |
| Current committed HEAD | 以 `git rev-parse HEAD` 为准；Stage12 bounded correction 已形成独立审计 commits |
| Last commit | 以 `git log -1` 为准；本文不冻结会被下一次 evidence commit 立即淘汰的 hash |
| Remote | 未 push；remote 仍不包含本轮 bounded correction/evidence |
| Pull request | [PR #1](https://github.com/jiangylin5-hue/telegram-bitable-work-agent/pull/1), open Draft |

当前工作树仍包含 Stage12-A–F 的其他本地交付路径；bounded correction 已按文档、TDD、runner 和 evidence 分批提交，不能据此把整个脏工作树视为已审计提交。真实 post-correction campaign 只使用 synthetic fixture；migrations 到 `0039` 只在 disposable 本地 PostgreSQL 验证。A–F 尚未接入生产 dispatch，Stage12 worker/UI/API activation 保持关闭。它没有 production migration、real-workspace Provider call、部署或外部发送变化。

本轮 bounded correction 的 task-level commits 都有对应 RED/GREEN 或审计证据；未 push、未建新 PR、未部署。后续不得把工作树中其他未提交 Stage12 文件顺手并入 Provider compatibility 修正。

## 4. 产品与技术基线

这是一个 Telegram-first、多维表格和表格绑定数字员工平台。产品核心顺序是：

```text
workspace
-> base
-> table
-> field schema
-> record
-> linked record
-> view/form/dashboard-lite
-> permission
-> digital employee
-> draft/controlled action
-> confirmation
-> audit
```

技术栈：

| Layer | Stack |
| --- | --- |
| Backend | Python 3.12+、FastAPI、SQLAlchemy 2.x、Alembic |
| Database | PostgreSQL、JSONB、pgvector |
| Queue/cache | Redis、Redis Streams |
| Agent orchestration | LangGraph-first，加自建 durable run/command/event/checkpoint 控制面 |
| LLM | OpenRouter-compatible API，模型由运行配置绑定 |
| Telegram | Bot API、Webhook、Mini App |
| Frontend | React、Vite、TypeScript、Tailwind、shadcn/ui、lucide-react |
| Deployment | 腾讯云 Ubuntu 原生 systemd 服务，不是旧 Docker 主路径 |

Agent 不得获得 raw SQL、数据库凭据、Provider key 或不受控发送权限。所有写入必须经过后端 service/Tool Gateway；高风险写入和外发必须确认并审计。

## 5. 当前生产事实

- Public domain: `https://stage07.jiangtest1.online`
- Active release: `stage09-p1-20260729-r76-stage11-terminal-fan-in`
- Alembic current/head: `20260728_0034`
- Public 与 loopback health 均为 `ok`
- 六个原生服务处于 active：API、worker、outbox bridge、Redis、agent outbox publisher、specialist worker
- r76 只增加 required child 失败后的 sibling command 原子终止，防止 terminal run 后重试
- r76 没有改变 r75 的 Query、Prompt、Truth Set、Scorer、Retrieval 或 Action Provider
- 生产 allowlist 仍只包含正式 workspace；Stage11 evaluation workspace 不对公网开放
- 没有启用真实 Telegram 自动发送权限

本轮 Stage12-A/B/C 本地实现没有部署到服务器；生产系统仍是 Stage11/r76。

## 6. Stage11 已经实现的能力

### 6.1 Durable control plane

- PostgreSQL 保存 workflow run、command、checkpoint、artifact、event、outbox 和加密 private input。
- Redis Streams 只承担 at-least-once 传输，数据库状态、幂等键、lease 和唯一约束保证 effect safety。
- SSE 是权限重验后的安全投影，支持 `Last-Event-ID`，不是内部事件总线。
- Supervisor 负责 fan-out/fan-in 和唯一 terminal state。
- required child 失败会终止未完成 sibling，optional child 失败可以降级。

### 6.2 Capability 和安全边界

- Registry 已注册 tabular、risk、daily 和 action proposal capability，并绑定固定 execution skill、工具、风险和 schema version。
- 公网 durable runtime 当前只派发 tabular/risk/daily 三个只读 command。
- Action Provider 和 Tool Gateway 已在隔离验收 runner 中真实调用。
- Tool Gateway 只能创建 `pending_confirmation` draft 或 `blocked` notification request。
- Agent 不能直接确认、修改业务 Record 或发送 Telegram。

### 6.3 当前不能声称的能力

- 不能声称生产中的三个 read Specialist 已切换为不同专业执行逻辑；本地 Stage12-E 已有四个不同 typed handler 和 registry，但 deployed Stage11 worker 尚未激活它们。
- 不能声称生产已有真正语义 embedding；runtime 当前主要是 keyword retrieval，8 维 hash vector 仅用于测试。
- 可以声称本地 Stage12-C shadow Query Engine 已对 C 适用集确定性执行复杂 Join、Count、Group By；不能声称生产回答链路已接入该引擎，当前生产仍大量依赖 LLM 从扁平证据推断。
- 不能声称公网已有 durable Action worker、ActionSlot API 或确认 UI。
- 不能声称 r75 综合分就是准确的产品回答质量。

## 7. Stage11 真实测试结果

### 7.1 Fixture 和 Provider

- 隔离 PostgreSQL workspace：1 个 workspace、1 个 base、7 张表、39 条虚构记录。
- 表覆盖 Projects、Work Items、Risks、Tasks、Owners、Daily Metrics、Interactions。
- 真实模型：`google/gemini-2.5-flash`。
- 真实链路：生产 identity dependency、PostgreSQL、Redis Streams、SSE、OpenRouter。
- Case：48 个复杂中文任务，包含多表、风险、日报、草稿、任务、提醒、权限、冲突和单 Query 多语义。

### 7.2 r75 指标

| Metric | Result |
| --- | ---: |
| Terminal/API/SSE | 48/48 |
| Capability precision / recall | 1.0000 / 0.9688 |
| Objective precision / recall / exact | 0.7656 / 0.9750 / 0.3750 |
| Record precision / recall | 0.5660 / 0.6521 |
| Retrieval readiness | 0.7917 |
| Action / field / persistence | 0.8229 |
| Permission safety | 1.0000 |
| External-send safety | 1.0000 |
| Overall | 83.8144，未达到 85 gate |
| Average / P95 latency | 6548.5 ms / 11499 ms |

结果状态：**runtime and safety PASS；quality FAIL**。PR 必须保持 Draft。

### 7.3 持久化和外发

- r75 新增 9 个 pending drafts。
- r75 新增 7 个 blocked notifications。
- Telegram 实际发送 0。
- 最终数据库审计包含早期保留轮次，共 12 个 pending drafts、14 个 blocked notifications。

## 8. 已确认的质量根因

### 8.1 Evaluator

- `risk_02` Gold truth 错误：fixture 中正确结果是 `MT-017`，旧期望写成 `MT-008`。
- Record P/R 从最终回答正则提取所有业务编号，无法区分结果、证据和分组对象。
- `answer_quality` 只检查答案是否非空。
- `retrieval_readiness` 只检查 citation 是否存在。
- Action runner 从 Gold truth 注入 expected action、target 和 fields，没有盲测 ActionSlot 解析。

### 8.2 Planner

- 使用 marker/substring 追加 Objective。
- 48 Case 中 30 个 Objective 不完全匹配，27 个多生成 `risk`。
- 单个 `requested_action` 无法表达一个 Query 中多个独立动作。
- `mixed_08` 正确识别冲突，但漏掉应继续创建的独立评审任务。

### 8.3 Retrieval、Embedding 和 Chunk

- Runtime 默认没有真实 semantic embedding provider。
- 全 workspace 关键词/测试向量混排后统一 Top 12。
- 没有按 Objective/Table 构造候选和配额。
- Record 被投影为扁平文本 Chunk，linked-record path 没有作为确定性查询执行。
- 全量汇总可能在进入 LLM 前已经丢失必要记录。

### 8.4 Specialist 和 Provider

- tabular/risk/daily 共享同一个 handler，主要区别是 capability 和 stream。
- Analysis Provider 输入仍是扁平 Evidence，错误类型被压缩成少数 unavailable 状态。
- Action Provider 只拿上游 answer 和 evaluator 注入的候选，缺少完整 record/schema/version/permission evidence。
- r75 有 5 个 `analysis_unavailable` 和 4 个 `provider_response_invalid_after_retry` action。

## 9. Stage12 批准与实施状态

Stage12 的详细方案已按主题拆分，入口是：

[Stage12 Quality Architecture V2 Index](project-docs/02-architecture/stage12-quality-v2/README.md)

推荐方向：

```text
Query
-> TaskSpec V2
-> Authorized QueryPlan
-> Deterministic Table Operators + Semantic Retrieval
-> EvidenceBundle
-> Typed Specialists
-> Objective Fan-in
-> ActionSlot / Safe Answer
-> Tool Gateway / Confirmation / Audit
```

关键原则：

- 表格事实、Join、Filter、Group 和 Aggregate 由确定性 Query Engine 执行。
- Embedding 只负责模糊实体、Schema matching 和非结构化文本候选。
- LLM 负责歧义、多语义拆解、风险分析和自然语言表达。
- 每个 Specialist 使用独立 handler、typed input/output 和允许工具。
- Action 必须走 `ActionSlot -> AuthorizedCandidateSet -> durable command -> Tool Gateway`。
- Evaluation V2 先建立可复用测量基础；大规模模型跑分在核心技术架构完成后用于总验收。

用户已于 2026-07-29 明确确认上述架构判断、schema/API/权限方向，并要求严格按文档开发、不得漂移、不得口头宣称完成、必须逐条验收。2026-07-30 comprehensive audit 已重开 A/B/E/F；C 保留 Query `46/46 exact`、Aggregate `11/11`、Sort `2/2`、Safety `48/48` 的组件证据，D 保留 embedding/retrieval 组件证据。V1 仍是唯一 dispatch authority。48 Case 多轮真实模型大评测必须在审计修复和人工 Gold 之后进行。生产部署、真实业务写入和 Telegram 发送仍未授权。

## 10. 下一步应该做什么

### Step 1：用户审计并确认 Stage12 架构（已完成）

重点审计：

1. 是否接受结构化查询优先，而不是 Text-to-SQL 或继续只调 Prompt。
2. 是否接受 TaskSpec V2、Authorized QueryPlan 和 ActionSlot contract。
3. 是否接受真正拆分 Specialist handler。
4. 是否接受新增 objective/action durable schema。
5. 是否接受生产 embedding profile 通过 V2 benchmark 后再选定。
6. 是否接受安全门不能被 Overall score 抵消。

### Step 2：实施 Stage12-A Evaluation V2（已完成 focused foundation）

已完成：

1. 定义结构化 Truth Case。
2. 人工复核现有 48 Case Gold，修正 `risk_02`。
3. 将 required result、allowed evidence、forbidden result、aggregate 分开。
4. 从 runtime trace/artifact 评价 retrieval，不从答案正文反推。
5. Action end-to-end 禁止注入 Gold candidate。
6. 执行聚焦 deterministic baseline，验证 truth、scorer、runner 和 hard gate 可运行。
7. 冻结三轮真实模型评测协议；核心架构完成后再执行，并与 r75 并列保留，不覆盖历史证据。

### Step 3：按退出门推进 B–F（comprehensive audit reopened）

```text
Stage12-B TaskSpec/Planner
-> Stage12-C Authorized Query Engine
-> Stage12-D Embedding/Chunk V2
-> Stage12-E Typed Specialist/Provider V2
-> Stage12-F Durable Action/UI
```

Tasks 1–9/Task9B、ISO-01、Human Gold 与 bounded Composer correction 已完成本地实施和两次真实 campaign。最新 campaign 证明 final-answer/Case quality 从三轮 `46/48` 修复为 `48/48`，但 Provider unavailable mean/worst 为 `0.833333/0.979167`，total-latency P95 mean/worst 为 `11636.716667/13775.8 ms`，所以总体 release 仍为 `FAIL`。下一门是先确认 focused Provider schema representation/profile 或重新定义 Composer Provider release role；在此之前不得部署或再跑全量 campaign。

## 11. 新对话禁止事项

- 不要重新发明第二套 Agent framework。
- 不要把旧 Stage09/Stage11 scorer 当作可靠 Gold。
- 不要先换模型再修 Evaluator 和 Retrieval。
- 不要把 test hash embedding 描述为生产语义向量。
- 不要让 LLM 生成或执行 raw SQL。
- 不要让 risk/daily worker 继续无条件复用 tabular handler并宣称专业化完成。
- 不要在 Action 测试中从 expected result 注入 target/field 后宣称端到端准确。
- 不要启用 Telegram 真实发送或外部写入。
- 不要覆盖 r75/r76 历史证据。
- 不要部署服务器、执行生产 migration 或启用 Stage12 worker/UI；新增 migration 或 schema 变化仍需新的文档与用户确认。

## 12. 已完成验证和清理

- Stage12-A focused suite：`58 passed in 2.66s`。
- Stage12-A backend regression：排除 4 个无法运行的历史 PostgreSQL-only 文件后 `1714 passed, 132 skipped in 142.57s`。
- Stage12-A PostgreSQL 限制：配置账号无权 `CREATE EXTENSION vector`；不得声称 PostgreSQL replay 通过。
- Stage12-A compileall、`git diff --check` 和 Alembic 单 head `20260728_0034`：passed；`ruff` 未安装。
- Stage12-B focused suite：review 后 `169 passed in 7.00s`。
- Stage12-B backend regression：排除相同 4 个历史 PostgreSQL-only 文件后 `1814 passed, 132 skipped in 140.97s`。
- Stage12-B 48 Case deterministic diagnostic：Objective raw `37/48`、Predicate `46/48`、B-applicable Objective `37/37`、Action template `24/24`；11 Objective Case 保留人工 Gold review，不得声称 48/48。
- Stage12-C deterministic diagnostic：Query `46/46 exact`、Join `8/8`、Aggregate `11/11`、Sort `2/2`、Safety `48/48`；Provider、Action expansion、后置 record writes 与 external sends 均为 `0`。
- Stage12-C focused A/B/C compatibility：`288 passed in 12.08s`；真实本地 PostgreSQL C integration：`1 passed in 3.85s`。
- Stage12-C backend regression：排除相同 4 个历史 PostgreSQL-only 文件后 `1928 passed, 133 skipped in 142.57s`。
- Stage12-D Task6 lifecycle/security：`22 passed`；focused D through Task6：`60 passed in 4.53s`。
- Stage12-D disposable PostgreSQL：migration/indexing/mutation/authorized fan-out/permission revoke `1 passed`；Alembic 单 head `20260729_0035`。
- Stage12-D Task6 fresh regressions：Stage06/07 `58 passed`；unit+API `1888 passed`；排除相同 4 个历史 PostgreSQL-only 文件后全后端 `1987 passed, 134 skipped`。
- Stage12-D compileall 与 `git diff --check`：passed；`ruff` 未安装，记录为 skipped/unavailable。
- Stage12-D Task7 RED：两个新服务缺失，2 个 collection errors；GREEN：`9 passed`。
- Stage12-D through Task7：D unit `68 passed`、真实 disposable PostgreSQL D integration `1 passed`；Stage12-C aggregate/query compatibility `38 passed`；Black check、compileall、单 Alembic head 与 `git diff --check` passed。
- Stage12-D Task8/final focused：`91 passed in 6.56s`；真实本机 C+D PostgreSQL `2 passed in 5.45s`。
- Stage12-D final regressions：unit+API `1906 passed in 155.27s`；排除相同 4 个历史 PostgreSQL-only 文件后全后端 `2005 passed, 134 skipped in 158.48s`。
- Stage12-D real synthetic-only OpenRouter diagnostic：`1/1` completed，Recall@20 `1.0`、MRR@20 `0.9583333333`、forbidden `0`、P95 `2498.3266 ms`、Provider calls `4`，Action expansion/record write/external send 均为 `0`。
- Stage12-D final structural checks：compileall、Black 12-file check、单 Alembic head `20260729_0035`、`git diff --check`、JSON/hash、credential 和 changed/new-file developer-path scan passed；`ruff` unavailable。
- Stage12-E RED→GREEN：contracts/registry、四类 handler、Provider gateway/validation、ClaimGraph/Composer、shadow/evaluation 均先观察到预期 missing-module/behavior failure 后实现。
- Stage12-E final focused：`78 passed in 7.54s`；真实 disposable PostgreSQL event/fan-in artifact `1 passed in 2.69s`；Redis integration `1 skipped`（缺少 `STAGE10_REDIS_URL` 和 Python `redis` 包）。
- Stage12-E regressions：unit/API `1966 passed in 146.04s`；排除相同四个历史 PostgreSQL-only 文件后全后端 `2065 passed, 134 skipped in 151.07s`。
- Stage12-E real synthetic-only Provider benchmark：`google/gemini-2.5-flash` risk/daily/composer `3/3`、attempts `3`、failures `0`、mean `3465 ms`、p95 `4957 ms`、tokens `207/125`。
- Stage12-E structural/security：compileall、Black E-file check、单 Alembic head `20260729_0035`、`git diff --check`、JSON/hash、credential 和 developer-path scan passed；`ruff` unavailable。Disposable `ads_agent_stage12_test` 已恢复到 `0035` 并核对 `vector`、`fields`、`stage12_retrieval_chunks`。
- Stage12-F focused：`49 passed in 11.67s`，包含真实 PostgreSQL 用户编辑值确认回归。
- Stage12-F full backend：在专用 `stage06_smoke` 与真实 PostgreSQL/pgvector 环境中 `2209 passed, 38 skipped in 442.18s`；跳过项为 Redis、online PostgreSQL 和独立 Stage08 RAG 数据库。
- Stage12-F Mini App：focused `25 passed`；全量 `79 files / 412 tests passed`；production build passed。
- Stage12-F real Provider：`google/gemini-2.5-flash` Action proposal `1/1`，provider calls `1`，writes/sends `0/0`。
- Stage12-F browser：真实 Vite/FastAPI/PostgreSQL 下完成 proposal/edit/confirm，页面 `executed` 且编辑值精确落库；390×844 无横向溢出、console errors `0`、Telegram sends `0`。
- Stage12-F structural/security：compileall、Black `132` files、Alembic head/current `20260730_0036`、`git diff --check`、credential/path/JSON scan passed；Ruff 与真实 Redis unavailable。
- Stage12 correction Tasks 1–5：Evaluation V2.1、shared Entity Linker、same-table relation identity、field-policy/blind Action、Retrieval registration/bootstrap/runtime 均为 `implemented-local`；Retrieval migrations 当前到 `0039`，无部署或激活。
- Stage12 correction Task 6：real worker registry/typed execution、sealed ClaimGraph、safe Composer 与 optional-last-failure convergence 已修正；E-focused `84 passed`、unit/API `2061 passed`、真实本机 PostgreSQL typed Risk fan-in `1 passed`、synthetic real Provider `3/3`。证据见 `project-docs/08-implementation/evidence/stage12-task6-typed-worker-composer-2026-07-30.md`。
- Stage12 correction Task 7：raw Query 隔离 A–F runner、stage hash/count/error/latency、原子脱敏报告与非破坏性 PostgreSQL fixture 已实现；`48/48 completed`、focused `102 passed`、unit/API `2071 passed`、PostgreSQL `1 passed`，head `0039`，临时 schema 残留 `0`，confirmed Action/business write/Telegram send 为 `0/0/0`。证据见 `project-docs/08-implementation/evidence/stage12-task7-isolated-af-2026-07-30.md`。
- Stage12 correction Task 8：真实 disposable Redis 7.4.10 已证明 duplicate suppression、crash-without-ACK、pending claim/recovery、ACK-once 与 terminal sibling drain；Redis integration `3 passed`、related runtime `25 passed`、DB residue `0`，container removed，Docker engine stopped。证据见 `project-docs/08-implementation/evidence/stage12-task8-real-redis-2026-07-30.md`。
- Stage12 correction Task 9/9B：final-answer contract、Planner/Authorized Query/ActionSlot 核心机制及 HG-09/HG-10 deadline 语义均已本地实现。确定性所有硬门与完整 release 均为 `48/48`；Task9B evidence 为 `project-docs/08-implementation/evidence/stage12-task9b-core-quality-correction-2026-07-31.md`。Business-context architecture 明确 `OUT OF STAGE12`。Human Gold 后续已显式签署 `48/48`，其旧 `0/48` 状态只属于历史快照。
- Backend：当前全量回归 `2366 passed, 40 skipped in 373.30s`；40 个 skip 为 Redis 3、Stage02 online PostgreSQL 17、Stage08 collaboration PostgreSQL 3、Stage08 RAG/pgvector 17。Stage12 PostgreSQL/pgvector `7/7` 单独通过。
- Stage11 生产候选隔离测试：27/27 passed。
- Python compileall：passed。
- Git diff check：passed at Stage11 commit。
- Mini App：Stage11 没有 frontend diff；此前 411 tests/build evidence 保留。
- 授权浏览器复杂 Action 点击：因没有 Telegram browser session 未执行，不得声称通过。
- 本机 `ruff` 未安装，因此没有 lint pass 声明。
- 临时 eval API、18082 端口、`/run` eval env、上传脚本和临时 SSH key 已清理。
- r67–r72 candidates 已清理；r73–r76 保留为额度失败、有效基线、报告同版和当前/回滚证据。
- Stage12 bounded Composer local gate：focused `113 passed`；expanded `446 passed, 1627 deselected`；全后端 `2411 passed, 40 skipped`；disposable PostgreSQL/pgvector `7 passed`，PostgreSQL `18.4`、pgvector `0.8.3`、Alembic current/head `0039`、临时 schema `0`。
- Stage12 bounded Composer real campaign：三轮 `48/48` final-answer/Case gates，Retrieval Recall@20 `1.0`，effects `0/0/0`；release `FAIL` only on Provider availability and total latency。Bundle `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`；无 secrets、raw query/prompt/response、Gold payload 或临时文件。

## 13. 当前交接结论

当前生产系统仍停留在已验证的 Stage11/r76。Stage12 correction、Human Gold、isolated acceptance、bounded Composer 和 post-correction real campaign 都只在本地完成；TaskSpec V2、Query Engine、Retrieval V2、Typed Specialist、Durable Action/UI 与 bounded Composer 都不参与生产 dispatch。没有部署变化，也没有 production migration、Stage12 worker/UI activation、已确认 Action、业务写入或外发变化。

新对话的正确动作是：先读取 bounded design/plan 与当前 campaign audit。可以声称本地最终回答完整性从 `46/48` 修复到 `48/48`，但必须同时说明大多数 real Provider 调用 schema-invalid 并走 deterministic fallback，Stage12 总 release 仍是 `FAIL`。先设计 focused compatibility benchmark，再由用户决定 list-shaped response contract、optional Provider release role 或新模型/profile；这三者都不是当前已授权实现。Business-context architecture 仍 `OUT OF STAGE12`。

不得再声称 Human Gold/Provider rounds pending：Human Gold 已 `48/48`，post-correction real rounds 已 `3/3`。也不得把它写成 Stage12 通过，因为 Provider availability 与 latency gate 明确失败。
