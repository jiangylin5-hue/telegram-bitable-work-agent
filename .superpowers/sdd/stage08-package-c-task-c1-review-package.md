# Stage08 Package C — Task C1 Review Package

## Review scope

The worktree is intentionally dirty and all Stage08 changes are uncommitted. Review Task C1 only after its implementer report is present in `.superpowers/sdd/stage08-package-c-task-c1-report.md`. The governing boundary is `.superpowers/sdd/stage08-package-c-task-c1-brief.md`, supplemented by `project-docs/08-implementation/STAGE_08_PACKAGE_C_CONTEXT_BDD_AND_ACCEPTANCE.md`.

## Expected task artifacts

- Typed contracts: `backend/app/runtime/stage08_context_contracts.py`
- Pure internal context compiler: `backend/app/services/stage08_context.py`
- Tests: `backend/tests/unit/test_stage08_context_contracts.py`, `backend/tests/unit/test_stage08_context_service.py`, `backend/tests/integration/test_stage08_context_postgres.py`
- Implementer evidence: `.superpowers/sdd/stage08-package-c-task-c1-report.md`

## Required review checks

1. `ContextPlan` is an inert internal plan, never a capability, execution ticket, permission grant or persistence request.
2. Source selection is solely through existing authorized service/UoW boundaries; raw ORM/SQL access cannot bypass view, record, Memory, employee or workspace scope.
3. A C1 plan never reads or imports `Message`, Telegram/群聊原文、历史窗口、chat/binding transport identity, LLM/provider, RAG/pgvector or any external system.
4. Business record and non-group business Memory evidence have exact `label`/`type`/`scope`/`version`; renderer redacts UUIDs, source refs, permission data, identity data and tokens.
5. Customer/project relation resolution is scoped, deterministic and fail-closed for ambiguous, inactive, unpermitted or stale inputs.
6. Budget caps, deterministic truncation/order and before-consumption reread all fail closed on stale/missing/revoked/version-mismatched inputs.
7. `general_advice` remains a bounded marker rather than fabricated fact; mixed intent does not leak non-authorized source data.
8. No API/router, migration, schema/role/permission model, agent execution, audit/draft/ticket/notification, Telegram or provider behavior was added.
9. Focused unit and local PostgreSQL evidence genuinely exercises the safety boundaries; flag every Critical and Important issue.
