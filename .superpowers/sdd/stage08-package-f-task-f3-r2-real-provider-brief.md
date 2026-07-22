# Stage08 Package F — F3 R2 versioned real Provider synthetic evaluation brief

## Start gate

The F3 general-advice remediation review is `PASS / 0 Critical / 0 Important /
0 Minor`. User authorization covers this bounded real OpenRouter evaluation.
The earlier F3 evidence (`11/12 HOLD`) is immutable and must remain unchanged.

## Execution

1. Run only the approved F1/F2 offline preflight that excludes the two tests
   intentionally mutating `STAGE08_F_ENV_FILE`.
2. For one process only, set `STAGE08_F_ENV_FILE` to:
   `D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env`
   and execute `backend/scripts/stage08_real_provider_evaluation.py` once.
   Do not print/read/copy/edit/persist env values.
3. No more than the fixed 12 synthetic cases, max two child processes. No
   retry batch, no prompt/code/expectation tuning after result.

## Absolute boundaries

- Telegram must remain dry-run; do not send message, call webhook, confirm a
  draft, deploy, or write to a Provider/notification service.
- Preserve only strict redacted runner output. Do not retain prompt, answer,
  fixture body, ID, token/cost value, request ID, exception text, raw response
  or credential.
- Any failed case is valid evidence and must not be made green by modifying the
  old F3 evidence.

## Artifacts

Create, without changing prior F3 files:

- `project-docs/08-implementation/evidence/stage08-package-f-real-provider-r2.md`
- `.superpowers/sdd/stage08-package-f-task-f3-r2-report.md`

Both artifacts must be Chinese and contain only timestamp/command boundary
without secrets, allowed aggregate/per-case fields, fixed codes, side-effect
assertions, and a truthful `PASS` or `HOLD` result.

## After run

Run no further real calls. Request independent F3 R2 / Package F review. Do
not claim Stage08 or production acceptance from this one batch.
