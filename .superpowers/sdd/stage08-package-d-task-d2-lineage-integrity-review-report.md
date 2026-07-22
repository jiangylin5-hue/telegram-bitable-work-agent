# Stage08 Package D / D2 Lineage Integrity Independent Review Report

## Status

- Review date: 2026-07-20
- Review scope: the second D2 lineage-integrity remediation, preserving the
  previously corrected lifecycle and trace-reference behavior.
- Overall verdict: **PASS**.
- Critical: **PASS** — 0 findings.
- Important: **PASS** — 0 findings.
- Minor: **PASS** — 0 findings.
- Gate: this review permits root-level **D2 closure consideration**. It does
  not itself declare D2, Package D, Stage08, retrieval, indexing, production,
  deployment, or any later task complete.

The previous cross-identity lineage Important finding was re-attacked rather
than waived. Valid real supersession, different Memory type, every requested
same-type scope drift family including `identity_token`, and trace redaction
were independently exercised against the current production service.

This review created only this report. It did not modify production code,
tests, contracts, models, migrations, UoW, API, database, Docker, Git state,
configuration, or any external system.

## Findings

No Critical, Important, or Minor findings were identified in the approved D2
lineage-integrity remediation boundary.

## Independent behavioral attacks

### 1. Valid real Memory supersession remains valid

The reviewer used `materialize_memory_from_projection` twice for one logical
identity, registered the first item, added an indexed old chunk, registered
the new-row item, and replayed that registration. The command was an inline
read/write-in-memory production-service corpus run from `backend`:

```powershell
@'<independent valid/collision/scope/trace production-service corpus>'@ | python -
```

Fresh valid-flow output:

```text
VALID True True superseded active replaced stale True True 1 1 True
```

The fields prove, in order:

- a new Memory UUID was created;
- the new active row points to the old row by `supersedes_id`;
- Memory states are `superseded` / `active`;
- the old Knowledge source is `replaced`;
- the old indexed chunk is `stale`;
- the new Knowledge source links the old Knowledge source;
- the root logical fingerprint is continuous;
- exactly one new index and one cleanup event were added; and
- replay returns the same source/event without duplication.

An additional valid flow used the same non-null 64-hex `identity_token` on
both Memory versions. Fresh result:

```text
valid_identity_token_supersession=True
identity_token_not_in_source_scope=True
```

Thus including `identity_token` in lineage identity does not break legitimate
same-token supersession and does not expose the token in the Knowledge source
scope returned by the safe projection.

### 2. Cross-type collision is rejected without side effects

The reviewer created valid `decision` A1 → A2 through the real materializer,
registered A1 and attached an indexed chunk, then created an unrelated valid
`preference` B in the same workspace. B's `supersedes_id` and superficial
version were tampered to point at A1 before registration.

Fresh output:

```text
CROSS_TYPE True True active indexed 1 1
```

This proves registration returned `None`, the complete pre-registration
snapshot remained equal, the old Knowledge source stayed `active`, the old
chunk stayed `indexed`, and source/event counts remained exactly one. Source
text, Knowledge `supersedes_id`, event tuple, and chunk text were included in
the equality snapshot; no replace, stale, clear, cleanup, link, source, or
event side effect occurred.

### 3. Same-type scope drift is rejected without side effects

For each attack, the unrelated current item was first created by the real
Memory materializer as a valid `decision` item. Only afterwards was its
lineage pointer and superficial version tampered. The reviewer independently
covered every scope family requested by the brief:

```text
SCOPE_TABLE True True active indexed 1 1
SCOPE_BASE True True active indexed 1 1
SCOPE_CUSTOMER True True active indexed 1 1
SCOPE_PROJECT True True active indexed 1 1
SCOPE_IDENTITY_TOKEN True True active indexed 1 1
```

Each first `True` means no registration; each second `True` means the full old
source/chunk/source-count/event-tuple snapshot was unchanged. The result is
consistent with the implementation:

- current identity is `(memory_type, canonical MemoryScopeProjection)`;
- every predecessor is Pydantic-normalized before comparison;
- `model_dump(..., exclude_none=False)` includes all optional scope fields;
- sorted canonical JSON makes key order irrelevant; and
- predecessor identity must equal the active current identity before any
  Knowledge source lookup, lifecycle lock, replacement, staling, cleanup, or
  insertion.

