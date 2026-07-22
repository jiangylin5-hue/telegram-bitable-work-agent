# Stage07 R0–R3 Closure Handoff

## 0. Read This Before Doing Anything

This file is written for a completely new Codex session with no prior conversation context. It is the current handoff for Stage07. R0-R3 assembled substantial implementation and evidence, but the strict final audit finds Stage07 **not accepted**. It is **not** permission to deploy production, send another Telegram message, or add a new Bot capability.

> 中文入口：先阅读 [Stage07 收口开发与验收报告（中文）](project-docs/08-implementation/STAGE_07_CLOSURE_REPORT_CN_2026-07-16.md)，再按本交接文档的读取顺序进入源码与原始 BDD/SDD。该中文报告不替代逐条验收账本。

## 0.1 新会话立即执行指南（2026-07-16，优先于旧日志）

### 本会话已经完成、但不应在新会话口头重报为“全阶段完成”的事实

1. 已定位真实 OpenRouter 配置于项目根目录忽略的 `.local/stage05-real-workflow.env`。密钥**绝不**打印、复制、写入 Markdown、提交 Git 或传给前端；仅允许通过子进程 `STAGE06_ENV_FILE` 传给既有 smoke 脚本。
2. 已完成的真实 Provider 证据：Team Bot safe route，以及 Stage06 shared live runtime 的 `summarize_basic`、`hidden_field_guard`、`citations_required`、`draft_update_status`、`unsafe_commit_refusal`。输入均是合成数据；无 Telegram 发送、无 webhook 变更、无远程部署/服务器写入；草稿保持 `pending_confirmation`，原记录未写入，未持久化原始 prompt/response。权威记录见 `project-docs/08-implementation/evidence/stage07-real-openrouter-provider-validation-2026-07-16.md`。
3. 已新增 TD009 客户端闭环测试：网络错误固定文案与重试、已选 view `404` 清理和延迟旧员工请求丢弃。定向 `4 passed`；之后 Mini App 全量 `63 files / 230 passed`，`npm.cmd run build` 通过。权威记录见 `project-docs/08-implementation/evidence/stage07-td009-client-closure-2026-07-16.md`。
4. 验收账本已将 `DE-A03/A04`、`ACD-A03/A06/A07/A08` 标为 `evidenced-pending`，**不是** `accepted`。Stage07 总状态仍是 `not accepted`。

### 新会话不得重做或误做的事

- 不得输出或扫描显示 `.local` 中的任何密钥值；不提交 `.local`、`.env`、令牌、chat id、真实 prompt/response 或真实业务标识。
- 不得为了“补测试”重发 Telegram、切换 webhook、修改 BotFather、SSH 写远端、部署/重启 Stage03 或 Stage07。此前外部证据是一次性、受用户授权的历史事实；需要新外部写入时必须再次取得用户明确授权。
- 用户明确不允许控制其 Chrome。若需视觉验收，只能使用 Codex **内置浏览器**；此前该 Browser webview 在本地 fixture 观察中脱离，不能把旧截图或 Testing Library 结果冒充为新的内置浏览器验收。
- 不得顺手实现客户群绑定、客户消息直写任务、群发、RAG、持久记忆、文件知识库、通用 Agent Builder、多 Base 员工、生产发布。这些均超出 Stage07 已批准范围，并且会改变 schema/API/权限/保留策略。

### 新会话的严格执行顺序

1. 先读本文件的「Mandatory read order」、中文收口报告、最终审计、验收矩阵和当前包的原始 BDD/SDD；以 `project-docs/08-implementation/evidence/stage07-acceptance-evidence-matrix.md` 为逐行状态唯一账本。
2. 运行 `git status --short`，保留当前 dirty worktree 的既有改动；不得 reset、checkout 或删除未跟踪文件。先运行 `git diff --check`。
3. 先执行不需要外部写入的回归：`mini-app` 的 `npm.cmd test -- --run` 与 `npm.cmd run build`；后端和 PostgreSQL 只运行与要补的 BDD 行对应的现有命令。更新证据时必须记录命令、结果、数据/环境边界，不得只写“通过”。
4. 对仍是 `blocked` 的每一行，先区分“缺实现”与“缺证据”。只有源码/测试明确暴露实现缺口时，才能按原 BDD/SDD 做最小 TDD 修复；仅缺内置浏览器观察时，不得无谓改业务代码。
5. 仅在 Codex 内置浏览器可连接、并创建完可销毁的本地 fixture 后，做真实渲染/焦点/宽度/文件选择的验收。每项必须保留观察路径、窗口宽度、角色/授权状态、固定错误文案和清理结果。若 Browser 仍无法连接，准确记录阻塞，不改用用户 Chrome。
6. 每完成一项只将对应矩阵行从 `blocked` 提升为 `evidenced-pending`；全部原 BDD 行经独立对照后，才可讨论 `accepted`。不得用总测试数、历史截图、API route smoke 或 Provider smoke 代替 literal Mini App UI 验收。

