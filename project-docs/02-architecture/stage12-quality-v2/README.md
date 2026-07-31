# Stage12 Quality Architecture V2 文档索引

## Status

- Document status: active approved architecture index
- Stage status: architecture approved; correction packages and bounded Composer are implemented locally. The post-correction real `48 × 3` campaign passes all returned-answer/Case gates `48/48` per round but overall release is `FAIL` on Composer schema availability and total latency. Production remains Stage11/r76.
- Scope: 评测可信度、Planner、结构化多表查询、Embedding/Chunk、Specialist、Provider/Model、Durable Action、API/SSE、实施与验收
- Baseline commit: `09b9d5f`
- Active production release: `stage09-p1-20260729-r76-stage11-terminal-fan-in`
- Evidence baseline: `../../08-implementation/evidence/stage11-r75-real-48case-report-2026-07-28.json`
- Current Stage12 evidence: `../../08-implementation/evidence/stage12-final-provider-campaign-v2-2026-07-31/AUDIT.md`, bundle `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`

## 1. 为什么拆分

Stage12 方案原先集中在一个 1,800 行以上的提案中，不利于审计、引用和后续维护。本目录按职责拆分，每项技术定义只有一个所属文档；索引只负责说明阅读顺序和文档所有权，不复制详细技术正文。

原单体文件 `STAGE_12_QUALITY_ARCHITECTURE_V2_PROPOSAL.md` 已移除，不能继续作为引用目标。本目录是唯一 Stage12 架构提案入口。

## 2. 建议阅读顺序

| 顺序 | 文档 | 负责内容 | 什么时候读 |
| ---: | --- | --- | --- |
| 1 | [当前基线与目标架构](01_BASELINE_AND_TARGET_ARCHITECTURE.md) | r75/r76 证据、根因、目标、非目标、方案比较、总架构 | 首次进入 Stage12 或审计架构方向 |
| 2 | [Evaluation V2](02_EVALUATION_V2.md) | Truth Case、Gold 审计、评分公式、隐藏集和多轮真实测试 | 修改测试数据、指标或评测 runner |
| 3 | [Planner 与 Query Engine](03_PLANNER_AND_QUERY_ENGINE.md) | TaskSpec、Objective、Predicate、ActionSlot 拆解、QueryPlan 和确定性操作符 | 修改任务理解、多表 Join、过滤或聚合 |
| 4 | [Retrieval、Embedding 与 Chunk](04_RETRIEVAL_EMBEDDING_AND_CHUNK.md) | 三层索引、Chunk、Embedding profile、Hybrid Retrieval、EvidenceBundle | 修改召回、索引、向量或证据组装 |
| 5 | [Specialist、Provider 与模型](05_SPECIALISTS_PROVIDERS_AND_MODELS.md) | 独立 handler、并行、typed fan-in、Model Gateway、Prompt、Repair | 修改 Agent 执行、模型选择或 Provider |
| 6 | [Action、Runtime、API 与 SSE](06_ACTION_RUNTIME_API_AND_SSE.md) | ActionSlot、候选解析、durable action、数据模型、Checkpoint、API/SSE | 修改草稿、任务、提醒、确认或事件协议 |
| 7 | [安全、可观测性与 SLO](07_SECURITY_OBSERVABILITY_AND_SLO.md) | 授权顺序、Prompt 数据最小化、写入安全、trace 和发布门 | 做安全审计、监控或性能验收 |
| 8 | [实施、测试与验收](08_DELIVERY_TEST_AND_ACCEPTANCE.md) | Stage12-A 至 F、测试矩阵、灰度、回滚、风险和审批清单 | 架构批准后编制实施计划和阶段验收 |

## 3. 文档所有权

| 主题 | 唯一真源 |
| --- | --- |
| 当前质量问题和目标架构 | `01_BASELINE_AND_TARGET_ARCHITECTURE.md` |
| 评测定义和指标公式 | `02_EVALUATION_V2.md` |
| Query 到 TaskSpec/QueryPlan | `03_PLANNER_AND_QUERY_ENGINE.md` |
| Chunk、Embedding、Hybrid Retrieval | `04_RETRIEVAL_EMBEDDING_AND_CHUNK.md` |
| Specialist、Model Gateway、Provider | `05_SPECIALISTS_PROVIDERS_AND_MODELS.md` |
| ActionSlot、durable runtime、API/SSE | `06_ACTION_RUNTIME_API_AND_SSE.md` |
| 权限、安全、观测和 SLO | `07_SECURITY_OBSERVABILITY_AND_SLO.md` |
| 实施顺序、测试、迁移、验收 | `08_DELIVERY_TEST_AND_ACCEPTANCE.md` |

