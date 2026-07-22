# Stage08 Package D / D2 Independent Review Report

## Status

- Review date: 2026-07-20
- Review scope: D2 safe Memory source projection, deterministic chunking,
  source lifecycle, reference-only outbox requests, and the six source/chunk
  UoW methods only.
- Overall verdict: **FAIL**.
- Critical: **PASS** — 0 findings.
- Important: **FAIL** — 2 findings.
- Minor: **PASS** — 0 findings.
- Gate: **D2 must not be declared complete and D3 must not proceed on this
  review** until both Important findings are resolved, regression-tested, and
  independently re-reviewed.

This report does not claim D2, Package D, Stage08, retrieval, indexing,
production, or deployment completion. Reviewer work changed only this report;
it did not modify implementation, tests, models, migrations, database, Docker,
Git state, or an external system.

## Findings

### Important

1. **The item-ID fingerprint is incompatible with the real Memory
   supersession lifecycle, leaving the old Knowledge source and chunks active
   and without cleanup.**

   D2 computes the logical fingerprint from the current Memory row UUID at
   `backend/app/services/stage08_retrieval.py:168`:

   ```text
   sha256("memory_item:" + memory_item_id)
   ```

   The actual Memory materializer does not increment a row in place. For the
   same logical identity it marks the old row `superseded` and creates a new
   row with a new UUID, `version=old.version+1`, and
   `supersedes_id=old.id` (`backend/app/services/stage08_memory.py:124-131`).
   The new UUID therefore produces a different Knowledge fingerprint. D2
   cannot find the old source in `related_sources`, cannot lock/mark it
   `replaced`, cannot mark its chunks `stale`, and cannot link the new source's
   `supersedes_id` to it.

   The existing changed-version test masks this production behavior by doing
   `item.version += 1` in place
   (`backend/tests/unit/test_stage08_retrieval_service.py:349-355`). That state
   is not produced by the reviewed Memory supersession flow.

   Independent in-memory reproduction used the real
   `materialize_memory_from_projection` twice for the same identity after a
   source record version change, with an indexed old chunk present. Fresh
   output was:

   ```text
   old_memory=superseded new_memory=active ids_differ=True
   old_source=active new_source=active linked=False
   old_chunk_status=indexed old_chunk_text_retained=True
   cleanup_events=0
   old_reread_none=True
   ```

   This is a functional stale-index/cleanup gap, not merely a formula-style
   concern. The approved D data contract requires source replacement to make
   the old source/chunks synchronously unreadable and then issue a
   reference-only cleanup event; D-B01 likewise requires the old logical
   source version to enter `replaced`. The D2 brief's item-ID formula conflicts
   with those lifecycle requirements and is not immunity from the conflict.

   The present source-specific Memory reread does fail closed:
   `read_memory_projection(..., lifecycle_mode="read_only")` returns `None`
   for the superseded old Memory row. A future retrieval path that performs
   the contract-required post-candidate reread can therefore drop the stale
   hit. That does **not** close the lifecycle defect: the PostgreSQL truth would
   still call the old source `active`, its old chunk remains `indexed` with
   text, structured prefiltering can continue to select it, and no cleanup is
   scheduled. The design conflict must be explicitly resolved (rather than
   silently changing the approved formula), and a regression must exercise
   the real new-row Memory supersession path.

2. **Arbitrary trace text, including body/secret material, is copied verbatim
   into the supposedly reference-only outbox event.**

   `_valid_trace_id` accepts any non-blank string up to 120 characters
   (`backend/app/services/stage08_retrieval.py:450-451`). `_build_reference_event`
   then copies it into both `payload["trace_id"]` and `OutboxEvent.trace_id`
   (`backend/app/services/stage08_retrieval.py:427-445`). This does not enforce
   the D2 brief's explicit requirement that the reference-only payload contain
   no projection/body or secret.

   Independent attack passed `projection-body-secret-Acme-approved` as the
   trace and observed:

   ```text
   registration_succeeded=True
   secret_marker_in_payload=True
   event_trace_secret=True
   ```

   Internal-only scope does not make an unconstrained text carrier a safe
   reference. The boundary needs an opaque server-derived trace reference (or
   a deterministic digest/reference representation) rather than arbitrary
   caller text, with regression cases for body, credential-like, whitespace,
   newline, and oversized carriers. Existing exact-key assertions do not catch
   this because `trace_id` is itself an approved key while its value is unsafe.

No Critical or Minor findings were identified independently of these two
blockers.

## Checks that passed

### Scope and UoW parity

- The D2 production services add no embedding/chunk persistence/search/API,
  worker, external provider, HTTP, Telegram, LangGraph, pgvector, audit, or
  business-write path.
- No D1 contract/model/migration, C1/C2, or Package B contract behavior was
  changed in the D2 implementation surface reviewed here.
