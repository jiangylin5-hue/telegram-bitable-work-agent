# Stage08 Package F — F2 evidence remediation independent review brief

## Scope

Independently review the remediation for the prior F2 `HOLD`, limited to:

- `backend/app/services/stage08_openrouter_analysis_provider.py`
- `backend/scripts/stage08_real_provider_evaluation.py`
- their two F1/F2 unit-test modules
- `.superpowers/sdd/stage08-package-f-task-f2-remediation-report.md`

Read the governing decision and plan first. This review is strictly offline.

## Blocking checks

1. Does the final F1 outbound prompt pass a process-local guard before any transport, with no prompt text/marker leaking to DTO, event, exception, file or stdout? Does a mutation with forbidden material reliably fail before transport for both fake and F1 paths?
2. Are `provider_invoked`, `provider_completed`, and `usage_metadata_present` actual facts rather than configuration? Can any Provider-preterminal/coordinator-only path falsely count as real coverage or leave conflicting evaluator `AgentRun` counts?
3. Are all twelve fixed strategies internally consistent with F1: unavailable is an offline F1 transport fault, policy deny uses controlled-write intent + deny, replay is coordinator-only, and fake cannot create draft intent?
4. Does the new optional observer seam remain evaluator-only by default and avoid changing normal/default API wiring, persistence, logging, public contracts, permissions or migrations?
5. Did spawn isolation, <=2 concurrency, per-child timeout, strict parent DTO validation, env fail-closed and Telegram dry-run remain intact?

## Rules

- Do not read or set `STAGE08_F_ENV_FILE`, `.local`, provider credentials, or run any external call.
- Run only focused offline tests needed for findings. Do not modify implementation.

## Output

Write `.superpowers/sdd/stage08-package-f-task-f2-remediation-review-report.md` with C/I/M findings and `PASS`/`HOLD`. Any Critical/Important blocks F3. A clean review permits the separately authorized synthetic OpenRouter evaluation only.