如果后续内容同时涉及多个主题，应在主负责文档写完整定义，其他文档只用相对链接引用，禁止复制形成第二真源。

## 4. 当前结论

Stage11 的 durable run、Redis Streams、SSE、权限与 Tool Gateway 安全边界已经通过运行验收；回答和检索质量未通过。r75 的评测器本身也存在 Gold truth、答案正则评分和 Action oracle candidate 注入问题。

推荐架构方向是：

```text
结构化查询负责表格事实、Join 和聚合
Embedding 负责模糊实体和非结构化候选
LLM 负责歧义解析、风险分析和自然语言表达
Specialist 使用独立 typed handler
Supervisor 负责 Objective DAG 与 typed fan-in
Tool Gateway 负责所有受控写入和外发
```

## 5. 审批边界

用户已于 2026-07-29 明确确认本目录的架构方向、schema/API/权限边界，并要求严格逐阶段开发与逐条验收；随后明确 Stage12 核心是技术架构改造，应先避开大规模评测。2026-07-30 comprehensive audit 已重开 A/B/E/F 与跨阶段门，当前不能声称 A–F 技术门通过。48 Case × 3 真实模型大评测仍是最终门，但必须先关闭审计缺口。以下能力尚未授权：

- Stage12 migrations `0035/0036` 的生产执行；
- Stage12 typed handler / durable Action worker 的生产 activation；
- Stage12 公网 API/SSE/Mini App UI activation；
- real-workspace embedding/Provider campaign；
- 生产真实写入或 Telegram 发送。

Stage12-A–F 都有独立代码级计划和历史验收记录，但 A/B/E/F 当前状态由 comprehensive audit supersede。Stage12-F source、plan、historical acceptance 与当前 audit 分别是 `../../08-implementation/STAGE_12_F_DURABLE_ACTION_UI_SOURCE_OF_TRUTH.md`、`../../../docs/superpowers/plans/2026-07-30-stage12-f-durable-action-ui.md`、`../../08-implementation/STAGE_12_F_DURABLE_ACTION_UI_ACCEPTANCE.md` 和 `../../08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`。

Stage12-B 代码级计划已写入 `docs/superpowers/plans/2026-07-29-stage12-b-taskspec-planner-v2.md`。它保持 V1 为唯一 dispatch plan，只以默认关闭、workspace allowlist 的 shadow 方式观察 V2；不提前实现 Stage12-C Query Engine。

Stage12-B 组件指标为 Objective `37/37` applicable、11 Case truth review required、Predicate `44/48`、Action template `24/24`；但 evaluator/runtime entity inputs 不一致，因此技术门已重开，且这些数值不可解释为产品总质量分。

Stage12-D 保留检索组件级证据；E/F 验收已重开。当前全量回归为 backend `2219 passed, 38 skipped`、Mini App `412 passed` 与 build PASS；真实 synthetic-only E Provider `3/3`、F Provider `1/1`、BGE-M3 Recall@20 `1.0` 均已复现。它们不抵消 runtime wiring、unsupported claim、field-policy 或 blind Action 门。Stage11 V1 仍是唯一 production dispatch/answer 真源，Stage12 没有部署、生产 migration、worker/UI activation 或 Telegram 发送。

2026-07-29 用户进一步确认数据依赖 ActionSlot 的阶段边界：Planner 不扫描记录；B 只生成 `query_spec_ref + expansion_policy` 逻辑模板，C 计算授权结果集，F 展开具体动作并完成最终 target/field/value 与持久化验收。B 的适用指标按规划期可知事实计算，最终 Stage12 发布门不降低。详细定义见 `03_PLANNER_AND_QUERY_ENGINE.md` 7.3.1 与 `08_DELIVERY_TEST_AND_ACCEPTANCE.md` Stage12-B 退出条件。

## 6. 与现有文档关系

- Stage11 已实现架构：`../STAGE_11_MULTI_AGENT_COORDINATION_MIDDLEWARE.md`
- Stage11 验收结论：`../../08-implementation/STAGE_11_ACCEPTANCE.md`
- Stage11 真实报告：`../../08-implementation/evidence/stage11-r75-real-48case-report-2026-07-28.md`
- 当前顶层真源：`../../00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- 无上下文交接入口：`../../../HANDOFF.md`

Stage12 文档描述已批准的目标架构，但 `../../08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md` 已证明当前实现尚未形成 A–F 集成链，并存在需修复或重新确认的评测、权限、Specialist 与 Composer 门禁。只有完成该审计的修复清单、最终评测、生产迁移、激活、线上验证和发布批准后，才能解释为当前生产能力。
