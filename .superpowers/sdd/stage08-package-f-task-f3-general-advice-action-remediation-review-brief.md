# Stage08 Package F — F3 general-advice action remediation independent review brief

## Scope

Review the implementation/report for
`STAGE_08_F3_GENERAL_ADVICE_ACTION_CONTRACT_DECISION.md` only. Historical F3
and R2 evidence are immutable and must not be altered.

## Blocking checks

1. F1 general-advice validation uses the sealed command snapshot and accepts
   only `general_advice`/`deny` with empty citations; `read_only + []` and any
   nonempty citations fail closed without weakening fact citation bounds.
2. F2 strict child/parent DTO permits only `analysis_action = none | read_only
   | general_advice | deny`; action is accurate on valid, invalid, fault and
   not-invoked paths and contains no raw content.
3. General-advice evaluator accepts safe denied terminal, rejects read-only
   path, and all existing redaction/guard/invocation/isolation/timeout/dry-run
   behaviors remain.
4. The test count and deliberate env-test deselection are valid, and the
   historical evidence files did not change.

## Rules

- Offline only. Do not read/set evaluator env or `.local`; no OpenRouter,
  Telegram, webhook/deploy/write. Do not modify code/docs/evidence.

## Output

Write `.superpowers/sdd/stage08-package-f-task-f3-general-advice-action-remediation-review-report.md`
with C/I/M and PASS/HOLD. Critical/Important blocks R3. A clean review allows
one separately versioned, user-authorized synthetic real Provider batch.
