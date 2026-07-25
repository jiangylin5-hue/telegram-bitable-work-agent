# 项目交接文档：Stage08/Stage09 与 Codex 式 AI 对话

## 给没有上下文的新会话

先完整阅读本文件，再按以下顺序读取：

1. `AGENTS.md`；
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`；
3. `project-docs/08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md`；
4. `project-docs/08-implementation/STAGE_09_UI_FUNCTIONAL_REMEDIATION_PLAN.md`；
5. `project-docs/08-implementation/evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md`。

不要因为域名仍叫 `stage07.jiangtest1.online` 就把线上系统回退到旧 Stage07。它目前承载的是已部署的 Stage09 原生服务。不得读取或输出任何 `.env`、token、数据库密码、Telegram 原始 `initData`、SSH 私钥或真实群聊原文。

## 1. 产品与硬边界

这是一个 Telegram-first 的多维表格、无代码工作区和表格绑定数字员工平台。产品主链是：

```text
workspace -> base -> table -> fields -> records/views -> permissions
-> template/import -> digital employee -> draft confirmation -> audit
```

数字员工只能在“配置范围 -> 调用者用户范围 -> Telegram/浏览器上下文范围”的交集中工作。它可以查询、总结、分类、生成草稿；受控写入默认走 draft confirmation；不能绕开权限、审计、工具网关或把聊天答案当成持久化业务结果。

业务实时事实以已授权表格为准；长期 memory 是偏好、决策、承诺等可检索经验；群聊只作为受控上下文工程检索源，不能把原文整段塞进模型或前端。

## 2. 代码、分支与工作区

| 项目 | 当前状态 |
| --- | --- |
| 主仓库 | `D:\telegram多维表格和工作智能体的开发` |
| 活动工作树 | `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui` |
| 分支 | `codex/stage07-mini-app-ui` |
| 已推送最新提交 | `274c6d9 docs(stage09): record r40 regression evidence` |
| 线上代码发布 | `stage09-p1-20260725-r39`，来源 commit `4f9096a` |
| 最新 r40 | 仅新增回归/上线就绪证据文档，不需要发布代码 |

工作树中存在用户自己的未提交内容，必须保留、不可重置、不可混入本次提交：

```text
M .superpowers/sdd/progress.md
M .superpowers/sdd/task-1-brief.md
M .superpowers/sdd/task-1-report.md
M .superpowers/sdd/task-2-brief.md
M .superpowers/sdd/task-2-report.md
?? project-docs/08-implementation/evidence/screenshots/2026-07-24-ui-audit/
```

后续提交只显式 `git add` 自己修改的文件。不要做 `git reset --hard`、广泛清理或覆盖上述内容。

## 3. 阶段进度

### Stage08：上下文、memory、RAG 与协作运行时

Stage08 的基础设施已实施：PostgreSQL + pgvector、Redis、权限过滤的业务上下文、受控群聊投影、memory/knowledge 检索、LangGraph-first 执行、草稿确认和审计。现有 `/api/stage08/assistant/query` 能在权限和 scope 内返回 `Stage08AssistantSafeView`。

尚未完成的是完整产品级实测：稳定浏览器/Telegram 会话内的真实业务闭环，以及用户当刻确认后的真实草稿或表格写入。不要把单元测试、模拟数据或端点 200 等同于完整上线验收。

### Stage09：原生部署与前端体验修复

服务已部署到服务器本机：原生 PostgreSQL 16 + pgvector、Redis、systemd、Nginx；没有使用 Docker。公网入口为 `https://stage07.jiangtest1.online/`，域名名称是历史遗留。

UI 已补齐多维表格工作台的多个能力入口：Base/表/记录上下文、关系跳转、模板与导入、创建、右键菜单、个人助手、Team Bot、AI 对话、记忆与知识等。用户要求保留“即将上线”的未来入口作为拓展，不要删除或伪装成已实现。

已知风险仍是“产品级交互不完整而非服务停机”：用户过去暴露过浏览器 handoff、Telegram 小窗、导入跳转与空权限页面等问题，后续要以实际浏览器步骤重测并修复，不可只看单测。

## 4. 最新真实验证证据（2026-07-26）

在工作树本地完成：

| 范围 | 命令/检查 | 结果 |
| --- | --- | --- |
| Mini App 全量测试 | `npm.cmd run test:run` | `76 files / 353 tests passed`，249.27 秒；未发现 `skip/todo/only`。 |
| Mini App 构建 | `npm.cmd run build` | 成功。 |
| 核心后端范围 | Stage06 import + Stage07 Mini App/relation/assistant/team-bot/draft 测试集合 | `106 passed in 25.29s`。 |
| 线上主页 | `GET https://stage07.jiangtest1.online/` | HTTP 200。 |
| 线上健康检查 | `GET https://stage07.jiangtest1.online/health` | HTTP 200，`{"status":"ok"}`。 |
| 线上静态资源 | r39 的 JS/CSS | HTTP 200，尺寸与本地 production build 一致。 |

已授权 Chrome 会话中读取到首页 DOM：工作区、待确认、Bases、Team Bot、AI 对话、记忆与知识、成员与权限，以及 3 个可访问 Base 都存在。CDP 的完整截图和日志读取一度超时并导致自动化连接重置；这是浏览器自动化通道不稳定，不能据此判断线上前端失败，也不能替代人工视觉验收。