### 新会话当前待收口的严格验收项

| 包 | 仍未闭环的 Requirement ID / 事实 | 新会话应做什么 |
| --- | --- | --- |
| V1 | `V1-A02/A05/A07/A08/A10` | 内置浏览器的 denied/invalid/numeric lookup/type/role/four-width 矩阵。 |
| Template/Import | `TI-A04/A06/A08` | 真实本地文件选择、预览/提交，以及四宽度焦点/安全错误。 |
| Governance | `GR-A03/A06`、`GW-A07` | authorized/denied/retry/paging/stale terminal 的 Browser 观察。 |
| TD005/TD006 | `DE-A05/A08/A09`、`CB-A06`，另有 TD006 BDD 逐条对照缺口 | field-filtered draft、失败清理、焦点/四宽度；不可绕过草稿确认。 |
| TD009 | `ACD-A10` | Codex 内置浏览器的 Home → 受限联系人 → 授权 view → reread → summary → 显式 Base handoff 的可视化/焦点记录。 |
| TD010 | `DEM-A01` 至 `DEM-A10` | manager/member 分离、`paused -> active read-only -> paused`、冲突 reread、桌面/移动焦点返回。 |
| TD011 | `TBK-A04` 至 `TBK-A09` | literal non-empty Mini App UI → 本地 API → 已有 Provider 的路径，以及 reselect/error/focus；必须与 API-route Provider smoke 分开记录。 |

### 本轮结束条件

新会话必须以矩阵逐行结果、变更文件、实际命令、跳过项及阻塞原因结束。若上述 Browser 行仍因 Codex 内置浏览器不可连接而无法验证，应报告 `blocked`，而不是继续扩展产品能力或宣称 Stage07 完成。

### 新会话必须了解：LLM、记忆、提示词与技术栈（2026-07-16）

**当前阶段真实状态**

- Stage07 是“表格权限 + 受控 LLM 单次调用 + 草稿确认 + 审计”的安全骨架，尚不是完整的 Telegram 协作 Agent 平台。
- LLM 上下文由服务器重新读取并投影：员工 scope -> 调用者权限 -> 当前 Base/Table/View/字段 -> 当前可见 records。浏览器、Telegram 文本、历史聊天和原始数据库不会直接作为模型上下文。
- 当前 live graph 只有 `prepare_context -> call_openrouter -> validate_output -> END`；没有 LangGraph checkpointer、跨轮 thread、持久对话、Supervisor 动态委派或任意 tool loop。
- Team Bot 对当前授权 View 先读取 `101` 条、只将前 `100` 条带入模型，并用 `truncated` 表示截断。它不是全文检索或 RAG。
- 当前 system prompt 强制 JSON、仅使用给定权限数据、不得宣称写入成功；user payload 是 action、employee、instruction、safe schema、safe records、record ID、skill evidence、response schema/output template 的结构化 JSON。OpenRouter JSON mode 后仍由服务端校验 output、citation 和 draft 边界。
- `prompt_version` 目前是代码中固定的稳定标签，如 `stage06-live-digital-employee-v1`；没有 prompt registry、灰度、回滚、离线评估集、模型路由或成本阈值系统。

**记忆边界（不可误报）**

- Stage07 **没有**长期/短期持久化 LLM memory、conversation thread、chat history、memory partition、retention/clear controls、embedding、vector retrieval、RAG、文件/URL 知识库或 browser localStorage 记忆。
- React 组件中的 selected employee/view、instruction、answer、request generation 是一次性临时状态；切换/关闭会清除，不是记忆。
- PostgreSQL records/views、record drafts、AgentRun/audit、idempotency receipt 和 Redis/Query cache 分别是业务事实、受控草稿、审计、重试控制和短期技术状态，**不是**语义记忆。
- 不得因 `pgvector/pgvector:pg16` 已出现在部署基础设施，就声称已做 vector search。它只是未来能力的基础条件。

**当前技术栈**

- Backend：Python 3.12+、FastAPI、Uvicorn、Pydantic、HTTPX。
- Data：PostgreSQL、JSONB、SQLAlchemy 2.x、Alembic、psycopg 3；pgvector ready but unused.
- Async：Redis 7、Redis Streams、Worker、Outbox bridge。
- Agent：LangGraph、OpenRouter-compatible API、`StructuredLLMClient`（fake/live）、deterministic Stage06 skill matching。
- Telegram：Bot API、Webhook、Mini App `initData` HMAC、deep-link resolver。
- Frontend：React、TypeScript、Vite、Tailwind CSS 4、TanStack Query、lucide-react、CVA/clsx、Vitest/Testing Library。
- Deployment/test：Docker Compose、Caddy、pytest、local disposable PostgreSQL integration tests。当前 UI 使用 shadcn-style 设计基线，但未安装独立 `shadcn/ui` runtime package，不能宣传为完整 shadcn 组件生态。

