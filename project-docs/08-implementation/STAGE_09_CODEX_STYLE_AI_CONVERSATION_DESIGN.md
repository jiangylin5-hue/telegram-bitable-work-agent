# Stage09 Codex 式 AI 对话工作台设计

## Status

- **Status:** 用户已确认产品设计、Ledgerline 视觉方向与 LLM skill launcher；先实施 skill runtime，再恢复 Task 4 收口
- **Date:** 2026-07-26
- **Scope:** 在现有工作台内，把“AI 对话”改为类似 Codex 的持续工作界面：底部固定输入区、上方持续输出、可直接套用的业务技能标签，以及真实受控的 SSE 状态流。
- **Confirmed decision:** 新增受控 SSE 接口；保留现有同步接口作为兼容路径。
- **Selected visual truth:** `project-docs/08-implementation/assets/stage09/ledgerline-workbench-selected.png`，由用户在 2026-07-26 选择 Product Design 方案 1。
- **Out of scope:** 不新建通用聊天记忆库；不把模型原始 token、思维过程、内部异常或群聊原文流式发送到浏览器；不绕过既有权限、审计、草稿确认与工具网关。

## 1. 现状与问题

当前 `CollaborationWorkbench.tsx` 是“员工选择 / 参数选择 / 最终结果”三列面板。它通过 `POST /api/stage08/assistant/query` 等待完整 `Stage08AssistantSafeView` 后一次性展示结果。

这能完成受控问答和草稿生成，但交互不像工作型 Agent：用户看不到任务正在进行到哪一步，也没有一个稳定、连续的输入与输出区域。用户已明确要求改为更接近 Codex 的工作流界面。

本设计只改变呈现和传输方式，不改变业务事实来源：表格是实时业务真源，记忆和知识用于检索，模型输出仍必须经既有安全投影与服务层校验后才能展示或进入草稿。

## 2. 用户可见体验

```text
选择数字员工与当前上下文
    -> 在底部输入任务，或点一个技能标签预填任务
    -> 发送
    -> 上方时间线依次显示“正在核验权限 / 正在检索表格与群聊上下文 / 正在分析 / 正在生成草稿”
    -> 安全答案分段出现
    -> 最终显示引用、降级说明、草稿入口或受控下一步
```

### 2.1 布局

| 区域 | 内容 | 规则 |
| --- | --- | --- |
| 顶部上下文条 | 当前数字员工、当前 Base/表/记录或群聊关联、可切换入口 | 只显示已授权的摘要；切换仍复用既有选择器。 |
| 主时间线 | 用户问题、执行阶段、答案分段、引用、草稿状态、失败/降级提示 | 新消息始终追加；滚动到用户手动上滚时不强制抢回视线。 |
| 底部 Composer | 单一主输入框、技能标签、发送按钮、当前模式提示 | 固定在对话底部；`Enter` 发送，`Shift+Enter` 换行；空输入禁止发送。 |
| 右侧信息区（桌面） | 当前已授权关系、可用技能和草稿队列入口 | 屏幕较窄时折叠为抽屉，不能遮住 Composer。 |

视觉沿用已部署 Stage09 工作台的白底、蓝色主操作、紧凑表格感和 Lucide 图标。避免大面积渐变、玻璃拟态、伪终端、无意义装饰卡片，也不伪造“模型思考过程”。

### 2.2 Ledgerline 视觉系统

选定方向不是“聊天气泡 + AI 动画”，而是“业务台账 + 连续执行日志”。视觉真源尺寸为 `1440 x 1024`，实现时保留其信息层级、节奏和组件语言，同时沿用项目现有导航、真实字段和已确认技能，不照抄图中仅用于构图的虚构数据或能力。

#### 2.2.1 构图与尺寸

桌面工作台使用接近满屏的受控 overlay，不嵌套为居中小卡片：

```text
viewport
└── workbench shell: min(1240px, 100vw - 32px), max-height: 100dvh - 32px
    ├── context strip: 56px
    ├── body: minmax(0, 1fr)
    │   ├── timeline index rail: 104px
    │   ├── continuous transcript: minmax(0, 1fr)
    │   └── safe scope aside: 248px
    └── composer dock: content-driven, 132–164px
```

- shell 圆角 `10px`，内层控件主要使用 `4px`、`6px`、`8px`，避免所有元素统一为大圆角。
- 主时间线内容最大阅读宽度约 `760px`，表格证据可扩展到 transcript 全宽。
- 时间线不是多张卡片：问题、状态、答案、证据和草稿共享同一张连续底纸，靠垂直蓝线、序号、时间和细分隔线建立层级。
- 右侧只显示已授权记录摘要、数字员工范围和审计入口；没有安全数据时显示简短空态，不用虚构指标填充。

