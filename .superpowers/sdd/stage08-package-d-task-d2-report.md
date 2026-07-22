# Stage08 Package D / Task D2 Evidence Report

## Status

- Status: `lineage-integrity remediation implemented; awaiting another independent fresh review`
- Scope: D2 safe source projection, deterministic chunk candidates, source lifecycle, reference-only outbox requests, and source/chunk UoW parity only.
- Worktree: existing dirty worktree preserved; no stage, commit, reset, checkout, clean, branch, push, PR, Docker, database, API, external provider, Telegram, LangGraph, or network action was performed.

## Changed Files

- Modified: `backend/app/services/stage06_platform.py`
  - Added only the six brief-approved `Stage08KnowledgeSource` / `Stage08KnowledgeChunk` Protocol, InMemory, and SQLAlchemy UoW methods plus backing lists/imports.
- Created: `backend/app/services/stage08_retrieval_chunking.py`
- Created: `backend/app/services/stage08_retrieval.py`
- Created: `backend/tests/unit/test_stage08_retrieval_chunking.py`
- Created: `backend/tests/unit/test_stage08_retrieval_service.py`
- Created: `.superpowers/sdd/stage08-package-d-task-d2-report.md`

No model, migration, contract, API, Docker, embedding/retrieval provider, C1, C2, Package B, external integration, or Git file/action entered D2 scope.

## TDD RED -> GREEN Evidence

### RED

Command:

```powershell
python -m pytest backend/tests/unit/test_stage08_retrieval_chunking.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error
```

Observed before production implementation:

- Exit: `1`
- Collection errors: `2`
- `ModuleNotFoundError: app.services.stage08_retrieval_chunking`
- `ModuleNotFoundError: app.services.stage08_retrieval`
- This was the expected missing-D2-module RED, not a typo or environment failure.

First implementation run observed `21 passed, 2 failed`; both failures were contradictions in the new tests, not production exceptions:

- the test incorrectly treated the required reference field `projection_hash` as body text;
- the test used a new Memory item ID to represent a changed version even though the brief fixes logical identity to `SHA-256("memory_item:" + item_id)`.

The tests were corrected to reject `projection_text` and advance the projection version on the same logical Memory item. No contract was changed.

The first independent review later demonstrated that this same-row test did not represent the real Memory supersession path and found two Important issues:

1. item-ID fingerprinting left the old Knowledge source/chunks active when Memory supersession created a new row UUID, and emitted no cleanup request;
2. caller trace text was persisted verbatim in the reference-only event payload and `OutboxEvent.trace_id`.

### Corrective RED

After adding only the remediation regression tests, the brief-focused command from `backend` produced:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

- Exit: `1`
- `10 failed, 24 passed in 4.95s`
- Failures covered root-lineage fingerprint/source ref, real new-row supersession replacement/cleanup, missing/cyclic/cross-workspace/non-monotonic/invalid-status lineage, SHA-256 trace persistence, and newline rejection.

