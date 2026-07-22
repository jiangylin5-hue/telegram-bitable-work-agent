# Stage08 C2 Long Context Task 1 Review Package

## Review Scope

- Task brief: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-1-brief.md`
- Implementer report: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-1-report.md`
- Git base recorded before dispatch: `09d213bf4a7b2cfd32a7ccf260c187b65dda4a00`
- Review type: documentation-only D3 contract reconciliation. No code, migration, test, API, external system or git commit is expected.

## Important Worktree Condition

The Task 1 documents are untracked in the shared dirty worktree. A normal `git diff BASE..HEAD` is therefore not a complete representation. The following files are the complete review diff surface and must be read directly:

1. `project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md` (new)
2. `project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md`
3. `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`
4. `project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md`
5. `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md`
6. `docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md`
7. `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-1-report.md` (new; evidence only)

## Binding Requirements

- New/edited authorized group/supergroup messages only; historical `Message.raw_text`, `raw_caption`, `normalized_text` are neither read nor backfilled.
- Fixed values: 30 days, 120 fragments, 500 code points/fragment, 60,000 raw, 24,000 final context, newest 24/raw 12,000, ephemeral digest 12,000, 7-day half-life.
- `best_effort_group_deletion`: only known edit, server-authorized purge, and expiry are reliable invalidation facts. Do not claim normal-group remote deletion/revoke is instantly observable.
- `GroupContextDigest` is current invocation Context only and has no persistent outlet. C2 has no Provider call; C3 owns merge/budget; Package E owns future compression call.
- D4 active binding to exactly one same-workspace customer/project record; D5 server-only opaque authority; D6 exact label/type/id/C3 ownership.
- Documentation must not claim C2 implementation, migration, tests, external calls, Provider readiness or deployment readiness.
- Task 1 must not modify code or add API/network/external scope.

## Implementer Evidence

- Stale-value scan returned no matches (`rg` exit 1, expected).
- `git diff --check` exit 0; supplemental trailing whitespace scan had no matches.
- The report records existing unrelated Stage06/07 line-ending warnings.
