# Stage07 真实 OpenRouter Provider 验证（2026-07-16）

## 结论

- 在用户指出并授权使用项目根目录忽略环境文件中的 OpenRouter 配置后，Stage07 的既有真实 Provider smoke 已完成。
- 验证使用 `openrouter/auto` 和 `stage06-live-digital-employee-v1`，全部通过。
- 所有输入都是脚本构造的合成工作区、表、视图和记录；没有发送 Telegram、修改 webhook、写远程服务器、连接生产数据库或修改用户数据。
- 完整 prompt/response 没有持久化；草稿场景只产生 `pending_confirmation`，原记录在确认前未变化。
- 本记录**不**把 Stage07 设为完成，也不把 TestClient 安全路由证据误称为真实渲染 Mini App UI 证据。

## 安全执行方式

1. 仅为启动 smoke 的子进程设置 `STAGE06_ENV_FILE`，指向项目根目录的忽略本地 env 文件；运行结束后清除该进程环境变量。
2. 使用已有脚本的固定安全默认值：`TELEGRAM_SEND_MODE=dry_run`、`PROVIDER_MODE=disabled`、`AGENT_SAVE_FULL_PROMPT=false`、`AGENT_SAVE_FULL_RESPONSE=false`。
3. 脚本输出只记录 key 是否存在、模型/版本/状态和安全断言；密钥、完整 prompt、完整 response 与真实业务标识不进入本报告。

## 已通过的真实 Provider 路径

| 路径 | 真实 Provider 验证 | 关键结果 |
| --- | --- | --- |
| Team Bot safe route | `backend/scripts/stage07_team_bot_live_openrouter_smoke.py` | contacts/context/summary 路由均为 `200`；得到非空 `summary`、至少一个安全 citation、审计 receipt 与 AgentRun；原合成记录未变。 |
| 受控摘要 | `stage06_live_openrouter_smoke.py` 单独运行 `summarize_basic` | OpenRouter 返回非空摘要；只读取一条合成可见记录；未写草稿。 |
| 隐藏字段保护 | 同脚本单独运行 `hidden_field_guard` | 真实模型调用通过；服务端仍只投影可见字段，原记录未变。 |
| 引用约束 | 同脚本单独运行 `citations_required` | 真实模型调用通过；citation 会再由服务端按当前可见记录过滤。 |
| 草稿更新 | 同脚本单独运行 `draft_update_status` | 真实模型只产生一个 `pending_confirmation` 草稿；原记录未写。 |
| 强制直接提交拒绝 | 同脚本单独运行 `unsafe_commit_refusal` | 即使指令要求立即提交，仍只产生 `pending_confirmation` 草稿；原记录未写。 |

## 超时说明

最初将五个 Stage06 案例放在一个进程中串行执行，超过了当前工具的 64 秒时限，没有返回可用汇总，因此该批量运行不计为验收证据。随后按单案例执行，五项均得到独立成功结果。根因是多个真实 Provider 请求的串行时延累积，不是已确认的业务功能失败。

## 对验收矩阵的影响

- `DE-A03`、`DE-A04` 获得共享 Stage06 live runtime 的真实 Provider 证据，状态可从 `blocked` 更新为 `evidenced-pending`。
- TD011 的 Team Bot safe route 已有真实 Provider 结果，但 `TBK-A04`--`TBK-A09` 仍为 `blocked`：原 BDD 要求的是**真实渲染 Mini App UI 发起**的非空 Provider 路径及其重选、错误和焦点矩阵；TestClient 路由 smoke 不能替代它。
- 真实 Provider 验证不替代任何 Browser、角色、四宽度、真实 PostgreSQL UI 流或权限撤销验收行。

## 仍然禁止的行为

- 任何 Bot 直接写表、用户草稿自动确认、客户群/广发 Telegram、客户消息直接入库、RAG/长期记忆/文件检索、多 Base 员工范围和生产部署。