**当前未完成的严格验收**

- V1：`V1-A02/A05/A07/A08/A10` 的 denied/invalid/numeric lookup/type/role/four-width Browser matrix。
- Template/Import：`TI-A04/A06/A08` 的真实文件选择、预览/提交和四宽度焦点/错误 matrix。
- Governance：`GR-A03/A06`、`GW-A07` 的 Browser denied/retry/paging/stale terminal states。
- TD005/TD006：`DE-A05/A08/A09`、`CB-A06` 的 field-filtered Browser、failure/focus/four-width evidence；`DE-A03/A04` 已有真实 Provider 证据但仍仅 `evidenced-pending`。
- TD009：仅 `ACD-A10` 的内置 Browser 完整视觉验收仍被阻塞；`ACD-A03/A06/A07/A08` 均有明确自动化或 PostgreSQL 证据但仍仅 `evidenced-pending`。
- TD010：`DEM-A01`--`DEM-A10` 的完整 manager/member、paused -> active read-only -> paused、conflict reread 和 focus/width Browser record。
- TD011：`TBK-A04`--`TBK-A09` 的 literal non-empty Mini App UI -> API -> Provider 及 error/reselect/focus evidence。

**真实 Provider 测试规则**

- 用户指出的真实 OpenRouter key 已在项目根目录的忽略 `.local/stage05-real-workflow.env` 文件中定位。绝不打印、复制或提交密钥；只为子进程设置 `STAGE06_ENV_FILE`，并在进程退出后移除该变量。
- 2026-07-16 的真实 Provider 验证已通过：Team Bot safe route，以及 Stage06 shared live runtime 的 `summarize_basic`、`hidden_field_guard`、`citations_required`、`draft_update_status`、`unsafe_commit_refusal`。完整 prompt/response 未持久化，草稿保持 `pending_confirmation`，原合成记录未写。证据在 `project-docs/08-implementation/evidence/stage07-real-openrouter-provider-validation-2026-07-16.md`。
- 此证据将 TD005 `DE-A03/A04` 移到 `evidenced-pending`，但不关闭 TD011 的 literal rendered Mini App UI -> Provider 验收，亦不自动授权任何 Telegram/webhook/deployment 操作。

**后续架构门槛**

不要在 Stage07 顺手实现 memory/RAG。下一阶段若要支撑“Telegram 与客户沟通、团队协作、项目健康与风险提醒”，必须先由用户确认一个 AI Runtime / 项目记忆 / 知识检索技术决策包：Memory Item schema、workspace/project/user 分区、源 record/provenance、字段级过滤、TTL/retention/clear/delete/export、embedding/indexing、retrieval 排序、prompt registry、评估集、模型路由/成本、人工确认和审计。此项会改变 schema/API/权限/保留策略，属于单独技术方案讨论，不在 Stage07 验收收口中实现。

### Latest closure state — 2026-07-15

- The user instructed us to implement any remaining in-scope unfinished/half-finished Stage07 work and to never substitute a verbal completion claim for evidence. The current closure record is [project-docs/08-implementation/evidence/stage07-final-closure-validation-2026-07-15.md](project-docs/08-implementation/evidence/stage07-final-closure-validation-2026-07-15.md).
- Implemented in this pass: safe release of pending and persistent idempotency reservations after a Team Bot or TD005 runtime/provider failure; TD009 assistant catalog table-scope recheck after selection/revocation; server `instruction <= 1000`; save-first employee activation guard; Template/Import conflict lock and complete protected import-query cleanup.
- Verified after implementation: backend `651 passed, 18 skipped`; the latest Mini App full regression is `63 files / 230 passed` and production build passed; focused real-local-PostgreSQL Team Bot retry `1 passed`, TD005 retry `1 passed`, TD009 scope-revocation `1 passed`. On 2026-07-16, the dedicated TD009 client closure command added `4 passed` for network-safe retry, revoked-view `404` cleanup and delayed employee-selection replacement; see `project-docs/08-implementation/evidence/stage07-td009-client-closure-2026-07-16.md`.
- A synthetic local FastAPI/PostgreSQL fixture was opened only with the Codex in-app Browser. It rendered a management create/table/view/member selection path, then the Browser webview detached. This is **not** TD010 lifecycle/role/mobile/focus acceptance and must not be reported as such. No user Chrome browser was controlled.
- The earlier local OpenRouter-preflight statement is superseded. The ignored local environment file was used only through `STAGE06_ENV_FILE` in a child process, and the safe Team Bot route plus five shared Stage06 runtime cases completed with a real Provider. No Telegram send, webhook mutation, remote deployment or server write occurred. See `project-docs/08-implementation/evidence/stage07-real-openrouter-provider-validation-2026-07-16.md`; never print or commit the key.
- The strict remaining acceptance rows are V1 Browser matrix, Template Browser file/four-width matrix, Governance Browser terminal states, TD005 Browser matrix, TD009 built-client visual review, TD010 complete lifecycle Browser evidence and TD011 literal Mini App UI -> provider path. Their exact requirement IDs are maintained in `stage07-acceptance-evidence-matrix.md`; do not reclassify them as complete because aggregate suites pass.

