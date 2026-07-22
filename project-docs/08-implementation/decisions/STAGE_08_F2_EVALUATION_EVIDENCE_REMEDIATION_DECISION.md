# Stage08 F2 评测证据闭环修复决定

## Status

- Decision status: approved implementation remediation
- Date: 2026-07-22
- Trigger: Package F F2 independent review `HOLD`（0 Critical / 3 Important）
- Scope: 仅 Stage08 合成真实 Provider 评测器及其内部测试；不改变业务 API、数据库 schema、权限、默认 Provider、Telegram 或部署行为。

## 问题与决定

F2 的进程隔离、DTO 白名单和 fail-closed env 已成立，但独立审查发现其“通过”不能可靠证明真实模型评测的安全性和覆盖度。为使 F3 的外部调用证据可解释，实施以下不可降级的内部合同。

### 1. 出站 prompt 最小化必须成为 case gate

每个子进程在 F1 构造 HTTP 请求之后、发起 transport 调用之前，只在进程内检查最终出站 prompt：

- `hidden_field`、`group_freshness`、`rag_lifecycle` 必须分别确认对应的受限、过期/撤权、删除/漂移 marker 不存在；
- 普通 case 也必须确认全局隐藏 marker 不存在；
- 观察器不得打印、返回、写入 prompt 或业务正文，只可回传固定布尔值或固定 failure label；
- 检查失败即终止该 case，结果使用固定 `outbound_prompt_unsafe`，不得调用外部 Provider。

离线 fake 与真实 F1 adapter 均必须经过同一条 process-local guard。测试必须含“故意把受限材料注入 material，评测失败”的 mutation 证据。

### 2. Provider 指标必须表示真实调用事实

删除“已配置即 metadata present”的含义。每 case 的内部可观测事实至少区分：

- `provider_invoked`：实际进入 Provider 的 `analyse`；
- `provider_completed`：该调用返回一个 Provider outcome；
- `usage_metadata_present`：仅表示响应中是否存在 usage 元数据，绝不保存 usage 数值、token、cost、request ID 或模型正文。

父进程 DTO 只接收上述布尔值与允许的聚合计数。预期在 Provider 前终止的 case 必须报告 `provider_invoked=false`；F3 只有明确应调用真实 Provider 的 case 才纳入真实调用覆盖 gate。与实际 invocation 不一致的 `AgentRun.usage_summary.provider_calls` 必须在 evaluator 的进程内以受控事实修正或明确不参与 F 证据。

### 3. 12-case 语义必须与 F1 可表达合同一致

每个固定 case 需要显式 `provider_strategy`，只能为：

- `real_analysis`：通过 F1 真实 adapter 运行；
- `fault_timeout` / `fault_http_error` / `fault_shape_drift`：通过 process-local F1 transport 注入验证 unavailable，不接触外部网络；
- `coordinator_only`：只验证既有 E 行为，并明确 `provider_invoked=false`，不冒充真实 LLM coverage。

具体约束：

- `provider_unavailable` 使用 F1 transport fault；
- `policy_deny` 的 command 必须是受控写请求，真实 Provider 仅能输出 F1 可表达的 `deny`；
- `safe_replay` 是 coordinator-only 的既有 replay/draft 合同，不计入真实 Provider coverage；
- deterministic fake 只能生成 F1 同构的 `read_only`、`general_advice`、`deny`，且 `draft_intent=None`。

## F3 启动门槛

完成本决定对应实现后，必须由新的独立 reviewer 验证三项修复与 mutation 测试。仅当审查为 `PASS`（0 Critical / 0 Important）时，才可载入显式 `.local` env，执行至多 12 个合成真实 OpenRouter case。

## 不变项

- 每 case `spawn` 隔离、最多 2 路并发、硬超时只终止本 child；
- Telegram 始终 `dry_run`，通知/Provider-write/原始 prompt/response 留存保持禁用；
- 无 public API、schema、migration、permission 或默认依赖 wiring 变化；
- F3 evidence 仍仅保存 case ID、固定码、布尔值、聚合计数与延迟桶。
