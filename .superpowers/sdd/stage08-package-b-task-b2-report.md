# Stage08 Package B — Task B2 Report

## Scope

Task B2 implements typed, projection-only Memory lifecycle behavior using the existing B1 models/UoW and Stage06 authorization, record-read and audit services. It excludes migrations, routes/API, B3 outbox hooks, B4 Telegram/candidate adapters, provider/RAG/LangGraph/Redis/frontend work and all external calls.

## TDD Evidence

### RED

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: expected collection failure (exit `2`): both focused modules failed with `ModuleNotFoundError: No module named 'app.runtime.stage08_memory_contracts'`. The new contract and lifecycle surface did not exist before implementation.

### GREEN

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `14 passed in 0.77s` (exit `0`). The focused suite covers recursive forbidden-key rejection, malformed source fields, unknown type/non-JSON values, idempotency, canonical equal-payload supersession, conflict preservation, active membership and workspace/base/table/relation scope denial, TTL/stale-source/field-visibility fail-closed transitions, response/audit redaction, unsupported source kinds, source-value mismatch, and candidate lock/state/version/role/workspace checks.

## Changed Files

- `backend/app/runtime/stage08_memory_contracts.py` — Added strict typed projection contracts, recursive forbidden-key checks, field-key/source-reference validation and JSON-safe payload validation.
- `backend/app/services/stage08_memory.py` — Added platform-record-only materialization, source/current-visibility revalidation, identity/source fingerprints, idempotency/supersede/conflict lifecycle, fail-closed safe reads, candidate rejection and redacted audit transitions.
- `backend/tests/unit/test_stage08_memory_contracts.py` — Extended B1 tests with B2 contract rejection cases.
- `backend/tests/unit/test_stage08_memory_service.py` — Added focused in-memory lifecycle, safety and authorization coverage.

## Audit and Raw-Content Evidence

- Every B2 create/reuse/supersede/conflict/expiry/source-delete/candidate-revoke path calls the existing `record_audit_event` against the UoW session target.
- Audit inputs carry only transition metadata: entity ID/type, status, version and a fixed action/reason code. They never pass payload, scope, source refs, source fingerprints, field keys or source values.
- The focused suite uses `approved` as a payload sentinel and verifies it never appears in the generated audit entries. Safe read responses expose only `id`, `memory_type`, `version`, `scope`, `payload` and `valid_until`; source provenance/fingerprints/audit entries are absent.
- No draft payload or Telegram message is read. No provider, Telegram, Redis, RAG/vector, LangGraph, frontend or external/network call ran.

## Not Done

- No migration/model/UoW/API/router/main change, confirmed-record/outbox adapter, group candidate creation/promotion adapter, Telegram adapter, RAG/vector, LangGraph/provider, Redis, frontend or external send path.
- No Package B integration/PostgreSQL acceptance sweep was run; this Task B2 evidence is the required focused unit command only.
- No git operation or temporary cleanup action was run.

## Remaining Risks

- B2 deliberately rejects draft/Telegram sources and group scope; B3/B4 must add approved, controlled adapters before those sources can be materialized/read.
- The durable schema/UoW comes from B1. B2 lifecycle persistence will need its later PostgreSQL lifecycle acceptance coverage in B5.

## Fix Round 1 — RED

After the independent review, new focused regressions were added before changing production code for valid-state revocation, forbidden field-key names, non-finite JSON numbers, timezone-aware TTL, strict candidate versions, inactive candidate workspaces and audit allowlisting.

Command:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: expected RED (exit `1`): `27 failed, 17 passed`. The failures demonstrate the reviewed defects: accepted forbidden field-key names and NaN/Infinity/naive TTL, inactive workspace/base/table/field/source/relation chains remaining readable/materializable, permissive/native-error candidate versions, inactive-workspace revocation and audit role leakage. PostgreSQL workspace-row serialization coverage is being added separately as required by the correction brief.

## Fix Round 1 — GREEN

### Corrections

- Materialization now acquires the existing `uow.lock_workspace_for_stage08_execution(workspace_id)` lock before item-state reads and retains that transaction lock through the lifecycle decision/write. It rejects a missing or non-`active` workspace.
- Scope and source revalidation now require `active` workspace, base, table, source field, source record and customer/project relation record chains. Safe reads transition an affected active item to `deleted`, set `deleted_at`, emit the redacted audit and return `None`.
- Contracts reject forbidden field-key names case-insensitively, recursively reject NaN/+Infinity/-Infinity, require timezone-aware `valid_until`, and canonical JSON uses `allow_nan=False` as a second boundary.
- Candidate revocation now accepts only a non-bool `int` greater than zero and rejects inactive workspaces. B2 audit `permission_snapshot` contains only the fixed `action`/reason code; actor role was removed.
- Added a disposable PostgreSQL dual-session race regression. It proves, via `pg_blocking_pids`, that the second materialization blocks on the existing workspace row lock; after the first commits, a same fingerprint reuses the first item and a distinct fingerprint/same identity produces the correct conflict version `2` chain.

### GREEN commands

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_memory_postgres.py -k "materialization_workspace_lock"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `2 passed, 5 deselected in 5.68s` (exit `0`). This used the configured disposable local PostgreSQL fixture and real dual sessions. It is local evidence, not staging/production evidence.

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/integration/test_stage08_memory_postgres.py -k "memory"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `51 passed in 11.04s` (exit `0`).

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result: `20260718_0029 (head)` (exit `0`). No migration was created or changed.

### Evidence correction

The initial report's statement that active membership/field visibility and source/TTL behavior were covered was too broad: it did not cover resource lifecycle status, forbidden field-key names, finite JSON, naive TTL, strict expected-version types or PostgreSQL materialization serialization. This Fix Round adds those exact regressions; the initial claim should not be read as evidence for them.

## Safety Notes

- The tests and intended service use only structured platform-record fields; no Telegram message or draft payload is read.
- Audit assertions use a sentinel payload value and require it not to occur in audit records.
- No external network, provider, Telegram, Redis or git operation has run.
