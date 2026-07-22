# Stage08 Package F — F2 evidence remediation implementation report

## Status

- Result: `READY_FOR_INDEPENDENT_REVIEW`
- Scope: 仅修复 F2 独立审查的 I-01、I-02、I-03；未扩大到业务 API、schema、migration、permission、默认 Provider wiring 或部署。
- Self review: `0 Critical / 0 Important / 0 Minor`
- External systems: 未读取或设置 `STAGE08_F_ENV_FILE`，未读取 `.local` 值，未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。

## Changed files

1. `backend/app/services/stage08_openrouter_analysis_provider.py`
   - 增加默认关闭、仅由 evaluator 注入的 `outbound_prompt_guard` 与固定事件 `event_observer`。
   - F1 在最终 request body 已构造、transport 调用前执行 prompt guard；guard 拒绝时返回固定 `invalid_input`，不触发 transport。
   - 只发出 `invoked`、`completed`、`usage_metadata_present` 三种固定事件，不把 prompt、response、usage 数值、token、cost 或 request ID 交给 telemetry。
2. `backend/scripts/stage08_real_provider_evaluation.py`
   - 固化 12-case `provider_strategy`：`real_analysis`、`fault_http_error`、`coordinator_only`。
   - `provider_unavailable` 改为真实 F1 adapter + process-local `httpx.MockTransport` 503 fault；无网络。
   - `policy_deny` 改为受控 `draft_update` 请求，F1-compatible `deny` 输出；`safe_replay` 明确为 coordinator-only E replay fixture，不计入 F1 Provider coverage。
   - deterministic fake 仅输出 `read_only` / `general_advice` / `deny`，始终 `draft_intent=None`，并与真实 F1 adapter 复用同一 prompt builder 与 child-local guard。
   - 父子 DTO 改为实际事实：`provider_invoked`、`provider_completed`、`usage_metadata_present`；aggregate 同步统计 invocation/completion case count，配置存在不再计作调用。
   - 增加固定失败码 `outbound_prompt_unsafe` 与 `provider_invocation_invalid`；预 Provider 终止 case 和 coordinator-only case 显式保持 invocation=false。
3. `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
   - 增加 outbound marker mutation 在 transport 前被阻断的测试。
   - 增加 invocation/completion/usage presence 仅固定事件的测试。
4. `backend/tests/unit/test_stage08_real_provider_evaluation.py`
   - 更新严格 DTO whitelist。
   - 增加 12-case strategy、实际 Provider invocation、受限 material mutation、完整离线 spawn aggregate 覆盖。

## I-01 / I-02 / I-03 closure

- I-01: 已关闭。受限 marker 被注入实际 synthetic record 后进入最终 F1 prompt，child-local guard 返回 false，结果固定包含 `outbound_prompt_unsafe`；F1 transport mutation test 证明 transport 未被调用。
- I-02: 已关闭。配置状态不再进入证据 DTO；`revoked_scope`、`budget_cancel`、`safe_replay` 均报告 `provider_invoked=false`，其余明确 Provider case 依据真实 `analyse` 进入/返回事实报告 invoked/completed。
- I-03: 已关闭。`provider_unavailable` 使用 F1 transport fault，`policy_deny` 使用真实受控写请求 + F1-compatible deny，`safe_replay` 独立标记 coordinator-only；deterministic fake 不再伪造 `draft_update` 或 draft intent。

## Verification

1. RED evidence（实现前）：

   ```text
   python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py
   30 failed, 9 passed
   ```

   失败原因与三个缺口一致：F1 无 guard/telemetry seam、DTO 仍以 configured 代替 invocation、mutation 未被拦截、case strategy 不存在。

2. F1 + F2 focused（包含完整 12-case fresh spawn matrix）：

   ```text
   python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py
   39 passed in 21.53s
   ```

3. F1 + F2 + Stage06 isolation evaluator 定向回归：

   ```text
   python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py tests/unit/test_stage06_live_llm_skill_quality_eval.py
   72 passed in 20.04s
   ```

4. 编译与 diff：

   ```text
   python -m compileall -q app/services/stage08_openrouter_analysis_provider.py scripts/stage08_real_provider_evaluation.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py
   exit 0

   git diff --check
   exit 0
   ```

## Skipped / remaining gate

- 按 remediation brief 未运行真实 OpenRouter、Telegram、webhook、部署或任何外部写入。
- 未运行 full backend/repository/UI suite；本次仅执行聚焦离线回归。
- F3 仍由新的独立 reviewer gate 阻断；只有复审达到 `PASS` 且 `0 Critical / 0 Important` 后才可读取显式评测 env 并启动真实 Provider case。
