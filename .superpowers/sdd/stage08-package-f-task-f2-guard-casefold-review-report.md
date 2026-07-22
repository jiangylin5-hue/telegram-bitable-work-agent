# Stage08 Package F — F2 guard casefold 独立审查报告

## Status

- Result: `PASS`
- Critical: `0`
- Important: `0`
- Minor: `0`
- External calls: `NONE`
- Environment boundary: 未读取、未设置 `STAGE08_F_ENV_FILE`，未读取 `.local`

## 审查结论

1. `_OutboundPromptGuard` 在任何 F1 transport 之前先对最终 outbound prompt 执行 `casefold()`，并对 `_HIDDEN_MARKERS` 中每个真实 fixture marker 同样执行 `casefold()` 后比较。大小写差异无法再绕过 evaluator-local guard。
2. `_HIDDEN_MARKERS` 直接由四个 fixture 真值常量组成：`_PRIVATE_HIDDEN_CONTENT`、`_EXPIRED_GROUP_CONTENT`、`_REVOKED_GROUP_CONTENT`、`_DELETED_RAG_CONTENT`。构建 hidden field、过期群聊、撤权群聊和 deleted RAG fixture 时使用的也是这些同一常量，不存在测试副本漂移。
3. 参数化 mutation 测试逐一把这四个真值写入新的可见 `title` 字段；deterministic fake 和 F1 adapter 两条路径都固定返回首个 failure label `outbound_prompt_unsafe`。F1 使用 `httpx.MockTransport` 记录 transport 是否进入，四次 mutation 均证明 transport 未被调用。
4. 两条 mutation 路径都保留真实 provider telemetry 语义：guard 前记录 `invoked`，guard 固定拒绝后记录 `completed`；结果仅携带严格枚举和布尔事实。`RedactedCaseResult` 不包含 prompt/answer/raw marker 字段，父进程继续以 exact-field DTO 和 case identity 重新校验。
5. provider strategy、最多 2 并发、每 case 独立 spawn、单 child hard timeout、E5 remaining deadline、fail-closed provider 选择和 Telegram `dry_run` 强制逻辑未被本修复改写。定向回归覆盖上述受影响契约并通过。

## Verification

```text
python -m pytest \
  tests/unit/test_stage08_real_provider_evaluation.py::<guard/DTO/spawn/timeout/strategy/dry-run focused nodes> \
  tests/unit/test_stage08_openrouter_analysis_provider.py -q

39 passed in 21.15s
```

本次按审查规则有意不运行会读取或设置 `STAGE08_F_ENV_FILE` 的两个 env 专项测试；fail-closed 分支通过源码核查，且未触发 real provider 构造或任何网络路径。

## Gate

F2 guard/casefold 修复满足 brief，无 Critical/Important 阻断项。允许进入已授权的、仅使用合成数据且 Telegram 保持 dry-run 的 F3 有界真实 Provider 任务。
