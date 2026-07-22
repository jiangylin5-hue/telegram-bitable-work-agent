# Stage08 Package F — F2 evidence remediation 独立复审报告

## Status

- Result：`HOLD`
- Findings：`0 Critical / 1 Important / 0 Minor`
- Gate：该 `Important` 表明 outbound prompt guard 仍可对 fixture 中的真实禁用材料产生安全假阳性，因此继续阻断 F3。
- Review mode：只读、严格离线；未读取或设置真实评测 env，未读取 `.local`，未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。

## Findings

### Important I-01：outbound prompt guard 大小写敏感，现有 mutation test 没有覆盖 fixture 的真实禁用值

`_OutboundPromptGuard.__call__()` 当前直接执行大小写敏感的子串比较（`backend/scripts/stage08_real_provider_evaluation.py:351-353`）。`_HIDDEN_MARKERS` 使用小写规范值（`153-158`），但 fixture 内隐藏字段、过期/撤销群投影和已删除 RAG 投影使用大写值（`804`、`857`、`865`、`891`）。因此，只要这些真实 fixture 值因投影回归进入最终 prompt，guard 仍会返回安全。

现有 mutation test 把 `_HIDDEN_MARKERS[0]` 本身写入可见字段（`backend/tests/unit/test_stage08_real_provider_evaluation.py:406-428`），注入的是与 guard 完全同形的小写值，所以只能证明小写测试样本会被挡住，不能证明 fixture 中实际受限材料会被挡住。F1 的 transport-before-guard 测试也使用同一个小写样本（`backend/tests/unit/test_stage08_openrouter_analysis_provider.py:102-136`）。

本次纯离线、无网络的 process-local probe 复用 fixture 自己的隐藏字段值，将其放入可见标题后运行 deterministic fake 主链，得到固定结果：

```text
passed=True
failure_labels=()
prompt_gate=True
```

这证明原 I-01 尚未真正关闭：如果权限/生命周期投影发生大小写保持的回归，F1 transport 前的 guard 不会失败，case 还会以 `outbound_prompt_safe` 通过。真实 Provider 可能收到受限合成内容，而父进程 DTO 无法识别。

**Required remediation：** guard 必须先对 prompt 和固定 marker 做同一确定性规范化（至少 `casefold()`；若支持非 ASCII marker，再补统一 Unicode normalization）后比较。mutation tests 必须直接复用 fixture 中四类实际受限值，或至少覆盖大小写变体，并分别证明 deterministic fake 与 F1 adapter 均在 transport 前返回固定 `outbound_prompt_unsafe`/`invalid_input`，且 transport 未被调用。修复后需再次独立复审。

## Blocking checks

1. **Prompt guard / mutation：HOLD。** F1 guard 的位置确实在最终 request body 构造后、transport 前；observer/DTO/异常只暴露固定事件或固定 code，fake 与 F1 也共用同一 builder/guard 设计。但大小写漏洞使真实 fixture 禁用材料不能可靠触发 gate，见 I-01。
2. **Provider facts：PASS。** `provider_invoked` 只在进入 `analyse()` 时设置，`provider_completed` 只在返回 Provider outcome 时设置；`usage_metadata_present` 只记录响应中 usage 的存在性。`revoked_scope`、`budget_cancel` 和 `safe_replay` 均不冒充 Provider invocation；coordinator-only replay 不进入真实 Provider coverage。evaluator DTO 不采纳 `AgentRun.usage_summary`，不存在配置状态冒充调用的旧路径。
3. **12-case strategy：PASS。** `provider_unavailable` 使用 process-local F1 503 fault；`policy_deny` 使用受控写意图并要求 F1-compatible `deny`；`safe_replay` 为 coordinator-only；deterministic fake 只返回 `read_only` / `general_advice` / `deny` 且 `draft_intent=None`。
4. **Observer seam / default wiring：PASS。** 新 seam 默认均为 `None`；全 backend 引用仅存在于 F evaluator、F1/F2 测试和 adapter 自身。正常 `Stage08CollaborationDependencies` 仍使用 `UnavailableAnalysisProvider`，未发现 public API、持久化、权限、migration 或默认依赖 wiring 变化。
5. **Isolation / timeout / DTO / safety env：PASS。** 每 case 仍使用 fresh `spawn` child；并发上限为 2；硬超时只清理当前 child；父进程按精确字段集合、strict Pydantic 和 case identity 重验 DTO；fake/fault/coordinator 分支不会读取真实 Provider config；Telegram 与外部写模式仍强制关闭。

## Fresh verification

只运行了不读取或设置真实评测 env 的离线聚焦测试：

```text
37 passed in 20.21s
```

覆盖 F1 mock transport、guard/telemetry、严格输出、F2 manifest/DTO、spawn、并发/timeout、完整 12-case deterministic matrix、case strategy 和现有 mutation test。额外 process-local probe 复现 I-01，未打印 prompt 或禁用材料正文。

## Skipped / Remaining

- 未运行会加载真实评测配置的路径；未读取 `.local` 或密钥。
- 未调用真实 OpenRouter，未发送 Telegram，未更新 webhook，未部署。
- 未运行 full backend/repository/UI suite；当前阻断项由源码和最小离线复现直接证明。
- 未修改任何业务实现或测试；本轮仅新增该独立复审报告。

## Final verdict

I-02 与 I-03 已关闭，spawn/DTO/env 等原有隔离边界也保持成立；但 I-01 的修复只覆盖了小写测试样本，未覆盖 fixture 中实际使用的大写禁用值。结论为 `HOLD`。完成大小写/规范化修复并补齐真实 fixture mutation 证据前，不应启动 F3 外部调用。
