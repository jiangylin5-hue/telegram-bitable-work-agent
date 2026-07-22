# Stage08 Package C3 / Task 3 Independent Review Brief

## Review target

Review only the completed C3 Task 3 change set and report the result in
`stage08-package-c-task-c3-task-3-review-report.md`. This is an independent
security and contract review; do not alter implementation, tests, schema,
API, documents outside the report, Git state, database, or any external
system.

## Intended contract

Task 3 adds the C3 composition behaviour for an actual C2 group-context
window that exceeds the direct C3 group budget:

- the regression fixture must be a genuine C2 window of `49 × 500 = 24,500`
  content characters, strictly greater than the C3 direct group budget of
  24,000 and within the C2 contract limits;
- C3 must return a truthful pending safe view, with `compression_required`
  propagated from C2, but must not perform compression itself;
- a pending composition must render C1 content only (if C1 is still valid),
  must not render any group text or synthetic group summary, and must never
  call the C2 group materializer during pending composition or render;
- Package E is the only future owner of compression. C3 may retain opaque
  private state for a future internal consumer, but it must expose no public
  content/handle/window/authority escape hatch;
- direct-path C3 behaviour must remain unchanged.

## Required review checks

1. Inspect the implementation and tests, including the private pending path
   and renderer. Confirm a real over-budget C2 window is used, status and
   `compression_required` arithmetic are truthful, and group blocks/characters
   are absent from the safe view and render output.
2. Verify that pending composition and rendering cannot invoke C2
   materialization, cannot persist data, cannot call LLM/provider/Telegram or
   other external systems, and do not introduce digest/summarization logic.
3. Look specifically for leakage through public properties/functions,
   `repr`/exception text, debug values, safe views, identifiers, or opaque
   authority/window references. Public interfaces must remain the documented
   safe view/render functions only.
4. Attack the lineage checks: stale C1, C2 mapping/projection/source/retention
   drift, forged or swapped window/authority, pending-to-direct substitution,
   and same `user_id` with a changed actor role/scope. Each must fail closed
   without content emission. Confirm legitimate pending rendering preserves
   only current, eligible C1 evidence.
5. Confirm direct C3 composition retains the C1-first then D6 group-header
   order and remains covered by regression tests.
6. Run or independently reproduce proportionate checks, preferably:

   ```powershell
   python -m pytest backend/tests/unit/test_stage08_context_composition_service.py -q -W error
   python -m pytest backend/tests/unit/test_stage08_context_composition_contracts.py backend/tests/unit/test_stage08_context_composition_service.py backend/tests/unit/test_stage08_group_context_authority.py backend/tests/unit/test_stage08_group_context_window.py backend/tests/unit/test_stage08_context_retrieval_service.py -q -W error
   python -m compileall -q backend/app/runtime/stage08_context_composition_contracts.py backend/app/services/stage08_context_composition.py
   ```

   Also perform targeted static inspection for raw group-content emission,
   prohibited external dependencies, and unintended public surface. If a
   check cannot run, record why rather than treating it as passed.

## Review outcome format

Record Critical / Important / Minor findings, exact evidence and commands,
scope confirmation, and a concise PASS/FAIL conclusion. Do not claim Package
C or C3 is complete: Task 4 PostgreSQL integration and Task 5 package review
remain outside this review.
