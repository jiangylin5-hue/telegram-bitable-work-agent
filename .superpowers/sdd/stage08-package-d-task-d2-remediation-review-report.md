# Stage08 Package D / D2 Remediation Independent Review Report

## Status

- Review date: 2026-07-20
- Review scope: the D2 root-lineage and trace-reference remediation only,
  including its current service, unit tests, D2 evidence report, D retrieval
  contract, and required D1/Memory contracts.
- Overall verdict: **FAIL**.
- Critical: **PASS** — 0 findings.
- Important: **FAIL** — 1 finding.
- Minor: **PASS** — 0 findings.
- Gate: **D2 cannot close and D3 must not proceed on this review** until the
  Important lineage-integrity finding is fixed, covered by regression tests,
  and independently re-reviewed.

The two findings from the first D2 review were independently re-attacked. The
valid production supersession path now performs source replacement/cleanup,
and raw trace text is now replaced by the documented SHA-256 reference. The
new finding below is a distinct bypass in malformed lineage validation; green
happy-path tests do not waive it.

This review changed only this report. It did not modify production code,
tests, contracts, models, migrations, database, Docker, Git state, or any
external system. It does not claim D2, Package D, Stage08, retrieval,
indexing, production, or deployment completion.

## Finding

### Important

1. **A same-workspace predecessor from a different Memory logical identity is
   accepted as lineage, causing an unrelated Knowledge source to be replaced
   and cleaned up.**

   `_resolve_memory_lineage_root` validates the current and predecessor rows'
   UUID/workspace/status/version, parses each scope, and validates each
   `source_refs` shape (`backend/app/services/stage08_retrieval.py:348-386`).
   It does not validate the relationship that makes the edge a supersession of
   the *same logical Memory identity*: predecessor and current `memory_type`
   are never compared, and their normalized identity scopes are only checked
   independently for the same `workspace_id`, not for equality
   (`backend/app/services/stage08_retrieval.py:389-398`).

   The existing malformed-lineage corpus covers missing predecessor, cycle,
   cross-workspace predecessor, non-monotonic version, predecessor status, and
   invalid source-kind metadata
   (`backend/tests/unit/test_stage08_retrieval_service.py:462-500`). It does
   not cover a predecessor that is individually valid but belongs to a
   different Memory type or different identity scope.

   Independent attack used only the in-memory UoW and production services:

   1. Materialize and register a valid `decision` item A1.
   2. Materialize A2 through the real production path so A1 is legitimately
      `superseded`.
   3. Materialize an unrelated, valid active `preference` item B in the same
      workspace.
   4. Set B's `supersedes_id` to A1 and B's version to `2`, preserving all
      checks currently performed by the resolver.
   5. Register B.

   Fresh output:

   ```text
   a1=decision,superseded,1 a2=decision,active,2
   current=preference,active,2 forged_predecessor=True
   registration_accepted=True
   fingerprint_collision=True
   unrelated_old_source_replaced=replaced
   new_source_links_unrelated=True
   cleanup_events=1
   ```

   Thus a malformed cross-identity edge does not fail closed. It adopts A1's
   root fingerprint, marks A1's unrelated Knowledge source `replaced`, links
   B's new Knowledge source to it, marks any old chunks stale, and schedules
   cleanup. The same weakness permits different base/table/customer/project
   identity scopes within one workspace to share a forged root. This is a
   destructive source-lifecycle and logical-identity integrity failure even
   though it does not reread the predecessor body.

   The remediation brief requires an invalid lineage/item to create neither a
   source nor event. The Memory service itself defines supersession identity
   from `memory_type` plus scope; the D2 resolver must validate the same
   non-payload identity metadata on every lineage edge. A regression should
   cover at least a different `memory_type` and a different same-workspace
   identity scope, while continuing to avoid any predecessor payload read.

No Critical or Minor finding was identified independently of this blocker.

## Independently verified remediation behavior

### Real production-shape supersession

The reviewer independently invoked `materialize_memory_from_projection`
twice for the same logical identity, registered the first item, attached an
indexed old chunk, registered the second new-row item, and replayed the second
registration. This was not inferred from the implementation test.

Fresh output:

```text
new_row=True link=True memory=superseded,active
fingerprint_stable=True
current_ref=True current_version=True
lifecycle=replaced,stale source_link=True
events=index:2 cleanup:1 total:3
replay_same=True
trace_exact=True
sentinel_absent=True
old_reread_none=True
```

For a valid lineage, the first review's lifecycle finding is closed:

- the current active item is read first through
  `read_memory_projection(..., lifecycle_mode="read_only")`;
- the two Memory rows have different UUIDs and a real `supersedes_id` edge;
- the logical fingerprint remains rooted at the first item while
  `source_ref.memory_item_id` and `content_version` identify the current row;
