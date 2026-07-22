# Stage08 Package D / D1 — Strict Retrieval Contracts and pgvector Schema

## Objective

Implement only Task D1: strict safe retrieval contracts, Knowledge source/chunk
ORM and Alembic migration `20260720_0032`. This task establishes no source
registration, chunker, index worker, retrieval provider or API; it must not
create any Knowledge data outside disposable pgvector integration tests.

Read first:

- `docs/superpowers/plans/2026-07-20-stage08-package-d-rag-implementation.md` Task 1
- `project-docs/08-implementation/decisions/STAGE_08_D_RETRIEVAL_DATA_CONTRACT.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_D_RAG_BDD_AND_ACCEPTANCE.md`
- `backend/app/models/stage08_memory.py`, `backend/app/models/stage08_group_context.py`, and migrations `20260718_0029`, `20260720_0031` for project conventions.

## Allowed files

- Modify `backend/pyproject.toml` only to add the `pgvector` Python package.
- Create `backend/app/models/stage08_knowledge.py`.
- Modify `backend/app/models/__init__.py` only to import/export the two new ORM models.
- Create `backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py`.
- Create `backend/app/runtime/stage08_retrieval_contracts.py`.
- Create `backend/tests/unit/test_stage08_retrieval_contracts.py`.
- Extend only `backend/tests/integration/test_stage08_retrieval_pgvector.py`.
- Create `.superpowers/sdd/stage08-package-d-task-d1-report.md`.

Do not alter C1/C2/B models/contracts, UoW, services, API, Docker compose,
existing migrations, external systems or Git state. Install `pgvector` locally
only as needed to run this task; do not add any embedding/model SDK.

## Exact data contract

`Stage08KnowledgeSource` table name: `stage08_knowledge_sources`.

- UUID/timestamps mixins; `workspace_id` FK to `workspaces.id`; `source_type`
  `String(40)`; `status` `String(20)`; `source_ref` and `scope` JSONB;
  `logical_source_fingerprint` and `projection_hash` `String(64)`;
  `projection_text` nullable Text; `content_version` Integer;
  `supersedes_id` nullable self FK; `valid_until`, `revoked_at`, `deleted_at`
  timezone aware timestamps.
- exact statuses: `pending|active|replaced|revoked|expired|deleted`.
- checks: source_ref/scope JSON object; both hashes 64 lower-case hex;
  content_version > 0; an `active` source has non-empty projection text.
- unique: `(workspace_id, source_type, logical_source_fingerprint, content_version)`;
  indexes at minimum workspace/status/valid_until and workspace/logical fingerprint/version.

`Stage08KnowledgeChunk` table name: `stage08_knowledge_chunks`.

- UUID/timestamps mixins; non-null `workspace_id` FK and `source_id` FK;
  `source_version`, `ordinal`, nullable Text `chunk_text`, `chunk_hash`
  `String(64)`, non-null PostgreSQL `ARRAY(String(64))` `keyword_terms`,
  nullable `embedding_profile` `String(80)`, nullable Integer
  `embedding_version`, nullable `pgvector.sqlalchemy.Vector()` `embedding`,
  `status` `String(20)`, optional `deleted_at`.
- exact statuses: `pending|indexed|stale|deleted|failed`.
- checks: source_version > 0; ordinal >= 0; chunk_hash lower-case 64 hex;
  indexed chunk has non-empty `chunk_text`; JSON is not used for keyword terms.
- unique: `(source_id, source_version, ordinal)`; indexes at minimum
  workspace/status/source_version and source/status.
- migration must create GIN `keyword_terms` index and partial HNSW cosine
  index named `ix_stage08_knowledge_chunk_hnsw_test_profile`, using expression
  `(embedding::vector(8)) vector_cosine_ops`, only when
  `status='indexed'`, `embedding_profile='stage08.test-hash-v1'`, and
  embedding is not null.

Migration must use `CREATE EXTENSION IF NOT EXISTS vector`; downgrade drops
only D tables/indexes and **never** drops `vector` extension. It must depend
on `20260720_0031`.

## Safe contract requirements

Create frozen Pydantic safe contracts with `extra='forbid'`, strict types and
hidden error input. The public/safe retrieval view may contain only fixed
contract version, status, source type category, scope category, count, boolean
and fixed degradation/error code. It must reject/omit text, IDs/UUIDs, source
ref, scope values, hashes, profile, embedding, query, score, actor, authority,
renderer and exception diagnostic fields—even with `model_construct` / nested
object bypass attempts. Add a deep `validate_retrieval_safe_view` function that
reconstructs all nested values rather than trusting Pydantic instance type.

## TDD / verification requirements

1. First write failing unit contracts for source/chunk status shapes, invalid
hash/version, forbidden safe fields, no nested `model_construct` escape, and
safe view privacy.
2. Run unit RED before implementation and record actual output.
3. First extend integration with failing migration assertions for vector
extension, both tables/constraints, GIN and exact HNSW expression. Run RED
against head before migration exists; record it.
4. Implement the minimal models/contracts/migration, then run GREEN with only
`STAGE08_RAG_DATABASE_URL` set. Prove upgrade/downgrade/re-upgrade inside the
dedicated disposable DB and that `vector` remains after downgrade.
5. Run `python -m compileall -q` over the new model/contract, static scans for
raw Message/provider/Telegram/API/imports in those production files and
`git diff --check`.

Report exact commands/counts, migration heads, extension proof, RED/GREEN,
dependency installation, skipped tests (never as pass), scope and remaining
risks. Do not claim Package D or actual retrieval complete.
