# Stage08 Package E — E4 strict assistant-query API implementation

## Purpose and approved boundary

Implement the already approved, single public entry point:

`POST /api/stage08/assistant/query`

The API contract is fixed by:

- `project-docs/08-implementation/decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`, sections 4–5;
- `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md`;
- `docs/superpowers/plans/2026-07-21-stage08-package-e-langgraph-collaboration.md`, Task E4.

E3 is closed. This task does not add a model, migration, permission role,
provider configuration, GET/list/admin endpoint, webhook, Telegram behavior,
or external call.

## Allowed files

- create `backend/app/schemas/stage08_collaboration.py`
- create `backend/app/api/routes/stage08_collaboration.py`
- modify `backend/app/main.py` only to register the single router
- create `backend/tests/api/test_stage08_collaboration_api.py`
- narrow modifications to existing Stage08 collaboration code/tests only when
  necessary for the adapter seam; do not weaken E1–E3 redaction, authority or
  transaction behavior
- create/update the E4 task report under `.superpowers/sdd/`

## Required behavior

1. Use the repository's existing strict `APIRoute` validation wrapper,
   verified identity and transaction patterns. The request body declares only:
   `workspace_id`, `employee_id`, `intent`, `query`, `requested_action`,
   optional `target_record_id`, and `idempotency_key`. Forbid extras.
2. Derive identity/authority server-side. Require an active workspace member,
   active in-workspace employee and current `digital_employee.invoke` scope.
   Do not accept client scope, field/view filters, provider/budget/tool knobs,
   ticket state, draft values or audit content.
3. Invoke only the E1–E3 collaboration service. Keep query/private graph
   material within request/process scope. Rebuild the response exclusively as
   `AssistantQuerySafeView`; never serialize command/state/authority/provider
   error/internal exception.
4. Commit only a successful internal transaction, rollback on unexpected
   exception. Same-key replay must still re-check current member/employee/
   target readability before returning the prior safe result.
5. Fixed response/error behavior: invalid body 422 without echoing sensitive
   content; current scope/permission denial 403; absent resource 404 without
   scope leakage; idempotency/run conflict 409; provider/read failure as its
   safe terminal response. No raw exception response.
6. Register no public route other than this POST path.

## Required tests and evidence

Write/extend focused API tests for extra-field rejection, verified identity,
member/employee/invoke deny, server-side command derivation, response
redaction including forged safe-view input, replay revalidation, transactional
rollback and error mappings. Run the E4 API file, the existing collaboration
unit suite, and the PostgreSQL integration test using only the disposable
loopback pgvector database. Run compileall and `git diff --check`.

Use real local PostgreSQL only as test evidence. Do not call OpenRouter,
Telegram, deployment, or any external system. Do not stage, commit, reset,
checkout, clean or push.

## Report

Create `.superpowers/sdd/stage08-package-e-task-e4-report.md` in Chinese with
changed files, test commands/counts, API behavior matrix, skipped work and
external-call statement. Do not declare Package E closed; a separate review
will decide that.
