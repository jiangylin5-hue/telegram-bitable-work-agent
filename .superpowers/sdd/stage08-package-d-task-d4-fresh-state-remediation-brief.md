# Stage08 Package D / D4 Fresh Current-State Revalidation Remediation Brief

## Status and Scope

- Status: `approved corrective implementation boundary`
- Trigger: fresh independent review found `1 Critical / 1 Important / 1 Minor` in D4 current-state consumption.
- Goal: ensure private evidence/citation/view never release material after a source, chunk, employee, membership, access grant, base/table/view, or business relation has changed in PostgreSQL.
- This corrects existing D4 requirements; it does not change architecture, schema, public API, permission model, provider selection, retention, deployment, or external integration. D5 remains blocked.

## Allowed Files

- Modify: `backend/app/services/stage08_retrieval_provider.py`
- Modify: `backend/tests/unit/test_stage08_retrieval_provider.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Modify: `.superpowers/sdd/stage08-package-d-task-d4-report.md`

Do not modify models, migrations, contracts, UoW interfaces, Memory/C1/C2/D3 services, API, Docker/configuration, Git state, or external systems.

## Required Corrections

### 1. Local fresh-current-state read boundary

For `SqlAlchemyStage06PlatformUnitOfWork` only, D4 must issue explicit, narrowly scoped ORM current-state reads with `populate_existing`/targeted refresh semantics for the entities needed to revalidate a result: workspace, employee, workspace member/grant, employee base/table/view, requested customer/project/relation records, KnowledgeSource, KnowledgeChunk, and current Memory lineage/item metadata. Do not call global `expire_all()` or mutate/flush unrelated session state. For the existing in-memory UoW, retain direct current-object validation.

The fresh read boundary must be used by both authority revalidation and every hit revalidation before `render_private_evidence`, `safe_citations`, and `safe_view`. It must not rely on ordinary `Session.get`/identity-map `scalars` results once a search result exists. Any query/read/shape failure is unavailable/no-hit; no private text, citation, score, identifier, error detail, or exception carrier may escape.

### 2. Terminal timestamp coherence

An active readable source requires `revoked_at is None` and `deleted_at is None`; an indexed readable chunk requires `deleted_at is None`. Enforce these predicates in PostgreSQL structured candidate query, in-memory candidate path, and post-selection/render revalidation. Contradictory status/timestamp rows are fail-closed without writing lifecycle/audit changes.

### 3. Memory root-lineage fingerprint verification

For `memory_item` source consumption, rederive the current valid same-workspace root `supersedes_id` chain without reading payload. Require consistent `memory_type`, normalized scope (including identity token), predecessor state/version ordering, and `SHA-256("memory_lineage:" + root_memory_item_id)` to equal `source.logical_source_fingerprint`. Missing/cyclic/cross-workspace/type/scope/version/fingerprint drift fails closed. Do not merely check 64-hex format or restore old content.

## TDD Required Evidence

Write RED first, then GREEN.

1. Dedicated pgvector, with previously searched result held in one SQLAlchemy session: change source to revoked/replaced or chunk to stale/deleted through an independent current database operation, then render/citations/view must have no hit. Repeat employee pause, member/grant/view or business-relation drift; authority becomes unavailable and no private evidence releases. Tests must prove database current facts, not only mutate ORM objects.
2. In-memory plus dedicated PostgreSQL contradictory source `revoked_at`/`deleted_at` and indexed chunk `deleted_at` rows are excluded from candidate and render paths without side effects.
3. Valid format but wrong root fingerprint, cross-lineage fingerprint, and malformed current Memory lineage each return no evidence; valid root lineage remains readable.
4. Existing valid keyword-only/hybrid ranking, no-default-test-provider, 12 cap, citation redaction, real GIN/`<=>` query evidence and D1–D4 regressions remain GREEN.

Run from `backend`:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/services/stage08_retrieval_provider.py
```

Update D4 report with the original findings, RED/GREEN evidence, exact database-refresh behavior, static/privacy scope check, dedicated pgvector facts, skips and cleanup. Do not claim D4, D5, Package D, Stage08, external semantic-provider quality, or production completion before fresh independent review.
