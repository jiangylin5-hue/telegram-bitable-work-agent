# Stage12 实施、测试与验收方案

> Parent index: [README.md](README.md)

## Status

- Document status: approved staged delivery and acceptance contract
- Current Stage: Human Gold remains `48/48` and the approved isolated-runtime wiring is implemented locally through the existing public Agent Run POST/SSE contract, including SQL admission, encrypted typed Specialist execution, Grounded Provider fan-in, safe replay and a sanitized deployed campaign harness. The harness has focused campaign/evaluation evidence of `94 passed` plus a read-only local PostgreSQL observer smoke; Planner plus real local PostgreSQL mixed/action evidence is `77 passed`. No deployed P2/P3, native Redis, server activation, rollback or Telegram proof has run. Release therefore remains `FAIL`, and historical component/in-memory P1/P2 evidence is not deployed-path acceptance.
- Current completion audit: `../../08-implementation/STAGE_12_INTEGRATED_SPECIALIST_OBSERVABILITY_COMPLETION_AUDIT.md`
- Stage12-B acceptance: `project-docs/08-implementation/STAGE_12_B_TASKSPEC_PLANNER_ACCEPTANCE.md`
- Stage12-C code-level plan: `docs/superpowers/plans/2026-07-29-stage12-c-authorized-query-engine.md`
- Stage12-D code-level plan: `docs/superpowers/plans/2026-07-29-stage12-d-retrieval-embedding-v2.md`
- Stage12-D acceptance: `project-docs/08-implementation/STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md`
- Approval: 用户于 2026-07-29 确认 Quality Architecture V2；于 2026-07-31 确认 Grounded Answer Provider V2、Git push、原生服务器候选部署、真实服务器后端和受限 Telegram 测试。Stage12 全生产 workspace 激活仍需最终独立确认
- Stage12-A code-level plan: `docs/superpowers/plans/2026-07-29-stage12-a-evaluation-v2.md`
- Execution rule: 严格逐阶段 TDD 和逐条证据验收；发现需要偏离本文的更优方案时暂停并与用户讨论

### 2026-08-01 deployed public-path acceptance clarification

- `backend/scripts/stage12_deployed_provider_campaign.py` is the only P2/P3 campaign entry for release acceptance. It submits the approved Human Gold Query through the existing public Agent Run POST, consumes the existing SSE stream, and replays through `Last-Event-ID`; it does not import `IsolatedAFExecutor` or invoke an in-memory UOW.
- The user-visible answer is checked in process for required/forbidden Gold results, citation presence, Chinese clarity, permission refusal/partial disclosure and pending/denied/blocked Action wording. Raw Query, answer, citation IDs, UUIDs, Prompt, Provider response and tokens are not retained.
- PostgreSQL is read only for acceptance observation: Provider call count is read from the persisted Grounded result before and after SSE replay; the workspace record-state hash and Telegram send, notification request and confirmed/executed Action counts are compared before/after. Any delta fails the campaign.
- P2 is exactly the approved 12 Case set × 3. P3 is exactly all 48 human-approved Cases × 3, requires a hash-valid passing deployed P2 report, and remains a single server execution after P2. A deterministic fallback fails both gates even when its answer text appears correct.
- Current status is `implemented-local`, not deployed or accepted. P2/P3 output directories must not pre-exist; evidence is immutable and sanitized once written.

## 16. 实施分阶段方案

本文是已批准的分阶段实施与验收合同。用户最新明确要求 Stage12 以技术架构改造为核心、先避开大规模评测。Stage12-A 仍须完成 evaluator contracts、Gold 修正、分层 scorer、无 Gold 注入 runner 和聚焦确定性验证；该基础门通过后进入 B–F。48 Case 多轮真实模型大评测不再阻塞 B，而是核心架构完成后的 Stage12 总验收门。每个技术阶段仍须保持文档、测试、实现和证据闭环。

### Stage12-A：Evaluation V2

目标：先建立可信测量系统。

