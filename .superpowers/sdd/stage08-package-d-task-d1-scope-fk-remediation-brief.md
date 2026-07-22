# Stage08 Package D / D1 — Source/Chunk Scope Composite-FK Remediation

## Defect

Independent D1 review found an Important data-integrity failure: the
`Stage08KnowledgeChunk.source_id`, copied `workspace_id`, and copied
`source_version` were enforced only by separate constraints/FKs. PostgreSQL
could therefore accept a chunk that references a source in another workspace,
or whose copied source version differs from the referenced source's
`content_version`. This violates the approved D contract before any runtime
provider can revalidate it.

## Scope

Modify only:

- `backend/app/models/stage08_knowledge.py`
- `backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py`
- `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- `.superpowers/sdd/stage08-package-d-task-d1-report.md` (append remediation)

Do not modify source/chunk public contracts, API, UoW, services, Docker,
dependency version, C1/C2/B, external systems or Git state.

## Required fix

1. Add a source-side unique constraint exactly on
   `(id, workspace_id, content_version)`; retained primary key `id` remains.
2. Add a chunk-side composite `ForeignKeyConstraint` exactly from
   `(source_id, workspace_id, source_version)` to
   `(stage08_knowledge_sources.id, stage08_knowledge_sources.workspace_id,
   stage08_knowledge_sources.content_version)`.
3. Update model and migration consistently. The migration is still revision
   `20260720_0032`; it has not been released, so edit it rather than create a
   new revision. Downgrade must remove the two tables and still never drop the
   `vector` extension.
4. Add real dedicated pgvector integration RED tests that attempt:

   - a chunk with the UUID of a source in workspace A but copied workspace B;
   - a chunk with source UUID/workspace correct but source_version different
     from the source content_version.

   Both must be rejected by PostgreSQL (`IntegrityError`/DBAPI constraint
   failure), not merely a service assertion. A matching tuple must still be
   insertable for existing migration/HNSW/GIN proof.
5. First run the new tests before the fix and record RED. Then run focused
   unit/integration with `-W error`, catalogue checks, downgrade to 0031 and
   re-upgrade to 0032. Prove extension `vector` remains after downgrade.
6. Update the D1 report with discovery, RED/GREEN commands/counts and the fact
   that the original D1 review has not yet been superseded until fresh review.

Do not claim D1, Package D or retrieval completion.