- the old Knowledge source becomes `replaced`, its indexed chunk becomes
  `stale`, the new source links it, one cleanup event is created for the old
  source, and one new index event is created;
- replay creates no duplicate source or cleanup event; and
- rereading the superseded old Memory row remains fail closed.

AST/source-order inspection confirmed that the read-only projection call
precedes `uow.get_memory_item`, and there is no direct `item.payload` access in
the retrieval service. The lineage traversal reads only metadata. C2/group
and Telegram metadata remain rejected.

### Trace sentinel and invalid input attacks

Using caller trace `projection-body-secret-Acme-approved`, the reviewer
serialized all in-memory Outbox fields plus registration/result
representations. Fresh results:

```text
sentinel_trace_exact=True
sentinel_absent_all_observed=True
revoke_cleanup_trace_exact=True
invalid_blank_closed=True
invalid_space_closed=True
invalid_newline_closed=True
invalid_oversize_closed=True
```

Both `payload["trace_id"]` and `OutboxEvent.trace_id` equal exactly:

```text
SHA-256("stage08-knowledge-trace-v1:" + caller_trace_id)
```

The same outer derivation is applied to the internally constructed revoke
cleanup reference and, in the valid supersession reproduction, to the old
source cleanup reference. The payload retains exactly the five approved keys:
`workspace_id`, `knowledge_source_id`, `content_version`, `projection_hash`,
and `trace_id`. The raw sentinel was absent from payloads, event fields,
result/repr, and other observed persisted state. Blank, whitespace-only,
newline-containing, and oversized inputs produced no Knowledge source or
Outbox event. The first review's raw-trace finding is therefore closed for the
paths attacked here.

## Fresh required verification

All commands below ran from `backend`, disabled the pytest cache provider,
and promoted warnings to errors where applicable.

### 1. D2 focused suite

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

Fresh result: exit `0`, `37 passed in 1.69s`.

### 2. D1 contracts plus D2

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

Fresh result: exit `0`, `93 passed in 1.76s`.

### 3. Memory contracts/service plus D2

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
```

Fresh result: exit `0`, `121 passed in 1.87s`.

### 4. Corrective production compile

```powershell
python -m compileall -q app/services/stage08_retrieval.py
```

Fresh result: exit `0`.

The three green test suites do not exercise the cross-identity lineage attack
above and therefore do not satisfy the remediation's fail-closed gate by
themselves.

## Static, dependency, scope, and diff inspection

Fresh AST/static results for `stage08_retrieval.py`:

```text
direct_item_payload=[]
raw_message_attrs=[]
forbidden_imports=[]
read_before_item=True
```

No HTTP, provider, Telegram, LangGraph, pgvector, OpenAI, raw Message, direct
Memory payload, API, worker, audit, or external-call dependency was added to
the remediation service. The current code remains within D2's service-only
behavior boundary apart from the lineage defect.

The relevant D2 service, test, report, and D contract paths are all untracked
in the shared dirty worktree. Consequently `git diff -- <paths>` has no tracked
baseline and cannot isolate remediation-only hunks; this review did not treat
an empty Git diff as evidence. The reviewer instead read the complete current
files and compared the remediation behavior with the first review, corrective
brief, D2 report, D contract, D1 retrieval contracts, Memory contracts/model,
and the actual Memory materialization/read paths. Direct trailing-whitespace
scans returned `0` findings for all four relevant current files.

The current D contract contains the root-lineage and derived-trace clauses
used for this review. Because all relevant documentation is untracked, this
review does not attribute pre-existing document authorship from Git status and
did not mutate the contract.

## Skipped evidence, remaining risks, and cleanup

- No PostgreSQL/pgvector test was run and no database row was created. D2
  remediation is in-memory/service scope; SQL locking, uniqueness races,
  persistence, worker replay, and real cleanup remain later integration
  evidence.
- No full backend suite was run. Only the four commands mandated by the review
  brief plus independent in-memory attacks and static inspection are claimed.
- No Docker, API, browser, Mini App, Redis, Telegram, LangGraph, LLM,
  embedding/retrieval provider, HTTP/network, staging, production, or
  deployment action was performed.
- No tracked temporary script, dataset, credential, database, or container was
  created. Inline reviewer scripts retained no artifact; `compileall` reused
  ignored cache locations. No Git stage/commit/reset/checkout/clean occurred.
- The D2 evidence report correctly says fresh independent review is pending
  and does not claim D2 closure. Its recorded green counts are consistent with
  the fresh results, but its statement that broken lineage is fully rejected
  is incomplete until cross-identity type/scope edges are covered.
- This Important finding remains blocking. D2 and Package D are not complete.

