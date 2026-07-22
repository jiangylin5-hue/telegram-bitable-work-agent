# Stage08 Package F — F3 real Provider evidence independent review brief

## Scope

Review the single executed F3 batch and its redacted evidence:

- `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md`
- `.superpowers/sdd/stage08-package-f-task-f3-report.md`
- current F1/F2 runner and focused tests as needed.

No external actions are permitted in this review.

## Blocking questions

1. Is the evidence strictly redacted and internally consistent with the
allowed DTO/aggregate (including 12 cases, 9 invoked/completed, 8 usage
presence, one `general_advice` citation failure)?
2. Did the executed path preserve the F2 guarantees: synthetic-only input,
child isolation, no prompt/response persistence, dry-run Telegram and no
external write/deploy? Identify evidence versus assertions precisely.
3. Is `general_advice -> citation_invalid` a valid model-quality/behavior
failure under the current approved contract, or an evaluator-contract defect?
Do not rewrite history or infer raw content. State the minimal next technical
step if a change is justified.
4. Does F3 remain `HOLD` rather than being overstated as acceptance or
production readiness? Check no retry/tuning was hidden in the batch.

## Rules

- Strictly offline; do not read/set evaluator env or `.local`; do not call
  OpenRouter, Telegram, webhook or deployment.
- Do not change implementation or evidence. Focused offline tests may be run.

## Output

Write `.superpowers/sdd/stage08-package-f-task-f3-review-report.md` with
C/I/M and `PASS`/`HOLD`, clear classification of the failed case, evidence
limits, and a bounded next-step recommendation. A real quality failure is not
to be converted into a green result by editing the existing evidence.
