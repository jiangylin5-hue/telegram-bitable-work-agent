# Stage08 Package F — F3 通用建议空引用合同修复报告

## Status

- Task: F3 general-advice citation remediation
- Result: implementation complete; offline verification passed
- Scope: F1 evaluator adapter、F2 synthetic evaluator tests only
- External calls: none

## Changed files

- `backend/app/services/stage08_openrouter_analysis_provider.py`
  - system prompt 明确要求 `general_advice` 与 `deny` 返回空 `citation_ordinals`。
  - user payload 增加稳定的 `citation_policy`，使空引用规则在模型输入中显式可见。
  - `_build_prompt` 返回同一次 sealed command snapshot 的 intent；严格 JSON parse 后，若 `general_advice` command 或 `deny` action 带非空 citations，则固定 fail closed 为 `unavailable/invalid_input`。
  - 既有普通事实 citation 范围校验、Provider telemetry、timeout、redaction 与默认 wiring 均未改变。
- `backend/scripts/stage08_real_provider_evaluation.py`
  - 仅适配 `_build_prompt` 的内部返回值；deterministic fake 行为未放宽。
- `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
  - 新增模型可见合同、通用建议空引用成功、非空引用拒绝、`deny` 空/非空引用合同测试。
- `backend/tests/unit/test_stage08_real_provider_evaluation.py`
  - 新增 F2 离线 F1 adapter 注入测试：空引用完成；非空引用安全降级；telemetry、redaction、无外部副作用保持。

## TDD evidence

RED 阶段先执行新增测试，得到预期失败：

- F1: `3 failed, 1 passed`，失败原因分别为模型输入缺少显式 `[]` 规则、`general_advice` 非空 citations 被错误接受、`deny` 非空 citations 被错误接受。
- F2: `1 failed, 1 passed`，非空 citations 的真实 adapter mock 路径错误返回 `completed`，而不是安全 `degraded`。

完成最小实现后同一聚焦测试转绿：

- F1 general-advice/deny focused: `4 passed`
- F2 F1-mock general-advice focused: `2 passed`

## Offline verification

- F1/F2 离线测试（排除两个会读取或设置 `STAGE08_F_ENV_FILE` 的既有 env 专项测试）：`46 passed, 2 deselected`
- 独立 12-case offline spawned matrix：`1 passed`，内部断言 `12/12` 全部通过。
- `python -m compileall`：通过。
- untracked-file whitespace/diff check：通过；仅出现仓库既有 LF/CRLF 提示。

## Boundaries and unchanged items

- 未读取或设置 `STAGE08_F_ENV_FILE`，未读取 `.local`。
- 未调用 OpenRouter、Telegram、webhook 或部署。
- 未修改 public API、schema、migration、permission、default Provider wiring。
- 未修改、覆盖或删除既有 `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md`（原 11/12 evidence 保持不变）。
- 未新增任何 prompt、answer、ordinal、token、request ID 或异常正文持久化。

## Remaining gate

F3 R2 仍未执行。下一步必须先完成本修复的独立离线 review，并达到 `PASS / 0 Critical / 0 Important`；之后才可按原门槛创建新的版本化 R2 synthetic-only evidence。旧 F3 evidence 不得改写。
