# Stage08 Package D / D2 — Safe Source Projection, Chunking and Reference-only Requests

## Objective

Implement D2 only: deterministic safe-text canonicalization/chunking, non-group Memory-to-KnowledgeSource adapter, source version/revoke lifecycle, corresponding UoW parity, and reference-only `OutboxEvent` reindex requests.

Do not generate embeddings, persist chunks, search/retrieve, create any API, call external services, or change D1 schema/migration.

Read first:

- `docs/superpowers/plans/2026-07-20-stage08-package-d-rag-implementation.md` Task 2
- `project-docs/08-implementation/decisions/STAGE_08_D_RETRIEVAL_DATA_CONTRACT.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_D_RAG_BDD_AND_ACCEPTANCE.md`
- `backend/app/runtime/stage08_retrieval_contracts.py`
- `backend/app/services/stage08_memory.py` `read_memory_projection`
- `backend/app/services/stage06_platform.py` UoW Protocol/InMemory/SQLAlchemy patterns.

## Allowed files

- Modify `backend/app/services/stage06_platform.py` only for D source/chunk UoW methods/imports/backing lists/SQLAlchemy operations.
- Create `backend/app/services/stage08_retrieval_chunking.py`.
- Create `backend/app/services/stage08_retrieval.py`.
- Create `backend/tests/unit/test_stage08_retrieval_chunking.py`.
- Create `backend/tests/unit/test_stage08_retrieval_service.py`.
- Create `.superpowers/sdd/stage08-package-d-task-d2-report.md`.

No models/migrations/contracts/API/Docker/embedding provider/retrieval provider/C1/C2/B changes. Do not modify D1 integration tests; the later worker task owns real vector/chunk persistence tests.

## Exact implementation boundary

### UoW parity

Add and implement, in Protocol + InMemory + SQLAlchemy only, the minimum methods necessary for later tasks:

```python
add_knowledge_source(source: Stage08KnowledgeSource) -> None
get_knowledge_source(source_id: UUID) -> Stage08KnowledgeSource | None
lock_knowledge_source_for_lifecycle(source_id: UUID) -> Stage08KnowledgeSource | None
list_knowledge_sources(workspace_id: UUID) -> list[Stage08KnowledgeSource]
add_knowledge_chunk(chunk: Stage08KnowledgeChunk) -> None
list_knowledge_chunks(source_id: UUID, source_version: int) -> list[Stage08KnowledgeChunk]
```

SQLAlchemy lifecycle lock must be source-row `FOR UPDATE`; lists must be deterministically ordered and filtered by exact workspace/source/version.

### Chunking

Expose only internal service functions:

```python
canonicalize_knowledge_text(text: str) -> str
chunk_knowledge_projection(text: str) -> tuple[KnowledgeChunkProjection, ...]
```

Canonicalization uses Unicode NFC, `\r\n`/`\r` to `\n`, strips C0 controls except newline/tab, and rejects empty result. Chunking has exact maximum `1,200` Unicode code points, exact overlap `200`, maximum `1,000` chunks, maximum source `1,000,000` code points, stable ordinal/hash, CJK two-character terms plus normalized Latin/digit tokens, at most `256` terms at most `64` characters. Never summarize, translate, call a provider, or split within a Python code point. An over-limit source raises a fixed safe validation code; it must not emit a partial source.

### Safe Memory source adapter

Expose only internal functions:

```python
register_memory_knowledge_source(uow, memory_item_id: UUID, *, actor: Actor, now: datetime, trace_id: str) -> KnowledgeSourceRegistration | None
revoke_knowledge_source(uow, source_id: UUID, *, now: datetime, reason_code: str) -> KnowledgeSourceLifecycleResult | None
```

`register_memory_knowledge_source` calls `read_memory_projection(..., lifecycle_mode="read_only")` and never queries Memory payload directly. It rejects no/invalid/stale projection and rejects any `group_chat_ref` or group/Telegram source: C2 group context remains Context-only and Package D has no approved group RAG authority. It forms canonical safe projection text only from the current projection's `memory_type` and payload canonical JSON; it must not include item ID, source refs, scope IDs, identity token, group ref or raw content carrier.

Use `logical_source_fingerprint = SHA-256("memory_item:" + item_id)` and `content_version = Memory projection version`; `projection_hash` is SHA-256 of canonical projection text. A same logical source/version/hash is idempotent: return/reuse its existing reference-only event without duplicate source/event. A changed version creates a new source, marks the previous active source `replaced` under lifecycle lock, and emits exactly one `stage08.knowledge.index_requested` event.

Outbox event `aggregate_type="stage08_knowledge_source"`; aggregate ID may be source UUID internally; idempotency key is deterministic per logical fingerprint/version/hash; payload contains exactly workspace/source/version/hash/trace reference fields—no projection/body/payload/source_ref/scope/actor or secret. It remains `pending`; D3 will consume it.

`revoke_knowledge_source` locks source, changes active/pending source to `revoked`, clears `projection_text`, writes `revoked_at`, and creates at most one reference-only `stage08.knowledge.cleanup_requested` event. It must not delete source rows or chunks, write audit text, or call a worker.

## Required TDD corpus

1. Chunk tests: NFC/newlines/control removal, exact 1,200/200 boundaries, stable repeated output, CJK/Latin terms, term cap, 1,000 chunk/1M source rejects, hash and ordinal stability, no external imports.
2. Service tests: non-group current Memory registers source/event; no-memory, expired/revoked/source drift, group-scoped Memory and `telegram_message` source reject; canonical text excludes IDs/scope/source refs; outbox payload exact keys/redaction; same version replay idempotent; changed version replaces old source; revoke immediate text scrub/one cleanup event; InMemory UoW parity.
3. First run new tests RED. Then minimum implementation GREEN with `-W error`.
4. Run current D1 strict contracts together with D2 tests; compile all new/modified production files, static scan for Message raw fields/Telegram/Provider/httpx/requests/LangGraph/pgvector imports in D2 production files, and `git diff --check`.

Record exact RED/GREEN counts, outbox payload keys, rejected source cases, scope, no database/external action and remaining risk. Do not claim D2 or Package D complete.
