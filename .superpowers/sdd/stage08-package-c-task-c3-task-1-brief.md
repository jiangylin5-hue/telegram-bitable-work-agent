# Stage08 Package C3 — Task 1 Strict Composition Contracts Brief

## Authority

Implement only Task 1 of `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md`, following `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md`. C1 and C2 are closed dependencies; do not change their public contracts.

## Scope

Create only:

- `backend/app/runtime/stage08_context_composition_contracts.py`
- `backend/tests/unit/test_stage08_context_composition_contracts.py`
- `.superpowers/sdd/stage08-package-c-task-c3-task-1-report.md`

Do not modify existing production code, C1/C2, schema/migrations, routes/API, permissions, Telegram, Provider/LLM, Memory/RAG/vector, Redis, LangGraph, audit/outbox, Mini App, deployment, or any unrelated worktree file. Do not stage, commit, reset, checkout, clean, or touch a database.

## Exact Contract

This module is only a strict Pydantic safe-view contract; it must contain no body/renderer/handle/actor/plan/scope-value/digest/source-reference field and no `UUID` field.

Define constants:

- `COMPOSITE_CONTEXT_C1_MAX_CONTENT_CHARS = 12_000`
- `COMPOSITE_CONTEXT_GROUP_MAX_DIRECT_CHARS = 24_000`
- `COMPOSITE_CONTEXT_MAX_CONTENT_CHARS = 36_000`
- `COMPOSITE_CONTEXT_MAX_C1_EVIDENCE_ITEMS = 24`
- `COMPOSITE_CONTEXT_MAX_GROUP_FRAGMENTS = 120`

Define frozen, strict, `extra="forbid"` models:

1. `CompositeContextBudgetUsage`
   - `c1_evidence_items: StrictInt` 0..24
   - `group_window_fragments: StrictInt` 0..120
   - `group_rendered_fragments: StrictInt` 0..120
   - `c1_content_chars: StrictInt` 0..12000
   - `group_rendered_chars: StrictInt` 0..24000
   - `total_content_chars: StrictInt` 0..36000
   - validators require rendered fragments <= window fragments and `total_content_chars == c1_content_chars + group_rendered_chars`.
2. `CompositeContextView`
   - `contract_version: Literal["stage08-composite-context.v1"]`
   - `status: Literal["internal_evidence", "group_compression_pending", "general_advice_only", "no_evidence"]`
   - `c1_status: Literal["internal_evidence", "general_advice_only", "no_evidence"]`
   - `group_status: Literal["group_context_unavailable", "group_context_partial", "group_context_available"]`
   - `group_compression_required: StrictBool`
   - `usage: CompositeContextBudgetUsage`
   - validators:
     - pending iff `group_compression_required is True`; pending has no rendered group fragment/body chars.
     - non-pending must have `group_compression_required is False`.
     - `internal_evidence` has at least one C1 evidence item or rendered group fragment, and cannot include general-advice-only C1 marker.
     - `general_advice_only` requires C1 general advice, group unavailable, zero rendered group, and zero content chars; it is a marker rather than internal content.
     - `no_evidence` requires C1 no evidence, group unavailable, zero items and chars.
     - C1 general advice with a usable direct group must be represented as `internal_evidence`, not as a general marker.
3. Export `validate_composite_context_view(view: CompositeContextView) -> CompositeContextView` that deeply reconstructs nested usage from attributes/dicts (do not trust subclass or `model_construct` identity).

Use stable validation code messages beginning `composite_context_`; do not include values in errors. No text/identifier field is permitted even as a private alias in these Pydantic models.

## TDD

Write tests first for:

- import/collection RED before the module exists;
- constants and valid direct/pending/general/no-evidence shapes;
- 36,000 arithmetic and all caps;
- pending with text-equivalent rendered chars/fragments rejected;
- invalid status/flag/c1/group combinations rejected;
- `extra` carrier fields named `content`, `renderer`, `digest`, `actor`, `plan`, `scope`, `chat_id`, `message_id`, `source_ref`, `uuid` rejected;
- nested `model_construct`/subclass bypass fails through `validate_composite_context_view`;
- `model_dump(mode="json")`, `repr` and validation errors contain none of test secret/UUID-like markers.

Run RED, implement the smallest GREEN contract, then run:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_contracts.py
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
python -m compileall -q backend/app/runtime/stage08_context_composition_contracts.py
git diff --check -- backend/app/runtime/stage08_context_composition_contracts.py backend/tests/unit/test_stage08_context_composition_contracts.py .superpowers/sdd
```

## Report

Record actual RED/GREEN command outputs, scope exclusion, static privacy check, skipped tests and cleanup. Return only status, exact verification, changed files, risks and report path. Do not claim C3/Package C completion.
