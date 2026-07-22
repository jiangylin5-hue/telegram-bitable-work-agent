# Stage08 Package C — C3 Direct-to-Pending Remediation Independent Review

## Scope

Independently review only the remediation for the Package C Task 5 Important
direct-to-pending defect. You may update only
`.superpowers/sdd/stage08-package-c-c3-pending-transition-remediation-review-report.md`.
Do not edit implementation, tests, schema, API, permissions, migrations,
database, Git state, active source documents, or external systems.

Read:

- `stage08-package-c-c3-pending-transition-remediation-brief.md`
- `stage08-package-c-c3-pending-transition-remediation-report.md`
- `stage08-package-c-task-c3-task-5-review-report.md`
- `backend/app/services/stage08_context_composition.py`
- `backend/tests/unit/test_stage08_context_composition_service.py`
- the approved C3 design/plan.

## Required security and contract checks

1. Independently reproduce the original unit regression: compose direct, make
   current C2 a real `49 × 500 = 24,500` pending window, render the old
   composite. Confirm pre-fix RED accurately observed empty output and C2
   materializer invocation.
2. Verify the remediation makes the rendering choice from the current,
   revalidated composite—not from stale original direct state. If current state
   is pending and C1 is still eligible, output exactly current C1 evidence.
3. Verify no C2 materialization, raw group body, truncation, summary/digest,
   Provider/network/Telegram call, persistence, log/audit side effect, opaque
   object or safe-view leak happens in this transition.
4. Attack adjacent paths: stale C1 must fail closed; current pending lineage
   drift/forgery must fail closed; old pending/direct/unavailable paths must
   preserve their existing intended behaviour and ordering; direct C1+C2
   still renders C1 first with authorised D6 headers.
5. Run focused service tests with `-W error`, C1/C2/C3 unit regression,
   compileall and static external-dependency/privacy/diff checks. Record exact
   output or why unavailable.

## Outcome

Report Critical / Important / Minor, evidence and PASS/FAIL. A PASS repairs
only the task-level remediation; it does not close C3 or Package C. The
package-level Task 5 reviewer must subsequently rerun its independent review.
