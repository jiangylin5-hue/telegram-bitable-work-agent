# Stage08 Package F — F3 R3 versioned real Provider synthetic evaluation brief

## Start gate

F3 action-verdict parent-validation review is `PASS / 0 Critical / 0 Important /
0 Minor`. User authorization covers this one bounded real OpenRouter batch.
F3 and R2 evidence are immutable and must remain unchanged.

## Execution

1. Run the focused F1/F2 offline preflight without the tests intentionally
   mutating `STAGE08_F_ENV_FILE`.
2. In exactly one process, set `STAGE08_F_ENV_FILE` to the ignored local
   `D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env`
   and execute `backend/scripts/stage08_real_provider_evaluation.py` exactly once.
3. Fixed 12 synthetic cases, max two child processes, no retry and no tuning.

## Boundaries

- Do not print/read/copy/edit/persist env values.
- Telegram dry-run only; no Telegram, webhook, draft confirmation, deployment,
  Provider write or notification write.
- No raw prompt/answer/fixture/ID/token-cost/request-ID/exception/response.

## New artifacts only

- `project-docs/08-implementation/evidence/stage08-package-f-real-provider-r3.md`
- `.superpowers/sdd/stage08-package-f-task-f3-r3-report.md`

Record the safe `analysis_action` enum for each case along with existing
redacted verdict fields. Confirm old F3/R2 hashes are unchanged. Then stop and
request a final Package F review; do not claim Stage08/production completion.
