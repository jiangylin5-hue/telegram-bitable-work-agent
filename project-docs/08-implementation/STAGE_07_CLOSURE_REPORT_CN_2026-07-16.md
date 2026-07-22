# Stage07 收口开发与验收报告（中文）

## 1. 报告结论

- 报告日期：`2026-07-16`。
- 当前阶段结论：**Stage07 整体尚未通过严格验收，不能宣称阶段完成。**
- 本轮目标：只补齐已经批准、且不与当前产品方向冲突的 Stage07 遗留实现和验证；不借机增加新业务范围、schema、API、权限模型或外部副作用。
- 核心原则：自动化回归通过只能证明局部实现未回归；原始 BDD 若明确要求真实 PostgreSQL、内置浏览器、角色/异常矩阵或真实 Provider 路径，就必须取得同等证据后才能关闭对应验收行。

逐条状态以 [验收证据矩阵](evidence/stage07-acceptance-evidence-matrix.md) 为准；英文命令、测试名和 API 名保留原样，便于复现。

## 2. 本轮做了什么

### 2.1 修复运行时失败后的可重试性

**问题：** Team Bot 和 TD005 草稿员工在调用运行时/Provider 前，会先创建幂等预留记录。若运行时失败，预留未被正确释放，同一个 idempotency key 的安全重试可能永久被拒绝。

**实现：**

- 在 `backend/app/services/stage07_team_bot_knowledge.py` 中修复 Team Bot 的预留清理。
- 在 `backend/app/api/routes/stage07_draft_employee_hub.py` 中修复 TD005 草稿调用的预留清理。
- 使用 SQLAlchemy `inspect(record)` 判断记录状态：
  - 尚未 `flush` 的 `pending` 记录使用 `expunge`；
  - 已持久化的 `persistent` 记录使用 `delete`；
  - 然后提交事务。

**为什么这样做：** 直接对 `pending` 记录执行 `session.delete` 会抛出 `InvalidRequestError`。按状态清理既避免异常，也不会把失败的请求伪装为成功，不产生直接写记录或泄露 Provider 原始信息。

**新增/补强功能：**

- Team Bot Provider 失败后允许以同一幂等键安全重试。
- TD005 运行时失败后允许以同一幂等键安全重试。
- 两条路径仍保持 `draft -> confirmation -> record service`，没有增加 Bot 直接写表能力。

### 2.2 收紧 Personal Assistant 上下文权限交集

**问题：** 数字员工配置中的 table scope 在用户权限被撤销后，目录读取必须立即排除该表，不能把过期的候选上下文交给 Mini App。

**实现：**

- 修改 `backend/app/api/routes/stage07_draft_employee_hub.py` 的 Assistant Catalog 组装逻辑。
- 目录只返回同时满足以下条件的候选：员工配置允许、调用者仍可访问对应 Base/Table/View、允许固定 `summarize` intent。

**技术方案：** 服务端计算有效权限交集，而不是让客户端根据缓存或配置自行判断；返回仍是安全 DTO，不返回原始配置、权限策略或内部标识。

**新增/补强功能：** 被撤销表权限后，员工目录不再暴露该上下文，防止过期授权进入后续摘要链路。

### 2.3 加固 Draft、数字员工管理与模板导入前端

- Draft API 服务端限制 `instruction` 最大长度为 `1000`，不再仅依赖前端输入控件。
- 数字员工管理页在 scope、view、member、action 等本地修改尚未保存并由服务端重新读取前，不允许激活员工；显示固定提示“请先保存当前配置和成员，然后激活员工。”
- 模板安装发生 `409` 冲突时，受影响模板卡片保持锁定至冲突处理完成，错误展示采用固定、脱敏文案。
- 退出 Template/Import 时，清理当前 user/workspace 下全部 import-job protected query，避免关闭面板后残留旧导入状态。

## 3. 怎么验证的

### 3.1 自动化与真实本地 PostgreSQL

