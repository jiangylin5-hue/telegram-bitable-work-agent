# Stage08 Package F — F3 general-advice action remediation brief

## Scope

Implement `STAGE_08_F3_GENERAL_ADVICE_ACTION_CONTRACT_DECISION.md` and its plan. This is evaluator-only and strictly offline.

## Requirements

- Enforce general-advice output action `{general_advice, deny}` plus empty citations from the same sealed command snapshot; reject `read_only` or any nonempty citation fail closed.
- Permit the approved deny terminal in F2 general-advice expectations.
- Add only the fixed non-sensitive `analysis_action` enum projection to strict child/parent result DTO/evidence path. It must accurately be `none` when no safe Provider decision exists.
- Cover all action/citation combinations through actual F1 adapter and F2 seams; retain outbound guard, invocation telemetry, isolation, timeout and safety tests.

## Boundaries

- Never read/set `STAGE08_F_ENV_FILE`/`.local`; no OpenRouter, Telegram, webhook, deployment, confirmation or write.
- No public API/schema/migration/permission/default-wiring change.
- Do not change F3/R2 historical evidence.

## Validation

Run focused offline suites, 12-case spawn, compile/diff. Report at `.superpowers/sdd/stage08-package-f-task-f3-general-advice-action-remediation-report.md` with changed files, results, skipped calls and R3 review gate.
