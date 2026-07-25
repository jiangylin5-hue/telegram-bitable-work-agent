# Stage09 Codex 式 AI 对话工作台设计

## Status

- **Status:** 用户已确认设计；实现尚未开始
- **Date:** 2026-07-26
- **Scope:** 在现有工作台内，把“AI 对话”改为类似 Codex 的持续工作界面：底部固定输入区、上方持续输出、可直接套用的业务技能标签，以及真实受控的 SSE 状态流。
- **Confirmed decision:** 新增受控 SSE 接口；保留现有同步接口作为兼容路径。
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

### 2.2 可展示的执行状态

| 阶段 key | 用户文案 | 可以展示的信息 |
| --- | --- | --- |
| `authorizing` | 正在核验当前身份与操作范围 | 是否正在检查；不显示原始身份票据或权限规则细节。 |
| `planning_context` | 正在确定本次工作范围 | 当前已选 Base、表、记录、数字员工的安全名称。 |
| `retrieving_knowledge` | 正在检索已授权业务数据、群聊上下文与知识 | 仅安全来源类别与数量摘要。 |
| `analysing` | 正在整理结论与下一步 | 无模型隐藏推理、无 provider 请求体。 |
| `creating_draft` | 正在生成待确认草稿 | 仅 `draft_update` 已被允许时出现。 |
| `completed` | 已完成 | 最终安全答案、引用、降级/拒绝解释或草稿状态。 |

“正在检索”不等于已经写入；所有写入仍必须通过现有 draft-confirmation 流程，界面不能把提议表述成已执行。

## 3. 技能标签

技能标签是快捷填充器，不是绕过确认的“自动执行按钮”。点击后会：预填 Composer、选择推荐的 `intent` 与 `requested_action`、聚焦输入框；用户仍可以编辑后发送。

| tag id | 标签 | 推荐 intent | 推荐 action | 约束 |
| --- | --- | --- | --- | --- |
| `business_summary` | 智能汇总 | `mixed` | `read_only` | 需要至少一个已授权业务范围。 |
| `table_lookup` | 查表问答 | `business_fact` | `read_only` | 优先使用当前表/视图。 |
| `group_context` | 群聊总结 | `mixed` | `read_only` | 只使用受控群聊上下文投影。 |
| `risk_review` | 风险识别 | `mixed` | `read_only` | 结论必须区分事实与分析。 |
| `memory_lookup` | 调用长期记忆 | `memory_lookup` | `read_only` | 记忆不是实时业务事实。 |
| `follow_up_draft` | 生成跟进草稿 | `mixed` | `draft_update` | 仅在当前记录可写且数字员工范围允许时展示。 |

标签文案需带小提示，例如“查表问答：基于已授权表格”“生成跟进草稿：需确认后写入”。不能把未实现功能伪装成可用技能。

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
2. 六类技能标签都能正确预填；`follow_up_draft` 在无写权限、无记录或范围不允许时不可用。
3. 前端只渲染允许的阶段和安全事件；不会展示原始群聊、凭据、模型推理、异常栈或 provider 内容。
4. 同步 `/query` 的既有测试和行为不回归；流接口有前后端自动化测试，build/test 通过。
5. 至少一次受控真实浏览器只读业务 case 成功，并保存截图和脱敏请求/审计证据；真实草稿或表格写入必须在执行当刻再次获得用户确认。
6. 视觉上固定输入区不会被时间线、抽屉、错误条或窄屏布局遮挡；桌面与 Telegram 紧凑容器均可回退使用。

## Current Progress

设计和 SSE 契约于 2026-07-26 获用户确认。本文件仅定义后续实现边界；尚未新增流接口、改动工作台或产生真实业务写入。
