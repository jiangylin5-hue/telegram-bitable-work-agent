# Stage08 Package C — C3 Direct-to-Pending Renderer Remediation

## Defect and contract

Package C Task 5 independently reproduced this Important defect without file
changes:

1. compose a valid direct C3 composite while its C2 window is at or below the
   direct 24,000-character budget;
2. add enough valid controlled C2 projections to make the current window
   `49 × 500 = 24,500` and therefore `group_compression_pending`;
3. render the old direct composite.

The current renderer recomposes, but then takes the old direct path and returns
`""`, discarding still-current C1 internal evidence. It does not leak group
body, but violates the approved C3 design:

- design §4 step 83: renderer re-runs current composition;
- design §5: any C1 plus compression-required C2 renders only current C1
  internal evidence while retaining opaque pending state for Package E;
- Package E, not C3, remains the sole future compression owner.

## Scope

Make the smallest C3-only correction in:

- `backend/app/services/stage08_context_composition.py`
- `backend/tests/unit/test_stage08_context_composition_service.py`
- a new remediation report under `.superpowers/sdd/`

No C1/C2 modification, migration/schema/API/permission change, database
integration change, external service, Provider, Telegram, RAG, LangGraph,
digest, persistence, Git action, or document-current-progress rewrite is
allowed.

## Required TDD and assertions

1. Add a failing unit regression that composes an originally direct C3 object,
   transitions only current C2 state to a real 24,500-character pending window,
   then renders the old object.
2. RED must prove the old output is empty or otherwise fails to preserve C1;
   record its exact output.
3. Make the minimal renderer correction so it bases rendering on the current
   recomposition state. On this transition it must:

   - render exactly the still-current C1 evidence, if any;
   - never materialize, truncate, synthesize, summarize or render group text;
   - never call a provider/external service or write persistence;
   - fail closed (`None`) if current C1 is invalid or current pending lineage
     is invalid.
4. Add negative assertions that old direct group text and newly added pending
   group text are both absent. Confirm stale C1 still fails closed and existing
   direct/pending scenarios retain their prior expected behavior.
5. Run focused C3 unit, C1/C2/C3 combined regression, compileall, production
   dependency/privacy scan and `git diff --check`; report exact outputs. A
   package-level review will follow, so do not claim Package C or C3 is
   complete.
