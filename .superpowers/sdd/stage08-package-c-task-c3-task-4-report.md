# Stage08 Package C3 / Task 4 — Disposable PostgreSQL Composition Report

## Status

- Task status: `implementation complete; pending independent review`
- Scope: C3 private composition and renderer against disposable local PostgreSQL only.
- Not claimed: C3 / Package C completion, Package E/F, provider/LLM validation, Telegram execution, deployment, or production readiness.

## Changed files

- `backend/tests/integration/test_stage08_context_composition_postgres.py`
  - Added 12 real PostgreSQL integration cases using the established disposable `stage06_postgres` fixture. Every case rolls back and closes its session.
  - Seeds C1 business/view/employee state and C2 active binding/mapping/projection state through existing services; the source Message shell has no body fields populated.
  - Proves unchanged direct composition renders fresh C1 evidence before authorised D6 group fragments in deterministic order.
  - Proves consumption-time C1 re-read after relation/record and field-visibility drift; lifecycle, source-version and scope drift each remove stale Memory evidence.
  - Proves active-mapping, business-relation, provenance/source-chat-type, retention-expiry and authorised-purge C2 drift never emits the stale group fragment. Where C1 remains current, the old direct composite renders only fresh C1 content.
  - Proves a 49 × 500-character (24,500-character) pending C2 window fails closed after group provenance drift and exposes no group body in renderer, safe view or private repr.
- `.superpowers/sdd/stage08-package-c-task-c3-task-4-report.md`
  - Records actual RED/GREEN and bounded verification.
- `project-docs/08-implementation/evidence/stage08-package-c3-composition.md`
  - Records the durable local PostgreSQL evidence for the later independent review.

No production C3 source was changed. The existing C3 renderer satisfied the approved re-read semantics against real PostgreSQL once the test fixture represented a legal C1/C2 state.

## Independent-review evidence remediation

The first version of this report placed an initial `7 passed, 3 failed` run
next to the final `12 passed` run without stating that the collection had
grown by two cases in between. That made the RED evidence non-auditable. This
section replaces that implication with the exact staged timeline below.

The initial source snapshot was an untracked working-tree file and was not
retained as a separate artifact. Therefore, this report does **not** claim
that the first RED run covered the final 12-item corpus. The verifiable facts
are the captured runner counts and failure names, the current collect-only
output, and the explicit source change recorded below.

| Step | Collection | Actual result | Reason |
| --- | --- | --- | --- |
| T0 initial RED | 10 items | `7 passed, 3 failed in 17.69s` | First PostgreSQL execution of the new file. |
| T1 legal-fixture GREEN | same 10 items | `10 passed in 15.26s` | Corrected only invalid test fixture values. |
| T2 coverage expansion | 12 items | targeted Memory cases `3 passed in 6.31s`; module `12 passed in 20.03s` | Added separate source-version and scope drift cases required by the brief. |
| T3 remediation re-run | 12 items | C3 unit `63 passed in 1.50s`; module `12 passed in 17.29s`; focused C1/C2/C3 `211 passed in 48.59s` | Fresh reproducible evidence after this remediation. |

### T0 initial 10-item collection

The contemporaneous runner output proves `7 + 3 = 10` collected items. Its
failure stack named the then-single Memory case
`test_composition_postgres_rereads_memory_lifecycle_before_render`. The 10
items at that point were:

1. `test_composition_postgres_direct_render_is_current_and_c1_first`;
2. C1 business-state `record_relation` and `field_visibility`;
3. the single Memory `lifecycle` case named above;
4. C2 drift `mapping`, `relation`, `provenance`, `retention`, and `purge`;
5. `test_composition_postgres_pending_group_drift_fails_closed`.

The three T0 failures were that single Memory fixture plus C2 `retention` and
`purge`. They occurred before a C3 renderer contract assertion: the Memory
payload did not match its source field, and retention equalled the event time,
which PostgreSQL rejected through `retention_after_event`.