| 验证 | 结果 | 证明范围 |
| --- | --- | --- |
| Team Bot 幂等单元测试 | `8 passed` | 覆盖 pending 预留清理与可重试性；不等于真实 Provider 调用。 |
| Team Bot Provider 失败 PostgreSQL 测试 | `1 passed` | 本地真实 PostgreSQL 中，失败后已持久化预留被释放。 |
| TD005 运行时失败 PostgreSQL 测试 | `1 passed` | 本地真实 PostgreSQL 中，草稿调用失败后可重试。 |
| TD009 table scope 撤销 PostgreSQL 测试 | `1 passed` | 授权撤销后 Catalog 排除该表。 |
| 模板/导入、protected query、员工管理聚焦前端回归 | `16 files / 56 passed` | 验证本轮 UI 安全修复，不等于浏览器视觉验收。 |
| Backend 全量 | `651 passed, 18 skipped` | 无 Stage07 失败；17 项为缺少历史 Stage02 在线数据库 URL，1 项为 POSIX 专用 shell 测试。 |
| Mini App 全量 | `63 files / 230 passed` | 最新客户端自动化回归通过，包含 TD009 的网络错误、`404` 清理和延迟替换闭环测试。 |
| `npm.cmd run build` | 通过 | Vite 生产构建通过。 |
| `alembic heads` | `20260713_0027 (head)` | 迁移图只有一个当前 head。 |
| `git diff --check` | 通过 | 没有 diff 空白错误；仅存在既有 LF/CRLF 提示。 |

所有 PostgreSQL 验证均使用本地可丢弃目标；没有对腾讯云、生产数据库或用户浏览器执行写入。

### 3.2 内置浏览器观察与清理

使用 Codex 内置浏览器和本地 FastAPI/Vite/隔离 PostgreSQL schema 建立合成 fixture，观察到：

1. 本地身份 bootstrap 返回合成工作区；
2. 从 Home 进入合成 Base；
3. 打开数字员工管理，创建草稿员工；
4. 选择 `Tasks` 后，才出现可授权的 `所有记录` view；
5. 完成成员选择。

之后内置浏览器 webview 无法重新附着，故没有把该观察扩大为完整 UI 验收。测试用 FastAPI/Vite 进程、`stage07_browser_acceptance_20260715` schema、PID、日志与 fixture 文件已逐项校验并清理。

## 4. 已开发的产品能力

本轮并非新增一个脱离产品场景的功能包，而是把已有产品能力的失败边界补齐：

| 产品能力 | 本轮完成的闭环 |
| --- | --- |
| Team Bot 受控知识摘要 | 运行时失败不会把幂等键永久卡死；重试保持 fail-closed。 |
| Draft Employee Hub | 运行时失败可安全重试；输入长度有服务端上限；仍只生成草稿，不直接改业务记录。 |
| Personal Assistant | 数字员工 scope、调用者权限、Base/Table/View 和固定动作必须同时成立，撤销立即生效。 |
| 数字员工管理 | 配置、成员和可访问范围必须先保存并重新读取，才能激活。 |
| 模板与导入 | 安装冲突不假报成功；关闭页面不保留旧工作区的受保护导入状态。 |

## 5. 本轮明确未做的内容

以下不是遗漏，而是保持在原批准边界之外：

- 没有增加客户群绑定、客户消息直接入库、Bot 直接建任务、群发或客户侧授权。
- 没有增加 RAG、长期记忆、文件/URL 读取、公开链接、任意工具调用或多 Base 数字员工范围。
- 没有变更 schema、API contract、权限模型或技术选型。
- 没有新发 Telegram、改 webhook、改 BotFather、写远程服务器、部署或进行生产操作。
- 没有控制用户 Chrome；只使用过 Codex 内置浏览器。

## 6. 尚未通过的验收项与阻塞点

### 6.1 仍缺同等 Browser 证据

这些项目并非一定没有实现，而是原始 BDD 指定的浏览器状态矩阵尚未获得可复现证据：

