# Stage08 Package D / D2 Remediation Independent Review Brief

## Review Boundary

Review the remediation described in `stage08-package-d-task-d2-lifecycle-redaction-remediation-brief.md` and the existing D2 implementation/report. This is an independent review only: modify no production code, test code, contract, migration, database, Docker, Git state, or external system. Write findings only to `stage08-package-d-task-d2-remediation-review-report.md`.

## Blocking Criteria

### Memory lineage lifecycle

1. Verify the active Memory item is read through the existing `read_memory_projection(..., lifecycle_mode="read_only")` gate before source registration, without direct `item.payload` reads.
2. Verify `logical_source_fingerprint` is derived from the root of the same-workspace `supersedes_id` lineage, while `source_ref.memory_item_id` remains the current Memory row ID and `content_version` remains current version.
3. Independently reproduce the real production shape with `materialize_memory_from_projection` twice: a new UUID, active new row, and `supersedes_id` to a superseded old row. With an indexed old chunk, registration of the new row must leave the old source `replaced`, old chunk `stale`, new source linked by `supersedes_id`, exactly one old-source cleanup event and one new-source index event. Replay must be idempotent.
4. Verify missing/cyclic/cross-workspace/non-monotonic or non-active predecessor states fail closed without a Knowledge source or Outbox event.
5. Verify no raw superseded Memory body is reread, reintroduced, or emitted, and C2/group/Telegram Memory remains RAG-ineligible.

### Trace reference redaction

1. Supply a sentinel such as `projection-body-secret-Acme-approved`. It must be absent from serialized event payload, `OutboxEvent.trace_id`, registration result/repr, error text and any other observable persisted record.
2. Confirm payload's existing `trace_id` key and `OutboxEvent.trace_id` each equal `SHA-256("stage08-knowledge-trace-v1:" + caller_trace_id)` exactly, including internally generated cleanup trace input.
3. Confirm blank, whitespace-only, newline and oversized caller trace input fail closed and do not echo the carrier.
4. Confirm event payload remains only its approved reference fields; no body, scope, source refs, secret, actor, caller trace or raw provider carrier appears.

## Fresh Verification

Run from `backend`:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m compileall -q app/services/stage08_retrieval.py
```

Inspect the diff and relevant D1/Memory contracts. Do not count passing tests as sufficient if source replacement or trace redaction is bypassable. Report Critical, Important, and Minor findings separately; only `0 Critical / 0 Important` permits D2 closure consideration. State skipped database/pgvector and external checks explicitly.
