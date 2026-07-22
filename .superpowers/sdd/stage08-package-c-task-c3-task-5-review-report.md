# Stage08 Package C / C3 Task 5 — Package-Level Independent Handoff Review Report

## Review scope and conclusion

- Review date: 2026-07-20
- Scope: Package C only (C1, C2 D1–D6, and C3 Tasks 1–4). This review does not assess Package D/E/F, real Provider or LLM quality, Telegram external activity, staging, or deployment.
- Permitted review action: created this report only. No implementation, test, migration, API, permission, active source document, Git state, or external system was changed. The mandated migration/test command used only `STAGE06_LOCAL_DATABASE_URL`; no default `DATABASE_URL` was used as evidence and no production/staging system was contacted.
- **Conclusion: FAIL.** Package C is not eligible for root-level documentation closure or handoff to Package D until the Important finding below is fixed, covered by a regression test, and independently re-reviewed.

## Findings

### Critical

None found.

### Important

1. **A direct composite that becomes compression-pending before render loses still-current C1 evidence.**

   The C3 design requires the renderer to recompose current state before output (design §4 step 83). Its state table also requires `compression required` to render current C1 internal evidence while retaining the group window only for Package E (design §5, row 4). The implementation does recompose in `render_stage08_composite_context`, but a composite originally built as direct continues into the direct branch. When the fresh composition is now `group_compression_pending`, its private `_blocks` is intentionally empty. The branch then returns `"\n\n".join(current._blocks)`, which is an empty string rather than rendering the fresh C1 pack or returning `None`.

   Independent in-memory reproduction, without modifying a file:

   1. Create an ordinary direct composite with valid C1 business evidence and one group fragment.
   2. Add 48 further 500-code-point controlled fragments. The new C2 window is over 24,000 code points and the fresh composite reports `group_compression_pending`.
   3. Render the original direct composite.

   Actual output:

   ```text
   original=internal_evidence
   current=group_compression_pending
   rendered=''
   contains_c1=False
   contains_old_group=False
   ```

   This does not disclose stale group text, but it violates the approved pending degradation behavior and passes a non-`None`, empty result to the future Package E call path. The implementation should explicitly handle a freshly pending recomposition: do not materialize, truncate, summarize, or render group text; render only the currently validated C1 internal pack when it exists, otherwise return `None`. Add regressions for direct-to-pending with current C1 evidence and for the no-internal-C1 case.

### Minor

1. `test_tampered_private_group_window_view_fails_closed` in `backend/tests/unit/test_stage08_context_composition_service.py` currently ends after fixture/composite construction (lines 397–403) and has no tamper operation or assertion. It therefore supplies no coverage despite its safety-oriented name. Replace it with the intended assertion or remove/rename it; this is a test-quality issue, not an observed runtime disclosure.

## Checks that passed

### C1/C2 preservation and C3 boundary

- C3 production source exposes only the two intended internal service entry points, `compose_stage08_context` and `render_stage08_composite_context`, plus strict count/status safe-view contracts. The composite is a slotted private object; its `repr` is count/status-only and safe view validation rehydrates the approved fixed fields.
- C3 source imports neither Telegram `Message` nor historical raw body fields, and the production dependency/privacy scan returned zero matches for raw-message, Telegram/network, Provider/LLM, API route, Redis/vector, LangGraph, Memory persistence, audit/outbox, `ContextCompressor`, and digest boundaries.
- The C2 controlled projection path remains the sole source available to C3. Full C1/C2/C3 regression passed, including C2 D1–D6 bounds and current-state checks: authorised group/supergroup projections; 30-day/120-fragment/60,000-code-point/500-character limits; historical raw body exclusion; lifecycle best-effort behavior; exact active mapping; opaque authority; and D6-only renderer categories.
- The existing 49 × 500 = 24,500 pending tests and PostgreSQL pending drift case show that an initially pending composite does not materialize, synthesize, digest, or render group body. The Important finding is specifically the untested inverse transition from an originally direct object to a newly pending current window.
- Direct C1-first ordering, D6 group headers, no-group C1 preservation, provenance/mapping/member/relation/retention/purge drift handling, private-object serialization failure, and safe-view/repr identifier redaction are covered by the successful focused corpus. No C3 schema, API, permission, retention, or persistence change was detected.

### Required disposable PostgreSQL evidence

The approved final command was run after assigning `DATABASE_URL` exclusively from `STAGE06_LOCAL_DATABASE_URL` and restoring it afterwards:

```powershell
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/integration/test_stage08_context_postgres.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage08_context_composition_postgres.py
```

Actual output:

```text
20260720_0031 (head)
211 passed in 50.79s
```

The C3 contracts/service subset also passed with warnings promoted to errors:

```powershell
python -m pytest -q -W error tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py
```

Actual output: `63 passed in 1.72s`.

The complete suite cannot currently be used with `-W error`: collection of the three PostgreSQL modules raises the pre-existing Starlette `TestClient` deprecation warning because `httpx2` is absent, and the warning becomes an error. This is an environment/dependency warning, not a C3 failure; standard-mode local PostgreSQL evidence above remains valid. It must not be represented as a warning-clean full-suite result.

### Static verification

```powershell
python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py
```

Result: exit `0`.

The approved production-source dependency/privacy `rg` scan produced zero matches. `git diff --check -- backend project-docs/08-implementation docs/superpowers` returned exit `0`; it emitted only pre-existing LF/CRLF conversion warnings and no whitespace error.

## Evidence-quality assessment

`project-docs/08-implementation/evidence/stage08-package-c3-composition.md` correctly distinguishes its C3 Task 4 timeline:

- T0 was an initial 10-case integration corpus (`7 passed, 3 failed`) whose failures were fixture constraint failures; it is not represented as the final 12-case corpus.
- T1 repaired the fixture and recorded `10 passed`.
- T2 added the two missing Memory source/scope cases and recorded the expanded 12-case corpus.
- T3 records fresh C3 unit and 12-case PostgreSQL reruns plus the 211-case focused regression.

This distinction is explicit and adequate for the evidence that does exist. It does not cover the newly discovered direct-to-pending transition, so the package evidence is not yet complete.

## Remaining risks and required follow-up

1. Fix the direct-to-pending renderer behavior described in the Important finding; add unit and, where proportionate, disposable PostgreSQL evidence; rerun C3 and the complete approved C1/C2/C3 command; then request a new independent Task 5 review.
2. Resolve or explicitly baseline the Starlette/`httpx2` warning issue before treating a warning-clean full test suite as evidence.
3. Even after Package C later passes, Package D retrieval/RAG, Package E LangGraph and compression ownership, Package F evaluation/operations, real LLM quality tests, Telegram external validation, staging, and deployment remain separate, unstarted or unaccepted gates.

---

## Fresh package-level re-review after direct-to-pending remediation

### Relationship to the first review

This is a fresh, independent re-review after the direct-to-pending remediation
and its separate independent review. It supersedes the **FAIL** disposition at
the top of this report only for the prior Important direct-to-pending finding.
The prior finding was not waived: it was re-attacked against the repaired
renderer, together with the original Package C checks, before this conclusion
was made.

Review scope remained Package C only. Reviewer work in this round was limited
to appending this section. No implementation, tests, migrations, API,
permissions, active source documents, Git state, production/staging system,
Telegram, Provider/LLM, or external system was changed. The required database
verification used `STAGE06_LOCAL_DATABASE_URL` only; it did not use the default
`DATABASE_URL` as evidence.

### Independent remediation attacks

I independently constructed an original direct composite with valid C1
business evidence and one 500-character controlled group fragment. I then
added 48 further controlled 500-character fragments, making the current C2
window exactly `49 × 500 = 24,500` characters and therefore pending. The C2
materializer was replaced with a fail-fast function for the transition.

Actual results:

```text
happy_current_c1=True
happy_no_group=True
happy_materializer_calls=0
stale_c1_is_none=True
pending_lineage_drift_is_none=True
pending_lineage_materializer_calls=0
```

The repaired renderer makes its branch decision from the fresh recomposed
object. When that object is `group_compression_pending`, it now calls the
private pending renderer with the fresh authority/window rather than returning
the old direct object's blocks or entering old direct materialization. Thus
the transition outputs only the current C1 evidence, contains neither the old
direct nor newly added pending group body, and performs no C2 materialization.

I also independently attacked two adjacent failure paths:

- a C1 view/version drift after the old direct composite was formed; and
- a mapping-version change between current pending recomposition and its
  second pending-lineage validation.

Both returned `None`, with the materializer still fail-fast and uncalled. This
confirms current C1 invalidity and current pending lineage drift fail closed.
The focused service corpus retains the existing checks for initially pending
lineage/forgery drift, pending-to-direct rejection, direct C1-first ordering,
D6 headers, unavailable-group C1 preservation, and safe-view/private-repr
redaction.

### Fresh final verification

Using only `STAGE06_LOCAL_DATABASE_URL` and restoring the original environment
variable afterwards:

```powershell
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/integration/test_stage08_context_postgres.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage08_context_composition_postgres.py
```

Actual result:

```text
20260720_0031 (head)
213 passed in 49.56s
```

The two added direct-to-pending regressions explain the increase from the
first review's 211 cases to 213. The focused strict C3 contracts/service run
also passed:

```powershell
python -m pytest -q -W error tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py
```

Actual result: `65 passed in 1.41s`.

`python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py` exited `0`. The approved C3
production dependency/privacy scan again returned zero matches for raw
Telegram-message fields, network/Provider/LLM/compressor, API, Redis/vector,
LangGraph, Memory persistence, AgentRun, audit/outbox, or digest boundaries.
`git diff --check -- backend project-docs/08-implementation docs/superpowers`
exited `0`, with only pre-existing LF/CRLF conversion warnings.

The full PostgreSQL suite still cannot be represented as warning-clean under
`-W error`: the pre-existing Starlette `TestClient`/missing `httpx2`
deprecation warning becomes a collection error. This is an environment
dependency limitation, not a C3 test failure; standard-mode local PostgreSQL
evidence above is the applicable package evidence.

### Evidence and boundary assessment

- The original Task 4 evidence continues to state the T0/T1/T2/T3 timeline
  accurately: its initial 10-case RED was not claimed as the final expanded
  12-case integration corpus.
- The remediation is confined to C3 renderer selection and its service tests.
  It does not alter C1/C2 contracts, D1–D6 retention/authority/mapping
  semantics, schema, API, permissions, or persistence boundaries.
- The original test-hygiene Minor remains: the older
  `test_tampered_private_group_window_view_fails_closed` fixture-only test is
  redundant and should eventually be implemented or removed. It is not a
  runtime defect and does not invalidate the independently exercised tampered
  window/lineage protections above.

### Fresh conclusion

**PASS / 0 Critical / 0 Important / 1 non-blocking Minor.** All required
Package C functional and safety checks, including the formerly failing
direct-to-pending migration, now pass. **Package C is eligible for root-level
documentation closure and handoff to Package D.**

This conclusion is deliberately limited to Package C. It does not declare
Stage08, Package D/E/F, ContextCompressor ownership, RAG, LangGraph runtime,
real LLM evaluation, Telegram external validation, staging, or deployment
complete.