#### 2.2.2 视觉 token

| token | 建议值 | 用途 |
| --- | --- | --- |
| `--ledger-canvas` | `#f8f7f2` | 温暖底纸，替代纯白 AI 面板。 |
| `--ledger-surface` | `#ffffff` | Composer、输入框和必要的交互表面。 |
| `--ledger-ink` | `#26313b` | 正文与标题，不使用纯黑。 |
| `--ledger-muted` | `#6f7882` | 时间、来源、辅助说明。 |
| `--ledger-line` | `#d9dee3` | 台账行线和结构分隔。 |
| `--ledger-blue` | `#2478e8` | 唯一主操作与时间线定位色。 |
| `--ledger-blue-soft` | `#eaf3ff` | 选中、focus、当前步骤。 |
| `--ledger-pending` | `#b76a16` | 仅用于“待确认、未写入”。 |
| `--ledger-danger` | `#b34b4b` | 拒绝或错误，不与 pending 混用。 |

正文保持 `14–16px`；标题使用 `600`，状态和导航使用 `500`；ID、sequence、时间和计数使用系统等宽字体与 `font-variant-numeric: tabular-nums`。不引入需要在线加载的新字体，中文优先沿用 `"PingFang SC", "Microsoft YaHei"`，Latin/数字使用系统 UI 与 monospace fallback，避免部署时字体漂移。

#### 2.2.3 图案、材质与图标

- 底纸使用一张低对比度、可平铺的 raster 台账纹理，包含细横线、微弱纸纤维与稀疏坐标刻度；目标文件为 `mini-app/src/assets/ledger-paper-texture.png`。
- 纹理透明度控制在 `6%–10%`，不能降低正文对比度，也不能在每个子组件重复铺设。
- 禁止用 CSS gradient、handcrafted SVG、emoji 或 `div` 拼图伪造该纹理。
- 图标复用项目已经安装并在相邻页面使用的 Lucide 集合，因为它与选定稿的细线图标和现有产品一致；统一 stroke width，不新增第二套图标依赖。
- 不使用发光球、sparkle、魔法棒、机器人、脑图标、紫蓝渐变、玻璃拟态或装饰性插画。

#### 2.2.4 组件层级

| 组件 | 视觉与交互职责 | 禁止事项 |
| --- | --- | --- |
| `ContextStrip` | 单行展示 workspace / Base / view / record / employee；每项可聚焦、可回到既有选择器。 | 不用五张独立卡片，不泄露 ID 票据或权限详情。 |
| `TimelineIndexRail` | sequence、时间、蓝色定位点、细竖线；当前运行步骤使用实心点。 | 不伪装未发生的 runtime 阶段。 |
| `TimelineEntry` | 用户请求、状态、最终答案共享 transcript 排版；答案宽度受控。 | 不使用左右聊天气泡，不显示隐藏推理。 |
| `EvidenceRows` | 引用、字段和值按紧凑表格行展示；可进入已授权记录。 | 不复制整个原始记录，不把每行做成卡片。 |
| `DraftSheet` | 使用 pending 色单边线、`待确认 · 未写入` 标识和“查看草稿”入口。 | 不显示“已执行”，不在这里自动确认。 |
| `SafeScopeAside` | 当前记录摘要、employee 范围、审计入口；桌面常驻、窄屏抽屉。 | 不展示 raw policy、token、provider 或群聊原文。 |
| `SkillStrip` | 六个矩形快捷项，点击只预填并聚焦 Composer。 | 不做自动执行按钮，不用满屏胶囊。 |
| `ComposerDock` | textarea、发送、停止查看、模式提示；与底部安全区相容。 | 不悬浮成聊天泡，不遮挡时间线最后一项。 |

视觉稿中的技能文案只作为构图示例。运行时继续使用第 3 节已经确认的六个稳定 `tag id` 与权限映射，不为了视觉稿新增“生成周报”等未定义能力。

#### 2.2.5 状态视觉

```text
idle       -> 空台账 + 一条具体起始提示 + 可用技能
streaming  -> timeline 点与状态文字变化；不得使用假百分比或循环“思考”
completed  -> result.safe_view 成为答案、引用、degraded/draft 的唯一真源
stopped    -> 保留已收到内容，明确“已停止查看”，不声称后端取消
error      -> 时间线内联稳定错误，Composer 可继续编辑；不使用 alert/modal
draft      -> pending 单边线 + “待确认 · 未写入” + 查看草稿入口
```

