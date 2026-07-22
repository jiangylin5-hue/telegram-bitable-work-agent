# Stage08 Package F — F2 outbound guard casefold repair brief

## Trigger and scope

The fresh F2 remediation review found one Important defect: the evaluator-only
outbound prompt guard compares lower-case synthetic marker constants against
the final prompt case-sensitively, while the real fixture marker values are
upper-case. A process-local probe proved an actual hidden marker can enter the
prompt and still produce a passing verdict.

Make the smallest evaluator-only repair. Do not redesign F2, call any external
system, or change public API/schema/permission/default provider wiring.

## Required implementation

1. Normalize both final prompt and every forbidden marker with Unicode-safe
   `casefold()` before comparison inside the child-local guard.
2. Replace/add mutation coverage so all four real fixture values for hidden,
   expired group, revoked group and deleted RAG content are injected into a
   visible synthetic field one at a time. For each:
   - fake path returns fixed `outbound_prompt_unsafe`;
   - F1 adapter guard blocks before transport;
   - no raw marker/prompt leaves the strict DTO, output or file.
3. Preserve all existing F2 instrumentation, strategy, actual invocation
   facts, spawn isolation, timeout, DTO, fail-closed env and dry-run behavior.

## Boundaries

- Offline only: do not read/set `STAGE08_F_ENV_FILE` or `.local`; no OpenRouter,
  Telegram, webhook or deployment.
- Run focused affected F1/F2 tests only, compile and diff check.
- Write `.superpowers/sdd/stage08-package-f-task-f2-guard-casefold-report.md`.

## Gate

This is an Important repair. A fresh independent reviewer must verify the
actual four fixture markers and transport-before-call behavior. F3 remains
blocked until that review is `PASS` with no Critical/Important finding.