主要变更：

- 重构 `backend/scripts/stage11_complex_coordination_eval.py` 的 Truth Case schema。
- 新建 V2 evaluator，读取 TaskSpec、QueryPlan、candidate/evidence trace 和 action slots。
- 修正现有 48 Case Gold，并增加 allowed evidence、forbidden result、aggregate truth。
- 保留 r75 报告不变，生成 V2 baseline。

实施步骤：

1. 定义 `EvaluationCaseV2`、`ExpectedTaskSpec`、`ExpectedQueryResult`、`ExpectedActionSlot` 的 Pydantic schema。
2. 为现有 48 Case 写转换测试，明确哪些旧字段被拆成 required result、allowed evidence、forbidden result 和 aggregate。
3. 使用 fixture 的真实字段值重新计算 Gold；人工逐 Case 复核并保存 reviewer/hash。
4. 改造 runner，使其读取 runtime trace/artifact，而不是从答案正文推断候选集。
5. 分别实现 Planner、Query、Retrieval、Answer、Action、Safety scorer；每个 scorer 有独立 unit tests。
6. 执行聚焦 deterministic baseline，证明 truth、scorer、runner 和 hard gate 可执行；不覆盖 r75。三轮 real LLM 全量 baseline 延后到核心架构完成后的 Stage12 总验收。

退出条件：48 Case Gold 已生成、来源审计记录完整且明确标注人工 sign-off 状态；旧/新指标差异可解释；Evaluator component tests、无 Gold 注入测试和聚焦 deterministic baseline 全通过。满足后可进入 Stage12-B，不要求先完成全量三轮 real LLM 跑分。

### Stage12-B：TaskSpec V2 与 Planner

目标：消除 marker 过度拆分，并支持多个独立 ActionSlot。

主要变更：

- 新建 `backend/app/schemas/agent_task_spec_v2.py`。
- 新建 `backend/app/services/agent_task_planner_v2.py`。
- 新建 lexical parser、schema binder 和 objective normalizer。
- Planner Provider 只作为受约束歧义解析器。
- 使用 feature flag 与 Stage11 Task Gateway 并行 shadow evaluation。

实施步骤：

1. 先用失败测试覆盖 27 个 extra-risk、`mixed_08` missing-task、权限局部拒绝和两个同类动作槽位。
2. 实现 Unicode/日期/编号/逻辑连接词 canonicalizer，输出带字符区间的 lexical token。
3. 实现 Schema Binder，输入仅为当前 authorized schema snapshot；输出 table/field/enum candidate 和 confidence。
4. 实现 clause segmenter、deterministic objective/action candidate builder 和 conflict detector。
5. 实现受约束 Planner Provider adapter，只在 binder 多候选或指代不清时调用。
6. 实现 TaskSpec semantic validator、normalizer、cost estimator 和 plan artifact serializer。
7. 在 shadow mode 同时运行 V1/V2，记录差异但仍由 V1 处理生产请求。
8. 达到指标后切换隔离 workspace，保留一键回退 V1。

2026-07-29 用户确认的阶段边界：Planner 不扫描记录。数据依赖动作在 B 中必须保存为 `query_spec_ref + expansion_policy` 的逻辑 ActionSlot 模板；C 计算授权结果，F 展开并持久化具体动作。不得用 48 Case Gold 的具体负责人或记录反向注入 Planner。

退出条件：

- 可静态判定的 Objective exact 与 Predicate exact 达到 `>= 0.90`；数据依赖 Predicate/Join 明确标记 `deferred_to_stage12_c`，不得伪装通过。
- 静态 ActionSlot 以及数据依赖模板的 action kind、静态 target、`query_spec_ref`、`expansion_policy`、confirmation policy 和局部 denial exact 达到 `>= 0.90`。
- 数据依赖具体 target 数量、target/field/value 与持久化不计入 B 的通过分母，分别归 Stage12-C/F；它们仍保留在最终 Stage12 `>= 0.90` 发布门中。
- shadow 默认关闭且仅限 workspace allowlist；V1 是唯一 dispatch 真源；shadow 无权限扩大、无 schema/API/SSE/migration 扩张、无 Provider/外发/业务写入。

