# Stage12 Task 5 Retrieval Materialization And Runtime Evidence

## Status

- Status: `implemented-local`
- Date: 2026-07-30
- Scope: approved correction-plan Task 5, including TDR-021 and TDR-022
- Production status: not deployed, not activated, no production migration, external Provider call, business write or Telegram send

## Implemented contract

- Relation identity includes source/target record identity, direction, versions, visibility profile and effective retrieval scope.
- Effective retrieval scope binds the authorized schema scope to the exact view set or whole-table marker.
- Durable registrations retain only authority references, hashes, versions and lifecycle; they expire and can be revoked.
- Source/projection/relation rebuilds revalidate current membership, employee, view, schema and V2 field policy; contraction revokes before rebuild and stale projection events cannot reactivate data.
- A new registration generation emits exactly one reference-only `stage12.retrieval_scope.bootstrap_requested` event. Idempotent refresh does not emit another root bootstrap.
- Bootstrap work is paged at no more than 200 authorized schema/record/long-field source references, revalidates authority before every page, emits existing projection requests and discards expired/revoked/drifted continuations.
- The default-off SQL runtime queries only the four Retrieval V2 event types and only `RETRIEVAL_V2_WORKSPACE_ALLOWLIST` workspaces. It cannot consume unrelated Outbox rows.

## RED evidence

- Registration emitted no bootstrap event.
- Stable pre-existing sources had no catch-up page or continuation.
- Revoked registrations had no stale-bootstrap handler.
- No dedicated Retrieval Outbox runtime or SQL event/workspace filter existed.
- Result: `5 failed, 6 passed` in the new focused suite before implementation.

## GREEN verification

| Verification | Result |
| --- | --- |
| Bootstrap/registration/runtime focused unit tests | `12 passed in 3.50s` |
| Retrieval V2 focused regression | `106 passed in 3.52s` |
| Stage12 API/Action/authorized-query boundary | `124 passed in 6.69s` |
| Full Retrieval V2 disposable PostgreSQL/pgvector file | `3 passed in 3.89s` |
| Bootstrap + SQL dual-filter PostgreSQL test alone | `1 passed in 2.66s` |
| Black check for the eight touched Python/test files | passed; eight files unchanged after formatting |
| Python `compileall` | passed |
| Alembic heads | one head: `20260730_0039` |
| Credential-pattern scan over the touched files | passed |
| `git diff --check` | passed; only existing Windows LF-to-CRLF warnings |

The real PostgreSQL test proves registration/bootstrap persistence, stable existing schema/record catch-up, relation materialization and query-level exclusion of both unrelated event types and a Retrieval event from a non-allowlisted workspace. Its transaction is rolled back and no retained business fixture is created.

## Changed files

- `backend/app/models/stage12_retrieval.py`
- `backend/alembic/versions/20260730_0038_stage12_relation_edge_identity.py`
- `backend/alembic/versions/20260730_0039_stage12_retrieval_scope_registration.py`
- `backend/app/services/retrieval_v2_scope.py`
- `backend/app/services/retrieval_v2_indexing.py`
- `backend/app/services/retrieval_v2_registration.py`
- `backend/app/services/retrieval_v2_runtime.py`
- `backend/app/workers/retrieval_v2_outbox.py`
- `backend/app/workers/retrieval_v2_outbox_runtime.py`
- related Retrieval V2 unit/integration/model/migration/API tests

## Skipped and remaining risks

- Full backend and Mini App regression are deferred to Task 10.
- Real Redis recovery/ack-once is Task 8.
- Real Provider and final-answer Case campaigns are Tasks 9–10; no quality acceptance is inferred from Task 5 component tests.
- The runtime remains default-off and has not been deployed or process-activated. First-use retrieval is asynchronous until bootstrap/projection events are consumed.
- No temporary file requires cleanup. PostgreSQL fixtures were transaction-rolled-back; no external resource was created.