`answer_delta` 只改变答案正文的渐进显示；只有收到并校验 `result` 与 `done` 后，时间线才进入 completed。发送按钮具有 hover、active 和 keyboard focus；所有图标按钮有可读 `aria-label`。

Task 4 独立审查后的状态约束：

- `result` 到达时可以保存并展示 `safe_view`，但 turn 仍处于 `finalizing`；只有 parser 读到物理 EOF、校验唯一 `result` 与 `done` 后，调用成功返回，reducer 才能转为 `completed`。
- `result` 后若 `done` 缺失、损坏或存在尾随数据，turn 必须进入 `failed`，不能因为已经显示 safe result 而忽略失败。
- reducer 额外锁定第一个 server `request_id` 和递增 `sequence`；这不是替代 parser，而是避免测试替身、未来 transport 或错误调用直接污染 UI 状态。
- 自动跟随滚动只在用户仍靠近时间线底部时发生；用户主动上滚后不得抢回视线。

草稿可用性必须同时由三个已证明条件决定：

```text
current record exists
AND current record write capability is explicitly true
AND selected employee belongs to the current Base/scope
AND employee allows draft_update
```

`currentRecordId` 存在本身不是写权限。若现有前端上下文无法证明 record writable 或 employee/Base 匹配，安全默认值必须是 `false`；本阶段不得为此新增权限 API 或推测权限。

#### 2.2.6 响应式规则

- `>= 1180px`：完整三轨结构；右侧 scope aside 常驻。
- `768–1179px`：隐藏文字型 timeline rail，只保留序号/点；scope aside 变为顶部“范围与审计”抽屉；Composer 仍固定在 shell 内。
- `< 768px`：工作台占满 `100dvh`；context strip 横向滚动且保持单行；时间线单列；证据表允许容器内横向滚动；技能条横向滚动；发送与停止查看始终可触达。
- Composer 使用 `position: sticky` 和 `env(safe-area-inset-bottom)`，正文底部 padding 至少等于 Composer 实际高度，避免 Telegram Mini App 键盘或底部导航遮挡。
- 任何断点都不隐藏安全状态、草稿“未写入”文案或 error；只允许折叠次要 context。

Base 主入口不得再把工作台固定为 `520px` side panel。桌面统一使用上述宽 Ledgerline dialog；窄屏由同一组件按断点进入全屏模式，避免维护两套信息架构。

dialog 可访问性：

- 打开后初始焦点进入 Composer textarea；
- `Tab` / `Shift+Tab` 在 dialog 内循环，背景内容不可被键盘或辅助技术误操作；
- `Escape` 关闭并中止本地查看；
- 关闭后把焦点还给触发工作台的控件；
- `aria-modal="true"`、可读标题和描述必须成组存在，不能只依赖视觉遮罩。

### 2.3 可展示的执行状态

| 阶段 key | 用户文案 | 可以展示的信息 |
| --- | --- | --- |
| `authorizing` | 正在核验当前身份与操作范围 | 是否正在检查；不显示原始身份票据或权限规则细节。 |
| `planning_context` | 正在确定本次工作范围 | 当前已选 Base、表、记录、数字员工的安全名称。 |
| `retrieving_knowledge` | 正在检索已授权业务数据、群聊上下文与知识 | 仅安全来源类别与数量摘要。 |
| `analysing` | 正在整理结论与下一步 | 无模型隐藏推理、无 provider 请求体。 |
| `creating_draft` | 正在生成待确认草稿 | 仅 `draft_update` 已被允许时出现。 |
| `completed` | 已完成 | 最终安全答案、引用、降级/拒绝解释或草稿状态。 |

“正在检索”不等于已经写入；所有写入仍必须通过现有 draft-confirmation 流程，界面不能把提议表述成已执行。

阶段 key 是协议允许集合，不代表首版必须全部发送。首版后端只有两个可以由现有服务边界证明的执行前状态：

```text
fresh request:
authorizing -> analysing -> answer_delta* -> result -> completed -> done

idempotent replay:
authorizing -> answer_delta* -> result -> completed -> done
```

- `authorizing` 在 UUID、workspace 权限、数字员工/记录 scope 和幂等检查开始前发送。
- `analysing` 仅在 fresh request 已完成授权与幂等 reservation、即将进入现有 `run_stage08_collaboration` 受控 runtime 时发送。
- replay 不重新执行 runtime，因此不能发送 `analysing`。
- 当前 runtime 没有暴露独立的上下文规划、知识检索或草稿创建回调，所以首版不发送 `planning_context`、`retrieving_knowledge` 或 `creating_draft`。不能仅凭请求意图推断这些阶段。
- 是否创建草稿、是否降级或拒绝，只能以校验并提交后的 `result.safe_view` 为真源。