### Stage12-C：Authorized Query Engine

目标：确定性完成多表过滤、关联和聚合。

主要变更：

- 新建 QueryPlan schema、validator、executor。
- 基于现有 Platform UOW 实现受控 operators。
- 实现 linked-record 正向/反向 traversal 与字段权限校验。
- 输出 StructuredQueryResult 和 provenance。

实施步骤：

1. 定义 QueryPlan AST 和 operator-field type compatibility matrix。
2. 为 identifier、复合过滤、否定条件、空值、日期、排序、分页写失败测试。
3. 实现 `ResolveEntity/ScanTable/Filter/Project/Sort/Limit` 单表执行器。
4. 为正向、反向、循环和不可见 target 写 linked-record 权限测试。
5. 实现 `TraverseLink`、visited edge、防爆预算和 relation provenance。
6. 实现 `GroupBy/Aggregate`，明确 count/distinct/null 语义。
7. 接入 scope/data version revalidation，并将结果写入 typed artifact。
8. 用 48 Case 中所有多表/聚合 Case 与 PostgreSQL fixture 做 exact comparison。

退出条件：全部多表 Gold Query 与聚合结果 deterministic exact match；不存在 raw SQL 入口。

2026-07-29 实际结果：**Stage12-C accepted locally**。C 适用结构化 Query `46/46 exact`，Join Gold `8/8`，Aggregate `11/11`，Sort `2/2`，Safety `48/48`；focused `288 passed`，真实本机 PostgreSQL `1 passed`，全后端 `1928 passed, 133 skipped`。无 raw SQL、Provider、Action expansion、业务写入或外发入口。验收见 `../../08-implementation/STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md`。

### Stage12-D：Embedding/Chunk V2

目标：提升模糊实体和非结构化文本召回，不影响结构化真值。

主要变更：

- 建立 schema/record/relation 三层索引。
- 选择并冻结生产 embedding profile。
- 新增版本化 pgvector column/index 和 background reindex job。
- Hybrid retrieval 只在授权候选内运行，并按 Objective/Table 配额组装 EvidenceBundle。

实施步骤：

1. 冻结 Evaluation V2 corpus，建立 schema/entity/non-structured retrieval 子集。
2. 实现 canonical schema、record、long-field 和 relation projection；测试隐藏字段不进入文本/hash/vector。
3. 实现 projection outbox、版本化 chunk builder、embedding batch adapter 和失败保留旧版本。
4. 对本地/远程候选 profile 执行相同 Recall@20、P95、成本和数据政策评测，形成 Technical Decision。
5. 按选定 dimension 新增 additive pgvector 表/索引，后台构建 V2 index。
6. 实现 exact/keyword/semantic/link expansion/per-table quota/rerank pipeline，并保存分项分数。
7. 实现 EvidenceBundle assembler、token budget、completeness 和 truncation 规则。
8. shadow 对比 V1/V2 candidate，不改变用户答案；通过后切换隔离 workspace。

退出条件：Recall@20、P95、数据最小化和索引切换/回滚门通过。

2026-07-30 实际结果：**Stage12-D accepted locally**。最终证据为 focused `91 passed`、真实本机 C+D PostgreSQL `2 passed`、unit+API `1906 passed`、全后端 `2005 passed, 134 skipped`。真实 synthetic-only OpenRouter focused diagnostic 为 Recall@20 `1.0`、MRR@20 `0.9583333333`、forbidden `0`、P95 `2498.3266 ms`、Provider calls `4`，Action expansion、record write、external send 均为 `0`。TDR-018/TDR-019 已确认；固定 `vector(1024)`、三层索引、revoke-first outbox、授权前置 hybrid retrieval、20/10/24 budget、EvidenceBundle 与 default-off shadow 均有本地证据。Production migration、D activation 与真实 workspace 外部 embedding 均未授权；runtime materialization seam 刻意不可用，Stage11 V1 仍是唯一 dispatch 真源。验收见 `../../08-implementation/STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md`。

