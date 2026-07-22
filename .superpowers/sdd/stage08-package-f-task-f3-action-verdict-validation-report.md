# Stage08 Package F — F3 action verdict 父进程闭环修复报告

## Status

- Status: implementation complete; pending fresh independent review
- Scope: F2 evaluator-only action verdict validation
- Date: 2026-07-22
- External execution: none

## Changed files

- `backend/scripts/stage08_real_provider_evaluation.py`
- `backend/tests/unit/test_stage08_real_provider_evaluation.py`
- `.superpowers/sdd/stage08-package-f-task-f3-action-verdict-validation-report.md`

## What changed

1. 新增 12 个固定 case 的静态 `case_id -> allowed passed analysis_action` 映射：
   - 事实读取类只允许 `read_only`；
   - `general_advice` 只允许 `general_advice | deny`；
   - `policy_deny`、`draft_pressure` 只允许 `deny`；
   - Provider 故障、预终态和 coordinator-only case 只允许 `none`。
2. `RedactedCaseResult` 的 strict model validator 现在会拒绝 `evaluation_passed=true` 且 case/action 语义不匹配的结果，不再只校验 action 是否属于合法枚举。
3. `_execute_synthetic_case()` 在严格结果创建前重新检查动作语义。错误动作会追加固定 `provider_invocation_invalid`，并把跨边界 action 安全投影为 `none`，因此不能生成假通过 verdict。
4. `_validated_child_payload()` 在父进程消费 child payload 时独立重验映射。即使 child 伪造了合法 enum（例如 `general_advice/read_only`），父进程也会把它转换为固定失败结果：
   - `evaluation_passed=false`
   - `failure_labels=(provider_invocation_invalid,)`
   - `analysis_action=none`
5. 新增直接 DTO、父进程、批次统计和完整 12-case strategy 回归，覆盖：
   - 伪造 `general_advice/read_only` 被拒绝/降为固定失败；
   - `general_advice/deny` 仍被接受；
   - 12 个固定 case 的 deterministic offline action 全部保持预期。

## Verification

在 `backend/` 目录执行，均为离线模式：

1. 新增与相关动作回归：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py -k "wrong_case_action or all_fixed_case_strategies"
   14 passed, 31 deselected
   ```

2. F2 + F1 聚焦组合：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py tests/unit/test_stage08_openrouter_analysis_provider.py
   69 passed
   ```

3. 完整 12-case isolated spawn 矩阵：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py::test_complete_twelve_case_offline_matrix_runs_through_isolated_children
   1 passed
   ```

4. 编译检查：

   ```text
   python -m compileall -q scripts/stage08_real_provider_evaluation.py tests/unit/test_stage08_real_provider_evaluation.py
   exit 0
   ```

5. 两个变更源文件分别执行 `git diff --no-index --check`，无 whitespace error；仅有工作区既有的 LF/CRLF 提示。

## Boundaries observed

- 未读取或设置 `.local` / 真实 Provider env 文件。
- 未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。
- 未修改 F1 adapter 行为、公开 API/schema/权限、migration。
- 未修改历史 F3/R2 evidence，也未生成新的真实 evidence。
- `analysis_action` 仍是原固定脱敏枚举，没有新增 prompt、answer、token、request ID 或其他 raw carrier。

## Skipped tests

- 未运行真实 Provider R3；按 brief，必须先完成 fresh independent review。
- 未运行全仓测试；本修复限定在 F2 evaluator action verdict，已运行 F2 全文件、F1 adapter 全文件及完整离线 spawn 矩阵。

## Remaining risks

- fresh independent review 尚未完成；review 达到 `PASS / 0 Critical / 0 Important` 前，R3 仍应保持禁止。

## Temporary cleanup

- 未创建临时脚本、真实输出、测试数据或外部 artifact；无额外清理项。