本轮没有创建/修改生产 Base、表、字段、记录、视图、模板或权限；没有提交 CSV/XLSX；没有发送 Telegram 消息；没有动 Stage03 Docker、webhook 或生产 schema。真实写入在执行当刻仍需用户再次确认并保留截图、回执和审计证据。

## 5. 当前已确认、但尚未实现的下一工作

用户已明确确认：AI 对话要做成类似 Codex 的连续工作台，并采用真实、受控的 SSE 状态流。

权威设计文件是：

`project-docs/08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md`

关键决定：

- 底部固定一个核心 Composer；上方是持续时间线，显示用户问题、允许的工作阶段、答案分段、引用和草稿结果；
- 技能标签可一键预填“智能汇总、查表问答、群聊总结、风险识别、调用长期记忆、生成跟进草稿”；标签不直接写库；
- 新增 `POST /api/stage08/assistant/query-stream`，保留旧同步 `/query`；
- 新端点只能复用既有身份、权限、scope、审计、幂等、`run_stage08_collaboration` 和 `validate_assistant_query_safe_view`，不得复制或旁路业务规则；
- SSE 只发送白名单阶段、已安全校验的答案片段、最终 `SafeView`、稳定错误和结束事件；不发送原始模型 token、隐藏推理、工具中间结果、原始群聊、凭据或堆栈；
- 不新建“聊天历史长期记忆”。长期保存继续使用既有 audit、agent run、draft 和 memory 机制。

这个 API contract 已有用户确认。实现前仍需要按照项目规则写失败测试和实现计划；实现时不要另行改变 schema/权限模型。

## 6. 关键文件地图

| 文件 | 作用 |
| --- | --- |
| `mini-app/src/app/CollaborationWorkbench.tsx` | 当前三列 AI 协作面板；下一步主要 UI 改造点。 |
| `mini-app/src/app/App.tsx` | 打开/关闭协作工作台及应用外壳。 |
| `mini-app/src/app/api.ts` | 当前 `queryStage08Assistant`；下一步新增 SSE client/parser。 |
| `mini-app/src/app/stage08-collaboration-types.ts` | intent、action、status、citation、degradation 前端类型。 |
| `mini-app/src/test/collaboration-workbench.test.tsx` | AI 工作台前端回归。 |
| `backend/app/api/routes/stage08_collaboration.py` | 当前同步查询路由；新增受控流入口的位置。 |
| `backend/app/schemas/stage08_collaboration.py` | Query/SafeView schema；流事件应在这里或同级严格声明。 |
| `backend/app/services/stage08_collaboration.py` | 当前协作运行服务；必须复用，不复制执行逻辑。 |
| `backend/tests/unit/test_stage08_*` | Stage08 后端测试集合。 |
| `project-docs/08-implementation/STAGE_09_UI_FUNCTIONAL_REMEDIATION_PLAN.md` | UI 功能修复、导入、关系跳转、菜单与回归要求。 |
| `project-docs/08-implementation/evidence/design-references/stage09-feishu-bitable/` | 飞书风格参考图资产；视觉修改时避免漂移。 |
| `project-docs/08-implementation/evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md` | 最新真实回归、线上状态与浏览器限制证据。 |

## 7. 推荐执行顺序

1. 先阅读本文件、项目规则与 Codex 式 AI 设计；确认活动工作树状态，不碰用户 dirty files。
2. 检查现有同步 API 的请求、响应、权限与测试，写一份简短实施计划，将新 SSE 路径映射到现有服务。
3. 先添加后端失败测试：事件顺序、拒绝、错误脱敏、read-only、draft；再实现最小流端点。
4. 再添加前端失败测试：固定 Composer、技能预填、事件顺序、断开、安全错误、不可写 draft；再改 `CollaborationWorkbench` 和 `api.ts`。
5. 运行针对性测试，然后全量 `npm.cmd run test:run`、`npm.cmd run build` 和相关后端 pytest；记录实际输出。
6. 仅在测试和代码审查通过后，按现有 Stage09 原生部署脚本发布。发布后复查 `/health`、资源 hash 和真实浏览器只读路径。
7. 想验真实导入或真实草稿/表格写入时，必须在点击最终 Commit/确认前再向用户索取动作级确认；完成后保存脱敏截图与审计证据。

## 8. 协作和沟通偏好

- 默认中文；文档中文，代码/API/字段名保持英文。
- 用户希望以开发完成度与真实可用性为主，避免无意义的反复确认；但 schema、API contract、权限模型、架构和真实外部写入必须说明边界并得到应有确认。
- 不得口头宣称“已上线/已验收/已修复”，除非有命令输出、线上检查或可保存的真实浏览器证据。
- 用户特别重视 UI 完整性：所有按钮、跳转、导入、右键菜单、表格常用操作和技能入口都要实际可用或明确标注未上线；不能只摆页面。
- UI 应参考飞书多维表格的产品语法，同时维持本项目自己的高信息密度、丰富但克制的配色和桌面/Telegram 双适配。不要退化成普通 AI 卡片页。

## Current Progress

本交接文档和 Codex 式 AI 对话设计于 2026-07-26 创建，用于让无历史上下文的新会话安全续做。截止写入时，SSE API 和新对话工作台尚未开始编码；Stage09 r39 仍稳定在线，r40 的真实回归证据已推送。
