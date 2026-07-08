# Stage 05 Local Real Workflow Env

## Status

- Document status: active local real-workflow runbook
- Scope: 项目级临时 env 文件、本地真实 OpenRouter 调用、Stage05 in-memory workflow 端到端验证。
- Current Progress: 2026-07-08 新增 `.local/stage05-real-workflow.env` 作为项目级临时 secrets 文件，并新增 `backend/scripts/stage05_local_real_workflow.py`。后续本地真实 LLM 验证必须先通过该脚本，再进入 Tencent Cloud staging 重试。
- Current Progress Update: 2026-07-08 Local real workflow passed with two redacted OpenRouter scenarios after the entity-key prompt contract fix. The routed draft scenario returned `workflow_status=routed`, `model_provider=openrouter`, `prompt_version=stage05-router-v1`, `intent_types=["recharge","customer_reply"]`, and created `recharge` plus `customer_reply` drafts with `status=pending_confirmation`, `provider_execution_allowed=false`, `send_request_created=false`, and `reply_text_present=true`. The default risk scenario returned `workflow_status=manual_review`, selected recharge/BM/customer-reply/account-inventory agents, and created no draft/provider/send side effects.

## 1. Purpose

这份文档替代之前只验证 adapter/parser 的 local smoke。当前要求是本地真实调用 OpenRouter，并跑完整 Stage05 workflow，而不是只打一条孤立的 LLM 请求。

本地真实 workflow 验证范围包括：

- 从项目级临时 env 文件读取 `OPENROUTER_API_KEY`、`OPENROUTER_MODEL` 和 `OPENROUTER_BASE_URL`。
- 使用真实 `OpenRouterStructuredLLMClient`。
- 调用 `Stage05AgentWorkflowService` 和 LangGraph Supervisor。
- 让 `message_intake_router` 真实解析一条中英混合业务消息。
- 通过 in-memory UOW 持久化 `AgentRun`、`ServiceDraft`、账户异常事件和 audit event。
- 只输出脱敏 evidence，不输出 raw key、raw token、raw prompt 或 raw LLM response。

该验证不连接 PostgreSQL、Redis、Telegram、Tencent Cloud 或 provider，不会产生任何真实发送、真实充值、真实账户生产、真实资金动作或真实 provider 写入。

## 2. Local Env File

实际填写文件：

```text
.local/stage05-real-workflow.env
```

该目录已经被 `.gitignore` 的 `.local/` 规则忽略。这个文件可以放本地测试 key/token，但不能加入 git，也不能复制到 Markdown、聊天记录、截图或提交信息里。

当前文件已在项目根目录创建，字段如下：

```text
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/auto
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

TELEGRAM_BOT_TOKEN=
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=

LLM_ENABLED=true
AGENT_WORKFLOW_MODE=real_openrouter
AGENT_SAVE_FULL_PROMPT=false
AGENT_SAVE_FULL_RESPONSE=false
TELEGRAM_SEND_MODE=dry_run
PROVIDER_MODE=disabled
```

## 3. Fill Rules

必须填写：

| Variable | Required | Notes |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | 只填在 `.local/stage05-real-workflow.env`，不要发到聊天。 |
| `OPENROUTER_MODEL` | yes | 默认 `openrouter/auto`；如果 staging 用指定模型，本地也填同一个模型。 |
| `OPENROUTER_BASE_URL` | yes | 默认 `https://openrouter.ai/api/v1`。 |

可选填写：

| Variable | Required | Notes |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | no | 当前本地真实 workflow 脚本不使用它，只为后续本地 Telegram send 检查预留。 |
| `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` | no | 当前本地真实 workflow 脚本不使用它。 |

安全字段必须保持：

| Variable | Required Value | Reason |
| --- | --- | --- |
| `AGENT_SAVE_FULL_PROMPT` | `false` | 禁止保存完整 prompt。 |
| `AGENT_SAVE_FULL_RESPONSE` | `false` | 禁止保存 raw response。 |
| `TELEGRAM_SEND_MODE` | `dry_run` | 本地 workflow 不允许真实 Telegram send。 |
| `PROVIDER_MODE` | `disabled` | 本地 workflow 不允许 provider 写入。 |

## 4. Run Command

用户填好 `.local/stage05-real-workflow.env` 后，不需要把任何值发出来。只要告诉 Codex `已填好`。

Codex 本地执行：

```powershell
cd "D:\telegram多维表格和工作智能体的开发\backend"
python scripts\stage05_local_real_workflow.py
```

脚本会自动从项目根目录读取：

```text
D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env
```

如需临时指定另一个 env 文件，可以设置：

```powershell
$env:STAGE05_LOCAL_ENV_FILE="D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env"
```

## 5. Built-In Test Message

脚本默认使用一条中英混合业务消息，覆盖 Stage05 真实场景：

```text
stage05_local_real 请帮客户 act_stage05_test 充值 100 USD，同时看下 BM invite 能不能处理；如果客户问进度，请回复：我们正在确认账户和资料，稍后同步。另外客户说 act_stage05_test 可能被风控了，请先标记异常，不要自动换号。
```

这条消息预期能触发或尝试触发：

