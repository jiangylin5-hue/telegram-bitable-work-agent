# Stage08 Package D / Task D3 Index Worker, Test Embedding & Cleanup Brief

## Status and Scope

- Status: `approved task-level implementation boundary after D2 closure`
- Consumes: D0 dedicated disposable pgvector environment, D1 source/chunk schema, D2 safe source/outbox lifecycle.
- Produces: internal `EmbeddingProvider` protocol, explicit unavailable/test-only providers, reference-only index/cleanup event consumers, and real dedicated PostgreSQL pgvector lifecycle evidence.
- This task is internal only. No public API, retrieval query provider, LangGraph, external embedding/LLM provider, Telegram, Redis, audit text, document transport, deployment, Milvus, or production database action is authorized.

## Allowed Files

- Create: `backend/app/services/stage08_retrieval_embeddings.py`
- Modify: `backend/app/services/stage08_retrieval.py`
- Modify: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Modify: `.superpowers/sdd/stage08-package-d-task-d3-report.md` (create this evidence report)

Do not modify models, migrations, contracts, UoW interfaces, API/routes, Docker topology, Memory/C1/C2/Package B behavior, runtime defaults, environment configuration, Git state, or any external system. The dedicated local Docker PostgreSQL named by `STAGE08_RAG_DATABASE_URL` may be written only by the authorized integration tests.

## Security and Data Rules

1. PostgreSQL/source records remain the truth. The event is only a reference; worker must re-lock and re-read the source before any indexing/cleanup change.
2. Accept only D2's exact reference-only event shape and derived 64-hex trace reference. No event payload/body/trace/scope/source-ref value may appear in result repr, error text, audit, or logs.
3. `process_knowledge_index_event` requires the event type and aggregate/payload to match one active current source version/hash. It locks the source row, verifies workspace/version/hash/active status/nonempty safe projection, then canonicalizes/chunks from that projection only.
4. An event for replaced/revoked/expired/deleted/missing/drifted source is a safe `discarded` result: it creates no readable chunk and must not revive a source. A processed replay is idempotent and returns the existing indexed count without duplicate chunks.
5. Assemble and validate every chunk and embedding before adding any chunk. A provider failure, invalid profile/dimension/non-finite vector, hash mismatch, cap failure, or duplicate/conflict must leave no partially readable chunk. Use only fixed codes such as `embedding_provider_unavailable`, `embedding_output_invalid`, `knowledge_index_source_invalid`, and `knowledge_index_failed`; never preserve exception/provider/body text.
6. `process_knowledge_cleanup_event` locks and revalidates the referenced source. For a legitimate replaced/revoked/expired/deleted source/version, it synchronously clears `projection_text`, and for every matching chunk clears `chunk_text`, `keyword_terms`, `embedding`, `embedding_profile`, and `embedding_version`, then marks it `deleted` with `deleted_at`. It must be replay-safe and never rehydrate data. A cleanup event cannot delete an active source/version or a source whose reference/hash does not match.
7. Existing D2 revoke/replacement first make chunks unreadable (`stale`) before cleanup. D3 cleanup only scrubs/tombstones; retrieval paths in later D4 must continue rejecting non-indexed/stale/deleted chunks.

## Embedding Boundary

Implement in `stage08_retrieval_embeddings.py` only:

```text
EmbeddingProvider.embed_batch(profile, texts) -> tuple[tuple[float, ...], ...]
UnavailableEmbeddingProvider
TestHashEmbeddingProvider
```

- The only D3 profile is `stage08.test-hash-v1`, version `1`, dimension `8`.
- `TestHashEmbeddingProvider` is deterministic, finite, exactly eight floats per input, has a visibly test-only name, and must never be instantiated/selected as a runtime default.
- `UnavailableEmbeddingProvider` raises only `embedding_provider_unavailable` before any source/chunk/event write. It has no HTTP/client/environment/provider-key dependency.
- Validate profile/version/dimension and every finite numeric output in the worker; a non-test provider is not introduced in D3.

## TDD Required Cases

Write RED cases before production code for at least:

1. Valid index event creates deterministic chunks with exact 8-float test vectors, marks chunks `indexed`, and processed replay adds no rows.
2. Source version/hash/workspace/event/payload drift, replacement/revoke/expiry/delete before execution, and a malformed raw trace/event are discarded or fail closed without readable chunks.
3. Unavailable provider, invalid vector dimension/nonfinite value, and a partial batch failure create no indexed/readable partial chunk and expose only a fixed error code.
4. Cleanup after replacement/revoke clears source projection and all chunk text/terms/vector/profile/version, uses tombstone status, and replay cannot restore data.
5. `TestHashEmbeddingProvider` cannot be selected implicitly; no external SDK/network/import is introduced.
6. Dedicated PostgreSQL: index actual `vector` values on D0's `STAGE08_RAG_DATABASE_URL`, observe the existing HNSW test-profile and GIN indexes, prove index replay idempotency plus cleanup/read-deny. The test must explicitly skip only if `STAGE08_RAG_DATABASE_URL` is absent, never fall back to `DATABASE_URL` or `STAGE06_LOCAL_DATABASE_URL`.

## Required Verification

Run from `backend`, with cache disabled and warnings as errors where applicable:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval.py app/services/stage08_retrieval_embeddings.py
```

Also run static scans for forbidden provider/network/Telegram/LLM imports, raw Memory/Message reads, raw event trace persistence, test-provider runtime-default selection, and `git diff --check`. Record exact RED/GREEN results, migration head, pgvector extension/image evidence, skips, risk, cleanup, and the absence of external calls in the D3 report. Do not claim D3, Package D, Stage08, semantic retrieval quality, provider integration, or production completion pending independent review.
