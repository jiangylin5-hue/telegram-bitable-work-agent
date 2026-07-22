# Stage08 Package C / C3 Task 5 — Package-Level Independent Handoff Review

## Review scope

Perform a package-level independent review of Package C after C1, C2 and C3
Tasks 1–4. This review may only create
`.superpowers/sdd/stage08-package-c-task-c3-task-5-review-report.md`; it must
not edit implementation, tests, migrations, API, permissions, active source
documents, database, Git state, or external systems.

This is the final technical gate for Package C only. It cannot declare
Package D, Package E/F, real Provider evaluation, Telegram activity, staging,
or deployment complete.

## Required source order

1. `AGENTS.md`
2. `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`
3. `project-docs/08-implementation/STAGE_08_PACKAGE_C_CONTEXT_BDD_AND_ACCEPTANCE.md`
4. `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md`
5. `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md`
6. C2 D1–D6 contract and C1/C2/C3 task reports/reviews/evidence.

## Package-level checks

### C1 and C2 preservation

- C1 remains a private, re-read, permission-filtered table/approved non-group
  Memory/general-advice composer with no group raw reads or mutation.
- C2 preserves D1–D6: only new/edited authorised group/supergroup controlled
  projections; max 30 days/120 fragments/60,000 code points/500 per fragment;
  historical raw message bodies unreadable; best-effort lifecycle; exact
  active mapping; opaque authority only; D6 categories only.
- C3 does not change C1/C2 public contracts, schema, retention, API or
  permissions, and no C3 path provides an identifier/handle/actor/scope/body
  escape hatch.

### Composition and safety

- Exactly preserve the content-level bound: C1 max 12,000 + direct C2 max
  24,000 = C3 max 36,000, item limits and C1-first / D6 group order.
- Verify all source/relationship/mapping/projection/provenance/member/actor/
  field/Memory/version/retention/purge drift paths re-read at consumption and
  fail closed without stale group text.
- Verify direct group unavailable preserves only still-current C1 evidence.
- Verify actual `49 × 500 = 24,500` C2 pending produces no materialization,
  truncation, synthesis, digest, summary, renderer group text, or external
  call. Only Package E may later own compression.
- Probe safe views, `repr`, exceptions, public module surface and test
  artifacts for raw body, `Message` fields, UUIDs/identifiers, plan/actor,
  opaque window or authority disclosure.

### Data, tests and evidence

- Inspect C3 Task4’s corrected T0/T1/T2/T3 evidence timeline. Do not treat
  the original 10-case RED as a full RED corpus for the later 12-case module;
  ensure the distinction remains explicit.
- Independently run proportionate final verification using only
  `STAGE06_LOCAL_DATABASE_URL`, including migration head and the complete C1,
  C2, C3 unit/integration group from the approved C3 plan. Record exact
  results or a reason for any unavailable check. Confirm no default orphaned
  `DATABASE_URL` is used as evidence.
- Run compileall, production-source dependency/privacy scans, and `git diff
  --check`.
- Check the task reports accurately distinguish local PostgreSQL evidence from
  production/staging evidence and do not overclaim real LLM/Telegram/deploy
  activity.

## Report format

State findings by Critical / Important / Minor, commands and actual outputs,
scope confirmation, evidence-quality assessment, remaining risks and an
explicit `PASS` or `FAIL`. If PASS, state only that Package C is eligible for
root-level documentation closure and handoff to Package D; do not modify those
documents yourself or announce Stage08 completion.
