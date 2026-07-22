# Stage08 C2 Long Context Task 4 Review Package

## Review Scope

- Task brief: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-brief.md`
- Implementer report: `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-report.md`
- Review type: private authority, C2 window and internal purge only. Task 5 closure and C3 consumption must remain absent.

## Important Worktree Condition

The working tree is dirty. Read the full Task 4 surface directly rather than trusting a normal git diff:

1. `backend/app/runtime/stage08_group_context_contracts.py`
2. `backend/app/services/stage08_group_context.py`
3. `backend/app/services/stage06_platform.py` (Task 4 C2 UoW additions only)
4. `backend/tests/unit/test_stage08_group_context_contracts.py`
5. `backend/tests/unit/test_stage08_group_context_service.py`
6. `backend/tests/integration/test_stage08_group_context_postgres.py` (Task 4 additions only)
7. `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-report.md`

## Binding Requirements

- Private non-Pydantic/non-JSON authority and projection handle may only be factory/service-issued from verified actor/employee/current workspace. They must not be client-constructible or repr/serializable with text/IDs.
- Every build/window/purge must fail closed after current workspace/member/employee/base/table/binding/mapping/customer/project/link/scope/version revalidation. Scope drift or lifecycle change cannot yield stale text.
- Window rules exact: 30d event-time hard ceiling, 120 fragments, 500 chars each, 60,000 raw, latest 24/12,000, history decay half-life 7d, `compression_required` iff raw chars >24,000. No query/text/embedding/LLM rank, C1/C3 merge, digest or Provider call.
- Public safe views are strict/revalidated count-only models: status, counts/budgets/omissions, compression bool only. Reject crafted `model_construct`, content, identifiers/source refs/scope values.
- Only private C2 internals may touch `content_fragment`. No public schema/API/audit/outbox/log/trace/Memory/RAG/AgentRun/Provider/LangGraph/Redis carrier.
- Individual authority-bound purge and internal expiry purge erase body/mark `purged`, are idempotent, lock only projection lifecycle and never raw `Message`; normal Telegram group delete is not claimed. Expiry picks narrow batches (`FOR UPDATE SKIP LOCKED` in SQLA) and honors `event_at +30d` even when stored expiry is late.
- No new models/migrations, webhook/parser/route, external network/write, API, C1, Memory/RAG/vector, Redis, LangGraph or Provider behavior.
- Evidence must distinguish approved disposable `STAGE06_LOCAL_DATABASE_URL` real PostgreSQL from default DATABASE_URL orphan revision risk. `ruff` unavailable/full suite absent are risks, not pass evidence.

## Expected Output

Read-only independent review. Return Spec Compliance, Strengths, Critical, Important, Minor and Assessment, with exact file/line refs. Do not edit or enlarge scope.
