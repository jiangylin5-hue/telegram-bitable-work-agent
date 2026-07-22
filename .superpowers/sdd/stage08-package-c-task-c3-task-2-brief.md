# Stage08 Package C3 — Task 2 Private Composer and Direct Renderer Brief

## Authority

Implement only Task 2 in `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md`, after Task 1 independent PASS. Treat `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md` as the authoritative C3 contract and preserve confirmed C1/C2 semantics.

## Scope

Create only:

- `backend/app/services/stage08_context_composition.py`
- `backend/tests/unit/test_stage08_context_composition_service.py`
- `.superpowers/sdd/stage08-package-c-task-c3-task-2-report.md`

Do not modify any C1/C2 code/contracts/tests, schema/migrations, routes/API, permissions, Telegram ingress/network, Provider/LLM, Memory/RAG/vector, Redis, LangGraph, audit/outbox, Mini App, deployment, or unrelated files. Do not stage, commit, reset, checkout, clean, or access a database/external system.

## Required Private Interface

Create a module-private `_Stage08CompositeContext` (ordinary `__slots__` object, non-Pydantic/non-JSON) and module-private block object(s). Publicly importable service functions may only be:

```python
def compose_stage08_context(
    uow: Stage06PlatformUnitOfWork,
    plan: ContextPlan,
    *,
    actor: Actor,
    now: datetime,
) -> _Stage08CompositeContext: ...

def render_stage08_composite_context(
    uow: Stage06PlatformUnitOfWork,
    composite: _Stage08CompositeContext,
    *,
    now: datetime,
) -> str | None: ...
```

`composite.view()` may return only Task 1's revalidated `CompositeContextView`. `repr(composite)` and every private helper repr must not include text, UUIDs, chat/message/binding/mapping identifiers, source IDs, plan/actor detail, or group context labels beyond a fixed safe status/count.

## Required Algorithm — Direct (non-compression) Path

1. Revalidate the `ContextPlan` dump and call existing C1 `compose_context_pack` for current authorization, records, fields, Memory and general-advice behavior.
2. Derive C2 authority only via `Stage08GroupContextAuthorityFactory.build` from C1 plan workspace/employee plus server actor; call C2 `build_group_context_window` using `plan.business_scope`. Never accept or derive caller chat/binding/message/text/group fields.
3. This task supports only `compression_required=False` direct group path. A group window that is unavailable simply leaves C1 behavior intact. The high-window compression branch belongs to Task 3; before Task 3 it must fail closed (safe no raw group rendering) rather than materializing a >24,000 window or calling any provider.
4. On usable direct C2 window, call the existing C2 private materializer after its fresh authority/mapping/provenance/lifecycle/retention re-read. If any C2 handle/version/purge/member/binding/mapping/relation/scope/source drift occurs, drop all group fragments; never fall back to `Message` or stale partial body.
5. Combine C1 existing evidence in current C1 order and C2 fragments in current C2 order. Count content only: C1 pack `usage.content_chars` + sum selected group fragment code points. Enforce exactly Task 1's 36,000 cap; if a theoretically inconsistent over-cap state occurs, return safe no-consumer content (not a text truncation) and never claim evidence.
6. Preserve C1 `internal_evidence` normally. If C1 has `general_advice_only` but direct group fragments exist, retain that only in safe `c1_status`, drop the C1 policy marker from private rendered blocks/counts, and set composite status `internal_evidence`. If both sources are unavailable, preserve C1 general/no-evidence result.
7. Renderer must recompose from private plan and server-derived actor every time before rendering. It must not trust a previously composed C1 pack or C2 materialization. Direct output is deterministic: C1's `render_evidence_pack` blocks first, then C2 blocks exactly:

```text
[group_context:NN label=group_context type=group_message_fragment scope=workspace/group/customer/project]
<controlled fragment>
```

Only `render_stage08_composite_context` may return that ephemeral string. A compression-pending, invalid, or stale private object returns `None`; no exception may echo private body/ID.

## TDD Corpus

Write tests before production code and run RED. Cover at minimum:

- same customer/project C1 business evidence plus valid C2 direct group fragment merges in C1-first/C2 deterministic order and safe view arithmetic;
- C2 unavailable preserves C1 internal/general/no-evidence behavior;
- C1 `general_advice_only` with direct group fragment renders only group block but safe `c1_status` stays general;
- direct group `partial` preserves safe C2 status but no identifier/text leaks into view/repr;
- all rendered text uses exact D6 header and contains no UUID/chat/message/mapping/binding metadata;
- a forged composite, `model_construct` C1 plan, nested safe-view subclass and invalid `now` fail closed;
- after composition, mutate C2 projection lifecycle/source type/mapping/member/binding/relation and C1 view/record/Memory state; render must recompose and never return old group text or revoked C1 content;
- no records, Memory items, audit/outbox events, Redis state or network/provider calls are created; module does not import `Message` or prohibited integration clients;
- a test-only inconsistent over-36,000 source state yields no rendered text and a safe no-consumer view, rather than truncation/persistence.

Run focused RED first, then minimal GREEN:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Then run Task 1 + C1/C2 units (no PostgreSQL in Task 2), compile both C3 modules, static boundary scan and scoped diff check.

## Report

Write actual commands/results, any fail-closed choices, scope exclusions, skipped PostgreSQL/Task3 compression coverage, and cleanup to the report. Return status, exact verification, changes, risks and report path. Do not claim Task 3/C3/Package C completion; fresh independent review is required after Task 2.
