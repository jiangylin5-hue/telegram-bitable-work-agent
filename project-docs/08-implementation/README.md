# Stage Implementation Documents

## Status

- **Current Progress Update (2026-07-31):** Human Gold is `48/48`. The bounded deterministic-section correction and its new independent real `48 × 3` campaign are complete, but release remains `FAIL`. All returned-answer and Case gates are `48/48` per round; Retrieval passes; `mixed_02`/`mixed_08` no longer collapse; confirmed/write/send are zero. Composer unavailable is `36/48`, `47/48`, `37/48`, and total-latency P95 worst is `13775.8 ms`. Current bundle hash `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`; old bundle `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6` remains historical. Stage12 remains local and inactive pending a separately approved Provider-schema compatibility or acceptance-contract decision.

- **Document status:** active implementation index
- **Current Stage:** Stage12 comprehensive audit reopened A/B/E/F and cross-stage acceptance; the nine-package correction is approved for local implementation; C/D retain component evidence
- **Previous local-audit snapshot:** Tasks 1–9/Task9B、HG-01～HG-10 与 ISO-01 的实现与本地验收数字保留为历史；其 Human Gold/Provider pending 计数已被上方最新进展取代。

## 1. Current Execution Entry

按以下顺序读取当前实现：

1. [Current root handoff](../../HANDOFF.md)
2. [Implementation Source Of Truth](../00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
3. [Stage12 comprehensive audit](STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md)
4. [Stage12 architecture correction source](STAGE_12_ARCHITECTURE_CORRECTION_SOURCE_OF_TRUTH.md)
5. [Stage12 Task 9 final-answer correction proposal](STAGE_12_TASK9_FINAL_ANSWER_QUALITY_CORRECTION_PROPOSAL.md)
6. [Stage12 Task 9 preflight evidence](evidence/stage12-task9-final-answer-preflight-2026-07-30.md)
7. [Stage12 Task 9 final-answer correction evidence](evidence/stage12-task9-final-answer-correction-2026-07-30.md)
8. [Stage12 Task9B core-quality correction source of truth](STAGE_12_TASK9B_CORE_QUALITY_CORRECTION_SOURCE_OF_TRUTH.md)
9. [Stage12 Task9B core-quality correction evidence](evidence/stage12-task9b-core-quality-correction-2026-07-31.md)
10. [Stage12 Quality Architecture V2 index](../02-architecture/stage12-quality-v2/README.md)
11. [Stage12-C acceptance](STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md)
10. [Stage12 Retrieval/Embedding architecture](../02-architecture/stage12-quality-v2/04_RETRIEVAL_EMBEDDING_AND_CHUNK.md)
11. [Stage12-D code-level plan](../../docs/superpowers/plans/2026-07-29-stage12-d-retrieval-embedding-v2.md)
12. [Stage12-D focused profile evidence](evidence/stage12-d-embedding-profile-benchmark-2026-07-29.md)
13. [Stage12-D acceptance](STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md)
14. [Stage12-D final evidence](evidence/stage12-d-retrieval-embedding-2026-07-29.md)
15. [Stage12-E source](STAGE_12_E_TYPED_SPECIALIST_PROVIDER_SOURCE_OF_TRUTH.md)
16. [Stage12-E code-level plan](../../docs/superpowers/plans/2026-07-30-stage12-e-typed-specialist-provider-v2.md)
17. [Stage12-E acceptance](STAGE_12_E_TYPED_SPECIALIST_PROVIDER_ACCEPTANCE.md)
18. [Stage12-E evidence](evidence/stage12-e-typed-specialist-provider-2026-07-30.md)
19. [Stage12-F architecture](../02-architecture/stage12-quality-v2/06_ACTION_RUNTIME_API_AND_SSE.md)
20. [Stage11 acceptance](STAGE_11_ACCEPTANCE.md)
21. [Stage11 real 48-case report](evidence/stage11-r75-real-48case-report-2026-07-28.md)

当前任务不需要顺序读取 Stage02–Stage10 全部文档。只有调查历史实现或修改对应模块时，才按下方 Stage Lifecycle 进入历史文档。

## 2. Stage Lifecycle

| Stage | Status | Read when |
| --- | --- | --- |
| Stage02 | `historical` | 调查最早 backend kernel、draft/outbox 设计 |
| Stage03 | `historical` | 修改 Telegram webhook、Redis worker 或 Stage03 deployment |
| Stage04 | `historical` | 修改 binding、restricted test send |
| Stage05 | `historical` | 调查早期 OpenRouter/LangGraph/advertising template |
| Stage06 | `accepted` backend baseline | 修改 generic platform resource、permission、import 或 digital employee core |
| Stage07 | `historical` Mini App/workspace delivery | 修改 Mini App table surface、view、governance、draft UI |
| Stage08 | `implemented`, product evidence bounded | 修改 context、memory、retrieval、collaboration runtime |
| Stage09 | `historical deployed foundation` | 调查 native deployment、SSE、Ledgerline、skill launcher 和中文响应修复 |
| Stage10 | `accepted control plane` | 修改 durable run/command/event/checkpoint、outbox 或 SSE runtime |
| Stage11 | `deployed; runtime/safety pass, quality fail` | 修改协调中间层、真实 48 Case 或当前生产 r76 |
| Stage12 | `local quality improved; release FAIL` | bounded correction 已消除回答坍缩，但真实 Provider schema 可用性与延迟未达门；生产激活仍需单独确认 |

## 3. Historical Primary Entrypoints

每个历史 Stage 先读自己的 Source Of Truth，再按需要进入 plan/SDD/BDD/API/acceptance。不要从 README 推断最终状态。

| Stage | Source | Final/Current evidence |
| --- | --- | --- |
| Stage02 | [Source](STAGE_02_SOURCE_OF_TRUTH.md) | [Final acceptance](STAGE_02_FINAL_ACCEPTANCE_REPORT.md) |
| Stage03 | [Source](STAGE_03_SOURCE_OF_TRUTH.md) | [Final acceptance](STAGE_03_FINAL_ACCEPTANCE_REPORT.md) |
| Stage04 | [Source](STAGE_04_SOURCE_OF_TRUTH.md) | [Final acceptance](STAGE_04_FINAL_ACCEPTANCE_REPORT.md) |
| Stage05 | [Source](STAGE_05_SOURCE_OF_TRUTH.md) | [Final acceptance](STAGE_05_FINAL_ACCEPTANCE_REPORT.md) |
| Stage06 | [Source](STAGE_06_SOURCE_OF_TRUTH.md) | [Stage acceptance](STAGE_06_STAGE_ACCEPTANCE_REPORT.md) |
| Stage07 | [Source](STAGE_07_SOURCE_OF_TRUTH.md) | [Final audit](STAGE_07_FINAL_AUDIT_REPORT.md) |
| Stage08 | [Source](STAGE_08_SOURCE_OF_TRUTH.md) | [Runtime closure](evidence/stage08-runtime-closure-2026-07-23.md) |
| Stage09 | [AI conversation design](STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md) | 当前 evidence 在交付后新增 |

## 4. Document Ownership

| Document type | Owns | Does not own |
| --- | --- | --- |
| `SOURCE_OF_TRUTH` | Stage 范围、边界、状态 | 逐任务终端日志 |
| `DESIGN` / `SDD` | 架构、数据流、权限和错误策略 | 实际通过声明 |
| `IMPLEMENTATION_PLAN` | 任务顺序、接口、TDD 和验收 | 外部环境事实 |
| `BDD` / `ACCEPTANCE` | Requirement 和成功标准 | 未执行的结果 |
| `PROGRESS` | 当前 Stage 的可定位进度 | 跨 Stage 顶层真源 |
| `evidence/` | 实际命令、结果、环境边界、清理 | 设计授权 |

## 5. Retention and Cleanup

- 保留 Alembic migrations、外部操作证据、安全/权限/并发证据和最终 acceptance。
- `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 是已批准设计/计划，保留。
- `.superpowers/` 是 brief/report/review/ledger 生成缓存，Git ignore，不再提交。
- 历史文件不因“旧”而删除；只有确认完全重复、无引用且不承担审计后才删除。
- 当前状态只更新 current Stage plan、current evidence、current handoff；不要回写所有历史 Progress。

## 6. Development Gate

当前 Stage12 gate：

1. 已完成 `stage12-quality-v2/README.md` 及八个主题文档审计并获得用户确认。
2. Stage12 architecture-correction Tasks 1–9/Task9B 与 bounded deterministic-section correction 均已 `implemented-local`；确定性和 post-correction real-campaign Case/final-answer gates 均为 `48/48`。
3. Human Gold `48/48` 与 post-correction exactly-three real Provider rounds 已完成，但总体 release 因 Provider schema availability 与 total latency 为 `FAIL`。下一步先批准 focused Provider compatibility 或 acceptance-contract 方向；不得直接再跑全量 campaign。不得通过 Case 特判或把 Specialist fact 冒充 Query fact 来迎合 Gold；Action 必须继续复用 F durable authority。
4. 行为变化必须先写失败测试并观察正确 RED，再写最小实现。
5. Action end-to-end 测试不得注入 Gold candidate；真实 LLM 至少三轮的 48 Case 大评测在核心技术架构完成后的总验收执行。
6. 权限和 external-send safety 必须始终为 1.00，不能被综合分抵消。
7. 真实草稿、记录、任务或 Telegram 写入必须经过 Tool Gateway 和确认。
8. 按用户要求，完整开发、验收、审计和清理结束后再统一提交。
