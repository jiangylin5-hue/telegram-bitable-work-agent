# Telegram 多维表格与数字员工平台文档入口

## Status

- **Document status:** active project document index
- **Current Stage:** Stage09 Codex-style AI conversation SSE
- **Active branch:** `codex/stage09-ai-conversation-sse`
- **Current Progress:** Stage06 是已接受后端基线；Stage07 完成 Mini App/表格工作台基础；Stage08 完成权限过滤的上下文、memory、retrieval 和 LangGraph-first collaboration runtime；Stage09 r39 已部署。当前只在隔离分支实现已批准的 Codex 式 AI 对话工作台和受控 SSE，尚未部署，也未执行真实业务写入。

## 1. 当前阅读顺序

新会话只需先读：

1. [项目协作规则](../AGENTS.md)
2. [Implementation Source Of Truth](00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
3. [当前 Handoff](00-governance/HANDOFF_2026-07-26_CODEX_STYLE_AI_CONVERSATION.md)
4. [阶段/工作树/文档生命周期治理](00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md)
5. [Codex 式 AI 对话设计](08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md)
6. [Codex 式 AI 对话实施计划](08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_IMPLEMENTATION_PLAN.md)
7. [详细 TDD 执行计划](../docs/superpowers/plans/2026-07-26-stage09-codex-ai-conversation-sse.md)
8. [Stage09 r40 回归与线上就绪证据](08-implementation/evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md)

除非当前任务修改历史模块，不要从 Stage02 开始顺序阅读全部文档。

## 2. 稳定产品真源

| Area | Document |
| --- | --- |
| Product constitution | [Implementation Source Of Truth](00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md) |
| Technical baseline | [Technical Decisions](00-governance/TECHNICAL_DECISIONS.md) |
| Generic table resources | [Bitable Schema Blueprint](03-modules/BITABLE_SCHEMA_BLUEPRINT.md) |
| Permissions and safety | [Permission And Security Model](05-data/PERMISSION_AND_SECURITY_MODEL.md) |
| Database | [PostgreSQL Database Design](05-data/POSTGRES_DATABASE_DESIGN.md) |
| Queue/worker | [Redis Queue And Worker Design](06-queue/REDIS_QUEUE_AND_WORKER_DESIGN.md) |
| Document lifecycle | [Project Structure And Document Lifecycle](00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md) |

## 3. 当前 Stage09 文件

| Purpose | Document |
| --- | --- |
| Current handoff | [Stage08/09 与 Codex 式 AI 对话](00-governance/HANDOFF_2026-07-26_CODEX_STYLE_AI_CONVERSATION.md) |
| Approved design/API contract | [Stage09 Codex 式 AI 对话设计](08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md) |
| Stage implementation plan | [Stage09 Codex 式 AI 对话实施计划](08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_IMPLEMENTATION_PLAN.md) |
| Existing UI remediation history | [Stage09 UI 功能完整性修复计划](08-implementation/STAGE_09_UI_FUNCTIONAL_REMEDIATION_PLAN.md) |
| Current live-readiness evidence | [Stage09 r40](08-implementation/evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md) |

## 4. 历史 Stage 入口

历史文档保留用于 schema、migration、安全、外部操作和回归追溯，不是当前执行入口。

| Stage | Status | Primary entry |
| --- | --- | --- |
| Stage02 | historical | `08-implementation/STAGE_02_SOURCE_OF_TRUTH.md` |
| Stage03 | historical deployed evidence | `08-implementation/STAGE_03_SOURCE_OF_TRUTH.md` |
| Stage04 | historical accepted | `08-implementation/STAGE_04_SOURCE_OF_TRUTH.md` |
| Stage05 | historical accepted | `08-implementation/STAGE_05_SOURCE_OF_TRUTH.md` |
| Stage06 | accepted backend baseline | `08-implementation/STAGE_06_SOURCE_OF_TRUTH.md` |
| Stage07 | historical Mini App/workspace delivery | `08-implementation/STAGE_07_SOURCE_OF_TRUTH.md` |
| Stage08 | implemented runtime; product evidence still bounded | `08-implementation/STAGE_08_SOURCE_OF_TRUTH.md` |
| Stage09 | active | 当前文件第 3 节 |

详细历史索引见 [Stage Implementation Docs](08-implementation/README.md)。

## 5. 文档与证据边界

- `project-docs/00-governance/`：当前真源与协作治理。
- `project-docs/08-implementation/`：Stage 设计、计划、合同和验收。
- `project-docs/08-implementation/evidence/`：脱敏的真实命令、外部操作和验收证据。
- `docs/superpowers/specs/`、`docs/superpowers/plans/`：已批准设计和可执行计划。
- `.superpowers/`：当前执行缓存，必须 Git ignore，不是长期项目文档。

完成状态只能由 Acceptance Criteria 对应的测试/观察、evidence 和 commit 支撑，不能由旧 README、总测试数或口头总结推断。