- Protocol, InMemory, and SQLAlchemy UoWs each expose all six approved methods:
  `add/get/lock/list_knowledge_source` and `add/list_knowledge_chunk`.
- InMemory and SQLAlchemy lists use exact workspace or exact
  `(source_id, source_version)` filters and deterministic ordering.
- SQLAlchemy `lock_knowledge_source_for_lifecycle` performs a source-row
  `SELECT ... FOR UPDATE`.

### Canonicalization and chunking

- NFC, CRLF/CR newline normalization, C0 removal except newline/tab, and
  fixed-code empty rejection are implemented.
- Chunking uses Python Unicode code points, exact 1,200 maximum, 200 overlap,
  stable zero-based ordinals and SHA-256 hashes.
- The 1,000,000-code-point source cap and 1,000-chunk cap reject before a tuple
  is returned; the exact cap produces 1,000 chunks.
- CJK bigrams plus case-folded Latin/digit terms are deterministic,
  deduplicated, and bounded to 256 terms of at most 64 code points.
- The chunking module has no transport/provider/network import.

### Memory projection and lifecycle behavior outside the findings

- Registration calls `read_memory_projection` first with
  `lifecycle_mode="read_only"` and contains no direct `item.payload` access.
- It rejects missing, revoked, expired, drifted, invalid-shape, workspace
  mismatch, `group_chat_ref`, and Telegram/group source metadata cases without
  creating a Knowledge source or event.
- Canonical source text is derived only from the returned Memory type and safe
  projection payload; reviewed tests and scans found no item/scope/source/raw
  carrier in the normal canonical text or safe `repr`.
- Same item/version/hash replay is idempotent in the modeled same-row case.
- Explicit source revoke locks the source, marks it `revoked`, clears
  `projection_text`, timestamps `revoked_at`, marks existing chunks stale, and
  creates at most one cleanup event. It does not invoke a worker, write audit
  text, or delete rows.
- Outbox event type, aggregate type, source aggregate ID, status,
  idempotency-key construction, and exact five-key payload shape are otherwise
  correct. The second finding is specifically the unconstrained value placed
  in the approved `trace_id` slot.

## Fresh verification

All pytest commands ran from `backend`, disabled the cache provider, and
promoted warnings to errors.

### D2 focused suite

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_retrieval_chunking.py `
  tests/unit/test_stage08_retrieval_service.py
```

Result: `25 passed in 1.75s`.

### D1 + D2 focused suite

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_retrieval_contracts.py `
  tests/unit/test_stage08_retrieval_chunking.py `
  tests/unit/test_stage08_retrieval_service.py
```

Result: `81 passed in 1.85s`.

### Memory + D2 focused suite

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_memory_contracts.py `
  tests/unit/test_stage08_memory_service.py `
  tests/unit/test_stage08_retrieval_chunking.py `
  tests/unit/test_stage08_retrieval_service.py
```

Result: `109 passed in 1.99s`.

These green counts do not waive the findings. In particular, the 109-case
Memory+D2 suite demonstrates that the real supersession-to-Knowledge bridge is
missing from the current regression corpus.

### Compile, static, and diff checks

```powershell
python -m compileall -q `
  backend/app/services/stage06_platform.py `
  backend/app/services/stage08_retrieval_chunking.py `
  backend/app/services/stage08_retrieval.py
```

Result: exit `0`.

AST/static checks returned:

```text
forbidden_imports=[]
raw_message_attrs=[]
direct_item_payload=[]
Protocol/InMemory/SQLAlchemy six_present=True
sql_lock_with_for_update=True
```

`git diff --check` over the five D2 implementation/test paths exited `0` and
reported only the existing LF-to-CRLF conversion warning for
`stage06_platform.py`, not a whitespace error.

## Scope, skipped evidence, risks, and cleanup

- The shared worktree contains extensive pre-existing Stage07/Stage08 dirty
  state. It was preserved and is not attributed to D2. Review evidence was
  restricted to the D2 files and their required D1/Memory contracts.
- No PostgreSQL/pgvector test was run and no database row was created. D2 does
  not own persistence integration; this review does not count in-memory tests
  as real PostgreSQL evidence.
- No full backend suite, Docker action, API/browser/Mini App, Redis, Telegram,
  LangGraph, LLM, embedding/retrieval provider, HTTP/network, staging,
  production, or deployment check was run or claimed.
- No tracked temporary script or dataset was created. `compileall` reused
  ignored cache locations. No Git stage/commit/reset/checkout/clean occurred.
- Both Important findings remain blocking. Passing chunk/UoW/static suites is
  insufficient to close D2 while real Memory supersession leaves stale active
  index state and arbitrary trace text can enter the reference-only outbox.

