# Stage08 Package D / D3 Independent Review Brief

## Review Scope

Independently review Task D3 against its implementation brief, Package D contract/BDD, D1 schema, D2 lifecycle closure, and current implementation. Do not modify production code, tests, contracts, models, migration, Docker, configuration, database fixtures, Git state, or external systems. Create or modify only `stage08-package-d-task-d3-review-report.md`.

## Mandatory Independent Attacks

1. Valid index event with `TestHashEmbeddingProvider` creates only safe indexed chunks, exact test profile/version/eight finite values, and event replay creates no duplicate chunk/event or mutable divergence.
2. `UnavailableEmbeddingProvider`, malformed event/reference/hash/version/workspace, invalid profile/dimension/nonfinite output, partial batch failure, source version drift, revoke/replacement/expiry/delete before worker all fail closed with no readable partial chunk and no source revival. Verify `bool` is not accepted as an integer version.
3. Replaced/revoked cleanup must lock/recheck its source reference, clear source projection and chunk text/terms/vector/profile/version, tombstone chunks, and replay without any rehydration. A forged cleanup for an active source/version must be rejected without loss.
4. TestHash provider is explicit only: no module/runtime default chooses it; no external provider key, OpenAI/OpenRouter, HTTP, network, Telegram, LLM, LangGraph, Redis, or audit body path exists.
5. Run real dedicated pgvector verification with only `STAGE08_RAG_DATABASE_URL`. Validate actual vector persistence and numeric re-read, 8-dimension profile compatibility, existing HNSW/GIN indexes, worker replay, cleanup/read-deny, and no native/default DB fallback.

## Required Fresh Commands

Run in `backend` with cache disabled and warnings as errors:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py
```

Inspect the current source and diffs. Report Critical/Important/Minor separately and exact command outputs. A `PASS / 0 Critical / 0 Important` allows D3 closure consideration only. State skipped full-suite/external/production evidence and cleanup. Any actual provider, public API, schema/migration/UoW change, raw body/trace persistence, non-dedicated database fallback, cleanup resurrection, or default test provider selection is blocking.
