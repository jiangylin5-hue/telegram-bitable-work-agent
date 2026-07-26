# Stage09 Codex 式 AI 对话工作台实施计划

## Status

- **Status:** SSE、Ledgerline UI 与 LLM skill launcher 均已批准；skill launcher 进入 TDD，随后恢复 Task 4 收口
- **Date:** 2026-07-26
- **Scope:** 在不改变 schema、权限模型和外部动作授权的前提下，为现有 Stage08 assistant 增加受控 SSE 兼容路径，并把三列协作面板改造成持续时间线与固定 Composer。
- **Design authority:** `STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md`
- **Detailed execution plan:** `docs/superpowers/plans/2026-07-26-stage09-codex-ai-conversation-sse.md`
- **Current Progress:** 文档真源和实施计划已建立。Task 1 基线修复已完成；Task 2 后端 SSE 修复并复核通过，87 项定向测试通过；Task 3 前端流客户端修复并复核通过，29 项定向测试及 TypeScript 校验通过；Task 4 Ledgerline 工作台初版已实现并通过 42 项定向测试与 build，但独立复核的终态、权限证明、宽屏 dialog、focus 和滚动问题尚未收口。用户已确认“技能标签必须真实调用后端 skills”的 API/runtime/permission 设计，独立 TDD plan 已建立，当前先实施 skill catalog/profile，再恢复 Task 4。Task5 已以 RED/GREEN 通过 internal/public HTTPS 模板的 SSE rendered-config 资产验证；review 后两套精确 block 测试还断言保留既有 loopback `proxy_pass` 和四项身份转发 header。全阶段 backend/frontend suite、生产 build、浏览器验收和部署仍未在本 Task 执行。根据用户要求，后续不创建 task 级 commit；所有开发、验收、审计和清理完成后，才把未推送的本地阶段 checkpoint 与后续改动 squash 为一个最终 Stage09 commit。

  2026-07-26 final acceptance update: the backend selected suite (`209 passed`),
  Mini App full suite (`397 passed`, `2 skipped`), production build and both
  rendered-Nginx scripts now pass. Final whole-branch review found no new
  Critical/Important code safety issue. Browser acceptance then used an isolated
  PostgreSQL workspace and captured populated desktop/compact Ledgerline states.
  It resolved the `/api` proxy, portal-layer and compact current-record-entry
  findings; root `design-qa.md` now passes. Cleanup/audit completed and the one
  permitted local squash commit is recorded on this branch.

### Commit policy

1. 文档仍然必须先于对应代码修改写入工作树，但“文档先行”不等于“文档先提交”。
2. Task 1、Task 2 和治理工作在用户提出单次提交要求前已经产生本地 checkpoint commit；这些 commit 未推送，仅作为开发中恢复点保留。
3. 从该要求生效起，前端、UI、Nginx、证据和修复均不做 task 级 commit。
4. Stage09 全部 acceptance、文档审计、独立整分支 code review 和 temporary cleanup 通过后，以批准基线 `b57b152` 为边界执行一次本地 squash，再创建唯一最终 commit。
5. 不因 squash 宣称部署、推送或生产验收；这些仍是独立授权门。

## 1. 实施边界

本轮只实现：

1. 保留 `POST /api/stage08/assistant/query`。
2. 新增 `POST /api/stage08/assistant/query-stream`。
3. 同步与流式路由复用同一个授权、scope、幂等、执行、审计和 `SafeView` 校验路径。
4. 浏览器使用 `fetch()`、`ReadableStream` 和增量 UTF-8 解码消费 SSE。
5. AI 工作台使用顶部安全上下文、持续时间线、固定 Composer、服务端技能启动器和安全草稿入口。
6. Nginx 对 SSE 路径关闭代理缓冲并提供不短于 Stage08 执行预算的读取超时。

用户已于 2026-07-26 单独确认，本轮继续扩展：

