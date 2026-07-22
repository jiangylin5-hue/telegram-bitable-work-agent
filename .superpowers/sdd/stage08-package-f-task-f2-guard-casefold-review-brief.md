# Stage08 Package F — F2 guard casefold independent review brief

## Scope

Independently review only the fix required by
`stage08-package-f-task-f2-guard-casefold-brief.md`, together with its report
and affected F1/F2 tests.

## Blocking checks

1. Does child-local guard compare both final prompt and forbidden marker values
   using `casefold()` before any F1 transport? Verify the actual fixture
   constants, not synthetic lower-case duplicates.
2. Do all four real marker categories (hidden field, expired group, revoked
   group, deleted RAG) have mutation evidence for fake and F1 transport-before-
   call paths?
3. Does the strict DTO/output remain free of raw marker, prompt and answer;
   do actual Provider telemetry, strategy, spawn isolation, timeout, DTO
   strictness, fail-closed env and Telegram dry-run remain intact?

## Rules

- Offline only. Never read/set `STAGE08_F_ENV_FILE` or `.local`; do not call
  OpenRouter, Telegram, webhook or deployment.
- Do not modify source. Run only the focused tests necessary to establish the
  above.

## Output

Write `.superpowers/sdd/stage08-package-f-task-f2-guard-casefold-review-report.md`
with C/I/M and `PASS`/`HOLD`. Any Critical/Important blocks F3; a clean review
allows the already-authorized bounded synthetic real Provider task to begin.
