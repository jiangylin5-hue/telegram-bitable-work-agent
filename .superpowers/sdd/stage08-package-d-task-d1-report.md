# Stage08 Package D / Task D1 Report

## Status

- Task status: `D1 implementation and dedicated-database verification passed`
- Scope: strict retrieval contracts, `Stage08KnowledgeSource` / `Stage08KnowledgeChunk` ORM, and Alembic revision `20260720_0032` only.
- Current Progress: 2026-07-20 completed real RED→GREEN against the dedicated disposable `pgvector/pgvector:pg17` database. The database is left re-upgraded at the single head `20260720_0032` for later Package D tasks.
- Package boundary: **this report does not claim Package D completion or actual retrieval capability**. Source registration, chunking, indexing workers, retrieval providers, UoW/service/API work, external embedding/LLM calls and Telegram behavior were not implemented.

## Changed Files

1. `backend/pyproject.toml`
   - Added only `pgvector>=0.4,<0.5`; no embedding/model SDK.
2. `backend/app/models/stage08_knowledge.py`
   - Added the two exact D1 ORM tables, lifecycle/hash/version/text constraints, PostgreSQL ARRAY keyword terms, unbounded `Vector()`, FKs, uniques and relational/GIN indexes.
3. `backend/app/models/__init__.py`
   - Imported/exported only `Stage08KnowledgeSource` and `Stage08KnowledgeChunk` in addition to pre-existing dirty-worktree content.
4. `backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py`
   - Added `CREATE EXTENSION IF NOT EXISTS vector`, both tables, checks/FKs/uniques/indexes, GIN keyword index and the exact profile-bound partial cosine HNSW expression index.
   - Downgrade removes only the D1 indexes/tables and never drops the shared `vector` extension.
5. `backend/app/runtime/stage08_retrieval_contracts.py`
   - Added frozen/strict/`extra='forbid'`/hidden-input private source and chunk projections plus public safe views containing only fixed categories, counts, booleans and fixed codes.
   - Added `validate_retrieval_safe_view`, which reconstructs each nested model and rejects constructed/mutated shape bypasses.
6. `backend/tests/unit/test_stage08_retrieval_contracts.py`
   - Added 56 strict contract/privacy tests.
7. `backend/tests/integration/test_stage08_retrieval_pgvector.py`
   - Retained the D0 environment-only preflight and added D1 real migration/table/constraint/ARRAY/GIN/exact HNSW assertions.
8. `.superpowers/sdd/stage08-package-d-task-d1-report.md`
   - This evidence report.

No C1/C2/B contract/model, UoW, service, API, external system, Docker compose, existing migration or Git state was changed by D1.

## Dependency Evidence

Command:

```powershell
python -m pip install "pgvector>=0.4,<0.5"
```

Actual result:

```text
Successfully installed pgvector-0.4.2
```

The declared project range is `pgvector>=0.4,<0.5`; no external embedding/model SDK was added.

## TDD RED Evidence

### Unit RED

Command, from `backend`:

```powershell
python -m pytest tests/unit/test_stage08_retrieval_contracts.py -q -W error
```

Actual result before production implementation:

```text
ModuleNotFoundError: No module named 'app.runtime.stage08_retrieval_contracts'
1 error in 0.32s
```

The failure was the expected missing D1 contract module, not a typo or environment failure.

### Migration RED

The dedicated database URL was set only in `STAGE08_RAG_DATABASE_URL`; because the existing Alembic environment reads `DATABASE_URL`, the command locally mapped `DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL`. No native/default database URL was used.

Command, from `backend`, before revision `0032` existed:

```powershell
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m alembic upgrade head
python -m alembic heads
python -m pytest tests/integration/test_stage08_retrieval_pgvector.py -q
```

Actual result:

```text
20260720_0031 (head)
2 failed, 1 passed in 0.72s
```

- The existing vector-extension preflight passed.
- Both new D1 assertions failed for the expected reason: `stage08_knowledge_sources`, `stage08_knowledge_chunks` and their indexes did not exist.

## GREEN Evidence

### Strict contracts

Command:

```powershell
python -m pytest tests/unit/test_stage08_retrieval_contracts.py -q -W error
```

Actual result:

```text
56 passed in 0.16s
```

Coverage includes exact source/chunk status sets, strict lower-case SHA-256/version/ordinal checks, active/indexed non-empty text, all forbidden safe field families, fixed safe categories/codes, privacy shape, and nested `model_construct` / mutation bypass rejection.

### Dedicated pgvector migration and combined tests

Command:

```powershell
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q -W error tests/unit/test_stage08_retrieval_contracts.py tests/integration/test_stage08_retrieval_pgvector.py
```

