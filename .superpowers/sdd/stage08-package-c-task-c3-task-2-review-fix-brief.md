# Stage08 Package C3 — Task 2 Review-Finding Fix Brief

## Trigger

The independent Task 2 review is `CHANGES REQUIRED` with one Important and one Minor. Repair only these findings, using TDD; do not begin Task 3 or mark Task 2/C3 complete.

## Exact Scope

Modify only:

- `backend/app/services/stage08_context_composition.py`
- `backend/tests/unit/test_stage08_context_composition_service.py`
- `.superpowers/sdd/stage08-package-c-task-c3-task-2-report.md`

You may create a narrow remediation report under `.superpowers/sdd/`. Do not alter C1/C2, contracts, schema/migration, API, permissions, Telegram/Provider/Memory/RAG/Redis/LangGraph/audit/outbox/Mini App/deployment, database, or Git state.

## Important — forged zero-fragment window lineage bypass

Before the fix, `_original_group_window_drifted` treats `window.view().usage.selected_fragments == 0` as no drift without checking opaque handles. A real composite that originally held a group fragment can have its private C2 `_view` replaced with a structurally valid unavailable/zero view; after mapping-version drift, renderer then accepts newly composed C2 group content and bypasses the old opaque lineage safety check.

Add a genuine RED that:

1. Creates a valid direct-group composite with a secret fragment.
2. Changes original mapping version (so normal renderer excludes secret).
3. Replaces only `composite._group_window._view` with a structurally valid zero/unavailable `GroupContextWindowView`.
4. Demonstrates pre-fix renderer wrongly renders the secret/current C2 group content rather than returning `None`.

Minimal correction must bind original window safety metadata to its actual opaque handle set and the composite’s original group-rendered count before treating any zero-fragment path as non-drift. At minimum, validate exact window/authority/handle classes, nonce/mapping relationship, handle tuple length against window view selected count, and original composite safe view group count. A structurally valid forged view/handle mismatch returns `None`; it must not fall back to C1-only or a newly composed group body. Preserve legitimate original no-group composites.

## Minor — budget branch coverage

Replace the `SimpleNamespace` fake in the over-budget test with exact private C2 materialization/fragment types or another test arrangement that passes type/shape guards and reaches the actual C3 `>24,000` / `>36,000` budget check. Assert no renderer text and safe no-consumer composite. Do not weaken production type guards merely to accommodate a fake.

## Verification

Run new RED(s), then focused GREEN with warnings errors. Re-run Task1+C1+C2+Task2 unit regression, compileall, prohibited-dependency scan and scoped diff check. Record actual outputs, scope exclusions, cleanup, and that fresh re-review remains required.