- V1 Saved View：`V1-A02`、`V1-A05`、`V1-A07`、`V1-A08`、`V1-A10`（拒绝、非法 payload、numeric lookup、类型非法、角色和四宽度）。
- Template/Import：`TI-A04`、`TI-A06`、`TI-A08`（真实文件选择、预览/提交、四宽度焦点和错误状态）。
- Governance：`GR-A03`、`GR-A06`、`GW-A07`（拒绝、重试、分页、stale 终态）。
- TD005/TD006：`DE-A05`、`DE-A08`、`DE-A09`、`CB-A06`（字段过滤后的草稿详情、失败清理、焦点和四宽度）。
- TD009：`ACD-A10`（使用 Codex 内置浏览器完成并留存的完整视觉评审）仍被阻塞。`ACD-A06/A07/A08` 已补网络固定错误/重试、`404` 清理与延迟替换的客户端自动化证据，均为 `evidenced-pending`；`ACD-A03` 的本地 PostgreSQL 证据也仍是 `evidenced-pending`，不是 accepted。
- TD010：`DEM-A01` 至 `DEM-A10`（完整 manager/member 分离、暂停→激活只读→暂停、冲突 reread、桌面/移动焦点返回）。
- TD011：`TBK-A04` 至 `TBK-A09`（真实 Mini App UI → 本地 API → Provider 的非空结果，以及重选/错误/焦点矩阵）。

**直接阻塞：** Codex 内置浏览器当前无法附着新本地页面。按用户要求，没有切换到其 Chrome，因此上述 Browser 行不能伪造为完成。

### 6.2 真实 Provider 证据已补齐的部分与剩余缺口

- 用户指出的项目根目录忽略 env 文件已用于一次新的真实 OpenRouter 验证；详细记录见 [真实 Provider 验证](evidence/stage07-real-openrouter-provider-validation-2026-07-16.md)。
- Team Bot safe route、摘要、隐藏字段保护、引用、草稿更新和“拒绝直接提交”六类安全场景均通过；草稿保持 `pending_confirmation`，原合成记录未变，完整 prompt/response 未持久化。
- 因此 TD005 的 `DE-A03`、`DE-A04` 由 `blocked` 变为 `evidenced-pending`，但仍不代表 Hub 的 Browser 验收已经完成。
- TD011 仍缺真实渲染 Mini App UI 发起的非空 Provider 路径；TestClient 的安全路由真实 Provider 结果不能替代这一 BDD 条件。

## 7. 下一步建议

先恢复 Codex 内置浏览器附着能力，再按验收矩阵成组完成 Browser 状态，而不是零散补截图。随后在忽略的本地环境文件中配置可用 `OPENROUTER_API_KEY`，并在明确的最小合成数据范围内完成 TD005/TD011 的真实 Provider 闭环。完成后仍需逐行更新矩阵，只有 BDD 原始条件满足的行才可标记 `accepted`。

## 8. 关联文档

- [逐项验收证据矩阵](evidence/stage07-acceptance-evidence-matrix.md)
- [最终审计报告](STAGE_07_FINAL_AUDIT_REPORT.md)
- [本轮详细英文技术证据](evidence/stage07-final-closure-validation-2026-07-15.md)
- [新会话交接文档](../../HANDOFF.md)

## 9. LLM 上下文工程：当前真实实现

### 9.1 当前不是“把聊天记录全部塞给模型”

当前调用的上下文由服务端临时组装，顺序如下：

```text
Telegram/Mini App 请求
-> 解析调用者身份与工作区
-> 校验员工状态、成员资格、Base/Table/View/字段权限与允许动作
-> 重新读取当前授权视图
-> 投影仅可见字段和记录
-> 组装受限 JSON 上下文
-> LangGraph 单次执行图
-> OpenRouter JSON 输出
-> 服务端校验、引用过滤、草稿/审计
```

关键实现位于：

- `backend/app/services/stage06_digital_employees.py`
- `backend/app/agents/stage06_live_digital_employee.py`
- `backend/app/services/stage07_team_bot_knowledge.py`

上下文不是浏览器传来的任意对象，而是服务端按当前权限重新读取的内容：

- 当前 action，例如 `summarize` 或 `draft_update`；
- 员工名称；
- 用户的有限 instruction；
- 当前授权 View 的 `view_id` 与可见 field key；
- 已过滤的当前 View records；
- `draft_update` 的唯一目标 `record_id`；
- 确定性 skill matching 产生的 `skill_evidence`。

Team Bot 还额外把读取窗口固定为：先探测 `101` 条，只向运行时传入前 `100` 条，并带上 `truncated` 状态。它不是全文检索，也不会把不属于当前 View 的历史记录混入上下文。

### 9.2 权限优先于模型

模型不拥有数据库连接、原始 SQL、Provider key、全局搜索权限或直接写表权。它只看到服务端完成权限交集后的投影。