## 3. 技能标签

原设计把技能标签定义成快捷填充器。2026-07-26 用户进一步明确：技能标签必须与后端真实 skills 高度关联，并在 LLM 执行链路中实际生效，不能只预填 Composer。该新要求由 `STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md` 详细定义；API contract、runtime 和 permission intersection 变更已获用户确认。

确认后的目标语义是：点击标签选择服务端 `skill_id`、预填可编辑任务并聚焦输入框；发送时服务端重新解析 manifest、权限交集、supporting guardrails 和 LLM execution profile。标签仍不是绕过确认的“自动执行按钮”。

以下旧 tag 仅作为已实现 UI 草稿的迁移清单，不再是能力真源：

| legacy tag id | 标签 | 迁移结果 |
| --- | --- | --- |
| `business_summary` | 智能汇总 | 迁移为 `platform-tabular-analysis` / 汇总分析。 |
| `table_lookup` | 查表问答 | 迁移为 `platform-base` / 查表问答。 |
| `group_context` | 群聊总结 | 迁移为 `platform-telegram-im` / 群聊上下文，仅有真实 chat proof 时启用。 |
| `risk_review` | 风险识别 | 不再作为独立 skill；是 `platform-tabular-analysis` 的任务表述。 |
| `memory_lookup` | 调用长期记忆 | 不再作为独立 skill；它是 Stage08 retrieval intent，不是 active Stage06 manifest。 |
| `follow_up_draft` | 生成跟进草稿 | 迁移到 `platform-task` 或 `platform-base` 的 conditional `draft_update`，仅有严格写证明时启用。 |

首批公开技能建议固定为 `platform-base`、`platform-tabular-analysis`、`platform-task` 和 `platform-telegram-im`，另保留 server auto mode。`platform-shared-policy` 与 `platform-approval` 由后端自动附加，不能显示为可选业务标签。技能目录失败时不能回退到静态可用标签。

## 4. SSE 接口契约

### 4.1 路由与兼容性

- 保留现有 `POST /api/stage08/assistant/query`，供旧界面、回退和现有测试继续使用。
- 新增 `POST /api/stage08/assistant/query-stream`，请求体复用现有 `AssistantQueryRequest` 的严格 schema，响应为 `text/event-stream`。
- 新接口必须复用现有身份、workspace/base/table/field/record scope、agent scope、chat scope、幂等、审计、`run_stage08_collaboration` 与 `validate_assistant_query_safe_view`；禁止另建旁路执行器。

### 4.2 事件格式

所有事件带严格单调递增的 `sequence` 和 `request_id`。浏览器只能处理下表白名单事件；未知事件必须安全忽略并记录开发期诊断，不能渲染其内容。

| SSE event | 必填字段 | 用途 |
| --- | --- | --- |
| `status` | `sequence`, `request_id`, `phase` | 展示上述允许的执行阶段。 |
| `answer_delta` | `sequence`, `request_id`, `text` | 已通过安全投影后的答案片段。 |
| `result` | `sequence`, `request_id`, `safe_view` | 最终完整 `Stage08AssistantSafeView`；作为引用、草稿和状态的真源。 |
| `error` | `sequence`, `request_id`, `code`, `message` | 稳定的用户可见错误，禁止携带堆栈、凭据、原始输入或 provider 响应。 |
| `done` | `sequence`, `request_id` | 正常结束标记。 |

### 4.3 为什么不是原始模型逐 token 转发

首版 SSE 是真实传输与真实生命周期状态，但不是原始 LLM token passthrough：服务端先完成既有受控执行，确认最终 `SafeView` 合格后，才将可展示答案按安全边界切成 `answer_delta`。这样既有连续输出体验，又不会把未经权限过滤的内容、模型隐藏推理或中间工具结果暴露给浏览器。

后续如果需要真正的模型流式生成，必须另做安全审查，证明每一段 token 都能在发送前独立完成字段、引用、敏感内容和策略校验。

### 4.4 断开、重试与草稿