### Stage12-E：Typed Specialist 与 Provider V2

目标：让每个 Specialist 真正使用不同 handler、工具和输出 contract。

主要变更：

- 拆分 tabular/risk/daily/action handlers。
- 新建 StructuredFactSet、RiskAssessment、DailyBrief、ControlledActionProposal schema。
- Supervisor 按 Objective artifact fan-in。
- Provider 增加错误分类、semantic validation 和可观测性。

实施步骤：

1. 定义四类 Specialist input/output Pydantic contract 和 artifact schema version。
2. 写 Registry readiness 失败测试，确保未注册 handler 不能回退 tabular。
3. 抽离 worker transaction/retry 外壳，分别注册 tabular、risk、daily、action handler。
4. 先完成不调用 LLM 的 Tabular handler，再让 Risk/Daily 消费其 typed artifact。
5. 实现 Model Gateway、role-based ModelProfile、token budget 和 Provider attempt observer。
6. 实现 Provider response pipeline、精确 error taxonomy 和一次 schema repair。
7. 实现 ClaimGraph fan-in、stale/conflict 处理和中文 Composer。
8. 验证并行、partial failure、deadline、checkpoint resume、terminal sibling cancellation 和 SSE 顺序。

退出条件：Specialist contract tests、partial failure、retry、checkpoint recovery 和端到端中文回答门通过。

2026-07-30 审计修正：**Stage12-E acceptance reopened**。Typed factories、Provider taxonomy/repair 与真实 synthetic-only `3/3` 调用保留组件证据；但 real worker 未接入 risk/daily typed handler，所谓 PostgreSQL fan-in 没有执行 E typed chain，ClaimGraph 信任任意 value，Composer 可接受 unsupported prose。详见 `../../08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`。

### Stage12-F：Durable Action 与 UI 验收

目标：将 ActionSlot 接入公网 durable command 和确认 UI。

主要变更：

- 新增 `agent_objective_runs`、`agent_action_slots` migration 和 repository。
- 新增 action Redis stream/worker。
- 扩展 API/SSE contract，展示 pending/denied/degraded action。
- Mini App 支持查看、编辑、确认或拒绝 proposal。
- 执行后写 audit，并验证 Telegram 零误发。

实施步骤：

1. 先确认 migration、API、SSE 和权限 contract，再建立 objective/action durable models。
2. 实现 ActionSlot candidate resolver；测试空候选、多候选、字段无权、record version drift。
3. 实现 action command/outbox/Redis stream/worker 和幂等 proposal persistence。
4. 将 Tool Gateway 接到 action worker，只生成 pending draft 或 blocked notification。
5. 实现 objectives/actions/evidence/confirm/reject API，并对每次读取重新授权。
6. 扩展 Mini App stream reducer、Objective timeline 和 proposal review UI。
7. 测试合法更新、冲突更新+合法任务、多个提醒、重复确认、过期 proposal 和 scope drift。
8. 在隔离 workspace 用真实 LLM 和授权浏览器执行多轮点击验收，确认 Telegram send count 为 0。

退出条件：盲测 ActionSlot、持久化、确认、版本冲突、幂等、权限和浏览器点击全部通过。

## 17. 测试策略

### 17.1 Unit

- 中文 lexical/operator parser。
- Objective normalize/merge。
- ActionSlot 多动作和局部冲突。
- QueryPlan semantic validator。
- 每个 operator 的字段类型与权限验证。
- linked-record 正反向 traversal。
- EvidenceBundle completeness/truncation。
- Provider error classifier 和 repair attempt。
- Fan-in partial success。

### 17.2 PostgreSQL Integration