Fresh final actual result after re-upgrade:

```text
20260720_0032 (head)
59 passed in 0.79s
```

An earlier GREEN observation run had `57 passed, 2 failed` because SQLAlchemy's generic inspector reflects an unbounded extension `vector` as `NullType`, and PostgreSQL canonicalizes expression-index casts/predicates. The integration assertion was corrected to query `information_schema`/PostgreSQL catalogs for `udt_name=vector` and to assert PostgreSQL's canonical HNSW definition. The required database type, dimension-8 expression, cosine opclass and exact partial predicate were not relaxed. The corrected suite was run with `-W error` and passed without warnings.

### Downgrade / extension-retention / re-upgrade

Command sequence:

```powershell
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m alembic downgrade 20260720_0031
# query alembic_version, pg_extension and information_schema.tables
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
python -m pytest -q -W error tests/unit/test_stage08_retrieval_contracts.py tests/integration/test_stage08_retrieval_pgvector.py
```

Actual proof while downgraded:

```text
current_revision=20260720_0031
vector_extension_present=True
d_table_count=0
```

Actual proof after re-upgrade:

```text
20260720_0032 (head)
20260720_0032 (head)
59 passed in 0.79s
```

One earlier proof-script attempt had a Python quoting `SyntaxError`; it is explicitly excluded from evidence. Alembic had still downgraded/re-upgraded in that attempt, and the complete fresh sequence above was rerun with guarded exit codes before recording a result.

### Final database/container facts

Read-only catalog/container probes returned:

```text
vector_extension_version=0.8.5
migration_revision=20260720_0032
d_table_count=2
d_index_count=2
container_image=pgvector/pgvector:pg17 health=healthy mounts=0
```

`d_index_count=2` is the specifically queried GIN + profile-bound HNSW pair; ordinary relational/unique/primary indexes also exist and are asserted by the integration suite.

## Static Verification

Command set:

```powershell
python -m compileall -q app/models/stage08_knowledge.py app/runtime/stage08_retrieval_contracts.py
rg -n -i '\b(raw_text|raw_caption|normalized_text)\b' <D1 production files>
rg -n -i '^(from|import)\s+.*\b(telegram|message|provider|fastapi|api|httpx|requests|openai|langgraph)\b' <D1 production files>
git diff --check
```

Actual result:

```text
compileall=passed
raw_message_field_scan_matches=0
external_transport_provider_import_scan_matches=0
git diff --check exit code=0
```

Repository-wide `git diff --check` emitted existing Windows LF→CRLF conversion warnings for many dirty-worktree files, including unrelated files, but reported no whitespace errors and exited `0`. No files were staged, committed, reset, checked out or cleaned.

## Skipped Tests

- Skipped tests: `0` in the recorded D1 GREEN commands.
- Full backend suite: not run and not counted as passed; D1 was intentionally restricted to the brief's unit and dedicated-pgvector integration targets.
- Native `STAGE06_LOCAL_DATABASE_URL`: not used and not counted as evidence.
- Staging/production tests: not run; local disposable Docker evidence is not production evidence.

## Data and External Side Effects

- No Knowledge source/chunk business data was created outside disposable integration tests; D1 integration assertions only inspect schema/catalogs and create no Knowledge rows.
- No external provider, embedding model, LLM, Telegram, API route, notification, business record, draft or audit action was invoked.
- The dedicated Docker container remains running and the database remains at `20260720_0032` because later Package D tasks consume it. Final `docker compose ... down --volumes` cleanup is intentionally deferred to Package D closure, per the D0/D1 brief.
- Local `__pycache__` generated by `compileall` is ignored runtime output, not a retained project artifact.

## Remaining Risks / Next Gates

1. This is local disposable PostgreSQL evidence only; it does not prove staging/production pgvector availability or migration authority.
2. The stored `Vector()` column is intentionally unbounded. Only the partial test-profile HNSW expression casts to `vector(8)`; production profile/dimension/provider selection remains a later approved task.
3. D1 provides contracts/schema only. No source registration, canonicalizer/chunker, outbox/index worker, lifecycle service, permission re-read, retrieval provider, citation renderer or API exists yet.
4. Safe-view contracts prevent public carrier expansion at this boundary, but later D tasks must continue deep reconstruction and current-authority/source revalidation rather than trust Pydantic instance identity or vector hits.
5. The shared worktree remains heavily dirty from prior/parallel packages; D1 preserved those changes and made no Git-state mutation.

## Independent Review Remediation: Composite Source Scope/Version FK

### Review status and discovery