The current definition matches the existing Memory materializer's logical
identity inputs: `memory_type` plus normalized scope. It does not compare or
reread predecessor payload/source values.

### 4. Trace redaction remains sound

The same independent corpus used caller sentinel
`projection-body-secret-Acme-approved` and reconstructed the documented hash.
Fresh output:

```text
TRACE_INDEX True True True
TRACE_REPLACE_CLEANUP True True
TRACE_REVOKE_CLEANUP True True
TRACE_BLANK True True True
TRACE_SPACE True True True
TRACE_NEWLINE True True True
TRACE_OVERSIZE True True True
```

Index, replacement-cleanup, and revoke-cleanup `payload["trace_id"]` and
`OutboxEvent.trace_id` each equal exactly:

```text
SHA-256("stage08-knowledge-trace-v1:" + caller_or_internal_trace)
```

The raw sentinel was absent from serialized event state and safe result
representation. Blank, whitespace-only, newline-containing, and oversized
trace inputs returned no registration and created neither a Knowledge source
nor Outbox event. Payload keys remain exactly `workspace_id`,
`knowledge_source_id`, `content_version`, `projection_hash`, and `trace_id`.

## Fresh required verification

All commands ran from `backend`; pytest cache was disabled and warnings were
promoted to errors.

### 1. D2 focused

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

Fresh result: exit `0`, `40 passed in 1.73s`.

### 2. D1 contracts plus D2

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

Fresh result: exit `0`, `96 passed in 1.90s`.

### 3. Memory contracts/service plus D2

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

Fresh result: exit `0`, `124 passed in 1.97s`.

### 4. Production compile

```powershell
python -m compileall -q app/services/stage08_retrieval.py
```

Fresh result: exit `0`.

The focused suite now includes explicit regressions for cross-type collision,
same-type/different-table scope, and same-type/different-`identity_token`, in
addition to real valid supersession, malformed lineage, group/Telegram denial,
trace hashing, replay, revoke, chunking, and UoW behavior.

## Static boundary and diff inspection

Fresh AST/source checks returned:

```text
direct_item_payload=[]
raw_message_attrs=[]
forbidden_imports=[]
read_before_item=True
identity_exclude_none_false=True
```

Registration still calls
`read_memory_projection(..., lifecycle_mode="read_only")` before loading
lineage metadata. The service does not directly access `item.payload`, import
raw Message behavior, or add provider/network/HTTP/API/worker/embedding/
LangGraph/pgvector/OpenAI behavior. Group scope and Telegram source metadata
remain RAG-ineligible.

The current remediation changes are confined behaviorally to the existing D2
service, service tests, and D2 evidence report. No model, migration, runtime
contract, UoW interface, API, Docker, provider, C1/C2, or Package B behavior is
introduced by the reviewed service.

The relevant service, test, D2 report, and D contract paths are all untracked
in the shared dirty worktree, so `git diff -- <paths>` has no tracked baseline
and cannot isolate a remediation-only patch. This review did not treat an
empty Git diff as evidence: it read the complete current files, both
remediation briefs, both earlier review reports, the updated D2 report, D
contract, D1 retrieval contracts, Memory contracts, and the Memory
materializer's `_stored_identity_fingerprint` implementation. Direct
trailing-whitespace scans returned `0` findings on all four relevant current
files.

## Skipped evidence, remaining risks, and cleanup

- PostgreSQL/pgvector was not used and no database row was created. Real row
  locking, uniqueness races, persistence, replacement/revoke concurrency,
  worker replay, chunk persistence, and cleanup execution remain later-task
  evidence.
- No full backend suite was run. Only the four mandated focused commands,
  independent in-memory attacks, and static inspection are claimed.
- No external provider, embedding, LLM, Telegram, API, browser, Mini App,
  Redis, LangGraph, HTTP/network, staging, production, or deployment evidence
  is part of this D2 review.
- The remediation does not migrate any hypothetical pre-remediation persisted
  fingerprints or raw trace values. Such data remediation would require a
  separately approved decision; no database action was performed here.
- No tracked temporary script, dataset, credential, database, or container was
  created. Inline reviewer code retained no artifact; `compileall` reused
  ignored cache locations. No Git stage/commit/reset/checkout/clean occurred.
- The updated D2 evidence report accurately remains at “awaiting another
  independent fresh review” and does not declare Package D complete. This
  PASS review resolves that review gate for D2 closure consideration only;
  later Package D tasks and package-level acceptance remain separate.