### Pitfall discovered in this closure

`begin_idempotent_operation` can return a SQLAlchemy **pending** record before flush. Calling `session.delete(record)` on that record raises `InvalidRequestError`, which leaves retries blocked. Cleanup must use `inspect(record)`: `expunge` pending records and `delete` persistent records, then commit. The red/green Team Bot unit and real-local-PostgreSQL tests cover this. Do not simplify the helper back to unconditional `session.delete`.

### Current repository state

- Worktree: `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui`
- Branch: `codex/stage07-mini-app-ui`
- User language: Chinese. Keep code, API, database names and stable status fields in English.
- Worktree is already dirty with prior Stage07 work. Treat unrelated existing edits as user-owned; inspect `git status --short` and never discard/revert them.
- No commit, push, pull request or branch merge has been performed for the current R0–R3 closure work.
- R0 is complete. Stage07 acceptance remains open; the detailed current authority is `project-docs/08-implementation/STAGE_07_FINAL_AUDIT_REPORT.md`. `evidence/stage07-r0-r3-final-reconciliation.md` is supporting evidence only, not a final decision.

### Mandatory read order

1. `AGENTS.md`
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
3. `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`
4. `project-docs/08-implementation/STAGE_07_R0_PRODUCT_ALIGNMENT_DESIGN.md`
5. `project-docs/08-implementation/STAGE_07_R0_ORIGINAL_CONTRACT_INVENTORY.md`
6. `project-docs/08-implementation/STAGE_07_R0_CLOSURE_MATRIX.md`
7. `project-docs/08-implementation/STAGE_07_FINAL_AUDIT_REPORT.md`
8. `project-docs/08-implementation/evidence/stage07-r0-r3-final-reconciliation.md` (supporting evidence only)
9. `docs/superpowers/plans/2026-07-15-stage07-r1-r3-closure.md` (historical execution plan)
10. The original technical decision, BDD, SDD, work-surface and implementation plan for the package being changed.

## 1. What We Are Building

The platform is a Telegram-first generic multidimensional-table and no-code workspace product. Durable product order remains:

```text
workspace
-> base
-> table
-> field schema
-> record
-> view / form / dashboard-lite
-> permission
-> template / import
-> digital employee
-> draft confirmation
-> audit
```

Telegram is an entry and communication surface, not a substitute for durable business data. A chat message, temporary agent memory or unpersisted JSON is not a completed business result.

Stage02–Stage05 advertising-agency work is historical evidence and may be an optional template. It must not become the product's top-level model.

## 2. Confirmed Product Direction From the 18-Question Discovery

The following answers are explicit user decisions. They are the business truth for future Stage07 closure and later stages.

| # | Question area | User selection | Product decision |
| --- | --- | --- | --- |
| 1 | First paying customer | `B + C` | Prioritize sales/customer-operations teams and enterprise internal-function teams. |
| 2 | First high-frequency workflow | `C + A` | Serve cross-department project execution plus customer-to-delivery coordination. |
| 3 | Primary business objects | `B + A + C` | Customer/Opportunity, Project and Task are all first-class; do not reduce the product to one object. |
| 4 | Data organization | `A` | Use a relational multi-table model, not a single overloaded spreadsheet. |
| 5 | First cost-reduction problem | `A + C` | Prevent project progress loss and give managers real-time project health. |
| 6 | Daily product entry | `A` | Telegram supplies reminders/light actions; Mini App supplies detail, table and controlled operations. |
| 7 | First digital employees | `A + B` | A Project Progress Assistant and Sales Operations Assistant are both relevant. |
| 8 | Initial data onboarding | `A or B` | Support both templates/Excel-CSV import and manual creation. Do not assume clean migration data. |
| 9 | External communication context | Free-text clarification | Target teams already use Telegram with customers and for team collaboration; customer project groups are real operating context. |
| 10 | Telegram group binding model | `A` | One customer project Telegram group maps to one Project. |
| 11 | Converting group requests to work | `B` | Bot uses a structured fixed-field conversation rather than opaque free-text inference. |
| 12 | Who can directly create an internal task | `A` | Only internal project members may create after structured input; customer messages must not directly enter the internal task pool. |
| 13 | Bot proactive communication | `A` | Send key-event alerts only; never high-frequency row-by-row synchronization. |
| 14 | Manager first screen | `A` | Prioritize project health: progress, milestones, blockers, waiting customer, overdue work and risk. |
| 15 | Required task data | `A` | A task requires Project, title, owner, due date and status. |
| 16 | Task state model | `A` | Fixed states: `not_started`, `in_progress`, `blocked`, `waiting_customer`, `done`. |
| 17 | Risk discovery | `A` | The Project Progress Assistant proactively scans explicit risk rules. |
| 18 | Default risk recipient | `A` | Risk alerts go to an internal project group or responsible internal member first; a customer-facing message requires responsible-person confirmation. |

