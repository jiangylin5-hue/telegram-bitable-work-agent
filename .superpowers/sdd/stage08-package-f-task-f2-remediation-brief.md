# Stage08 Package F — F2 evidence remediation task brief

## Scope

Implement the approved evaluator-only remediation in:

- `project-docs/08-implementation/decisions/STAGE_08_F2_EVALUATION_EVIDENCE_REMEDIATION_DECISION.md`
- `docs/superpowers/plans/2026-07-22-stage08-package-f-f2-evidence-remediation.md`

The F2 review found I-01 outbound prompt absence gap, I-02 false Provider invocation metric, and I-03 fake/real contract mismatch. Repair all three with focused tests.

## Non-negotiable boundaries

- Offline only. Do not read/set `STAGE08_F_ENV_FILE`, call OpenRouter/Telegram/webhook/deployment, or inspect `.local` values.
- No public API/schema/migration/permission/default-provider change.
- Never output/persist prompt, response, synthetic business body, UUID, token/cost/request ID or exception text.
- Preserve fresh `spawn` per case, max parallelism 2, per-child hard timeout and fail-closed safety env.

## Required outcomes

1. Final outbound prompt is checked inside the child immediately before F1 transport; all relevant forbidden markers cause a fixed safe case failure without network. Both fake and real adapter paths exercise the guard. Add a mutation test.
2. Parent DTO and aggregate distinguish actual Provider `invoked`, `completed`, and usage-metadata presence. Configuration alone must not count. Provider-preterminal and coordinator-only cases report false and do not enter real coverage.
3. Fixed strategy makes `provider_unavailable` an offline F1 transport fault, `policy_deny` a controlled-write request expected to get F1-compatible deny, `safe_replay` coordinator-only, and fake outputs only F1-compatible actions/no draft intent.
4. Update BDD/source progress only if implementation evidence supports it. Write a task report under `.superpowers/sdd/` including exact validation commands and skipped external calls.

## Validation

Run only focused offline tests. Report C/I/M-equivalent self findings, test counts, and no-network evidence in `.superpowers/sdd/stage08-package-f-task-f2-remediation-report.md`.
