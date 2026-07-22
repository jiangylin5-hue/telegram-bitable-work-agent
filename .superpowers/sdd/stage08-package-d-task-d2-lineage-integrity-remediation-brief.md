# Stage08 Package D / D2 Lineage Integrity Remediation Brief

## Status

- Status: `approved corrective implementation boundary`
- Trigger: fresh D2 remediation review proved that a same-workspace, incrementing `supersedes_id` can still connect unrelated Memory identities and incorrectly replace a Knowledge source.
- Scope: narrow safety correction only. It implements the approved “valid supersession lineage” rule; no schema, public API, permission, provider, external system, or deployment change is authorized.
- Gate: D2 and D3 remain blocked until a fresh independent review passes with zero Critical/Important findings.

## Allowed Files

- Modify: `backend/app/services/stage08_retrieval.py`
- Modify: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modify: `.superpowers/sdd/stage08-package-d-task-d2-report.md`

Do not modify models, migrations, runtime contracts, UoW interfaces, API, Docker, embeddings/retrieval providers, Memory service behavior, C1/C2, Package B, environment, Git state, or an external system.

## Required Correction

When resolving the root of a `MemoryItem.supersedes_id` chain, every predecessor must pass all current structural checks **and** prove the same existing Memory logical identity as the active current item:

```text
predecessor.memory_type == current.memory_type
canonical(MemoryScopeProjection(predecessor.scope))
    == canonical(MemoryScopeProjection(current.scope))
```

`MemoryScopeProjection` validation must happen before comparison and covers all scope fields, including `identity_token`. Do not compare raw dicts or payload/source refs. A type mismatch, any normalized scope mismatch, invalid scope, or identity-token mismatch must fail closed before source/event creation. It must not lock, replace, stale, clear, clean up, or link any existing Knowledge source.

The real valid new-row supersession flow must remain intact: same type and normalized scope, incrementing version, old `superseded`, current `active`, root fingerprint continuity, old source `replaced`, old chunks stale, one cleanup event and one new index event; replay remains idempotent.

## Required TDD and Evidence

Write RED tests before production correction:

1. Construct valid `decision` A1 → A2 and an unrelated valid `preference` B in the same workspace. Tamper B to reference A1 with a superficially valid incrementing version. Registration of B must return the safe no-registration result and leave A1 Knowledge source/chunks/events unchanged.
2. Repeat with the same memory type but one changed scope component (including a different `identity_token`); prove no source/event side effect.
3. Retain/execute all prior valid real supersession and trace-ref regressions. They must stay GREEN.

Run from `backend`:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m compileall -q app/services/stage08_retrieval.py
```

Update the existing D2 evidence report with RED/GREEN results and the new logical-identity boundary. Do not declare D2 or Package D complete; await a fresh independent review.