A second metadata/tampered-event RED command produced:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_service.py -k "invalid_metadata or raw_trace_carrier"
```

- Exit: `1`
- `2 failed, 24 deselected in 1.32s`
- Failures proved an unapproved predecessor `source_kind` and an existing raw-trace event were not yet rejected.

After the minimal metadata and event-shape correction, the same targeted command produced `2 passed, 24 deselected in 1.07s`.

A final exact-shape projection-version drift RED produced `1 failed, 26 deselected in 1.31s`; after enforcing `content_version == current_item.version`, the targeted GREEN produced `1 passed, 26 deselected in 0.97s`.

### GREEN

Fresh D2-only command:

```powershell
python -m pytest backend/tests/unit/test_stage08_retrieval_chunking.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error
```

Observed:

- Exit: `0`
- `25 passed in 1.69s`
- Warnings treated as errors.

Fresh D1 strict contracts plus D2 command:

```powershell
python -m pytest backend/tests/unit/test_stage08_retrieval_contracts.py backend/tests/unit/test_stage08_retrieval_chunking.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error
```

Observed:

- Exit: `0`
- `81 passed in 1.78s`
- Warnings treated as errors.

Fresh Memory read-service plus D2 service regression:

```powershell
python -m pytest backend/tests/unit/test_stage08_memory_service.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error
```

Observed:

- Exit: `0`
- `62 passed in 0.93s`
- Warnings treated as errors.

### Corrective GREEN

All commands below ran from `backend` with warnings promoted and pytest cache disabled.

Focused D2 remediation:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

- Exit: `0`
- `37 passed in 1.74s`

D1 strict contracts plus D2:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

- Exit: `0`
- `93 passed in 1.83s`

Memory contracts/service plus D2:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

- Exit: `0`
- `121 passed in 2.05s`

Corrective production compile:

```powershell
python -m compileall -q app/services/stage08_retrieval.py
```

- Exit: `0`

### Lineage-integrity corrective RED -> GREEN

The second independent remediation review verified the valid supersession and trace-ref corrections, but found one new Important gap: lineage traversal validated rows independently without proving predecessor `memory_type` and normalized full scope matched the active current Memory identity. A forged same-workspace edge could therefore replace and clean up an unrelated Knowledge source.

Only collision regressions were added before the production correction. The focused brief command produced:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

- Exit: `1`
- `3 failed, 37 passed in 2.21s`
- Failures covered a valid unrelated `preference` predecessor collision, same-type/different-`table_id`, and same-type/different-`identity_token`.
- Each test snapshot the unrelated Knowledge source status/text/link, indexed chunk status, Knowledge source count, and exact event tuple, proving fail-closed means no replace/stale/clear/cleanup/link/event mutation.

After adding normalized logical-identity equality on every lineage predecessor, fresh checks from `backend` produced:

```text
focused D2:      40 passed in 1.76s
D1 + D2:         96 passed in 1.89s
Memory + D2:    124 passed in 1.91s
compileall:       exit 0
```

All pytest commands used `-q -W error -p no:cacheprovider`; compile used `python -m compileall -q app/services/stage08_retrieval.py`.

## Implemented D2 Behavior

### Canonicalization and chunks

- Unicode NFC.
- `\r\n` and `\r` normalized to `\n`.
- C0 controls stripped except newline/tab; empty canonical result raises the fixed safe code `knowledge_source_text_empty`.
- Exact chunk maximum `1,200` Python/Unicode code points, overlap `200`, step `1,000`.
- Exact source maximum `1,000,000` code points and maximum `1,000` chunks; over-limit input raises `knowledge_source_text_limit_exceeded` before any chunk tuple is returned.
- Stable zero-based ordinals and SHA-256 of each canonical chunk.
- Stable CJK two-code-point terms and case-folded Latin/digit terms, deduplicated and bounded to `256` terms and `64` code points per term.
- No summarization, translation, provider, embedding, network, or worker path exists in the D2 chunker.

### Safe Memory adapter and C2 boundary

- Calls `read_memory_projection(..., lifecycle_mode="read_only")` before registration.
- Does not access `Stage08MemoryItem.payload`; only `scope` and `source_refs` metadata are inspected after the safe projection read so group/Telegram origin cannot be mistaken for approved RAG authority.
- Canonical source text is exactly canonical JSON of `memory_type` plus the safe projection `payload`.
- Canonical text excludes Memory item ID, workspace/base/table/customer/project scope IDs, source refs, identity token, group binding, Telegram carrier, and raw content carrier.
- Explicitly rejected cases covered by tests:
  - no Memory item;
  - revoked Memory;
  - expired Memory in read-only mode without lifecycle/audit mutation;
  - source/version drift;
  - invalid/client-like projection shape;
  - workspace scope mismatch;
  - `group_chat_ref` scope;
  - `telegram_message` source metadata;
  - a simulated readable group projection (defense in depth);
  - payload keys carrying scope IDs, identity token, raw caption, or source refs.
  - broken root lineage: missing predecessor, cycle, cross-workspace predecessor, non-monotonic version, invalid predecessor status, and invalid predecessor source metadata.
  - cross-identity lineage: different `memory_type`, different normalized table scope, and different `identity_token`, with unrelated Knowledge source/chunk/events remaining unchanged.
- C2/group history remains Context-only. No group-scoped or Telegram Memory becomes a `KnowledgeSource` or outbox request.

### Source lifecycle and outbox

- `logical_source_fingerprint = SHA-256("memory_lineage:" + root_memory_item_id)` after following a valid same-workspace `supersedes_id` chain without reading any Memory payload.
- The active current item defines lineage identity as `(memory_type, canonical MemoryScopeProjection)`. Every predecessor must match both values exactly. Scope comparison happens only after Pydantic normalization and canonical JSON serialization of all scope fields, including `identity_token`; raw scope dicts are not compared.
- Lineage `source_refs` remain structural safety metadata only and are not used as logical identity; predecessor payload is never read or compared.
- `source_ref.memory_item_id` points to the current Memory row, while the fingerprint remains stable across valid new-row supersession.
- `content_version` is the Memory safe projection version.
- `projection_hash` is SHA-256 of canonical projection text.
- Same fingerprint/version/hash reuses the existing source and deterministic index event, including when replay trace differs.
- A real new-row Memory supersession locks and marks the previous active/pending Knowledge source `replaced`, marks its chunks `stale`, links the new source with `supersedes_id`, emits exactly one cleanup request for the old source, and emits one index request for the new source. Replay creates neither a duplicate source nor duplicate cleanup.
- Revoke locks active/pending source, marks it `revoked`, immediately clears `projection_text`, writes `revoked_at`, marks chunks `stale` without deleting/scrubbing chunk rows, and creates at most one cleanup request.
- Caller and internally constructed cleanup traces are persisted only as `SHA-256("stage08-knowledge-trace-v1:" + caller_trace_id)`; the compatibility payload key remains `trace_id`, but both it and `OutboxEvent.trace_id` contain only the 64-hex digest. Blank, newline-containing, and over-120-character caller inputs fail closed without echo or persistence.
- Idempotent replay rejects an existing event whose trace payload/event field is not the safe 64-hex reference shape.
- No audit text, row delete, worker invocation, embedding, search, or external call is performed.

Reference-only index and cleanup payload keys are exactly:

```text
workspace_id
knowledge_source_id
content_version
projection_hash
trace_id
```

Both event types use `aggregate_type="stage08_knowledge_source"`, remain `pending`, and use deterministic idempotency keys. Payloads contain no projection/body/payload/source_ref/scope/actor/reason/secret field, and the raw caller/internal trace string is absent from all persisted fields and safe result representations.

### UoW parity

Protocol, InMemory, and SQLAlchemy each contain exactly the six brief-approved methods:

```text
add_knowledge_source
get_knowledge_source
lock_knowledge_source_for_lifecycle
list_knowledge_sources
add_knowledge_chunk
list_knowledge_chunks
```

- InMemory behavior is covered for add/get/lock, exact workspace/source/version filters, and deterministic ordering.
- SQLAlchemy source lifecycle lock is source-row `FOR UPDATE`.
- SQLAlchemy lists filter exact `workspace_id` or exact `(source_id, source_version)` and order deterministically.

## Static and Syntax Verification

Production compile command:

```powershell
python -m compileall -q backend/app/services/stage06_platform.py backend/app/services/stage08_retrieval_chunking.py backend/app/services/stage08_retrieval.py
```

Observed: exit `0`.

AST/static scan of the two new D2 service files observed:

- imports inspected: `18`;
- forbidden Message/Telegram/Provider/httpx/requests/LangGraph/pgvector imports: `0`;
- raw `raw_text` / `raw_caption` / `normalized_text` attribute reads: `0`;
- direct `item.payload` access: `0`.

UoW AST assertions observed:

- three UoW implementations each expose all six methods;
- SQL source-row `with_for_update`: `true`;
- SQL exact source/chunk filters: `true`.

Whitespace verification:

- `git diff --check`: exit `0`; the dirty worktree emitted pre-existing LF-to-CRLF conversion warnings only.
- New D2 file trailing-whitespace scan: `0` findings.

## Skipped Tests and External Actions

- No PostgreSQL/pgvector test was run and no database row was created; D1 owns schema evidence and D3/later worker work owns real source/chunk persistence and lifecycle integration evidence.
- No Docker lifecycle action was run.
- No API, browser, Mini App, Telegram, Redis, LangGraph, embedding, retrieval provider, LLM, HTTP, or other external action was run.
- No full backend suite was run; D2 strict, D1+D2 strict, and Memory+D2 regression commands are recorded above.

## Remaining Risks

1. The lineage-integrity corrective implementation is awaiting another fresh independent review. The second independent remediation review remains FAIL evidence until that new review explicitly passes with zero Critical/Important findings.
2. SQLAlchemy query shape is compiled/static-checked in D2, but real PostgreSQL row locking, unique-race behavior, chunk persistence, replacement/revoke concurrency, and cleanup/reindex worker replay remain later-task evidence.
3. This remediation does not migrate already-persisted pre-remediation source fingerprints or raw trace values. No database action was authorized or performed; any existing deployed data would require a separately approved migration/cleanup decision.
4. Chunk candidates have no embeddings and are not persisted by D2. Retrieval quality, pgvector behavior, provider availability, citations, API permissions, and production readiness remain outside this report.

## Temporary Cleanup

- No tracked temporary script, test dataset, database, container, credential, or external artifact was created.
- Test/compile Python cache files remain ignored runtime cache only; no cleanup action touched unrelated worktree files.

This report records Task D2 implementation and two corrective rounds of evidence only. A fresh lineage-integrity remediation review is pending. It does not declare Task D2, Package D, Stage08, provider, deployment, or production readiness complete.
