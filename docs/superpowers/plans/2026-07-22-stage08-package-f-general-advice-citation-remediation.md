# Stage08 Package F 通用建议空引用修复计划

## 目标

修复真实 Provider 在 general advice 场景返回 citation ordinal 的行为，使模型提示与 adapter 严格合同一致；不掩盖既有 F3 失败，也不扩展业务能力。

## 文件与步骤

1. `backend/app/services/stage08_openrouter_analysis_provider.py`
   - 将 general-advice 空引用规则加入可见给模型的 JSON 合同。
   - 在 parse 后基于 sealed command snapshot 做本地 fail-closed validation。
2. `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
   - general advice 空引用成功、非空引用拒绝、deny 无引用的 adapter 测试。
3. `backend/scripts/stage08_real_provider_evaluation.py`
   - 仅在需要时调整 case 合同，使 F1 rejected output 安全映射为固定评测结果；不得放宽 `citation_current`。
4. `backend/tests/unit/test_stage08_real_provider_evaluation.py`
   - 覆盖 general-advice fake/F1 mock 的空引用正反用例，保留现有 spawn/telemetry/redaction 测试。

## 非目标

- 不修改 F3 既有 evidence。
- 不改变默认 API Provider、业务写入、表格/权限 schema、Telegram 行为或 deployment。
- 不在修复任务中读取 env、调用 OpenRouter 或重试真实评测。

## 退出条件

F1/F2 聚焦离线测试、12-case offline spawn、compile/diff 均通过；新的 reviewer 确认空引用规则既明确给模型又由 adapter 强制。随后才可新建 F3 R2 单批真实 synthetic evidence。