- JSONB typed field、linked record、view scope 和 field permission 联合测试。
- pgvector profile/version/index 切换。
- 同 workspace 跨 table 与跨 workspace fail-closed。
- record/schema 更新后的索引失效和重建。
- concurrent confirmation、version drift 和 idempotency。

### 17.3 Redis/Runtime

- 每个 capability 使用独立 handler。
- consumer crash、claim pending、retry、dead letter。
- required/optional Objective failure。
- terminal run 后 sibling command 不再执行。
- Last-Event-ID SSE resume。
- Checkpoint 恢复前重新验证 scope/data version。

### 17.4 Real Provider

- 中文多表查询、风险、日报和多动作至少三轮。
- Schema invalid、language invalid、citation invalid、429、timeout、quota exhaustion。
- Provider 失败不得生成伪答案或伪 proposal。
- Action end-to-end 不注入 Gold candidate。

### 17.5 Browser

- TaskSpec/Objective 进度可见。
- completed/proposed/denied/degraded 分项显示。
- Evidence 可追溯但不暴露隐藏字段。
- Proposal 编辑、确认、拒绝和版本冲突恢复。
- 桌面和 Telegram Mini App 都完成授权态点击验收。

## 18. 迁移、灰度与回滚

### 18.1 Feature Flags

```text
QUALITY_EVAL_V2_ENABLED
TASK_PLANNER_V2_MODE=off|shadow|active
AUTHORIZED_QUERY_ENGINE_V1_MODE=off|shadow|active
RETRIEVAL_V2_MODE=off|shadow|active
TYPED_SPECIALISTS_V2_MODE=off|shadow|active
DURABLE_ACTION_V1_MODE=off|isolated|active
```

### 18.2 灰度顺序

1. Evaluation V2 独立上线，不影响生产回答。
2. Planner V2 shadow，只比较计划，不派发新 command。
3. Query Engine shadow，与现有回答并行计算但不展示。
4. Retrieval V2 双索引，验证覆盖率后切换读取。
5. Typed Specialist 在隔离 workspace active。
6. Durable Action 先只生成 pending object，保持外发 blocked。
7. 达到门槛后扩大 allowlist。

### 18.3 回滚

- 每个 V2 contract 带 version；旧 worker 不消费未知 version。
- Planner、Query、Retrieval、Specialist 可分别回退 feature flag。
- 新 embedding profile 不覆盖旧向量；回滚只切换 active profile。
- 新 action worker 停止后 pending proposal 仍可读取，但不可执行。
- Migration 先 additive，稳定期内不删除 Stage11 字段和索引。

## 19. 风险与缓解

| Risk | 影响 | 缓解 |
| --- | --- | --- |
| QueryPlan 语法过度复杂 | 维护成本上升 | 只实现当前 48+ Case 所需 operator；新增 operator 必须有 Gold Case |
| Embedding 数据出境 | 合规风险 | Profile 决策记录 provider location；敏感字段不 embedding；可选本地服务 |
| Relation expansion 爆炸 | 延迟和上下文膨胀 | Objective/Table 配额、depth 默认 2、循环检测、aggregate-first |
| Planner LLM 不稳定 | Objective 漂移 | lexical parser 优先、JSON Schema、normalizer、shadow mode |
| Schema 更新导致旧计划失效 | 错答/错写 | schema version、data version、执行前重验 |
| Partial success 表达不清 | 用户误认为全部成功 | 每个 Objective/ActionSlot 独立状态，终态 composer 不合并失败语义 |
| 新旧链路长期并存 | 代码和文档漂移 | 每个子阶段设退出条件；active 后删除对应 flag/旧路径需单独审批 |
| Evaluator 迎合测试集 | 泛化下降 | 保留隐藏 holdout、同义改写、扰动数据和真实用户匿名 Case |

## 20. 审计检查清单

### 20.1 架构确认

