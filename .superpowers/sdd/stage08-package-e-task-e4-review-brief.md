# Stage08 Package E — E4 independent review brief

## Scope

Review only the E4 implementation of the approved single endpoint:

`POST /api/stage08/assistant/query`

Read the E contract, data/API contract, E4 brief/report, existing Stage08 API
patterns, source and tests. This endpoint is the only new E4 public surface.

## Blocking review questions

1. Does the request schema accept exactly the approved fields and reject
   client-supplied scope, field/view filters, provider/budget/tool settings,
   ticket state, audit data and draft values without reflecting sensitive input?
2. Does the route use verified identity and current active member/employee/
   `digital_employee.invoke` authority, and does it recheck actor/employee/
   target readability before idempotency replay response?
3. Is the service-derived collaboration command the only graph input? Can
   request JSON reach private command/state/authority/provider input?
4. Is every success response reconstructed as strict `AssistantQuerySafeView`,
   including forged/malformed return objects? Are private query/material,
   UUIDs, raw errors and authority absent from response/error/logging paths?
5. Are transaction commit/rollback and 422/403/404/409/safe-degradation
   mappings correct and non-leaking?
6. Does router registration expose exactly this POST endpoint, without
   incidental schema/migration/permission/Provider/Telegram/deployment scope
   expansion or a Stage06 default behavior change?
7. Are tests substantive and is the reported PostgreSQL evidence actually
   local loopback pgvector behavior rather than a connectivity-only check?

## Method and output

Directly inspect source and run focused tests necessary to validate concerns.
Do not edit implementation. Write
`.superpowers/sdd/stage08-package-e-task-e4-review-report.md` in Chinese with
Critical/Important/Minor findings, exact evidence and a closure recommendation.
Do not call external services or modify Git state.
