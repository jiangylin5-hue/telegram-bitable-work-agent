# Stage08 Package D / D4 Fresh Current-State Remediation Independent Review Brief

## Review Goal and Boundary

- Status: `pending implementation evidence`
- Review only after the D4 remediation implementation reports its GREEN evidence.
- Decision target: determine whether the existing D4 current-state requirements are now satisfied. This is not an approval to start D5.
- Expected report: `.superpowers/sdd/stage08-package-d-task-d4-fresh-state-review-report.md`.
- Source tree is shared and dirty. Treat the remediation brief, D4 initial review, D4 report, Package D data contract/BDD, C1 scope and Memory projection as the review baseline; do not assume an empty `git diff` is evidence.

## Permitted Change Surface

The reviewer may create or update only the expected review report. Do not modify application code, tests, contracts, models, migrations, UoW interfaces, APIs, Docker/configuration, Git state, external systems, or records outside disposable test transactions.

## Required Functional Checks

1. **Fresh database facts after search.** In a dedicated pgvector test, retain a successful result in an SQLAlchemy session, make a separately issued current database change to revoke/replace the source or stale/delete its indexed chunk, verify the database current fact, then invoke private evidence, citation and safe-view consumption. All must be unavailable/no-hit with no private text or identifier escape. Repeat for a paused employee and at least one membership/grant/view or business relation change. Verify the implementation uses narrowly scoped `populate_existing` or targeted refresh reads; it must not invoke `expire_all()`.
2. **Lifecycle timestamp coherence.** For both in-memory and dedicated pgvector paths, active source rows with `revoked_at` or `deleted_at`, and indexed chunk rows with `deleted_at`, must be excluded before ranking and again at render. Confirm no lifecycle, audit, outbox or source/chunk mutation occurs.
3. **Memory root fingerprint.** Valid SHA-256-shaped but incorrect root fingerprint, cross-lineage fingerprint and malformed/cyclic/current lineage must yield no evidence. A valid current same-workspace lineage with matching type, normalized scope including identity token, predecessor state/version and recomputed root fingerprint must remain readable. Review must not read or disclose Memory payload.
4. **No regression of D4 product boundary.** Existing keyword-only default, explicit deterministic test embedding only, 1–12 cap, GIN `&&` and pgvector cosine `<=>` production query, safe citation DTO redaction, source-specific `document_projection` / `approved_summary` fail-closed state, and no provider/network/API/UoW/schema expansion remain intact.

## Mandatory Commands

Run from `backend` with test cache disabled and warnings as errors:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval_provider.py
```

Also verify dedicated database cleanliness after tests (no retained D4 source/chunk/outbox rows) and report `vector` version plus migration head without credentials/DSN values.

## Report and Gate

The report must list Critical, Important and Minor findings separately; include the exact fresh-current-state proof, command outcomes, static/privacy/scope review, skipped work and cleanup. It must not disclose payload, query, UUID, token, DSN, score/vector or authority internals.

Only `0 Critical / 0 Important` permits the root agent to consider D4 closure. A nonblocking Minor may be recorded, but D5 remains blocked until the root updates the active Stage08 progress documents. Do not claim D5, Package D, Stage08, real provider quality, deployment, or production completion.
