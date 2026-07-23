# Stage08 真实运行时收口实现证据

## Status

- Date: 2026-07-23
- Scope: 结构化 LLM 输出、`draft_update` 语义、Stage08 OpenRouter 运行时装配、Home 授权业务关联索引。
- External writes: 已在用户授权下发布 Stage09 原生 r15/r16/r17 release，完成固定迁移与受限 systemd 服务重启；未发送 Telegram、未确认草稿、未写业务记录或 Provider 业务端。
- Real Provider: 本地工作树无 Stage08 Provider 环境文件；真实复测已改在服务器受控运行时完成。评测临时读取三项 Provider 配置到一次性受限文件，结束即删除；不记录密钥、完整 prompt 或完整 response。

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
| `python -m pytest tests/unit/test_llm_adapters.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage07_mini_app_api.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_runtime_configuration.py tests/unit/test_stage08_real_provider_evaluation.py -q` | `93 passed in 56.92s` |
| `npm.cmd run test:run` | `65 files, 238 tests passed` |
| `npm.cmd run build` | TypeScript + Vite production build passed |
| `git diff --check -- backend mini-app project-docs docs` | passed |

## 真实服务器复测与发布

- Stage09 r17 的 sealed release、部署资产、固定迁移离线校验、运行时 preflight 和原子切换均通过；`current`、`current-venv`、静态站点均指向 r17。
- API、worker、outbox bridge、Nginx 均为 `active`；API 回环 `/health`、外部 HTTPS `/health` 与首页均实际返回成功。
- 初始真实评测揭示两项评测契约遗漏：无有效群上下文时模型 `deny` 是合格安全答案；`draft_update` 是已支持的待确认草稿动作。修正后，另一轮评测暴露 OpenRouter 自动路由的偶发语义漂移，因此 Provider 新增“仅对 HTTP 成功但结构/语义无效的结果重试一次”。网络、HTTP 或超时错误仍不重试并失败闭合。
- 最终 r17 真实评测：`case_count=12`、`passed_count=12`、`failed_count=0`、`timed_out_count=0`、`all_gates_passed=true`；9 次 Provider 调用均完成，8 次带 usage metadata。隐藏字段、撤权、群上下文生命周期、RAG 生命周期、拒绝、草稿压力、取消、安全重放与中英混合场景均通过；未产生 Telegram 发送、业务记录写入或草稿确认。

## 未完成或未执行

- `python -m pytest -q` 两次运行均超过 5 分钟且无完成结果，已人工终止；不能计入全后端回归通过。聚焦回归已通过。
- 全后端 `python -m pytest -q` 两次运行超过 5 分钟未完成，未计入通过；其余上述聚焦、Mini App 和真实服务器证据均独立记录。
- 本任务没有新增独立的群聊详情页；群聊索引明确跳转到现有受控上下文工作台。