### Product synthesis

The initial durable business loop is:

```text
Import/template or manual creation
-> Customer/Opportunity, Project and Task tables
-> Project-linked accountable tasks and fixed task states
-> internal Mini App reads/controlled updates
-> project-health views and permitted digital-employee summaries
-> internal risk action first
-> future confirmation-controlled customer-group communication
```

The required relational shape is:

```text
Customer / Opportunity
    -> Project
        -> Task
```

This does **not** authorize the following new behavior in the current R0–R3 pass: persistent Telegram group-to-Project mapping, internal Bot direct-task command, customer message intake state machine, scheduled risk sends, customer-group send, customer Mini App authorization, RAG, memory, files, public links, broadcast or multi-Base employee scope. Those require a later dedicated technical decision because they change persistence, API, identity, permissions and external side effects.

## 3. User’s Current Stage07 Instruction

The user explicitly selected the Stage07-first approach and then clarified its exact meaning:

> Every originally approved Stage07 function that is unfinished or half-delivered, and does not conflict with the confirmed business direction, must be completed. Do not reclassify it as later scope merely to make Stage07 appear smaller.

Therefore:

- `partial-local` is not a final disposition. Determine whether code is missing, evidence is missing, or documentation is stale.
- Original approved schema/API/permission behavior may be implemented without asking again, provided it remains inside the original document boundary.
- A genuinely new schema/API/permission/external-action change still requires a new technical decision and user confirmation.
- Work must be grouped into coherent R1/R2/R3 substages. Do not fragment the stage into tiny unrelated microtasks.

## 4. R0–R3 Delivery Map

### R0 — Product alignment and original-contract inventory

Status: **completed**. Documentation package exists:

- `project-docs/08-implementation/STAGE_07_R0_PRODUCT_ALIGNMENT_DESIGN.md`
- `project-docs/08-implementation/STAGE_07_R0_PRODUCT_ALIGNMENT_BDD_AND_ACCEPTANCE.md`
- `project-docs/08-implementation/STAGE_07_R0_PRODUCT_ALIGNMENT_SDD.md`
- `project-docs/03-modules/STAGE_07_R0_PRODUCT_ALIGNMENT_WORK_SURFACE.md`
- `project-docs/08-implementation/STAGE_07_R0_PRODUCT_ALIGNMENT_COMPLEX_FEATURE_INDEX.md`
- `project-docs/08-implementation/STAGE_07_R0_ORIGINAL_CONTRACT_INVENTORY.md`
- `project-docs/08-implementation/STAGE_07_R0_CLOSURE_MATRIX.md`

R0 established the product truth and completed the document-by-document original-contract inventory. It was reopened after the user clarified that compatible original work must not be deferred; that clarification is now incorporated in the matrix and R1-R3 plan. R0 authorizes no new contract or external action. R1 remains active and cannot be called complete until its residual rows close.

### R1 — Customer-project core and safe operations

Scope: Foundation, Home/Base navigation, Base/Table/Field/Relation/Lookup reuse, V1 saved views, Template/Import, record conflict/re-read and their existing-contract evidence. It must use synthetic Customer/Project/Task data, no new group binding or Bot write.

Current immediate test-first artifact:

- `backend/tests/unit/test_stage07_customer_project_core_api.py` was just added with a synthetic Customer/Project/Task relation, viewer-field omission and outsider-denial scenario.
- It passed (`1 passed`) after a test-fixture correction: relation candidates were always safe, but the original fixture had not declared the relation field in the Project view's explicit field list. No production code or permission rule changed.
- `mini-app/src/test/customer-project-core-app-flow.test.tsx` passed (`1 passed`): safe Customer -> Project -> Task labels, record-detail open/close and return navigation work without rendering opaque IDs.
- Current-contract focused suites also passed: backend `39 passed`; Mini App `11 files / 53 tests passed`; disposable PostgreSQL builder `11 passed`; disposable PostgreSQL template/import authorization `6 passed`; Mini App build passed.
- Codex in-app Browser loaded the built client against a temporary safe local synthetic fixture. At `1440`, it completed Home -> Base -> Projects -> Tasks -> Record Detail -> Projects with business labels and no opaque IDs; at `1280`, `430` and `390`, the Base workbench, tabs and Project label remained visible. Final console `error`/`warn` count was `0`.
- A second disposable built-client fixture pass closed the current Home/Base empty/denied render states and bounded V1 recovery proof: owner Grid/Kanban/Calendar/Form semantics, Builder/template-import entry, viewer omission of view/schema/record/management controls, and a `409` View conflict that showed fixed copy then re-read canonical view/row labels. The owner workbench and Builder dialog remained reachable at `390 x 844`; only informational official Mini App bridge logs were present. Controlled `ImportWizard` tests supply the approved file-input preview/mapping/commit alternative; do not claim Browser-native chooser selection.
- The temporary fixture process and source were deleted and port `4179` is closed. This is rendered-client evidence only, not FastAPI/PostgreSQL/identity/Telegram proof. Full detail: `project-docs/08-implementation/evidence/stage07-r1-customer-project-core.md`.
- No production code was changed by these R1 tests/evidence because no test exposed a current-contract product defect.

