# Stage08 Package B — Task B3 Review Package

## Review scope

This task is uncommitted by design because the shared worktree is dirty. Review only the B3 changes described in `stage08-package-b-task-b3-report.md`; do not treat unrelated Stage07 or prior Stage08 work as part of this task.

## Artifact paths

- Task brief: `.superpowers/sdd/stage08-package-b-task-b3-brief.md`
- Implementer report and TDD evidence: `.superpowers/sdd/stage08-package-b-task-b3-report.md`
- Current implementation: `backend/app/services/stage08_memory.py`
- Integration hook: `backend/app/services/stage06_digital_employees.py`
- UoW additions: `backend/app/services/stage06_platform.py`
- Internal contract: `backend/app/runtime/stage08_memory_contracts.py`
- Task tests: `backend/tests/unit/test_stage08_memory_confirmed_record.py`

## Review questions

1. Does the confirmed-draft hook execute strictly after the existing confirmation audit, while never modifying source records, confirming drafts, or issuing external calls?
2. Is every event payload exactly six references (`workspace_id`, `table_id`, `record_id`, `record_version`, `policy_version`, `rule_index`) with no raw value, field key, identity token or provider/Telegram content?
3. Does materialization fail closed on stale record/policy/scope/field/actor state, set terminal status only after B2 materialization succeeds, and preserve idempotency?
4. Is `identity_token` HMAC-only, server generated, never client supplied or returned by safe read projections, and based on policy identity values rather than scope alone?
5. Does accepting a policy with multiple rules silently lose eligible rules, or is that case explicitly safe? Does a processed event still honor actor authorization before returning an item?
6. Are UoW implementations and existing tests compatible, and is the scope limited to B3?

## Verification already run

`71 passed in 1.43s` for B3/B2 Memory, Tool Gateway and Stage06 digital employee runtime focused suites; `compileall` exited 0. The reviewer should inspect evidence but need not repeat identical tests unless validating a concrete finding.
