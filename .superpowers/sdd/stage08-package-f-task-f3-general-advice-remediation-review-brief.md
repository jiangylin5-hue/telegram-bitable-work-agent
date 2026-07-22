# Stage08 Package F — F3 general-advice citation remediation independent review brief

## Scope

Review the completed F1/F2 remediation for
`STAGE_08_F3_GENERAL_ADVICE_CITATION_CONTRACT_DECISION.md` and its task report.
This is a new offline review; prior F3 11/12 evidence must remain untouched.

## Blocking checks

1. Does the real F1 model-facing contract unambiguously require empty citations
   for `general_advice` and `deny`, without injecting or logging raw content?
2. After strict parse, does the adapter use the same command snapshot to fail
   closed on nonempty citations for both actions? Verify usual evidence-range
   validation is not weakened.
3. Do F1 and F2 tests exercise success and violation paths through the actual
   adapter seam, and does the 12-case offline matrix retain isolation, DTO,
   telemetry, dry-run and no-direct-write guarantees?
4. Were the two deliberately deselected env-mutating tests correctly scoped
   under the task's no-env rule, with remaining needed behavior covered rather
   than silently removed?
5. Is old F3 evidence unchanged and is the proposal limited to a new versioned
   R2 real batch after review rather than retrying/rewriting history?

## Rules

- Offline only. Do not read or set `STAGE08_F_ENV_FILE`/`.local`; no OpenRouter,
  Telegram, webhook or deployment. Do not modify source/evidence.
- Run only focused tests needed for these checks.

## Output

Write `.superpowers/sdd/stage08-package-f-task-f3-general-advice-remediation-review-report.md`
with C/I/M, `PASS`/`HOLD`, and exact R2 gate. Critical/Important blocks any
new real Provider batch.
