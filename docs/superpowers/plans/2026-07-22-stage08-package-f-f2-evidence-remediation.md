# Stage08 Package F F2 评测证据闭环修复计划

> 执行前提：F2 独立审查为 `HOLD`，3 项 Important 均已在
> `project-docs/08-implementation/decisions/STAGE_08_F2_EVALUATION_EVIDENCE_REMEDIATION_DECISION.md`
> 固化。本计划只修复 evaluator 内部合同，绝不运行真实 OpenRouter。

## 目标

让 F3 的真实 Provider 结果能够被解释为：哪些 case 真正调用过 Provider、最终 outbound prompt 未含任何受限合成标记、哪些 case 是 transport-fault/coordinator-only 而非真实 LLM coverage。

## 修改范围

1. `backend/app/services/stage08_openrouter_analysis_provider.py`
   - 仅增加 evaluator 可选的 process-local telemetry/observer seam。
   - observer 只接收最终 prompt 并只产生布尔/固定码，不记录、打印、持久化或跨进程回传正文。
   - telemetry 只记录 invoked/completed/usage-presence 布尔事实；正常业务默认不启用。

2. `backend/scripts/stage08_real_provider_evaluation.py`
   - 固化 12 个 case 的 `provider_strategy`。
   - 加 child-local outbound guard、严格 redacted DTO 字段和 aggregate。
   - `provider_unavailable` 以 F1 transport fault 运行；`safe_replay` 为 coordinator-only；`policy_deny` 使用受控写请求并验收 F1 可表达 deny。
   - fake provider 与 F1 action/draft 合同同构；不再返回 `draft_update` 或 draft intent。
   - 把真实 Provider 覆盖 gate 限定到 `real_analysis` case，且修正 evaluator 内部 usage 调用事实。

3. `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
   - 测 observer/telemetry 无正文留存、transport-fault、usage presence 布尔边界。

4. `backend/tests/unit/test_stage08_real_provider_evaluation.py`
   - 测受限 marker mutation 会在 child 内失败且不尝试 transport；
   - 测 invoked/completed 不把 configured 当作调用；
   - 测 12-case strategy 与 F1 合同相容，coordinator-only 不算真实 coverage；
   - 保留并复跑 spawn/并发/timeout/DTO/env fail-closed 测试。

## 不可变约束

- 不读、不设 `STAGE08_F_ENV_FILE`；不调用 OpenRouter/Telegram/webhook/deployment。
- 不改 public API、schema、migration、permission 或默认 `UnavailableAnalysisProvider`。
- 不保留 prompt/response/UUID/token/cost/request ID；无输出 artifact。
- F2 remediation 独立审查通过前，禁止启动 F3。

## 验证

1. F1 与 F2 focused tests。
2. 12-case offline spawn matrix。
3. F1 + F2 + Stage06 isolation evaluator 定向回归。
4. `compileall` 与 `git diff --check`。
5. 单独审查三个之前的 Important 发现；任何 Critical/Important 继续阻断 F3。
