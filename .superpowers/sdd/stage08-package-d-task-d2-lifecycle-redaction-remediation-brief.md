# Stage08 Package D / Task D2 Lifecycle & Trace Redaction Remediation Brief

## Status

- Status: `approved corrective implementation boundary`
- Trigger: independent D2 review found two Important findings; this brief implements the already-approved Package D lifecycle and reference-only data boundary, without a schema, API, permission, provider, or external-system change.
- Gate: D2 remains open and D3 must not start until this brief has passed an independent fresh review.

## Allowed Files

- Modify: `backend/app/services/stage08_retrieval.py`
- Modify: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modify: `.superpowers/sdd/stage08-package-d-task-d2-report.md`

Do not change models, migrations, contracts, UoW interfaces, API, Docker, embedding/retrieval providers, Memory service behavior, C1/C2, Package B, external integrations, Git state, or runtime configuration.

## Required Corrections

### 1. Root-lineage logical fingerprint

The logical identity of a `memory_item` Knowledge source is the root of the valid same-workspace `MemoryItem.supersedes_id` chain, not the current row UUID.

```text
root_memory_item_id = follow_same_workspace_supersedes_chain(current_item)
logical_source_fingerprint = SHA-256("memory_lineage:" + root_memory_item_id)
content_version = current_item.version
source_ref.memory_item_id = current_item.id
```

- Follow the chain without reading any Memory payload. A missing predecessor, cycle, cross-workspace predecessor, non-increasing version, invalid item, or failed existing read-only projection verification must fail closed: return the existing safe no-registration result and create neither source nor event.
- On a real new-row Memory supersession, lock the prior active/pending source having the same logical fingerprint; mark it `replaced`, synchronously mark its chunks `stale`, link the new source with `supersedes_id`, and create one reference-only cleanup request for the old source in addition to the new source index request.
- A replay of the same current Memory item/version/hash must remain idempotent and must not create another cleanup request.
- Preserve the existing source-specific read-only projection gate: a superseded old Memory row remains unreadable to a future retrieval path. Do not restore or read its body.

### 2. Derived trace reference only

`caller_trace_id` remains an internal input validation parameter only. Derive:

```text
trace_ref = SHA-256("stage08-knowledge-trace-v1:" + caller_trace_id)
```

- The exact reference-only payload key remains `trace_id` in this limited remediation for compatibility, but its value is `trace_ref`; `OutboxEvent.trace_id` also stores only `trace_ref`.
- The raw caller string must not appear in payload, `OutboxEvent.trace_id`, registration result/repr, error text, audit, or any persisted field.
- Input must remain a nonblank bounded string; reject whitespace-only, newline, and oversized input with the existing safe no-registration behavior. Do not echo rejected text.
- Existing internally constructed cleanup references must also be passed through the same derivation before persistence.

## Required Regression Evidence

Write RED cases first, then GREEN cases.

1. Use the real `materialize_memory_from_projection` supersession path twice for the same logical Memory identity, so the second item has a different UUID and `supersedes_id` points to the first. Register the first, add an indexed old chunk, register the second, then prove old source is `replaced`, old chunk is `stale`, new source links to old, and exactly one old-source cleanup plus one new-source index event exists. Replaying the second registration creates neither a new source nor a duplicate cleanup.
2. Prove broken/cyclic/cross-workspace/non-monotonic lineage produces no new Knowledge source/event.
3. Supply `caller_trace_id = "projection-body-secret-Acme-approved"`; prove that sentinel is absent from serialized payload, event `trace_id`, registration repr/result, and any safe error. Prove persisted reference is exactly the documented SHA-256 and has no raw carrier. Cover whitespace-only, newline, and oversized rejection.
4. Retain existing D2 valid registration, chunk, revoke, idempotency, and no-direct-payload-access tests.

Run from `backend` with warnings promoted:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py
python -m compileall -q app/services/stage08_retrieval.py
```

## Completion Report

Update the D2 evidence report with the original findings, the root-lineage and trace-ref implementation, RED/GREEN commands/counts, independent-review status, skipped integration/external actions, risks, and cleanup. It must not claim D2, Package D, Stage08, provider, deployment, or production completion before a fresh independent review passes.