- [x] 同意采用方案 B：结构化查询优先的混合架构。
- [x] 同意 LLM 不执行 Join/Count/权限裁决。
- [x] 同意 TaskSpec V2 和 ActionSlot V1 作为新的稳定 contract。
- [x] 同意 Specialist 拆分独立 handler，而不是继续共用 tabular handler。
- [x] 同意 Action 接入第四类 durable worker。

### 20.2 Schema/API/权限确认

- [x] 同意新增 `agent_objective_runs` 和 `agent_action_slots`。
- [x] 同意新增版本化 QueryPlan、EvidenceBundle、Specialist Result API/schema。
- [x] 同意扩展 SSE 以展示 Objective 和 ActionSlot 状态。
- [x] 同意 embedding profile 选择后新增固定维度 pgvector 索引。
- [x] 同意 Tool Gateway 继续作为唯一写入和外发边界。

### 20.3 质量确认

- [x] 同意 r75 只作为历史粗基线。
- [x] 同意先完成 Evaluation V2 基础门，再进入技术架构优化；大规模跑分在架构完成后执行。
- [x] 同意安全门不可由综合分抵消。
- [x] 同意最终 real LLM 至少三轮并报告方差，但不将大规模跑分作为 Stage12-B 前置门。
- [x] 同意 Action end-to-end 测试禁止注入 Gold candidate。

## 21. 变更影响范围

预计实施会影响但不限于：

```text
backend/app/schemas/agent_task_spec_v2.py                         new
backend/app/schemas/authorized_query_plan.py                      new
backend/app/schemas/agent_specialist_results.py                   new
backend/app/services/agent_task_planner_v2.py                     new
backend/app/services/authorized_table_query.py                    new
backend/app/services/retrieval_v2.py                              new
backend/app/services/agent_specialists_v2.py                      new
backend/app/services/agent_action_provider.py                     modify
backend/app/services/agent_orchestrator.py                        modify
backend/app/workers/agent_specialist_runtime.py                   modify
backend/app/workers/agent_action_runtime.py                       new
backend/app/models/agent_event_runtime.py                         modify
backend/app/models/stage08_knowledge.py                           modify or supersede
backend/app/api/routes/agent_runs.py                              modify
backend/alembic/versions/20260729_0035_stage12_objectives_actions.py new after approval
backend/scripts/stage12_quality_evaluation.py                     new
backend/tests/unit/test_agent_task_planner_v2.py                  new
backend/tests/unit/test_authorized_table_query.py                 new
backend/tests/integration/test_stage12_retrieval_pgvector.py      new
backend/tests/api/test_stage12_agent_runs.py                      new
mini-app/src/app/agent-run-events.ts                              modify in Stage12-F
mini-app/src/app/api.ts                                           modify in Stage12-F
mini-app/src/app/CollaborationWorkbench.tsx                       modify in Stage12-F
mini-app/src/test/agent-run-events.test.ts                         modify in Stage12-F
mini-app/src/test/agent-run-api.test.ts                            modify in Stage12-F
mini-app/src/test/collaboration-workbench.test.tsx                 modify in Stage12-F
```

实际实施计划必须在本提案获批后读取最新代码重新锁定文件和函数位置，不能把本节视为提前授权或最终 diff。

## 22. Acceptance Decision

当前 Decision：**ARCHITECTURE APPROVED — IMPLEMENTATION ACCEPTANCE REOPENED; STAGE12 INTEGRATED QUALITY GATE NOT ACCEPTED**。

执行顺序：按已批准 Grounded V2 计划先完成 fixed-array contract、grounding validator、真实 Provider adapter 和 `answer_source` trace；随后执行 12-call P1、冻结代表集三轮 P2、全量回归、push、原生服务器 default-off/allowlist candidate 和服务器后端验证。仅这些门全部通过后，才在服务器执行一次 48 Case × 3 P3；要求 `144/144 answer_source=real_provider`、zero fallback、质量/安全/SLO 全部通过。最后执行受限真实 Telegram 测试。现有 Stage11 trace adapter 和 deterministic fallback 均不能作为真实模型验收替代品。
