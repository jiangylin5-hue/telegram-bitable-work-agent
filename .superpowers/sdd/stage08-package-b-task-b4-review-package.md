# Stage08 Package B — Task B4 Review Package

## Review scope

The worktree is intentionally dirty and all Stage08 changes are uncommitted. Review Task B4 only. Its complete self-report and test evidence are in `.superpowers/sdd/stage08-package-b-task-b4-report.md`; design constraints are in `.superpowers/sdd/stage08-package-b-task-b4-brief.md`.

## Current task artifacts

- Source adapter: `backend/app/services/stage08_group_memory_source.py`
- Strict contracts: `backend/app/runtime/stage08_memory_contracts.py`
- Candidate/lifecycle/list/revoke service: `backend/app/services/stage08_memory.py`
- Safe DTOs/routes: `backend/app/schemas/stage08_memory.py`, `backend/app/api/routes/stage08_memory.py`, `backend/app/main.py`
- Tests: `backend/tests/unit/test_stage08_memory_contracts.py`, `backend/tests/unit/test_stage08_memory_service.py`, `backend/tests/unit/test_stage08_memory_api.py`, `backend/tests/integration/test_stage08_memory_postgres.py`

## Required review checks

1. Candidate confidence is an exact non-overridable `Decimal("0.85")`; below threshold writes no candidate/Memory/outbox/audit.
2. Adapter accepts only a current in-process group/supergroup input bound to an active `chat_user` binding, active member and active workspace; chat IDs/text/user IDs never leave adapter as persistence/API/audit/log data.
3. Candidate and Memory contracts reject all raw-text carriers recursively; exact Telegram source/ref/binding shape is enforced and arbitrary Telegram source remains denied.
4. Candidate create/promotion/revoke use current scope/binding/member checks, exact safe fingerprint correlation, version/TTL/lock semantics and do not overwrite conflicting active facts.
5. Safe list/revoke APIs use verified identity plus only existing authorization actions, do not accept client actor/scope/source/payload/confidence, and response/errors redact input, IDs, sources, scopes and values outside permitted payload projection.
6. Source corruption/deletion, binding/member revocation and TTL immediately fail closed and persist the correct lifecycle transition without external calls.
7. Ensure B3 behavior/regression, migrations/head, router integration, SQLAlchemy `autoflush=False` candidate visibility, and task scope are sound. Flag all Critical/Important issues.

## Implementer evidence

- Task aggregate including local PostgreSQL: `72 passed`.
- B3/B2/runtime regression: `110 passed`.
- Alembic head: `20260718_0029` only.
- No external call was made; no migration, permission action/role, webhook/ingestion, frontend or provider change was permitted.
