# Stage08 真实运行时收口：结构化决策与授权关系 DTO

## Status

- Document status: approved by current user implementation instruction
- Date: 2026-07-23
- Scope: 修复真实业务 Prompt 评测中暴露的结构化输出、能力选择和草稿措辞问题；把已经存在的授权群聊—客户—项目—数字员工映射投影到 Mini App。
- Non-goals: 不新增数据库表或迁移；不扩大权限；不读取历史群聊原文；不自动确认草稿；不发送 Telegram、webhook 或通知；不改变 Stage03。
- Current Progress: 2026-07-23 已完成实现。Stage08 只会在 `LLM_ENABLED=true` 且 `AGENT_WORKFLOW_MODE=real_openrouter` 时按单请求 30 秒总时限接入 OpenRouter；无该组合时仍使用不可用 Provider 安全降级。尚未在本次代码变更中运行新的真实 Provider 复测。

## 1. 目标

本收口把两个已有但未完全连通的能力接到真实运行时：

1. `OpenRouterStructuredLLMClient` 必须把调用方提供的 JSON Schema 作为 OpenAI-compatible `json_schema + strict` 请求发送，并在本地严格复核响应；不再只要求宽泛的 `json_object`。
2. Stage06 的 `draft_update` 回复不能把模型在“建议阶段”的文本当作已执行事实。只有持久化草稿回执存在时才能使用完成态文案；运行时未确认时统一渲染为“已提出待确认草稿”。
3. Stage08 OpenRouter analysis provider 必须能在已请求 `draft_update` 时返回单字段、受现有 `DraftIntent` 约束的提议；任何多字段、未授权 action、无 citation、越界 ordinal、额外字段、无效 JSON 或不安全完成态文案都 fail closed。
4. Mini App Home 只投影当前调用者已绑定的 active `chat_user` 群关系：`digital employee -> authorized group -> customer record + project record`。客户/项目标签只能从当前 actor 已可读的记录派生；无法安全读取、歧义或已失效时整条关系不返回。

## 2. 设计边界

### 2.1 输出与路由

运行时的真实可执行 action 仍只有既有 `read_only` 和 `draft_update`；不把评测中的 `lookup_table`、`knowledge_search`、`group_context` 伪装成可执行工具。它们由 Context/Retrieval 的已有实际分支决定，而非让模型自由声明。

| 输入条件 | 允许模型 action | 运行时结果 |
| --- | --- | --- |
| `requested_action=read_only` 且非 `general_advice` | `read_only` 或 `deny` | 仅返回安全答案/引用或拒绝 |
| `intent=general_advice` | `general_advice` 或 `deny`，无 citation | 不读取业务事实作建议依据 |
| `requested_action=draft_update` | 仅 `draft_update`，且一个 `field_key/value`、至少一个当前 citation | 已有 Policy Gate 和 Tool Gateway 创建 `pending_confirmation` 草稿 |

解析失败不会把原始模型文本返回给用户，也不会进入 Gateway。Provider 失败统一走现有 `analysis_unavailable` 降级。

### 2.2 JSON Schema

通用结构化 LLM 客户端使用调用方现有 `StructuredLLMRequest.response_schema` 生成：

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "structured_llm_response",
    "strict": true,
    "schema": {"...": "request.response_schema"}
  }
}
```

本地仍调用 `json.loads` 并拒绝非 object，Provider 的 schema 服从不能取代服务端校验。

### 2.3 Stage08 真实 Provider 装配

`POST /api/stage08/assistant/query` 在完成现有权限、业务范围和幂等校验后，为每次调用创建一个共享的 30 秒运行时 deadline。

- 只有 `LLM_ENABLED=true` 且 `AGENT_WORKFLOW_MODE=real_openrouter` 时，路由才装配 `OpenRouterStage08AnalysisProvider`。
- Provider 使用同一个 deadline 的剩余时间，并且自身仍受 20 秒 Provider 子预算限制；超时、HTTP 错误、结构不合规或不安全文本统一返回既有降级结果。
- 未启用该组合或没有 API Key 时，运行时不访问外部网络；保持 `UnavailableAnalysisProvider` 和既有安全降级。
- Provider 不获得数据库凭证、Telegram 凭证、原始聊天内容或写权限。`draft_update` 仍经既有 Policy Gate、Tool Gateway 和 `pending_confirmation` 落地。

### 2.4 Mini App 授权关系 DTO

`GET /workspaces/{workspace_id}/home` 在既有 `workspace.read` 授权后新增可选 `business_context_relations`。每项只包含：

```text
employee(id, name, base_id)
group(binding_id, label="已授权群聊 N")
customer(record_id, base_id, label)
project(record_id, base_id, label)
mapping_version
```

关系只从当前用户唯一 active workspace membership 对应的 active `chat_user` binding 及其唯一 active Stage08 mapping 读取。记录 label 只使用 `read_record_for_actor()` 返回的可见值中的首个非空短文本；没有可见文本则使用固定“客户记录/项目记录”，不输出 Telegram ID、群消息或隐藏字段。

前端在 Home 显示这些关系为可点击的“已授权业务关联”索引：员工按钮进入其所属 Base 的数字员工管理入口；客户/项目按钮通过既有 `openBase(..., { recordId })` 打开对应记录；群聊按钮进入既有受控上下文工作台，但不声称拥有未实现的群聊详情页。Base 工作台与 Team Bot 同时显示同一份权限过滤后的关系摘要，避免在不同页面制造不一致或假数据。

## 3. TDD 实施任务

1. 先为 `OpenRouterStructuredLLMClient` 写请求 JSON Schema、非 object 拒绝和现有 JSON 兼容测试，再实现 adapter。
2. 先为 Stage06 `draft_update` 写“模型完成态文本被安全替换”的失败测试，再实现固定草稿提议文案。
3. 先为 Stage08 analysis provider 写 draft action、错误 action、错误 citation、完成态文案和 JSON Schema 请求测试，再扩展 provider；仅在既有真实 OpenRouter 运行开关同时启用时按请求装配 Provider。
4. 先为 Home service/API 写授权 relation 正向、无 membership/失效 mapping/隐藏字段 fail-closed 测试，再扩展 DTO 和服务。
5. 先为 Mini App Home 写真实 relation 渲染与 record 索引回调测试，再接入类型和 `App.tsx` 回调。

## 4. 验收

- 本实现不发送 Telegram 或数据库业务写入；真实 Provider 仅由既有 `LLM_ENABLED=true` 与 `AGENT_WORKFLOW_MODE=real_openrouter` 组合显式启用。
- 结构化 JSON 的 transport request、服务端解析与 output guard 均由 unit test 证明。
- 草稿文案在未持久化前不出现“已生成/已执行/已写入”。
- Home API 不返回 chat ID、群片段、隐藏字段或无法重新授权的关系。
- 后端聚焦测试、Mini App 聚焦测试、完整 backend/mini-app 回归和生产构建通过后，才运行新的脱敏真实 Provider 复测。