### R2 — Governance, drafts and digital employees

Scope: compatible approved S3/S4, TD005/TD006, TD009, TD010 and TD011 work. Mandatory remaining examples:

- hidden-field/resource omission in UI/cache/safe evidence;
- governance terminal/denied/conflict UI states;
- field-filtered draft confirm/reject/replay/conflict/expiry lifecycle;
- TD009 PostgreSQL intersection/revocation and delayed replacement;
- TD010 management workbench visual/lifecycle evidence;
- TD011 non-empty permitted Team Bot Mini App -> safe route -> real provider path.

Do not add memory/RAG/files/generic direct writes/Telegram group actions under R2.

### R2 evidence added in this continuation

- Focused backend unit packages pass `41 passed`; the five approved disposable local PostgreSQL packages pass `11 passed`; focused Mini App packages pass `20 files / 62 tests`; and the production build passes.
- A reusable test-first harness, `backend/scripts/stage07_team_bot_live_openrouter_smoke.py`, was added for the exact approved safe-route provider path. Its missing-module test first failed; its preflight/service/API regression then passed `9 passed`.
- With the existing ignored local OpenRouter environment file loaded, the harness made one real provider request through the existing Mini App Team Bot contacts -> permitted context -> summary API sequence. All three routes returned `200`; the summary was non-empty, had one safe citation, contained an audit receipt and agent run, and left its one synthetic record unchanged. It stores/emits no raw prompt, response, identifier or secret.
- The built Mini App was separately exercised in the Codex in-app Browser with a loopback-only safe fixture: Home -> `团队 Bot` -> `Project Progress Assistant` -> `Project Risks` -> summary; the synthetic citation/audit receipt rendered, the `390 x 844` viewport retained the Team Bot/summary/receipt, and console `error`/`warn` count was `0`. This fixture never called a provider and was not the user's Chrome.
- Together these are real safe-route-to-provider evidence plus client rendering evidence, **not** a literal browser UI-to-provider run, Telegram, production database, staging or whole-R2 acceptance. Full detail: `project-docs/08-implementation/evidence/stage07-r2-governance-draft-employee.md`.

### R3 — Telegram truth, visual matrix and final audit

Scope: correct stale TD007/TD008 documentation, preserve S6.3 cleanup evidence, consolidate safe selected-design visual evidence and run the final Stage07 traceability audit.

Do not send a new Telegram message. The observed bounded S6 evidence is sufficient for the existing approved smoke; no automatic retry or redeployment is authorized.

### R3 reconciliation completed in this continuation

- TD007/TD008/S6.3 are now stated consistently in the active checklist, roadmap, source-of-truth, traceability audit and final-closure evidence: two separately approved one-attempt isolated non-production deliveries occurred; the first exposed the missing official Telegram bridge; the bridge repair was test-first; the second completed the signed resolver/Base reread; and the isolated environment was removed while Stage03 health remained intact.
- Those facts close the bounded external smoke only. They do **not** authorize another Telegram send, restored deployment, Stage03 mutation, group delivery, staging/production claim or whole-stage completion.

### Historical blockers before final reconciliation

These are the remaining compatible Stage07 rows, not new business scope:

1. R1: remaining evidence is now limited to verified identity/session/revocation, Home queue-to-Draft Hub, cursor/error breadth, editor visual treatment and all invalid/F2/device V1 states. Authorized/empty/denied Base rendering, bounded owner/viewer V1 controls, one `409` canonical reread and the approved controlled import alternative are closed.
2. R2: complete dedicated governance/draft/employee-management visual and terminal/recovery observations. The Team Bot selection/rendering UI now has a safe local-fixture observation and the provider safe route has a real smoke; do not merge those two proofs into a user-operated Mini App/provider assertion.
3. R3: rerun the final proportional integrity/traceability check only after those rows are closed, and keep Stage07 explicitly open if any one remains unaccepted.

The external Telegram and real OpenRouter prerequisites are no longer the current blockers. Do not invent Customer-group binding, structured Bot direct task creation, customer intake, risk send, memory, RAG, files or new schema/API/permissions to solve these residual Stage07 rows.

### Current R0-R3 Acceptance State

The historical evidence pass does not close the residual list merely because it contains focused tests or fixture observations. A new session must follow `STAGE_07_FINAL_AUDIT_REPORT.md`, which identifies compatible original BDD/SDD evidence gaps to close before Stage07 can be accepted.

