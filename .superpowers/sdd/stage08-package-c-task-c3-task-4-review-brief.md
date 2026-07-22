# Stage08 Package C3 / Task 4 Independent Review Brief

## Review target

Independently review Task 4's disposable PostgreSQL composition evidence and
the changed test/evidence/report files. Write findings only to
`stage08-package-c-task-c3-task-4-review-report.md`. Do not edit production
code, tests, schema, API, documentation outside this review report, Git
state, database, or external systems.

Read first:

- `.superpowers/sdd/stage08-package-c-task-c3-task-4-brief.md`
- `.superpowers/sdd/stage08-package-c-task-c3-task-4-report.md`
- `project-docs/08-implementation/evidence/stage08-package-c3-composition.md`
- `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md`
- `backend/tests/integration/test_stage08_context_composition_postgres.py`
- `backend/app/services/stage08_context_composition.py`

## Required checks

1. Validate that all tests use only the established disposable local PostgreSQL
   fixture, rollback/close their sessions, contain no production database
   assumptions, and have no Telegram/Provider/network side effects.
2. Verify the actual RED history is accurately stated: the original 3 failures
   came from invalid test fixtures blocked before C3 renderer consumption, not
   a falsely dismissed production failure. Confirm the legal corrected setup
   is meaningful.
3. Check direct-path consumption-time behaviour against the approved C3
   design:
   - unchanged direct composite renders C1 before authorised D6 group content;
   - relation/field/record and Memory lifecycle/source/scope changes re-read
     rather than emit stale C1;
   - C2 mapping/relation/provenance/source-chat-type/expiry/purge drift emits
     no stale group text and preserves fresh C1 only where C1 remains eligible;
   - source/retention drift must not fall back to `Message` or raw history.
4. Check a genuine `49 × 500 = 24,500` character pending window and its drift
   path: no group body materialization, summary/digest, unsafe safe view, or
   accidental C1/actor/scope leak.
5. Confirm the test values/queries do not encode or expose restricted IDs,
   raw Message fields, transport objects, or group content through assertion
   failures, artifacts, reports, or public DTOs.
6. Independently reproduce the integration module (if the disposable
   environment is available) and at least the relevant focused regression;
   record exact results. Do not count skipped/unavailable commands as passed.
   Also inspect compile/static external dependency boundary/diff hygiene.

## Outcome

Record Critical / Important / Minor findings, command evidence, scope and a
PASS/FAIL conclusion. Do not declare C3 or Package C complete: Task 5 is the
separate package-level handoff review.
