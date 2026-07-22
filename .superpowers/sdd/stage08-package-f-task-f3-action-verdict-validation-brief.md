# Stage08 Package F — F3 action verdict parent-validation brief

## Scope

Implement `STAGE_08_F3_ACTION_VERDICT_VALIDATION_DECISION.md` as the smallest evaluator-only fix.

## Requirements

- Add a static case-to-allowed-action fail-closed validator to strict result creation and parent child-payload revalidation.
- A forged valid enum with an invalid case/action pairing must become/reject to a fixed failed safe result; no batch false pass.
- Cover forged `general_advice/read_only`, accepted `general_advice/deny`, and regression for all 12 fixed strategies.

## Boundaries

- Offline only, no env/.local reading or setting, no external call/write/deploy.
- Do not change F1 behavior, public interfaces, historical F3/R2 evidence or action redaction fields.

## Deliverable

Run focused F2/F1 + offline spawn/compile/diff checks and write `.superpowers/sdd/stage08-package-f-task-f3-action-verdict-validation-report.md`. Fresh review is mandatory before R3.
