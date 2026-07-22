# Stage08 Package F — F3 通用建议动作合约修复报告

## Status

- Task: F3 general-advice action remediation
- Result: implementation complete; focused offline verification passed
- Scope: F1 evaluator adapter、F2 synthetic evaluator、严格脱敏 DTO 与测试
- External calls: none

## Changed files

- `backend/app/services/stage08_openrouter_analysis_provider.py`
  - 使用 `_build_prompt` 返回的同一份 sealed command snapshot intent，同时校验 action 与 citation。
  - `intent=general_advice` 只接受 `general_advice` 或 `deny`，且引用必须为空；`read_only` 与任意非空引用固定 fail closed 为 `unavailable/invalid_input`。
  - 增加 evaluator-only `action_observer`，只在严格 payload 和 `AnalysisDecision` 均验证成功后投影固定安全动作；异常输出不会产生动作证据。
- `backend/scripts/stage08_real_provider_evaluation.py`
  - `RedactedCaseResult` 新增严格枚举 `analysis_action = none | read_only | general_advice | deny`，父进程仍按 exact field set 与 Pydantic strict schema 重新验证。
  - Provider 未调用、fault/unavailable 或没有安全决策时保持 `none`；真实 F1 adapter 与 deterministic fake 共用同一 telemetry 投影。
  - general-advice terminal contract 允许现有 `completed` 及受控 `denied`；未改动核心 Coordinator 行为。
  - `_redacted_failure` 固定输出 `analysis_action=none`。
- `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
  - 覆盖 `general_advice/deny/read_only` 与空引用动作组合，验证非法 `read_only` fail closed。
- `backend/tests/unit/test_stage08_real_provider_evaluation.py`
  - 覆盖严格 DTO enum/extra rejection、实际 F1 adapter 的五组 action/citation 组合、deny terminal contract、spawn DTO 投影，以及 invoked-fault/not-invoked 的 `none` 语义。

## TDD evidence

- RED：先加入动作合约与 DTO 测试，得到 `10 failed, 44 passed`；关键失败为 `general_advice + read_only` 被错误接受，以及 `analysis_action` 字段不存在。
- GREEN：完成最小实现后，F1/F2 两个聚焦文件 `55 passed`。

## Offline verification

- F1/F2 + collaboration contracts/service/graph（显式排除两项 env selector 专项）：`138 passed, 2 deselected`。
- 独立 12-case spawned deterministic matrix：`1 passed`，测试内部断言 12/12 全通过。
- `python -m compileall`：通过。
- `git diff --check` 与 trailing-whitespace scan：通过。

## Boundaries and skipped calls

- 未读取真实 `.local` 或任何真实凭据；正式验证命令排除了会操作 `STAGE08_F_ENV_FILE` 的两项 env selector 单测。
- 未调用 OpenRouter、Telegram、webhook、部署、确认或任何外部写入。
- 未修改 public API、schema、migration、permission、default Provider wiring 或核心 Coordinator。
- 未修改、覆盖或删除任何历史 F3/R2 evidence。

## Remaining gate

本修复已准备进入 R3 独立离线 review。只有 review 达到 `PASS / 0 Critical / 0 Important` 后，才可按决定文档运行新的、单独命名且不覆盖历史证据的 bounded real Provider R3 batch。
