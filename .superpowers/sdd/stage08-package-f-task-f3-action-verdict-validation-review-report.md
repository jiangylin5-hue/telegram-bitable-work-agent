# Stage08 Package F — F3 action verdict 父进程闭环独立复审报告

## Status

- Status: PASS
- Review result: 0 Critical / 0 Important / 0 Minor
- Scope: F3 action verdict parent-validation remediation
- Date: 2026-07-22
- External execution: none

## Findings

### Critical

无。

### Important

无。

### Minor

无。

## Blocking checks

1. 12 个固定 `case_id` 均在 `_ALLOWED_PASSED_ANALYSIS_ACTIONS` 中有且仅有明确的通过动作集合：普通事实读取为 `read_only`；`general_advice` 为 `general_advice | deny`；策略拒绝和 draft 压力为 `deny`；撤权、Provider 故障、预算取消和安全重放等前置终态为 `none`。离线固定策略逐 case 回归全部通过，没有发现合法动作被误判。
2. `RedactedCaseResult` 的 strict `model_validator` 会拒绝 `general_advice/read_only/evaluation_passed=true`；父进程 `_validated_child_payload()` 在模型重建前后均执行 case/action 校验，并把该类伪造 payload 投影为固定的 `provider_invocation_invalid` 失败结果。该结果进入 `_batch_result()` 后 `passed_count=0`、`failed_count=1`、`all_cases_passed=false`。
3. `general_advice/deny` 保持可接受；故障、前置终态和 coordinator-only case 的 `none`，以及普通读取/策略拒绝动作均保持可接受。完整 deterministic 12-case isolated spawn 矩阵仍为通过状态。
4. `RedactedCaseResult` 的父进程边界字段集合未扩展，`analysis_action` 仍为固定脱敏枚举；没有 prompt、answer、token、request ID、exception 或任意 raw carrier。F1 prompt guard、telemetry、deadline/timeout、进程隔离和 forced dry-run 回归全部通过；被审修复未新增外部写入或历史 evidence 改写路径。

## Verification

在 `backend/` 下仅执行离线测试：

```text
python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py -k "redacted_dto_rejects_valid_enum_with_wrong_case_action_pairing or parent_converts_wrong_case_action_pairing_to_fixed_failed_verdict or all_fixed_case_strategies_emit_allowed_passed_action or general_advice_f1_mock_enforces_action_and_citation_contract or case_strategy_reports_actual_provider_invocation"
24 passed, 21 deselected
```

```text
python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py tests/unit/test_stage08_openrouter_analysis_provider.py
69 passed
```

## Boundaries observed

- 未读取或设置真实 Provider env / `.local` 文件。
- 未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。
- 未修改源码、测试或历史 evidence；本复审仅新增本报告。

## Verdict

PASS。F3 action verdict 的 strict DTO、父进程重校验与批次失败统计闭环成立；按 brief，可进入且仅进入一次带版本标识的 R3 真实 Provider synthetic batch。
