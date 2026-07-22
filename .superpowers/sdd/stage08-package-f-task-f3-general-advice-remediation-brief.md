# Stage08 Package F — F3 general-advice citation remediation brief

## Scope

Implement the approved decision `project-docs/08-implementation/decisions/STAGE_08_F3_GENERAL_ADVICE_CITATION_CONTRACT_DECISION.md` and the matching implementation plan. The prior F3 evidence is immutable.

## Required work

- Add an explicit general-advice empty-citation instruction to the F1 provider payload contract.
- After strict JSON parse, fail closed when a general-advice command yields nonempty citations; `deny` must also not fabricate citations.
- Add focused F1/F2 tests for valid empty citations and invalid nonempty ones, while preserving actual Provider telemetry, redaction and all other F2 protections.

## Boundaries

- Offline only: do not read/set `STAGE08_F_ENV_FILE`/`.local`, call OpenRouter, Telegram, webhook or deployment.
- No public API/schema/migration/permission/default wiring change.
- Do not edit existing `stage08-package-f-real-provider.md` or alter old 11/12 evidence.

## Validation and report

Run focused F1/F2 tests plus 12-case offline spawn, compile and diff check. Write `.superpowers/sdd/stage08-package-f-task-f3-general-advice-remediation-report.md` with changes, test results, no-external-call evidence and remaining F3 R2 gate.
