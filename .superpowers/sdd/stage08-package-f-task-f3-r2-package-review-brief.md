# Stage08 Package F — F3 R2 and package closure independent review brief

## Scope

Independently review the completed Package F chain:

- F1 adapter and tests;
- F2 isolation/telemetry/strategy and final remediation reviews;
- immutable original F3 `11/12 HOLD` evidence and its review;
- F3 general-advice remediation and review;
- R2 evidence/report:
  `project-docs/08-implementation/evidence/stage08-package-f-real-provider-r2.md`
  and `.superpowers/sdd/stage08-package-f-task-f3-r2-report.md`.

This is a final offline package review. Do not issue any external call.

## Blocking checks

1. Evidence lineage: original 11/12 failure remains intact, R2 is separately
   versioned, has one bounded batch/no retry, and no result is rewritten.
2. R2 redaction and metric integrity: exact 12-case result, expected safe
   non-completed terminals versus passed_count, 9 invoked/9 completed/8 usage,
   aggregate/per-case consistency and no raw data/secret exposure.
3. General-advice repair: model-facing instruction plus adapter fail-closed
   enforcement are real and R2 has zero citations for that case; ordinary
   fact citation/range gates did not weaken.
4. Safety: F2 child isolation/strict DTO/outbound marker guard, F1 deadline,
   Telegram dry-run, disabled notifications/Provider write, no default API
   wiring change; confirm evidence limits versus claims.
5. Package conclusion: determine whether Package F is accepted for its stated
   Stage08 quality-evidence scope only. It must not claim full Stage08 closure,
   production deployment, server readiness, or real Telegram send acceptance.

## Rules

- Never read/set evaluator env or `.local`; no OpenRouter, Telegram, webhook,
  deployment or write.
- Do not change source, docs or evidence. Run focused offline tests only where
  necessary.

## Output

Write `.superpowers/sdd/stage08-package-f-final-review-report.md` with C/I/M,
`PASS`/`HOLD`, evidence commands, scope-limited Package F conclusion and any
remaining Stage08/production gates. Critical/Important holds Package F.
