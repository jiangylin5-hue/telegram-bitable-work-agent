# Stage08 真实运行时收口实现证据

## Status

- Date: 2026-07-23
- Scope: 结构化 LLM 输出、`draft_update` 语义、Stage08 OpenRouter 运行时装配、Home 授权业务关联索引。
- External writes: 无 Telegram、webhook、通知、业务记录确认或部署写入。
- Real Provider: 本地工作树未发现可用于 Stage08 真实调用的环境文件；本次未伪造真实 Provider 结果。部署环境在 `LLM_ENABLED=true` 且 `AGENT_WORKFLOW_MODE=real_openrouter` 时才会启用该 Provider。

## 已完成实现

1. 通用 OpenRouter 结构化客户端使用 `response_format.type=json_schema` 与 `strict=true`，并继续在服务端拒绝非 JSON object。
2. Stage06 `draft_update` 仅在后端已创建 `pending_confirmation` 草稿后，返回“已提出一个待确认草稿。”；不透传模型的完成态说法。
3. Stage08 analysis provider 支持受 `DraftIntent` 约束的单字段草稿；未请求的 action、无 citation、越界 citation、额外字段、非法草稿值和“已写入/已完成”等误导文案均 fail closed。
4. Stage08 API 请求在既有真实 OpenRouter 开关同时启用时，为单次运行创建共享 30 秒 deadline，并把同一剩余时限传给 Provider；不开关时仍为 `UnavailableAnalysisProvider`。
5. Home API 返回当前用户唯一 active `chat_user` binding 的安全映射：数字员工、脱敏群聊标签、客户记录、项目记录。Telegram chat/user ID、群消息片段和不可读字段不进入响应。
6. Mini App 首页显示可点击关系索引：客户/项目打开记录，数字员工打开其管理入口，群聊打开既有受控上下文工作台；Base 工作台和 Team Bot 复用同一份授权关系摘要，窄屏也保留首页索引。

## 验证结果

| 命令 | 结果 |
| --- | --- |
| `python -m pytest tests/unit/test_llm_adapters.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage07_mini_app_api.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_runtime_configuration.py -q` | `44 passed in 14.30s` |
| `npm.cmd run test:run` | `65 files, 238 tests passed` |
| `npm.cmd run build` | TypeScript + Vite production build passed |
| `git diff --check -- backend mini-app project-docs docs` | passed |

## 未完成或未执行

- `python -m pytest -q` 两次运行均超过 5 分钟且无完成结果，已人工终止；不能计入全后端回归通过。聚焦回归已通过。
- 新实现尚未使用真实 OpenRouter 做复测，原因是当前本地工作树不存在可用的 Stage08 Provider 环境文件。该复测应在部署后使用已配置环境执行，并以脱敏报告记录。
- 本任务没有新增独立的群聊详情页；群聊索引明确跳转到现有受控上下文工作台。