- `read_only`：用户关闭或切换页面时停止前端订阅，显示“已停止查看结果”；不得声称服务器任务已取消。重新发送时使用新的 request id。
- `draft_update`：请求一旦被后端受理，前端不能提供虚假的“撤销执行”。最终以已有待确认草稿队列和审计记录为准。
- 网络中断：显示“连接中断，可重试”，不得用前端缓存假装已完成；如果收到了 `result`，以其中安全结果为准。
- 流生成器在 `prepare` 后持有未完成幂等 reservation 时，必须使用 `finally` 覆盖正常异常、客户端断开和 `GeneratorExit`：未完成时回滚 SQLAlchemy session，并清除 InMemory reservation；已经由 `complete` 提交的结果不得被反向清理。
- 不把这轮 UI 历史写入新的长期记忆表。持久化结果只沿用既有 audit、agent run 和 draft 机制。

## 5. 实现边界与文件方向

| 层 | 主要文件 | 预期改动 |
| --- | --- | --- |
| 前端工作台 | `mini-app/src/app/CollaborationWorkbench.tsx` | 三列选择器重构为顶部上下文、连续时间线与固定 Composer；保留既有员工和上下文选择能力。 |
| 前端 API | `mini-app/src/app/api.ts` | 增加严格 SSE 请求/解析器与断开处理；保留 `queryStage08Assistant`。 |
| 前端类型与测试 | `mini-app/src/app/stage08-collaboration-types.ts`、`mini-app/src/test/collaboration-workbench.test.tsx` | 加入流事件类型、技能填充、顺序、失败、断开、草稿边界测试。 |
| 后端 API | `backend/app/api/routes/stage08_collaboration.py` | 新增受控流端点，复用同步执行/校验服务，不复制业务规则。 |
| 后端 schema/service/test | `backend/app/schemas/stage08_collaboration.py`、相关 service 与 `backend/tests/unit/test_stage08_*` | 声明事件 schema，覆盖权限拒绝、顺序、错误脱敏、draft/read-only 路径。 |

实现前必须先把失败测试写出来，再完成最小改动；不能仅靠动画或前端 mock 宣称流式工作。

## 6. 验收标准

1. 已授权用户在浏览器工作台中能打开 AI 对话、选择上下文、输入问题并看到阶段状态和连续答案。
2. `SkillStrip` 只展示服务端目录返回的精选 active skills；显式选择会真实进入后端 LLM execution profile，任何 draft-capable skill 在无写证明、无记录或范围不允许时不得提供 `draft_update`。
3. 前端只渲染允许的阶段和安全事件；不会展示原始群聊、凭据、模型推理、异常栈或 provider 内容。
4. 同步 `/query` 的既有测试和行为不回归；流接口有前后端自动化测试，build/test 通过。
5. 至少一次受控真实浏览器只读业务 case 成功，并保存截图和脱敏请求/审计证据；真实草稿或表格写入必须在执行当刻再次获得用户确认。
6. 视觉上固定输入区不会被时间线、抽屉、错误条或窄屏布局遮挡；桌面与 Telegram 紧凑容器均可回退使用。

## Current Progress

**2026-07-26 final acceptance update:** automated acceptance and populated Browser
QA are complete in the
isolated worktree: 209 selected backend tests, 397 Mini App tests with 2
historical skips, production build and both rendered Nginx asset checks pass;
whole-branch review found no new Critical or Important code safety issue. The
final commit is deliberately blocked, not omitted: Product Design QA recorded
`final result: blocked` in root `design-qa.md` because no authorized local
backend/workspace data state was available to render and compare the populated
Ledgerline reference state. Deployment, Telegram writes and real business writes
remain out of scope.

设计和 SSE 契约于 2026-07-26 获用户确认。隔离分支 `codex/stage09-ai-conversation-sse`、阶段实施计划与详细 TDD 执行计划已经建立。后端 Task 2 的状态真实性与断开清理问题已修复并复核通过，87 项定向测试通过；前端 Task 3 的真实 data-only wire format、身份 header、结果一致性和终止状态机问题已修复并复核通过，29 项定向测试及 TypeScript 校验通过。Task 4 Ledgerline UI 初版已完成并通过 42 项定向测试与 build，但独立复核发现的终态、权限证明、dialog、focus 和滚动问题尚未收口。用户新增并确认 LLM skill launcher；详细 API/runtime/permission 方案和独立 TDD plan 已建立，当前进入后端 catalog/profile 实施。Task5 已为 internal/public HTTPS 模板的精确 `/api/stage08/assistant/query-stream` route 完成 RED/GREEN rendered-config 检查，验证 HTTP/1.1、关闭 proxy buffer/cache、90s read timeout 和 `X-Accel-Buffering: no`；部署、全阶段验收和真实业务写入尚未开始。所有变更将在整阶段验收与审计后单次提交。
