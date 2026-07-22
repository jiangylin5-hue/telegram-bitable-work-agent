# Stage08 Package D / D4 Independent Review Brief

## Review Boundary

Independently review D4 against its implementation brief, Package D contract/BDD, current D1–D3 services, existing C1/Memory/employee authority rules, D4 report and the actual current source/tests. Create or modify only `stage08-package-d-task-d4-review-report.md`. Do not modify production/test/contracts/models/migrations/UoW/API/Docker/config/database/Git or external systems.

## Required Functional Review

1. Authority creation/revalidation: valid employee/member scope succeeds; forged/unavailable/stale/cross-workspace/employee-inactive/access-mode/member grant/base-table-view/business relation drift fails closed. Authority/private hit repr and serialization paths must not reveal identifiers or content.
2. Candidate narrowing: require active workspace/source/indexed chunk/profile/status and exact structured employee/business scope before ranking. Validate SQLAlchemy PostgreSQL path contains actual `keyword_terms &&` GIN candidate operator and pgvector cosine `<=>` expression for explicit test vector mode, rather than in-memory-only approximation or raw SQL.
3. Source consumption re-read: Memory candidates must use read-only projection only and drop revoked/expired/superseded/version/hash/scope/relation drift after selection; group/Telegram/raw source carriers remain ineligible. No lifecycle/audit side effect from search.
4. Ranking/degradation: injected test-only embedding permits deterministic hybrid order; default has no TestHash/runtime external provider and returns explicit keyword-only degradation without synthetic vector score. Limit remains 12, stable ties return no score/ID.
5. Rendering/citation: revalidate authority/source/chunk immediately before private render; revocation/replacement/stale chunk drops evidence. Safe citation/view DTOs and errors/repr contain no UUIDs, source/chunk/record/field IDs, names, URLs, query, content, score, vector, profile, actor or authority.
6. Dedicated pgvector evidence: run only against `STAGE08_RAG_DATABASE_URL`; verify HNSW/GIN existing indexes, real GIN/vector predicate behavior, structured narrowing/re-read drift, and no default/native database fallback.

## Required Fresh Commands

Run from `backend` with warnings as errors and cache disabled:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/runtime/stage08_retrieval_contracts.py app/services/stage08_retrieval_provider.py
```

Run static/diff inspection. Classify Critical/Important/Minor. Only `0 Critical / 0 Important` permits root-level D4 closure consideration; report that D5/Package D/Stage08/real semantic provider/production remain open.