```text
员工配置 scope
-> 调用者成员/字段权限
-> Telegram 或 Mini App 当前上下文
-> 当前 Base/Table/View/Record 的实时可读性
-> 最小记录窗口
-> LLM
```

模型给出的 citations 也会被服务端二次过滤：只保留当前授权窗口内、格式正确且去重后的 `record_id`。模型声称的字段、角色、写入成功或越权引用不会直接进入客户端结果。

### 9.3 当前 LangGraph 编排深度

当前通用数字员工使用一个窄图，而不是多 Agent 自治系统：

```text
prepare_context
-> call_openrouter
-> validate_output
-> END
```

- `prepare_context`：确定 response schema、输出模板和权限过滤后的 payload；
- `call_openrouter`：经 `StructuredLLMClient` 调用 OpenRouter-compatible `chat/completions`；
- `validate_output`：检查 `answer`、`citations`，并在草稿更新时检查目标 `record_id` 与 `proposed_values`；
- 后续写入不是模型 tool call：模型最多产出建议，业务记录仍必须走 draft confirmation、版本校验和审计。

LangGraph 是已采用的编排框架，但**当前没有启用 checkpointer、跨轮线程状态、Supervisor 动态委派或任意 tool loop**。历史 Stage05 还保留一个面向旧广告业务的 Router/Supervisor 实现；它是历史能力证据，不应被误当成当前 Telegram 协作产品的通用运行时。

## 10. 提示词编排：当前实现与不足

### 10.1 当前提示词构成

当前 live digital employee 的 prompt 有两层：

1. **System message（硬约束）**：只能使用提供的权限过滤数据；只返回一个 JSON object；不得宣称已提交写入；`draft_update` 只能给出草稿字段值。
2. **User message（结构化上下文）**：将 action、员工、instruction、safe schema、safe records、record_id、skill evidence、response schema、output template 序列化为 JSON。

OpenRouter 请求指定 `response_format = {"type": "json_object"}`。服务端在模型输出后再次解析 JSON，并验证字段形状、目标记录、citation 可见性和草稿边界。

`prompt_version` 当前是代码中的稳定版本，例如 `stage06-live-digital-employee-v1`；模型名通过 `OPENROUTER_MODEL` 运行时配置，默认 `openrouter/auto`，不硬编码在业务服务中。

### 10.2 当前不足

- prompt 版本是代码常量，不是可审计、可灰度、可回滚的 prompt registry；
- 缺少以真实 Telegram 协作任务为样本的离线评估集、回归评分、成本/延迟阈值和模型路由策略；
- 没有面向多轮对话的上下文压缩、摘要、事实冲突检测或记忆召回；
- Team Bot 的“非空 Mini App UI -> Provider”链路仍未得到真实验收；
- 现有 Stage05 Router prompt 含历史广告业务 intent，不应直接复用于客户项目协作场景。

因此，当前提示词工程可称为“安全结构化输出基础”，不能称为成熟的项目协作 Agent prompt 平台。

## 11. 记忆体系：当前状态与正确理解

### 11.1 当前没有持久化 LLM 记忆

这是 Stage07 的明确边界，不是遗漏：

- 没有用户/团队 Bot memory partition；
- 没有 conversation thread、chat history、retention 或 clear controls；
- 没有 knowledge source、文件/URL ingestion、embedding、pgvector retrieval 或 RAG；
- 没有浏览器 `localStorage`、`sessionStorage` 或持久化 React Query context。

Mini App 内的 `selectedEmployeeId`、`selectedViewId`、instruction、answer 和请求 generation 只是组件内临时状态；工作区/Base/联系人/页面切换或关闭后会清除。它们不是“记忆”。

### 11.2 当前已持久化的不是记忆，而是业务与控制事实

| 类型 | 当前用途 | 是否作为 LLM 长期记忆 |
| --- | --- | --- |
| PostgreSQL Bitable records / views | 业务事实、授权后的当前工作上下文 | 否；按当前权限读取。 |
| `record_change_drafts` | 需人工确认的变更建议 | 否；是受控业务草稿。 |
| `AgentRun` / audit events | 可追溯执行摘要、模型/版本、结果摘要 | 否；默认不保留完整 prompt/response。 |
| idempotency receipt | 重试与防重放 | 否；不是语义记忆。 |
| Redis / Query cache | 队列、短期受保护请求状态 | 否；不可成为跨用户知识来源。 |

