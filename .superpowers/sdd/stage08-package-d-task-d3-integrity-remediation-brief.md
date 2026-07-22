# Stage08 Package D / D3 Index Integrity & Error Convergence Remediation Brief

## Status

- Status: `approved corrective implementation boundary`
- Trigger: fresh D3 review found three Important failures in replay integrity and safe failure convergence.
- Scope: a minimal correction to existing D3 worker behavior only. No schema, migration, contract, API, permission, provider, Docker, deployment, or external action change is authorized.
- Gate: D3 remains open until this remediation passes a fresh independent review with no Critical/Important findings.

## Allowed Files

- Modify: `backend/app/services/stage08_retrieval.py`
- Modify: `backend/app/services/stage08_retrieval_embeddings.py` only if a pure, explicit deterministic-vector verifier is necessary; do not instantiate/select the test provider as a runtime default.
- Modify: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Modify: `.superpowers/sdd/stage08-package-d-task-d3-report.md`

Do not modify models, migrations, contracts, UoW interfaces, API/routes, Docker/configuration, Memory/C1/C2/Package B code, Git state, or any external system.

## Required Corrections

### 1. Replay must prove immutable index equivalence

For an existing indexed chunk set, replay acceptance requires exact equivalence of source/workspace/version, ordinal, text, hash, keyword terms, profile, embedding version, and all eight finite vector values to the deterministic D3 test-profile result for that chunk text. A merely finite eight-dimensional alternative vector is not equivalent.

If any existing source-version chunk conflicts or is malformed, synchronously make every related existing chunk unreadable before returning the fixed `knowledge_index_failed` result: clear text, terms, vector/profile/version and mark each `stale` (or `deleted` only where existing lifecycle requires it). Do not mark the event processed, create new readable chunks, mutate unrelated source versions, or expose conflict data. Preserve the active source projection so a later controlled reindex/version workflow can decide recovery; this task must not invent source status values or an API.

The deterministic expected-vector check may call a pure explicit helper for the fixed test profile, but must not implicitly instantiate/select `TestHashEmbeddingProvider` as the runtime worker default and must not add an external provider.

### 2. Converge all D3 chunk reads to fixed safe results

Wrap the post-lock `list_knowledge_chunks` call in both index and cleanup workers. Any exception must produce only `KnowledgeIndexResult` or `KnowledgeCleanupResult` with `status="failed"`, `error_code="knowledge_index_failed"`, zero counts, and no source/chunk/event mutation. Do not include exception class/message/body/trace in result/repr, outbox fields, audit, or logs.

### 3. Converge every embedding-output conversion failure

All conversion, iteration, numeric and finite validation inside `_validated_embeddings` must catch `OverflowError` as well as other conversion failures and return invalid output rather than raising. The worker must return only `embedding_output_invalid`, keep the event pending, and create no readable/pending/failed partial chunk. Do not echo provider values or exception text.

## Required RED/GREEN Cases

1. Start with a valid indexed chunk, then mutate indexed metadata and separately mutate it to a different finite 8-vector. Each replay must stale/scrub the old chunk synchronously, preserve no readable indexed chunk, return `knowledge_index_failed`, and not process the event.
2. Simulate `list_knowledge_chunks` raising a sentinel-bearing exception after source lock in index and cleanup flows. Each must return the fixed safe result, retain all preexisting source/chunk/event facts unchanged, and never expose the sentinel in result/repr/event fields.
3. Provide an embedding batch with an integer too large for float conversion and an exceptional iterable/element; each must return `embedding_output_invalid`, leave event pending, and create no readable chunk.
4. Retain valid index/replay, valid cleanup/replay, TestHash default-isolation, full D1/D2/Memory regression, and dedicated pgvector lifecycle evidence.

Run from `backend`:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py
```

Update D3 report with the three original findings, RED/GREEN counts, no-external-action evidence, skipped coverage, cleanup, and the need for fresh independent review. Do not declare D3 or Package D complete.