7. 由后端 Stage06 registry 驱动的只读技能目录。
8. 同步/SSE 共用 request、command、provider、idempotency、SafeView 和 audit skill profile。
9. 前端 `SkillStrip` 删除静态能力真源，改为消费服务端精选技能。

详细边界、公开 skill 集合与分步实现见 `STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md` 和 `docs/superpowers/plans/2026-07-26-stage09-llm-skill-launcher.md`。

本轮不实现：

- 原始模型 token passthrough；
- hidden chain-of-thought、provider 请求体或工具中间结果展示；
- 新聊天历史表、浏览器 `localStorage` 记忆或新 Alembic migration；
- 自动确认草稿、自动重试写入、生产数据写入或 Telegram 发送；
- 新数字员工、RAG、memory 或权限能力。

## 2. 后端结构

### 2.1 共享执行边界

将当前同步路由中的应用级逻辑拆成两个共享阶段，并由一个兼容包装函数串联：

```python
def prepare_assistant_query(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity,
    uow: Stage06PlatformUnitOfWork,
) -> PreparedAssistantQuery:
    ...

def complete_assistant_query(
    prepared: PreparedAssistantQuery,
    uow: Stage06PlatformUnitOfWork,
) -> AssistantQuerySafeView:
    ...
```

`prepare_assistant_query` 负责：

- UUID 和严格输入解析；
- `authorize_workspace_action`；
- `_require_current_query_scope`；
- `_query_fingerprint` 与现有 `_OPERATION`；
- idempotency start/replay；
- server-derived command。

`complete_assistant_query` 负责：

- `run_stage08_collaboration`；
- `validate_assistant_query_safe_view`；
- idempotency complete；
- commit、rollback 和安全错误映射。

同步路由通过 `execute_assistant_query` 连续调用两段并保留现有 HTTP 行为。流路由在 generator 内依次调用两段，但只能发送当前服务层能够证明的状态：`authorizing` 在 `prepare` 前发送；fresh request 的 `analysing` 紧邻 `complete` 中的受控 runtime 调用前发送；replay 不执行 runtime，因此不发送 `analysing`。当前单体 runtime 没有独立暴露 context planning 或 draft creation 回调，首版不得发送 `planning_context` 或 `creating_draft`。流路由不得创建新的业务执行器或新的幂等 operation；相同 request body 与 idempotency key 必须复用同步结果，避免断线重试产生重复草稿。

### 2.2 Generator 生命周期与事务所有权

`prepare_assistant_query` 可能已经完成幂等 reservation，并在 SQLAlchemy 路径中打开事务。SSE generator 在 `prepare` 之后会发生多次 `yield`，所以不能只依赖 `except Exception`：客户端断开时 Python 会以 `GeneratorExit` 关闭生成器，它不属于 `Exception`。

实现必须维护一个“是否仍持有未完成 reservation”的显式状态，并用 `try/finally` 收口：

```text
prepare started
-> reservation owned by generator
-> yield permitted status
-> complete commits and marks ownership released
-> emit safe result

任何 complete 前的 close / GeneratorExit / error
-> finally rollback SQLAlchemy transaction
-> discard InMemory reservation
-> do not emit a synthetic SSE error for GeneratorExit
```

清理必须幂等：已经 replay 或已经完成 commit 的请求不能被 `finally` 反向删除；同步 `/query` 仍由 `complete_assistant_query` 保持原有异常映射。

### 2.3 SSE 安全投影

新增严格事件 schema：

```text
status       sequence, request_id, phase
answer_delta sequence, request_id, text
result       sequence, request_id, safe_view
error        sequence, request_id, code, message
done         sequence, request_id
```

`request_id` 由服务端生成，与 `idempotency_key` 分离。`answer_delta` 只能从已经通过 `validate_assistant_query_safe_view` 的最终 answer 中按文本边界切分，全部 delta 拼接后必须与 `result.safe_view.answer` 完全相等。

首版状态流只报告真实可证明的边界。每个阶段事件在对应操作开始前发送；只有上一个阶段成功后才进入下一个阶段：