- Independent D1 review result: `FAIL (Important)` because the original schema used independent `source_id` and `workspace_id` FKs while `source_version` had no FK relationship to `content_version`.
- PostgreSQL could accept a chunk whose copied workspace or source version did not match the referenced source.
- The original failed review **has not been superseded**. This section records remediation evidence for a required fresh independent review; it does not claim D1, Package D or retrieval completion.

### Remediation RED

Tests were added before the fix to assert the exact source-side unique, exact chunk-side composite FK, real PostgreSQL rejection of both mismatch cases, and successful insertion of a matching tuple.

Command against the still-original `0032` schema:

```powershell
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m pytest -q -W error tests/integration/test_stage08_retrieval_pgvector.py -k 'exact_tables_columns_and_constraints or chunk_scope_tuple_mismatch or chunk_matching'
```

Valid RED result after correcting the success observation to query the inserted UUID rather than rely on psycopg's unspecified insert `rowcount`:

```text
3 failed, 1 passed, 2 deselected in 1.26s
```

Expected failures:

1. Catalog assertion raised `KeyError` for missing `uq_stage08_knowledge_source_id_workspace_version`.
2. Cross-workspace chunk insert failed the test with `DID NOT RAISE IntegrityError`.
3. Wrong-source-version chunk insert failed the test with `DID NOT RAISE IntegrityError`.

The correct source/workspace/version tuple inserted and was read back successfully. A preliminary run before the observation correction produced `4 failed, 2 deselected`; its fourth failure was only `rowcount == -1` after a successful psycopg insert and is excluded from behavioral RED evidence.

### Minimal fix

Only the four remediation-authorized files were changed:

- `backend/app/models/stage08_knowledge.py`
  - Added `UNIQUE (id, workspace_id, content_version)` named `uq_stage08_knowledge_source_id_workspace_version` while retaining primary key `id`.
  - Added `FOREIGN KEY (source_id, workspace_id, source_version) REFERENCES stage08_knowledge_sources(id, workspace_id, content_version)` named `fk_stage08_knowledge_chunk_source_scope_version`.
  - Removed the redundant source-id-only FK; the existing workspace-to-workspaces FK remains.
- `backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py`
  - Made the same unreleased-revision schema correction without adding a revision or changing downgrade/extension behavior.
- `backend/tests/integration/test_stage08_retrieval_pgvector.py`
  - Added catalog and real database enforcement tests with transaction rollback, so no Knowledge test rows persist.
- `.superpowers/sdd/stage08-package-d-task-d1-report.md`
  - Appended this remediation evidence.

No public contract, API, UoW, service, Docker, dependency, C1/C2/B, external system or Git state changed.

### Remediation GREEN and migration lifecycle

The disposable database was downgraded first so edited unreleased revision `0032` could be reapplied.

Command sequence:

```powershell
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m alembic downgrade 20260720_0031
# read-only revision/extension/table catalog proof
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
python -m pytest -q -W error tests/integration/test_stage08_retrieval_pgvector.py -k 'exact_tables_columns_and_constraints or chunk_scope_tuple_mismatch or chunk_matching'
```

Actual downgrade proof:

```text
current_revision=20260720_0031
vector_extension_present=True
d_table_count=0
```

Actual re-upgrade/focused GREEN:

```text
20260720_0032 (head)
20260720_0032 (head)
4 passed, 2 deselected in 1.11s
```

The two mismatch cases now raise SQLAlchemy `IntegrityError` from PostgreSQL, and the matching tuple remains insertable.

### Full focused suite and catalog proof

Command:

```powershell
$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL
python -m pytest -q -W error tests/unit/test_stage08_retrieval_contracts.py tests/integration/test_stage08_retrieval_pgvector.py
```

Actual result:

```text
62 passed in 1.24s
```

Read-only `pg_constraint` proof:

```text
fk_stage08_knowledge_chunk_source_scope_version|f|FOREIGN KEY (source_id, workspace_id, source_version) REFERENCES stage08_knowledge_sources(id, workspace_id, content_version)
uq_stage08_knowledge_source_id_workspace_version|u|UNIQUE (id, workspace_id, content_version)
constraint_count=2
```

Additional verification:

```text
python -m compileall -q app/models/stage08_knowledge.py alembic/versions/20260720_0032_stage08_knowledge_indexing.py -> exit 0
git diff --check -> exit 0, only pre-existing worktree LF-to-CRLF warnings
skipped tests in full focused GREEN -> 0
```

The dedicated database is left at `20260720_0032`; the container remains running for later D tasks. Fresh independent review is still required before the original D1 review status can be replaced.
