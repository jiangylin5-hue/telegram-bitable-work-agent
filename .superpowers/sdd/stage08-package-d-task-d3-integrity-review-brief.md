# Stage08 Package D / D3 Integrity Remediation Independent Review Brief

## Boundary

Independently review only the D3 remediation in `stage08-package-d-task-d3-integrity-remediation-brief.md`, against the D3 contract/BDD, original review report, updated D3 report, and current code/tests. Create or modify only `stage08-package-d-task-d3-integrity-review-report.md`. Do not modify application/tests/contracts/models/migrations/UoW/API/Docker/configuration/database/Git state or external systems.

## Required Functional Checks

1. Establish a normal indexed source with explicit test provider. Change indexed metadata and, separately, replace its vector with a different finite eight-value vector. Replay must synchronously leave no readable indexed chunk/material, return only `knowledge_index_failed`, leave the event unprocessed, avoid new rows, and avoid unrelated source-version mutation.
2. Cause post-lock `list_knowledge_chunks` to fail in index and cleanup independently. Each result must be fixed `knowledge_index_failed`, with source/chunk/event unchanged and no sentinel/error detail in result/repr/persisted state.
3. Return an oversized integer or abnormal iterable/element from a provider batch. Worker must return exactly `embedding_output_invalid`, leave event pending, and create no partial readable/pending/failed rows.
4. Confirm normal valid index/replay and valid cleanup/replay still work; cleanup active/hash-mismatch sources remain denied; explicit TestHash profile/runtime isolation remains intact.
5. Re-run dedicated Docker pgvector evidence, including finite vector drift scrub/replay and HNSW/GIN/no-default-DB behavior.

## Required Commands

Run from `backend`, warnings as errors and cache disabled:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py
```

Inspect current source/diff for no external provider/network/Telegram/LLM/API/Milvus additions and no raw data persistence. Report Critical/Important/Minor and exact command results. Only `0 Critical / 0 Important` permits D3 closure consideration; explicitly state that Package D/D4/D5/production remain open.
