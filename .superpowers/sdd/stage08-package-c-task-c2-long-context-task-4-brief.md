# Stage08 Package C2 Long Context — Task 4 Brief

## Task

Implement Task 4, **Opaque Authority, Long-Window Contract and Purge Service**, from `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md` and the approved decision record `project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`.

Tasks 1–3 are independently approved. This task makes group Context safely selectable and removable; it does not make it consumable by C1, C3, a renderer, an LLM, or a user-facing API. Use TDD for each production behavior: written focused test, recorded RED, smallest GREEN. Do not start Task 5 final package closure.

## Exact Scope

Create:

- `backend/app/runtime/stage08_group_context_contracts.py`
- `backend/app/services/stage08_group_context.py`
- `backend/tests/unit/test_stage08_group_context_contracts.py`
- `backend/tests/unit/test_stage08_group_context_service.py`
- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-report.md`

Modify only when required for internal read/lock/purge UoW parity and the Task 4 focused tests:

- `backend/app/services/stage06_platform.py`
- `backend/tests/integration/test_stage08_group_context_postgres.py`

Do **not** modify any webhook/parser/ingestion route, model, migration, public schema/API, C1 Context contracts/services, Memory, RAG/vector, Redis, LangGraph, Provider, AgentRun, audit/outbox, deploy/secrets, or git index. Do not stage/commit/reset/checkout/clean.

## Fixed Contract — No Variations

- Source retention: 30 days.
- At most 120 selected fragments, max 500 Unicode code points per fragment, total raw selected window max 60,000 code points.
- Latest raw band: newest 24 fragments ordered by `(event_at DESC, projection internal id DESC)`, consuming max 12,000 code points.
- History: select remaining eligible fragments only by time decay with a 7-day half-life, then `event_at DESC` and internal id as stable ties. Never rank by query, text, keyword, embedding or LLM.
- `compression_required` is exactly `raw_selected_chars > 24000`; C2 does not compress, call a Provider, make a digest, merge C1/C2 or implement global budget. Future C3/E alone own those steps.
- Only active, unexpired, nonempty controlled projections for one current qualifying mapping can be examined. Historical `Message.raw_text`, `raw_caption`, `normalized_text` cannot be read, enumerated, or used.
- `best_effort_group_deletion`: known edit is already handled by Task 3. This task implements idempotent server-authorised individual purge and expiry purge that erase fragment text and mark lifecycle `purged`. It must not claim a normal Telegram group remote delete/revoke is observable.

## Authority and Business Scope

Implement `Stage08GroupContextAuthorityFactory` whose only construction entry takes `uow`, a verified `Actor`, `employee_id`, and `workspace_id`. Its result must be a private non-Pydantic, non-JSON dataclass/object. No HTTP/Mini App/Telegram/outbox/audit/client input, mapping id, chat id, message id, text, scope values or caller-supplied binding may construct it.

At build and every window/purge operation, revalidate fail-closed:

1. active workspace; actor is a user and is an active member of it;
2. active employee in the same workspace, active base, employee member eligibility (reuse project semantics for workspace/assigned employee), and strict valid `accessible_tables` IDs;
3. exactly one active Stage06 `chat_user` binding for the relevant group source, whose workspace/member/current status remains valid;
4. exactly one active C2 mapping for the binding, same workspace, customer and project records currently active, their tables/base active and in the workspace, their tables are employee-accessible, and their current relationship remains valid/visible through existing record-link semantics;
5. supplied `ResolvedBusinessScope` exactly matches the current customer/project IDs and versions; null, ambiguity, inactive state, status/version drift or relation drift returns unavailable/rebuild-required without exposing text.

The factory may return a safe internal no-source authority only when no qualifying mapping exists, but must not expose why or attempt another mapping. Any `PlatformValidationError`/invalid state must be converted to the fixed C2 unavailable path, never leak IDs/values.

## Internal-only Types and Serialization Boundary

Create strict frozen Pydantic contracts only for safe, count-only views (for example budget constants, omission counts and `GroupContextWindowView`). Revalidate public-safe models via dump/revalidate before return. `GroupContextWindowView` must contain only:

- contract version;
- status: `group_context_unavailable | group_context_partial | group_context_available`;
- count/budget usage and fixed omission categories;
- boolean `compression_required`.

It must reject `model_construct`/client-shaped carriers and cannot contain text, UUID, Telegram/binding/mapping/source IDs, tokens, permissions or scope values.

Keep `_GroupContextAuthority`, `_GroupProjectionHandle`, raw fragment text and private selected-fragment records as private dataclasses/objects only. They must not subclass BaseModel and must have no JSON/Pydantic conversion, public renderer or DTO route. `GroupContextWindow` is private; its only observability method may return a revalidated count-only `GroupContextWindowView`.

Each selected private evidence item must have only the future internal metadata: label `group_context`, source type `group_message_fragment`, display ID `group_context:NN`, and scope dimension **categories** only. It may not use the C1 `EvidenceItem` type or enter C1 packs in this task.

## Window and Lifecycle Behavior

- `build_group_context_window(uow, authority, *, business_scope, now)` revalidates authority/mapping/source/current scope before returning any private fragment. It accepts timezone-aware UTC `now`; invalid/non-UTC input is rejected.
- status is `unavailable` if no safe source; `partial` if at least one source but any age/count/character/budget omission; `available` only when at least one source and no such omission. Excluded sources from expiry, 120/60,000/latest-band limits must increment fixed count-only omissions—never textual or identity hints.
- Ordering and truncation are deterministic. An input whose first eligible item alone breaches a character limit must be omitted safely, not sliced or sent elsewhere.
- `purge_group_context_projection(uow, authority, *, projection_handle, now)` accepts only factory/service-issued private handles; it revalidates authority and ownership/current mapping then locks the projection, empties text and marks `purged`. It is idempotent and returns a count-only `GroupContextPurgeResult`.
- `purge_expired_group_context_projections(uow, *, now)` is internal server maintenance only (not route/API). It must lock each expired active projection before erase, be idempotent, never return text or IDs, and keep its selection/lock narrow. Add the minimum UoW method if required; do not lock raw `Message` rows.
- A window built before mapping/member/employee/record relation/purge/version drift must become unavailable or require a rebuild when revalidated; it may never yield stale text. No Memory/outbox/audit/AgentRun mutation is permitted.

## Required Tests and Commands

### Contract tests first

Write tests for exact constants, valid/invalid statuses, strict public views, `model_construct` or crafted carrier rejection, count-only omission, forbidden content/IDs/source refs, 501st code point, 121st fragment and any public compression view carrying text. Run RED:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

### Service tests next

Write tests for factory rejection on actor/member/employee/base/binding/mapping/customer/project workspace/relation drift and private/channel; deterministic latest-24 plus decay-selected history, 120/60,000 bounds, `raw_selected_chars > 24000`, status/omission, expiry and authorised purge, and post-plan re-read drift. Assert no Memory/outbox/audit/AgentRun mutations. Run RED:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

After minimal implementation run:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_group_context_ingestion.py tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
python -m compileall -q backend/app/runtime/stage08_group_context_contracts.py backend/app/services/stage08_group_context.py backend/app/services/stage06_platform.py
```

If an integration test needs `DATABASE_URL`, temporarily point it to the approved disposable `STAGE06_LOCAL_DATABASE_URL`, restore the original value and explicitly disclose the existing default database orphan-revision risk. Do not hide failure behind PowerShell’s last-command exit behavior.

Run static boundaries on the changed C2 files. `content_fragment` is allowed only inside model/private service/private test paths and must not occur in public schemas, APIs, audit, logging, Memory, RAG/vector, Provider, AgentRun or LangGraph/Redis code. No new network/API/Provider matches are allowed.

## Report

Write `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-report.md` with changed files, all RED/GREEN commands/results, real PostgreSQL evidence, privacy/static checks, direct statement of no external write/Provider/Telegram network/API/Memory/RAG/C1/C3 action, remaining risks and cleanup. Return only status, one-line verification, concerns and report path.
