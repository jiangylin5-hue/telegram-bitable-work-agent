# Stage Implementation Documents

## Status

- **Document status:** active implementation index
- **Current Stage:** Stage09 Codex-style AI conversation SSE
- **Current Progress:** 当前隔离分支为 `codex/stage09-ai-conversation-sse`。阶段/worktree/文档生命周期治理、后端 SSE 和前端 stream client 已完成并复核；Ledgerline 工作台初版已完成，Task 4 review 问题待收口。后端 LLM skill launcher 设计已获用户确认，进入严格 TDD 实施。Nginx、全量验收、视觉 QA、审计、清理和单次最终提交尚未完成。

## 1. Current Execution Entry

按以下顺序读取当前实现：

1. [Current handoff](../00-governance/HANDOFF_2026-07-26_CODEX_STYLE_AI_CONVERSATION.md)
2. [Project structure and document lifecycle](../00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md)
3. [Stage09 Codex-style AI conversation design](STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md)
4. [Stage09 Codex-style AI conversation implementation plan](STAGE_09_CODEX_STYLE_AI_CONVERSATION_IMPLEMENTATION_PLAN.md)
5. [Approved Stage09 LLM skill launcher design](STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md)
6. [LLM skill launcher detailed TDD plan](../../docs/superpowers/plans/2026-07-26-stage09-llm-skill-launcher.md)
7. [SSE and Ledgerline detailed TDD plan](../../docs/superpowers/plans/2026-07-26-stage09-codex-ai-conversation-sse.md)
8. [Stage09 r40 regression and live-readiness evidence](evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md)

当前任务不需要顺序读取 Stage02–Stage08 全部文档。

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
| Stage09 r39 native release | `deployed` | 调查当前 native deployment 和线上只读状态 |
| Stage09 AI conversation slice | `in_progress` | SSE/client 已完成，Ledgerline 初版待修；LLM skill launcher 已批准并进入 TDD |

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

当前 SSE/skill launcher 开发必须满足：

1. 不改变数据库 schema 和 Telegram/外部写入权限；skill launcher 的 API/runtime/permission intersection 已于 2026-07-26 获用户确认。
2. 同步与 SSE assistant 共享授权、scope、幂等、审计和运行服务。
3. 先写失败测试并观察正确 RED，再写最小实现。
4. 前端只渲染白名单事件和最终 `SafeView`。
5. 真实草稿、导入、记录或 Telegram 写入在动作发生前再次确认。
6. 完成声明必须引用测试/浏览器观察、evidence 和 commit。