- R1 closes with backend identity/pagination `31 passed`, Customer/Project/Task/V1/import evidence and built-client draft/pagination/editor recovery.
- R2 closes with existing focused backend/PostgreSQL/Mini App/build evidence, TD009 backend `2 passed`, TD009 Mini App `2 files / 3 passed`, governance/draft/assistant/employee Browser observations and the already recorded real safe-route OpenRouter result.
- R3 closes with selected 1440/1280/430/390 coverage, exact evidence/doc reconciliation, fixture deletion/port closure and the current non-production decision.
- Production rollout and all customer/group/RAG/memory/files/direct-write expansions are later technical-decision work. They are not unfinished Stage07 scope.

## 5. Actual Completion Status Before R0–R3

These are bounded facts, not a whole-stage completion claim.

| Family | Direct status |
| --- | --- |
| P3 Base/Table Builder | `implemented-local` with real disposable PostgreSQL rollback/concurrency/default-view evidence. |
| F1 Field Builder | `implemented-local` with approved types, local PostgreSQL and four-width local UI evidence. |
| F2 Relation/Lookup | `implemented-local` with same-Base relation, fixed lookup aggregation, local PostgreSQL and four-width local UI evidence. |
| V1 Saved View Builder | `partial-local`; typed/server/local PostgreSQL and partial real-backend UI evidence exist; stale/type-invalid/full role/width acceptance remains. |
| Template/Import | Source/test implementation exists, but originating BDD has stale `design-only` wording and browser upload evidence is incomplete. |
| S3/S4 Governance | local implementation exists; selected visual/terminal evidence remains incomplete. |
| TD005/TD006 Draft Hub/context binding | local bounded implementation exists; lifecycle Browser/provider evidence and some progress wording need reconciliation. |
| TD009 Personal Assistant | `partial-local`; PostgreSQL intersection/revocation, delayed replacement and visual evidence remain. |
| TD010 Employee Management | `implemented-local`; management workbench visual/lifecycle evidence remains. |
| TD011 Team Bot | `partial-local`; real non-empty permitted safe-route -> provider smoke and fixture-based Mini App selection/rendering evidence are recorded. A literal user-operated UI -> provider proof remains unclaimed. |
| TD007/TD008/S6.3 Telegram | bounded real non-production identity/deep-link/delivery and cleanup were observed; several older BDD/checklist rows still falsely say the smoke is pending. |

### Latest verified regression evidence

- Mini App: `61` files / `222` tests passed.
- Mini App build: passed.
- Real OpenRouter safe matrix: five approved cases passed with no pre-confirmation record write and no raw prompt/response persistence.
- S6.3: two separately user-approved one-attempt deliveries produced `sent`/outbox-processed receipts. The first exposed the missing official WebApp bridge; after a test-first bridge correction, the second produced the real signed-launch resolver outcome `resolved` for a Base destination.
- S6.3 cleanup: isolated Compose services/volumes/runtime directory, Caddy host/backup and temporary SSH public key were removed. Stage03 health stayed `200` before, during and after cleanup; the revoked key was rejected by a batch-mode SSH check.

### Current files changed in this continuation

Do not claim every dirty file below was created in this continuation; many existed beforehand. The current continuation directly added or changed:

- `mini-app/index.html` — official Telegram WebApp bridge script before Vite module.
- `mini-app/src/test/telegram-mini-app-host-page.test.ts` — bridge host-page regression.
- R0 package, original-contract inventory and R1–R3 plan named above.
- `backend/tests/unit/test_stage07_customer_project_core_api.py` — passing Customer/Project/Task safe-relation and authorization regression.
- `mini-app/src/test/customer-project-core-app-flow.test.tsx` — passing server-backed Mini App core-flow regression.
- Top-level Stage07 source, progress, roadmap, checklist, traceability and S6 evidence documents to record actual S6.3 cleanup/closure and R0 direction.
- `project-docs/08-implementation/evidence/stage07-r1-customer-project-core.md` records the exact R1 safe-core tests, built-client boundary and temporary-fixture cleanup. The client flow is synthetic safe-DTO coverage, not server-backed acceptance.
- `backend/scripts/stage07_team_bot_live_openrouter_smoke.py` and `backend/tests/unit/test_stage07_team_bot_live_openrouter_smoke.py` provide the bounded Team Bot real-provider smoke without secret or raw-business output.
- `project-docs/08-implementation/evidence/stage07-r2-governance-draft-employee.md` records the exact R2 regression, real-provider and remaining-boundary evidence.

## 6. External Acceptance History and Current External Boundary

### Completed bounded non-production operation

The earlier isolated Stage07 environment is gone. Its purpose was only TD007/TD008 smoke. The official Telegram host bridge was required because the first delivered Mini App opened without `window.Telegram.WebApp.initData`; after the bridge was added, a new explicit user-approved request—not an automatic retry—produced resolver/Base reread evidence.

