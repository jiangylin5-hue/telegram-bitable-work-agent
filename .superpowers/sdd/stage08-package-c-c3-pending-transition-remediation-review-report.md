# Stage08 Package C — C3 Direct-to-Pending Remediation Independent Review

## Scope and conclusion

- Review date: 2026-07-20
- Reviewed only the direct-to-pending renderer remediation described in
  `stage08-package-c-c3-pending-transition-remediation-brief.md`.
- Reviewer action: this report only. No implementation, test, schema, API,
  permission, migration, database, Git, or external system was changed.
- **Conclusion: PASS / 0 Critical / 0 Important / 0 Minor.** The remediation
  repairs the task-level direct-to-pending defect. It does **not** close C3 or
  Package C; the package-level Task 5 reviewer must still perform its fresh
  independent review.

## Independent reproduction of the original defect

Without changing source files, I constructed an in-memory direct C3 composite
with one 500-character authorized group projection, then added 48 additional
500-character projections. The current C2 window was therefore exactly
`49 × 500 = 24,500` characters and the fresh C3 result was
`group_compression_pending` with 49 window fragments.

I evaluated the pre-remediation decision sequence against that same state:

```text
original_direct_status=internal_evidence
current_status=group_compression_pending
current_fragment_count=49
historical_branch_drift=False
historical_branch_output=''
historical_materializer_calls=1
```

This independently confirms the prior RED report: the stale direct branch
would have returned the empty string and called the C2 materializer despite
the now-pending window.

The repaired public renderer on the same in-memory objects produced current
C1 evidence, did not contain the old group fragment, and had a 173-character
output:

```text
fixed_output_has_c1=True
fixed_output_has_old_group=False
fixed_output_length=173
```

## Contract and security assessment

`render_stage08_composite_context` first recomposes the current C1/C2 state.
When that fresh state is `group_compression_pending`, it now dispatches the
fresh private object to `_render_pending_composite` instead of continuing into
the original direct materialization path. `_render_pending_composite` requires
an internal current C1 pack and revalidates the pending C2 authority, window,
view, selected-count and projection-handle lineage before returning C1 only.
It does not call the C2 materializer.

Additional independent in-memory attacks all failed closed:

```text
stale_c1_result_is_none=True
pending_lineage_drift_result_is_none=True
pending_lineage_forgery_result_is_none=True
```

They respectively exercised a C1 view change after the old direct composite,
a mapping-version change after current recomposition but before pending
lineage validation, and a forged current pending projection handle. Existing
service cases that passed in the focused corpus also cover initially pending
to direct rejection, unavailable-group C1 preservation, direct C1-first/D6
ordering, pending lineage drift, and pending window forgery.

No raw group body is returned on the transition; neither old nor newly added
group fragments appear in the rendered output. The pending branch creates no
truncation, summary, digest, provider/network/Telegram call, persistence,
audit/log side effect, or safe-view/private-object disclosure. The review used
only `InMemoryStage06PlatformUnitOfWork`; no PostgreSQL, Redis, provider,
Telegram, or network resource was accessed.

## Verification

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py -W error
```

Actual: `38 passed in 1.58s`, with warnings promoted to errors.

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py -W error
```

Actual: `196 passed in 2.09s`, with warnings promoted to errors.

```powershell
Push-Location backend
python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py
```

Actual: exit `0` with no compiler output.

The production composition contract/service source was scanned for raw-message,
Telegram, HTTP, provider/LLM/compressor, API, Redis/vector, LangGraph, memory
persistence, agent-run, audit/outbox, and digest dependencies. Result: `0`
matches. `git diff --check` over the remediation source, test, and report paths
exited `0` with no whitespace errors.

## Remaining boundary

This is a narrow remediation review only. It does not replace the required
fresh package-level C3/Package C review, disposable PostgreSQL composition
evidence, Package D retrieval, Package E compression/LangGraph ownership,
Package F evaluation/operations, real LLM quality tests, Telegram external
validation, staging, or deployment gates.