- `recharge`：只创建充值服务草稿，`provider_execution_allowed=false`。
- `bm_invite`：只创建 BM invite 服务草稿，缺字段时进入 `needs_more_info`。
- `customer_reply`：只创建回复草稿，`send_request_created=false`。
- `account_status_exception`：只在 in-memory UOW 内对测试账号 `act_stage05_test` 标记异常，不做自动换号或真实分发。

如需临时覆盖测试消息，可以设置：

```powershell
$env:STAGE05_LOCAL_TEST_MESSAGE="your local test message"
```

覆盖消息仍然必须遵守本地边界：不得包含真实客户隐私、真实付款凭证、raw token、raw allowlist 或生产账户敏感信息。

## 6. Output Shape

脚本只输出脱敏 JSON evidence。关键字段包括：

- `ok`
- `openrouter_key_present`
- `telegram_bot_token_present`
- `provider_mode`
- `telegram_send_mode`
- `workflow_status`
- `selected_agents`
- `manual_review_reasons`
- `message_intent_status`
- `agent_runs[].model_provider`
- `agent_runs[].model_name`
- `agent_runs[].prompt_version`
- `agent_runs[].status`
- `agent_runs[].intent_types`
- `agent_runs[].redacted_summary`
- `service_drafts[].draft_type`
- `service_drafts[].status`
- `service_drafts[].missing_fields`
- `account_status_events[]`
- `audit_event_types`

脚本不会输出：

- `OPENROUTER_API_KEY` 的值。
- `TELEGRAM_BOT_TOKEN` 的值。
- raw Telegram chat id allowlist。
- raw prompt。
- raw LLM response。
- provider credential。

## 7. Pass Criteria

本地真实 workflow 通过条件：

- `ok=true`。
- `workflow_status` 是 `routed` 或 `manual_review`。
- 至少存在一条 `agent_runs`。
- `agent_runs[0].model_provider=openrouter`。
- `agent_runs[0].prompt_version=stage05-router-v1`。
- `agent_runs[0].status=succeeded`。
- `agent_runs[0].intent_types` 非空，且只包含 Stage05 支持的 intent。
- 如果有 `service_drafts`，所有 draft 都必须保持人工确认或补资料状态，不允许 provider execution。
- `provider_mode=disabled`。
- `telegram_send_mode=dry_run`。
- 输出不包含 raw key、raw token、raw prompt、raw response 或 raw allowlist。

`manual_review` 不是失败。对于缺少 BM invite 细节、账户异常证据不足、模型保守判断等情况，进入 `manual_review` 是安全结果。

失败条件：

- `workflow_status=agent_failed`。
- `agent_runs[0].error_code=agent_output_invalid`。
- 出现 unsupported top-level router shape。
- 出现 provider write、Telegram send 或 secrets 泄露风险。
- `PROVIDER_MODE` 不是 `disabled`。
- `TELEGRAM_SEND_MODE` 不是 `dry_run`。

## 8. Failure Handling

如果失败为 `agent_output_invalid`：

1. 不进入 staging。
2. 记录脱敏 evidence。
3. 回到 `message_intake_router` prompt/schema contract。
4. 补本地 deterministic tests。
5. 重新跑：

```powershell
pytest tests/unit/test_stage05_router_schema.py tests/integration/test_stage05_agent_workflow.py -q
python scripts\stage05_local_real_workflow.py
```

如果失败为 `llm_runtime_error`：

1. 检查 `.local/stage05-real-workflow.env` 是否填了 key。
2. 检查 `OPENROUTER_MODEL` 是否可用。
3. 检查网络和 OpenRouter 额度。
4. 不把 key 粘贴到聊天里。

## 9. Cleanup

本地验证后可以保留 `.local/stage05-real-workflow.env` 供后续重复测试，因为 `.local/` 已被忽略。

如果需要清空 secrets，直接在该文件里删除 value：

```text
OPENROUTER_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=
```

再次运行脚本时，缺少 `OPENROUTER_API_KEY` 会 fail closed。

## 10. Current Pass Evidence

Current pass evidence after the entity-key prompt contract fix:

```text
routed draft scenario:
ok=true
workflow_status=routed
model_provider=openrouter
model_name=openrouter/auto
prompt_version=stage05-router-v1
intent_types=recharge,customer_reply
requires_manual_review=false
overall_confidence=0.9550
service_drafts=recharge:pending_confirmation,customer_reply:pending_confirmation
provider_execution_allowed=false
send_request_created=false
reply_text_present=true

default risk scenario:
ok=true
workflow_status=manual_review
model_provider=openrouter
model_name=openrouter/auto
prompt_version=stage05-router-v1
intent_types=recharge,bm_invite,customer_reply,account_status_exception
requires_manual_review=true
service_drafts=none
provider_mode=disabled
telegram_send_mode=dry_run
```

Do not proceed to staging if this gate fails with `agent_output_invalid` or any safety preflight error.

## 11. Stage Gate

后续 Stage05 Task12 staging 重试顺序必须是：

1. 本地 deterministic tests pass。
2. 本地真实 workflow 脚本 pass。
3. 再推送 prompt/schema/workflow fix。
4. Tencent Cloud staging fetch/build/restart。
5. staging 真实 OpenRouter + allowlisted Telegram evidence。
6. staging business no-op evidence。
7. staging account exception evidence。
8. safety close。

没有本地真实 workflow evidence 时，不再直接进入 staging 实测。
