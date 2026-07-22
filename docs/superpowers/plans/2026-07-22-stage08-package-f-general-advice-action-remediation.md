# Stage08 Package F 通用建议动作合同修复计划

## Goal

补全 general-advice 的 action/citation 合同，并在不泄露内容的前提下，让版本化真实评测能证明实际安全动作。此任务不改写 F3/R2 证据，不扩展业务能力。

## Steps

1. F1 adapter
   - 从同一 sealed command snapshot 判断 `general_advice` intent。
   - 只允许 `general_advice` 或 `deny` 且空引用；其它 action 或非空引用 fail closed。
2. F2 evaluator
   - 将 `analysis_action` 加入严格内部 redacted DTO，限定为 `none/read_only/general_advice/deny`。
   - Provider pre-terminal/fault/coordinator-only 为 `none`；不得把 raw answer 或任意动作名称跨进程。
   - general-advice case 将 `deny` 作为已批准安全终态，拒绝 `read_only`。
3. Tests
   - F1 mock transport 逐项覆盖 valid general_advice、valid deny、invalid read_only、invalid citations。
   - F2 fake/real seam/strict parent DTO/terminal expectation/redacted action coverage，保留完整 offline spawn matrix。
4. Evidence
   - 新 F3 R3 evidence 的每 case 仅记录 allowed action enum；F3/R2 历史文件不动。

## Non-goals

- No public API/schema/migration/permission/default Provider change.
- No env reading, real Provider, Telegram, webhook or deployment in implementation/review tasks.
- No retry or alteration of historic evaluation results.

## Exit gate

Focused offline F1/F2 and 12-case spawn pass; fresh review verifies action enforcement and enum redaction. Only then can the user-authorized R3 bounded real OpenRouter batch run.
