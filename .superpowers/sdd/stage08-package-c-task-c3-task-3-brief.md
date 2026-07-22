# Stage08 Package C3 — Task 3 Compression-Pending Semantics Brief

## Authority

Implement only Task 3 of `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md`, using the approved C3 design. Task 1/2 are independently reviewed clean. This task completes only C3's private pending handoff; it does not implement Package E compression.

## Scope

Modify only:

- `backend/app/services/stage08_context_composition.py`
- `backend/tests/unit/test_stage08_context_composition_service.py`
- `.superpowers/sdd/stage08-package-c-task-c3-task-3-report.md`

Do not modify contracts, C1/C2, schema/migrations, API/routes, permissions, Telegram, Provider/LLM, Memory/RAG/vector, Redis, LangGraph, audit/outbox, Mini App, deployment or Git state. Do not access a database or external system.

## Exact Required Behavior

When C2 `window.view().compression_required is True`:

1. C3 must not call C2 `_materialize_group_context_window`, read any group fragment text, create a digest, call/import a Provider/LLM, or persist/cache/log/audit/outbox the group body/window.
2. Return a real private `_Stage08CompositeContext` with valid `CompositeContextView`:
   - `status="group_compression_pending"`;
   - `group_compression_required=True`;
   - `group_status` and `group_window_fragments` copied only from the C2 safe view;
   - `group_rendered_fragments=0`, `group_rendered_chars=0`;
   - C1 internal evidence counts/chars retained if current C1 status is `internal_evidence`; C1 general marker remains unrendered and zero-count; total equals C1 content only.
3. The object may retain the exact opaque C2 authority/window only as an in-process future Package E handoff. Its repr/view/JSON error paths cannot disclose body, handles, IDs, C1 plan/actor or source references; no new public handoff API is created.
4. `render_stage08_composite_context` must recompose before any output. If the original pending lineage is still valid and current C1 has internal evidence, it may return only current C1 renderer output. It must never include raw group fragment text. If C1 is only general/no evidence, return `None`. If original pending authority/window/handle/view/provenance/lifecycle/mapping/member/binding/relation/retention drifted or was forged, return `None`, not a C1 fallback that falsely looks like a valid pending handoff.
5. If currently recomposed C2 changes from pending to direct/unavailable, an original pending composite still requires explicit rebuild: return `None`; do not quietly consume newly materialized group text.
6. Maintain direct-path behavior unchanged. Any `compression_required=True` source remains safely non-consumable to callers other than future Package E.

## TDD Corpus

Before changing production code, add high-window tests using current verified C2 projections totaling strictly over 24,000 but within 60,000 / 120 / 500 limits. Run RED. Cover:

- safe pending view exact arithmetic/status and opaque repr;
- monkeypatched C2 materializer that fails if called proves C3 never loads raw body on pending path;
- renderer with C1 internal evidence renders C1 current evidence only, never a group secret; general/no C1 returns `None`;
- no Provider/network/persistence/Memory/audit/outbox/Redis/LangGraph imports/calls or side effects;
- after initial pending composition, projection purge/source type/mapping version/member/binding/relation/retention/view/actor drift or forged safe window/handles makes renderer `None`;
- an original pending composite cannot silently render newly direct group evidence if current window later falls below pending threshold;
- direct C2 existing regression remains unchanged.

Run focused RED first, then GREEN:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py -W error
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Then rerun Task1+C1+C2+Task2+Task3 units, compileall, prohibited scan and scoped diff check. Record actual outputs. Fresh independent review is mandatory; do not claim Task 4/C3/Package C completion.
