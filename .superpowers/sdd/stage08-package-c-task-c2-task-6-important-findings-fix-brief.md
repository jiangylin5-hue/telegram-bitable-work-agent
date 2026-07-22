# Stage08 Package C2 — Task 6 Important-Findings Fix Brief

## Trigger and Authority

Task 6 independent review is `FAIL / C3 HANDOFF BLOCKED` with exactly two Important specification deviations and one Minor documentation drift. This brief restores the already user-approved D2/D6 contract; it does not introduce a new architecture, schema/API/permission decision or scope expansion.

Read the C2 long-context design, C2 implementation plan, C2 BDD, Task 6 review/review package, current contracts/service/tests, and source-chat-type decision before editing.

## Exact Corrections

1. `group_context_partial` must require both at least one selected safe fragment and at least one omission. If no eligible/selected fragment exists — including count-only age/limit omissions — return `group_context_unavailable` with zero selected/raw chars. Update contract validation and window construction accordingly.
2. Every private C2 group fragment evidence item must expose the exact category names `("workspace", "group", "customer", "project")`; this is a category shape only, not an ID/value, and must not change authority scope, persistence, DTOs, renderer/API, audit/log, or privacy behavior.
3. Update the source-chat-type decision’s status/current progress to truthfully say it is implemented and Task 4 independently reviewed, while retaining Task 5/6 status accurately. Do not mark C2 complete or unblock C3 in that document.

## Scope

Modify only:

- `backend/app/runtime/stage08_group_context_contracts.py`
- `backend/app/services/stage08_group_context.py`
- `backend/tests/unit/test_stage08_group_context_contracts.py`
- `backend/tests/unit/test_stage08_group_context_service.py`
- `project-docs/08-implementation/decisions/STAGE_08_C2_SOURCE_CHAT_TYPE_PROPOSAL.md`
- `.superpowers/sdd/stage08-package-c-task-c2-report.md`

You may create a focused remediation report under `.superpowers/sdd/`. Do not modify PostgreSQL tests, schema/migrations, UoW/locking, C1/C3, route/API, Telegram networking, Provider/LLM, Memory/RAG/vector, Redis, LangGraph, audit/outbox, Mini App, deployment, or unrelated dirty files. Do not stage, commit, reset, checkout, clean, or touch the default database.

## TDD and Verification

Add/adjust focused contract and service tests first so they fail against the current incorrect behavior. Explicitly cover:

- a `group_context_partial` view with zero selected fragments is rejected;
- an expired/count-only omission with zero safe fragment builds `group_context_unavailable`, not partial;
- a partial view with a real selected fragment plus omissions remains valid;
- private materialized fragments report exact category names including `group`, while their repr/public safe views still omit text/IDs.

Run these tests RED before production code. Then make the smallest code corrections and run GREEN:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Then run the Task 6 focused C2/C1 verification with disposable `STAGE06_LOCAL_DATABASE_URL`, restoring `DATABASE_URL` afterward; run compileall and `git diff --check` for the allowed scope. Record actual RED/GREEN results and exclusions.

## Return

Return concise status, RED/GREEN outcomes, changes, verification, risks, and report path. Do not claim Task 6 passed or C3 unblocked; a fresh independent re-review is required.