```text
fresh:
authorizing -> analysing -> answer_delta* -> result -> completed -> done

replay:
authorizing -> answer_delta* -> result -> completed -> done
```

未经服务层显式证明时，不发送 `planning_context`、`retrieving_knowledge` 或 `creating_draft`，避免用动画伪造内部执行阶段。草稿是否存在只能读取最终 `result.safe_view`。

FastAPI request schema 与身份依赖错误在开始流式响应前继续使用安全 HTTP `401/422`。generator 内的 workspace/employee/record scope、幂等和执行异常只能发白名单 `error` 事件并终止，不发送 traceback、provider 内容、原始 query、凭据或内部异常文本。

## 3. 前端结构

新增独立的 SSE 解析和请求单元，避免把传输协议塞进大型 `api.ts`：

```text
mini-app/src/app/stage08-collaboration-stream.ts
```

它负责：

- `fetch()` POST、现有身份 header/cookie 与 `Idempotency-Key`；
- 校验 `content-type: text/event-stream`；
- 使用 `TextDecoder` 的 streaming 模式处理任意字节边界；
- 处理多行 `data:`、CRLF/LF、未知事件、严格 sequence 和终止状态；
- 将事件交给调用方，不把 raw body 或错误细节写入 UI。

### 3.1 Wire format 与事件判别

真实后端 `encode_sse_events` 的首版 wire format 是：

```text
data: {"event":"status","sequence":1,...}\n\n
```

它没有单独的 SSE `event:` field。前端必须把 JSON payload 内的 `event` 作为事件 discriminant；测试 fixture 必须直接复用该 data-only 形态，不能人为补 `event:` 掩盖前后端不兼容。如果以后服务端同时发送 SSE `event:` field，则它只能作为冗余校验，必须与 payload `event` 相同，否则 fail closed。

### 3.2 身份与 header 合并

流请求复用现有 Stage06 identity helper 和 cookie 策略。调用方在 `RequestInit.headers` 中明确提供的 `X-Telegram-Init-Data`、其他已支持身份 header 和 tracing header 不得被删除；客户端只补充 `Content-Type`、`Accept: text/event-stream` 与 `Idempotency-Key`，冲突时遵循现有同步 wrapper 的合并规则。测试必须断言 Telegram header 实际到达 `fetch`。

### 3.3 结果一致性与终止状态机

parser 维护：

```text
expected_sequence
request_id
delta_buffer
result_count
terminal_state = open | done | error
```

- recognized event 的 sequence 必须从 1 严格连续递增，且 request id 始终一致；
- `result` 只能出现一次；
- `done` 必须在唯一 `result` 后出现；
- 全部 `answer_delta.text` 拼接值必须与 `result.safe_view.answer` 完全相同；空答案按空字符串比较；
- `done`/`error` 后的任何事件、非空 data 或尾随字节都使整个流失败；
- parser 必须读到 EOF 并完成上述校验后，才能向调用方发布 terminal `done`/`error`，不能先让 UI 进入完成态再发现协议错误；
- HTTP 错误、非 SSE、非法 UTF-8、非法 JSON 或协议错误只能映射为稳定客户端错误，不把 response body、header、原始 payload 或内部异常文本写入 UI。

`CollaborationWorkbench` 使用 reducer 管理每个 `request_id` 的 timeline，最终 `result.safe_view` 是引用、草稿与状态真源。`answer_delta` 只提供渐进展示，不能单独宣称成功。

工作台视觉实现必须以用户选定的 `assets/stage09/ledgerline-workbench-selected.png` 为唯一视觉真源，并遵循 Stage09 设计文档 `2.2 Ledgerline 视觉系统`。UI 代码按 `ContextStrip / TimelineIndexRail / TimelineEntry / EvidenceRows / DraftSheet / SafeScopeAside / SkillStrip / ComposerDock` 划分职责；视觉纹理由独立 raster asset 提供，不使用 CSS gradient、inline SVG 或 `div` 图案替代。

Task 4 review fix contract:

1. reducer 的 `result` 动作只写入 `safe_view` 并进入 `finalizing`；stream Promise 在 parser 校验 `done + EOF` 后 resolve，单独的 `complete` 动作才进入 `completed`。
2. `result` 后的 terminal failure 仍必须覆盖为 `failed`。
3. `canDraft` 消费显式的 current-record writable 与 employee/current-Base scope 事实；未知时为 `false`，不能从 record id 推断。
4. collaboration 主入口统一使用宽 Ledgerline dialog，不保留桌面 `520px` side-panel 变体。
5. dialog 实现 initial focus、focus trap、background isolation、Escape 和 focus restore。
6. reducer 锁 server request id/sequence；timeline 只在 near-bottom 时自动跟随。

断开规则：

- `AbortController` 只表示停止查看，不声称服务器任务已取消；
- `read_only` 可由用户重新发送；
- `draft_update` 不自动生成新幂等键重发；用户先检查既有草稿队列或审计结果；
- 时间线只保存在当前 React 生命周期，不写入新持久记忆。

## 4. Nginx 与部署

为内部和公网 HTTPS 模板增加精确的 SSE location：

```nginx
location = /api/stage08/assistant/query-stream {
    proxy_pass http://stage09_api;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 90s;
    add_header X-Accel-Buffering no always;
}
```

实际 `proxy_pass`、header 与 upstream 写法必须复用各模板现有配置，不能凭空引入新 upstream。部署资产测试必须渲染模板并断言行为，不只 grep 源文件。

响应必须包含：

```text
Content-Type: text/event-stream
Cache-Control: no-store
X-Accel-Buffering: no
```

## 5. TDD 顺序

1. 修复既有 Stage08 API 测试替身的过期签名，恢复可信基线。
2. 先写后端事件 schema、序列、安全 delta 和路由失败测试。
3. 实现共享执行函数与流路由，保持同步测试通过；补客户端 close/`GeneratorExit` 清理测试，并验证 degraded/无草稿结果不会出现 `creating_draft`。
4. 先写前端流解析器的字节分块、顺序、未知事件和安全错误测试。
5. 实现 `fetch` SSE client。
6. 先写工作台 Composer、服务端技能目录/选择、时间线、断开和 draft 边界测试。
7. 实现工作台 UI 和响应式样式。
8. 先写 Nginx 渲染资产失败测试，再增加无缓冲配置。
9. 运行 Stage08/Stage09 定向测试、Mini App 全量串行测试、生产构建和 `git diff --check`。

## 6. Acceptance Criteria

1. 同步 `/query` 行为和 replay/idempotency 不回归。
2. 流路由只发送严格白名单、安全校验后的事件。
3. 事件 `sequence` 严格递增，正常流以唯一 `result` 和 `done` 结束。
4. 所有 `answer_delta` 拼接值与最终 `SafeView.answer` 完全一致。
5. 在 skill launcher 扩展获确认后，`SkillStrip` 只消费服务端精选 active skills；显式技能真实约束后端 LLM profile、action validation 与审计，无严格写证明时任何技能都不能发起 `draft_update`。
6. Composer 支持 Enter 发送、Shift+Enter 换行，窄屏不被抽屉或错误状态遮挡。
7. 中断不伪称取消，写入型请求不自动重复提交。
8. Nginx 不缓冲 SSE，部署资产测试覆盖内部与公网 HTTPS 配置。
9. 至少完成一次受控浏览器只读验收并保留脱敏证据；任何真实草稿或表格写入仍需动作级确认。

## 7. Remaining Risks

- 当前 Stage08 API 基线存在一个旧 monkeypatch 签名失败，必须先修复测试基线。
- `npm audit` 报告一个既有 high severity 依赖问题；本轮不自动升级依赖，需单独评估兼容性。
- 真实浏览器自动化通道此前不稳定，可能阻塞最终视觉证据，但不能由单测替代。
- 本轮不部署；发布仍需在代码审查和本地验证通过后单独执行。
