# Stage08 Package F — F3 action verdict parent-validation independent review brief

## Scope

Review only the action verdict parent-validation remediation and its report.

## Blocking checks

1. Static allowed-action mapping is complete for all 12 case IDs and produces
   no legitimate false failure.
2. Strict result creation and parent child-payload revalidation both reject a
   forged `general_advice/read_only/evaluation_passed=true`; batch cannot count
   it as passing.
3. Valid general-advice deny, fault/pre-terminal/coordinator-only `none`, and
   ordinary fact/deny actions remain correctly accepted.
4. No raw content/action expansion crosses DTO; F1, isolation, guards,
   telemetry, timeout/dry-run and historical evidence are unchanged.

## Rules

- Offline only; do not read/set env/.local, call external systems or modify
  source/evidence.

## Output

Write `.superpowers/sdd/stage08-package-f-task-f3-action-verdict-validation-review-report.md`
with C/I/M and PASS/HOLD. A clean review permits exactly one versioned R3 real
Provider synthetic batch.
