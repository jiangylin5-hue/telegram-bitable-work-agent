# Stage08 Package D / D2 Lineage Integrity Independent Review Brief

## Review Boundary

Perform a fresh independent review of the second D2 remediation. Read the D contract, the two remediation briefs, both earlier review reports, the updated D2 evidence report, actual service/test diff, and the existing Memory materializer logical-identity implementation. This review may create or modify only `stage08-package-d-task-d2-lineage-integrity-review-report.md`. Do not modify code, tests, contracts, migrations, database, Docker, Git state, configuration, or external systems.

## Must Independently Reproduce

1. **Valid flow stays valid.** Use the real `materialize_memory_from_projection` twice for one identity and verify a new UUID/new active row, root fingerprint continuity, old Knowledge source `replaced`, old indexed chunk `stale`, single cleanup, new index, and replay idempotency.
2. **Cross-type collision is rejected.** Create valid decision A1 → A2 and unrelated preference B in one workspace. Tamper B's `supersedes_id` and superficial version to point at A1. Registering B must return no registration and leave A1 source status/text/link, indexed chunk, source count, and events exactly unchanged.
3. **Same type / scope drift is rejected.** Repeat using the same `memory_type` but respectively a different table/base/customer/project scope value and a different `identity_token`. Any normalized `MemoryScopeProjection` inequality must fail closed with the same no-side-effect guarantees.
4. **Trace fix remains sound.** Verify exact SHA-256 derived persistence for index and cleanup paths, raw sentinel absence from observable output, and invalid trace rejection.
5. **Boundary remains intact.** No direct Memory payload read, C2/group/Telegram admission, provider/network/API/worker behavior, or unintended model/migration/UoW/API change.

## Required Fresh Commands

Run from `backend` with warnings as errors:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m compileall -q app/services/stage08_retrieval.py
```

Inspect diff/scope statically. Classify Critical/Important/Minor. Only `0 Critical / 0 Important` allows D2 closure consideration. Explicitly state that PostgreSQL/pgvector, external provider, Telegram, API and deployment evidence are not part of this D2 review.