Never recreate this deployment, use the removed SSH key, resend a Telegram message, alter BotFather, alter a webhook or reuse the previous test target merely for documentation cleanup. Any new external operation needs fresh user authority and a new environment decision.

### Remaining external/environment limitations

- The Codex in-app Browser reached the temporary R1 loopback fixture and the fixture is now removed. Its rendered-client evidence remains synthetic only; retain separate API/PostgreSQL evidence and never call the result identity, production or Telegram acceptance.
- The real Team Bot safe-route -> provider smoke is now recorded. The UI flow is separately fixture-tested; it remains deliberately non-provider. If literal user-operated UI -> provider evidence is later required, define it as a separate acceptance row and never substitute a fake LLM result.
- No production/staging claim is authorized.

## 7. Non-Negotiable Safety and Product Rules

1. Never expose secrets, raw Telegram IDs, raw `initData`, deep links, provider prompt/response, database URL, hidden fields, raw policies, raw saved-view configuration, draft before/proposed values or audit bodies.
2. Use Codex in-app Browser only. Do **not** control the user’s Chrome browser.
3. Agent writes default to `record_change_draft` plus explicit confirmation. The future structured direct-create exception for internal Telegram members is not authorized until a new decision exists.
4. Preserve server authority: frontend never reconstructs permissions, performs raw SQL, decides scope or claims success before a persisted authoritative reread/receipt.
5. Reuse FastAPI, SQLAlchemy, Alembic, PostgreSQL JSONB/pgvector, Redis, LangGraph, OpenRouter-compatible API and Telegram Bot API. Do not invent a new framework.
6. Documentation first. Any new schema/API/permission/external action requires a detailed decision/BDD/SDD/module/index and explicit user approval.
7. The user prefers one coherent substage with a few substantial deliveries, not many tiny fragments.
8. For future clarification, use one multiple-choice question at a time in the chat, label the recommended choice, and provide at least two alternatives. The user may answer multiple letters when several choices apply.
9. Focus effort on completing the initial product; do not spend disproportionate time on redundant testing. Still retain direct evidence for every claimed acceptance item.

## 8. Pitfalls That Must Not Be Repeated

1. **Do not mistake stale documentation for missing code.** Template/Import, TD006, TD007 and TD008 contain older status text contradicted by newer source/test/evidence. Correct the documents instead of duplicating functionality.
2. **Do not silently defer compatible originally approved work.** The user explicitly rejected that scope shrink. Read original documents before marking anything later-gated.
3. **Do not mistake local evidence for acceptance or production proof.** `implemented-local`, `partial-local` and bounded external evidence are not Stage07 completion. Do not merge a Browser fixture with a separate API/provider smoke and call it literal UI-to-provider proof.
4. **Do not retry Telegram delivery automatically.** A pointer expires; any new send needs a new user-approved request. The previously observed second send was explicitly approved and separate.
5. **Do not recreate or touch Stage03.** S6.3 was isolated and has been cleaned. Stage03 remained healthy and must stay untouched.
6. **Do not use in-memory-only tests as database/concurrency proof.** Atomic/rollback/unique/lock claims require disposable real PostgreSQL evidence.
7. **Do not treat skipped tests as passed.** State pass/fail/skip exactly.
8. **Do not leak backend error details.** Client maps only allowlisted stable codes to fixed safe copy; raw server `detail.message` must never render.
9. **Do not force a UI interaction that the app correctly locks while pending.** Prove stale scope behavior through application-level tests when a modal prevents unsafe interaction.
10. **Do not expand into customer group mapping or client direct-write during R0–R3.** It is a later technical-decision package, even though it is strongly supported by the product discovery.

## 9. Immediate Next Actions

Run these in order from the Stage07 worktree:

```powershell
# 1. Inspect the current dirty state before touching unrelated work.
git status --short

# 2. R1 core/direct evidence is recorded. Do not rerun it merely for volume.
# Read project-docs/08-implementation/evidence/stage07-r1-customer-project-core.md,
# then work only on the residual R1 rows (identity/session/revocation, Home queue-to-Draft Hub,
# cursor/error breadth, editor and invalid/F2/device V1 states) with a focused test first.

# 3. R2 focused test, local PostgreSQL, safe-route real-provider evidence and R3 documentation
# reconciliation are recorded. Continue only the residual R1/R2 visual/recovery rows above.
# Do not re-run the live provider smoke unless a changed owning contract requires it.

# 4. After each residual row, update its exact evidence. Once all are closed, run the final
# proportional integrity/traceability check. Preserve TD007/TD008/S6.3 as terminal historical
# evidence: do not send Telegram again, recreate the removed isolated environment or touch Stage03.
```

Then continue the plan at:

`docs/superpowers/plans/2026-07-15-stage07-r1-r3-closure.md`

Before reporting any R1/R2/R3 completion, run proportional focused checks and at minimum:

```powershell
git diff --check
```

and update the R0 Closure Matrix, acceptance checklist, traceability audit, source of truth and progress with exact evidence and remaining risks.