配置默认 `AGENT_SAVE_FULL_PROMPT=false`、`AGENT_SAVE_FULL_RESPONSE=false`。即使未来需要审计，也必须先定义脱敏、保留期限、删除权与权限读取规则，不能把原始聊天或表格内容直接当作“记忆”。

### 11.3 面向真实 Telegram 协作场景的后续建议（尚未实现）

这需要新的技术决策和用户确认后才能实施。建议分层，而不是建立一个无边界“聊天记忆库”：

1. **业务工作记忆**：Customer / Project / Task / Milestone / Risk 等仍以 Bitable 表为唯一事实来源；Agent 每次按权限读取当前视图。
2. **短期会话状态**：仅保存单次任务的结构化 state、确认状态和有限 TTL，不保存完整原始聊天上下文。
3. **项目级可审计记忆**：把确认过的决策、风险、客户承诺、交付摘要写为带来源 record、权限、版本、TTL 和删除能力的显式 Memory Item；不得由模型自行写入。
4. **知识检索层**：只对已批准的文档/表记录建立索引；检索前先做 workspace/Base/project/field 权限过滤，再做向量或关键词排序；每个回答附来源和 freshness。
5. **隐私与治理**：按用户、项目、团队分区；提供 retention、clear/export/delete、审计、敏感字段排除和成本上限。

## 12. 技术栈（当前实际基线）

| 层级 | 技术 | 当前用途与说明 |
| --- | --- | --- |
| Backend | Python 3.12+、FastAPI、Uvicorn | API、Webhook、Mini App 服务与 Worker 入口。 |
| 数据与迁移 | PostgreSQL、JSONB、SQLAlchemy 2.x、Alembic、psycopg 3 | 通用表格、字段、记录、视图、草稿、审计、幂等与权限相关数据。 |
| 向量能力 | `pgvector/pgvector:pg16` 镜像作为基础设施准备 | 已具备未来承载条件；当前未实现 embedding/RAG/向量检索。 |
| 缓存与异步 | Redis 7、Redis Streams、Worker / Outbox bridge | 队列、事件和受控异步处理；不是长期记忆存储。 |
| LLM / Agent | LangGraph、OpenRouter-compatible API、HTTPX、结构化 JSON adapter | 单次受控数字员工图，支持 fake/live runtime；模型通过环境变量配置。 |
| 能力匹配 | 项目内 deterministic skill matching | Stage06 有 LarkSuite 风格 manifest 参考；当前活跃核心能力有限，不能等同完整工具生态。 |
| Telegram | Telegram Bot API、Webhook、Mini App `initData` HMAC、深链接 resolver | 身份和受控入口；不能绕过系统权限。 |
| Frontend | React、TypeScript、Vite、Tailwind CSS 4、TanStack Query、lucide-react、CVA/clsx | Mini App 与桌面浏览器复用界面；受保护查询按 user/workspace 作用域清理。 |
| UI 组件策略 | Tailwind 自定义组件与 shadcn 风格基线 | 当前 `package.json` 未引入独立 `shadcn/ui` 运行包；不应宣称已完整采用其组件生态。 |
| 测试 | pytest、Vitest、Testing Library、jsdom、本地 PostgreSQL 集成测试 | 单元/API/真实本地数据库/客户端回归；Browser 验收仍有缺口。 |
| 部署基础 | Docker Compose、Caddy、PostgreSQL/Redis 独立卷 | 有隔离验收部署资产；当前不等同生产上线。 |

## 13. 架构结论与下一步边界

当前产品已经有“表格权限 + 受控 LLM 调用 + 草稿确认 + 审计”的安全骨架，但尚未具备完成真实 Telegram 客户协作所需的记忆、知识、项目风险主动扫描、群绑定和客户沟通闭环。

在继续开发上述能力之前，应先完成两件互不混淆的工作：

1. 继续关闭 Stage07 原始验收矩阵，尤其是 Browser 与真实 Provider 行；
2. 单独编写并确认“AI Runtime、项目记忆与知识检索”技术决策包，明确数据模型、权限分区、保留与删除、索引策略、prompt registry、评估集、模型路由、成本控制和人工确认边界。

第 2 项会涉及新的 schema、API、权限模型和数据保留策略，必须在实施前单独与你讨论并取得确认。
