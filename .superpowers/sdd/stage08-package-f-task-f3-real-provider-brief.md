# Stage08 Package F — F3 real Provider synthetic evaluation task brief

## Start gate

Do not start unless the fresh F2 remediation review report says `PASS` with
`0 Critical / 0 Important`. This task has explicit user authorization for a
bounded real OpenRouter call, but it remains limited to synthetic fixtures.

## Scope

1. Re-run the focused offline F1/F2 test modules once.
2. Use only the ignored local evaluator env file:
   `D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env`.
   Do not print, copy, edit or persist its values. It is supplied to the child
   solely through `STAGE08_F_ENV_FILE` for the one command.
3. Run `backend/scripts/stage08_real_provider_evaluation.py` from the worktree.
   It may call OpenRouter for no more than the fixed 12 synthetic cases, with
   max two child processes. The runner itself must force Telegram dry-run,
   notifications/Provider-write off and no full prompt/response retention.
4. Preserve only its strict redacted JSON (case ID, fixed code, booleans,
   counts, terminal/latency bucket) long enough to create:
   `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md`.
   The evidence must be Chinese and never include prompt, answer, synthetic
   business body, identifier, token/cost value, request ID, exception text,
   model credentials or raw provider response.

## Required evidence

- command boundary and timestamp without secrets;
- 12-case aggregate: pass/failed/timed out, terminal/latency counts,
  Provider invoked/completed/usage-presence counts;
- per-case only allowed ID, strategy, terminal, gate booleans and fixed
  failure labels;
- explicit confirmation that Telegram send is dry-run, no draft confirmation,
  no webhook/deployment/Provider-write happened;
- if any gate fails, record the failure as evidence; do not modify prompts,
  routing, expectations or source code to turn it green.

## Stop conditions

- Missing/invalid env, timeout, Provider error, redaction violation or a
  failed case is a valid F3 result: safely stop and write only redacted
  evidence.
- Never retry beyond the single bounded batch and never contact Telegram.

## Post-run

Write `.superpowers/sdd/stage08-package-f-task-f3-report.md` with exact
offline and bounded-real commands, redacted aggregate, skipped actions and
remaining risks. Then request independent F3/Package-F review; do not claim
production readiness or deployment.