### T1 legal-fixture green for the original 10

The Memory payload was made equal to the existing platform-record `title`,
and the C2 projection was made one minute older before setting retention to
`NOW`. Neither change altered production code, C1/C2 state semantics, or the
assertions under review. The same 10 collected scenarios then produced
`10 passed in 15.26s`.

### T2 deliberate 10 → 12 coverage expansion

After the original lifecycle case was green, the single test was changed to
the current parameterized
`test_composition_postgres_rereads_memory_state_before_render` with
`lifecycle`, `source`, and `scope`. This intentionally adds exactly two
items—`source` and `scope`—so the Task 4 brief's “Memory
lifecycle/source/scope drift” is independently covered. It is a test-coverage
addition, not a fix for a production defect. The current collection is
reproducibly:

```text
12 tests collected in 2.21s
```

The current twelve node IDs are one direct item, two C1 business-state items,
three Memory-state items, five C2 drift items, and one pending item; the exact
node IDs are captured in the remediation evidence document.

## Historical RED / staged GREEN evidence

### Initial RED — 10-item source snapshot only

Before any production change, the new file was run with the disposable database:

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m pytest -q tests/integration/test_stage08_context_composition_postgres.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

Actual: `7 passed, 3 failed in 17.69s` (`10` collected items, not the later
12-item corpus).

The failures were in the new test setup, before the C3 renderer contract was reached:

1. The Memory fixture used a payload value different from the current platform-record field, so the existing Memory source validator correctly rejected materialisation.
2. Retention was set equal to the projection event time, violating the existing PostgreSQL `retention_after_event` check constraint before any C3 read.

This was not a C3 production defect and did not justify changing C1/C2 persistence or C3 runtime code. The fixture was corrected to use the current source value and an event one minute before expiry, then rerun.

### GREEN — original 10, then separately expanded 12

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m pytest -q tests/integration/test_stage08_context_composition_postgres.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

After the legal fixture correction but before the deliberate source/scope
coverage expansion, the original collection was `10 passed in 15.26s`.
After T2, the expanded collection was `12 passed in 20.03s`.

The retention and authorised-purge cases confirm the approved direct-path rule: an old direct composite must never render stale group content; it may still render fresh C1 content when C1 remains current. The pending-path case remains stricter and returns `None` after C2 lineage drift.

## Final verification

The required disposable PostgreSQL focused corpus was run after `alembic upgrade head`:

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/integration/test_stage08_context_postgres.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage08_context_composition_postgres.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

Actual results:

- Alembic single head: `20260720_0031 (head)`.
- Historical focused C1/C2/C3 corpus: `211 passed in 51.97s`.
- Remediation re-run: C3 contracts/service `63 passed in 1.50s`; current
  12-item PostgreSQL module `12 passed in 17.29s`; full focused C1/C2/C3
  corpus `211 passed in 48.59s`.
- `python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py`: exit `0`.
- Prohibited production-source scan for raw Message fields, Telegram/network/provider/API/Redis/vector/LangGraph/Memory persistence/audit/outbox/`ContextCompressor`/digest: zero matches.
- `git diff --check -- backend project-docs/08-implementation docs/superpowers`: exit `0`; only pre-existing worktree LF/CRLF warnings were printed.

## Boundaries and cleanup

- All test rows existed only in the disposable local database and each test rolled back and closed its session.
- No Telegram, OpenRouter, HTTP, provider, Redis, vector, LangGraph, API, schema, migration, permission or audit/outbox operation was added or called.
- No group body was written to evidence, public DTO, safe view, exception or log artifact.
- No temporary script, background process, database migration or external record was retained.

## Remaining risk

- Task 5 independent review remains required. It must review this real PostgreSQL evidence together with C1/C2 compatibility, pending/direct distinctions and the full C3 privacy boundary.
- The known default `DATABASE_URL` orphan-revision deployment preflight risk remains outside Task 4 and was not changed.
