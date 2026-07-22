# Stage08 Package D / D1 Independent Review Report

## Status

- Review date: 2026-07-20
- Review scope: D1 strict retrieval contracts, Knowledge source/chunk ORM,
  Alembic revision `20260720_0032`, and D1 unit/integration evidence only.
- Overall verdict: **FAIL**.
- Critical: **PASS** — 0 findings.
- Important: **FAIL** — 1 finding.
- Minor: **PASS** — 0 findings.
- Gate: **D2 is not permitted by this review** until the Important finding is
  fixed, covered by real PostgreSQL regression, and independently re-reviewed.

This report does not claim Package D completion or retrieval capability. It
does not review or establish source registration, chunking/index workers,
retrieval providers, UoW/service/API behavior, external embeddings, Telegram,
staging, production, or deployment.

## Finding

### Important

1. **The database does not bind a chunk's copied workspace to its referenced
   source workspace.**

   The approved D retrieval data contract defines
   `Stage08KnowledgeChunk.source_id / workspace_id` as non-null foreign keys
   whose values “二者必须一致”. The copied `workspace_id` is a structured
   retrieval prefilter, so this is a security-relevant relational invariant,
   not merely duplicated display metadata.

   Both the ORM and migrated catalog instead have two independent foreign
   keys:

   ```text
   FOREIGN KEY (source_id) REFERENCES stage08_knowledge_sources(id)
   FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
   ```

   There is no composite foreign key, composite referenced unique constraint,
   check, or other database invariant tying the chunk pair to the source row.
   The same schema also does not bind copied `source_version` to the referenced
   source's `content_version`. Consequently, the database can accept a chunk
   whose `workspace_id` is a valid workspace A while `source_id` identifies a
   Knowledge source in workspace B (and whose copied source version differs).
   Later post-retrieval permission revalidation may reject such a row, but D1
   currently has no such service, and the PostgreSQL truth itself violates the
   approved source/chunk relation contract.

   Required remediation before D2: add an enforceable relational invariant in
   ORM and migration. A composite source key and chunk composite FK that binds
   `source_id`, `workspace_id`, and, if retained as a copied invariant,
   `source_version` to source `id`, `workspace_id`, and `content_version` is the
   direct design. Add a dedicated pgvector PostgreSQL regression proving that
   a cross-workspace (and version-mismatched, if included) chunk is rejected,
   while a matching chunk succeeds. Re-run downgrade/re-upgrade and request a
   fresh independent D1 review.

No Critical or Minor findings were identified independently of this blocker.

## Review boundary and allowed-file scope

Read before review:

- `.superpowers/sdd/stage08-package-d-task-d1-review-brief.md`
- `.superpowers/sdd/stage08-package-d-task-d1-brief.md`
- `.superpowers/sdd/stage08-package-d-task-d1-report.md`
- `project-docs/08-implementation/decisions/STAGE_08_D_RETRIEVAL_DATA_CONTRACT.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_D_RAG_BDD_AND_ACCEPTANCE.md`
- `docs/superpowers/plans/2026-07-20-stage08-package-d-rag-implementation.md`
  (Task 1)
- the D1 model, runtime contract, migration, unit/integration files and the
  predecessor model/migration conventions named in the brief.

The D1 implementation report lists only allowed D1 files. The only tracked
dependency delta is `pgvector>=0.4,<0.5`; no embedding/model SDK was added.
The D1-specific `app.models.__init__` delta only imports/exports
`Stage08KnowledgeSource` and `Stage08KnowledgeChunk`; other Stage08 imports in
that already-dirty tracked file predate D1. D1 production files import no UoW,
service, API, provider, Telegram, Message, network, OpenAI, or LangGraph layer.
They contain no C1/C2/B behavior.

The shared worktree contains extensive pre-existing Stage07/Stage08 changes,
so repository-wide dirty status is not attributed to D1. This review created
only this report as a source-controlled deliverable; it did not edit
application, tests, migrations, compose, project truth documents, or Git
state, and did not contact an external system.

## Strict DTO and privacy attacks

The public surface is exactly:

```text
RetrievalSafeView:
contract_version,status,sources,result_count,has_results,degradation_code,error_code

RetrievalSafeSourceView:
source_type_category,scope_category,count,available
```

Both use `extra='forbid'`, strict types, frozen instances, and hidden input in
validation errors. An independent in-memory attack corpus covered every
forbidden carrier family in both outer and nested positions: text/content/body,
generic ID/UUID and source/chunk/record/field IDs, source ref, scope values,
hash, profile, embedding, query, score, actor, authority, renderer, exception,
diagnostic and diagnostics. It also attacked ordinary/subclass dicts, a fake
nested object, invalid nested and outer `model_construct`, a mutated nested
subclass, list-based nested bypass, and a valid subclass rehydration.

Command shape, from `backend`:

```powershell
@'<56-case in-memory dict/subclass/model_construct/fake/extra corpus>'@ |
  python -
```

Fresh result:

```text
privacy_attack_cases=56 all_rejected_or_cleanly_rebuilt=True
```

All malicious cases were rejected without reflecting injected secret markers
in error strings. The valid subclass case was rebuilt as the exact
`RetrievalSafeSourceView` base type, and its JSON contained none of the tested
forbidden carriers. The existing 56-case unit file also exercises strict
statuses, hashes, versions, non-empty active/indexed text, fixed safe values,
outer extras, nested `model_construct`, mutated nested objects and exact safe
field sets.

## Dedicated pgvector catalog and migration evidence

The reviewer process initially had `STAGE08_RAG_DATABASE_URL` unset and did
not fall back to `DATABASE_URL` or `STAGE06_LOCAL_DATABASE_URL`. Root then
explicitly authorized use of the D0 disposable `stage08_rag_test` DSN and the
reversible `0031 -> 0032` migration proof, with a mandatory final restore to
`0032`. For Alembic only, `DATABASE_URL` was temporarily mapped from that same
dedicated variable because the existing Alembic environment reads
`DATABASE_URL`; native/default values were removed.

Catalog inspection at the final restored state proved:

- one database revision `20260720_0032` and one code head
  `20260720_0032 (head)`;
- `vector` extension version `0.8.5`;
- exact source/chunk table and column names, UUID/timestamptz fields, JSONB
  source ref/scope, `varchar(64)[]` non-null keyword terms, and unbounded
  nullable `vector` embedding;
- exact source/chunk status, JSON object, lower-case 64-hex, positive version,
  non-negative ordinal, active projection and indexed text checks;
- the required source/chunk unique constraints and relational B-tree indexes;
- GIN `keyword_terms` index; and
- exact HNSW catalog definition:

```text
CREATE INDEX ix_stage08_knowledge_chunk_hnsw_test_profile
ON public.stage08_knowledge_chunks USING hnsw
(((embedding)::vector(8)) vector_cosine_ops)
WHERE status='indexed'
  AND embedding_profile='stage08.test-hash-v1'
  AND embedding IS NOT NULL
```

The review queried `information_schema` and PostgreSQL catalogs, not
SQLAlchemy's `NullType` reflection, to prove the `vector` type and canonical
index expression.

### Corrected downgrade / re-upgrade proof

Authorized command sequence:

```powershell
$env:STAGE08_RAG_DATABASE_URL = <authorized D0 disposable pgvector DSN>
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:STAGE06_LOCAL_DATABASE_URL -ErrorAction SilentlyContinue
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m alembic downgrade 20260720_0031
# read-only catalog snapshot
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
```

Fresh corrected snapshots:

```text
before:
revision=20260720_0032 vector=0.8.5 d_tables=2 d_indexes=10
non_d_tables=58 hash=4b5e02fb7f6d565417e2dbdd6fae907c20c939f0a1bdaffa17f2ea4d200ef6a6
non_d_indexes=136 hash=19bdd85433d0a90617cff61fe883296fbdf9bc44c6fac662626ad9d10cf48c32

downgraded:
revision=20260720_0031 vector=0.8.5 d_tables=0 d_indexes=0
non_d_tables=58 hash=4b5e02fb7f6d565417e2dbdd6fae907c20c939f0a1bdaffa17f2ea4d200ef6a6
non_d_indexes=136 hash=19bdd85433d0a90617cff61fe883296fbdf9bc44c6fac662626ad9d10cf48c32

re-upgraded:
revision=20260720_0032 vector=0.8.5 d_tables=2 d_indexes=10
non_d_tables=58 hash=4b5e02fb7f6d565417e2dbdd6fae907c20c939f0a1bdaffa17f2ea4d200ef6a6
non_d_indexes=136 hash=19bdd85433d0a90617cff61fe883296fbdf9bc44c6fac662626ad9d10cf48c32
20260720_0032 (head)
20260720_0032 (head)
```

This proves downgrade removed only the two D tables and their ten D-owned
primary/unique/ordinary/GIN/HNSW indexes, retained all non-D tables/indexes and
the shared `vector` extension, and re-upgrade restored one `0032` head.

An earlier snapshot classifier omitted the two `pk_stage08_knowledge_*`
indexes from its D-index prefix set, making its non-D index hash differ by two
entries. That classifier output is excluded from evidence. The migration was
already guardedly restored, the classifier was corrected, and the complete
sequence above was freshly rerun. A separate first catalog query used invalid
SQLAlchemy `:t::regclass` bind syntax and is also excluded; the corrected
`CAST(:t AS regclass)` query completed and supplied the catalog facts above.

## Tests and static verification

Final strict command after re-upgrade, with only the dedicated pgvector
variable configured and pytest cache disabled:

```powershell
python -m pytest -q -W error -p no:cacheprovider \
  tests/unit/test_stage08_retrieval_contracts.py \
  tests/integration/test_stage08_retrieval_pgvector.py
```

Fresh result:

```text
59 passed in 0.82s
```

This is 56 unit and 3 dedicated-pgvector integration cases, with zero skips
and zero warnings. A pre-migration-review run of the same 59 tests also passed
in `0.79s`; the post-re-upgrade result above is the final evidence.

Compile verification:

```powershell
python -m compileall -q \
  app/models/stage08_knowledge.py \
  app/runtime/stage08_retrieval_contracts.py \
  alembic/versions/20260720_0032_stage08_knowledge_indexing.py
```

Result: `compileall_exit=0`.

Production scans returned zero matches for raw Telegram message/body carriers,
behavior-layer imports, UoW/service/API/provider/network/OpenAI/LangGraph and
Telegram dependencies in the D1 model, contract and migration files. The only
dependency addition remains `pgvector`.

## Skipped tests, remaining risks, and cleanup

- Skipped tests: `0` in the recorded strict D1 commands.
- Full backend suite: not run and not counted as passed; the focused 59-case
  corpus is proportional to D1.
- Default/native PostgreSQL: not used and not counted as evidence.
- Staging/production and external provider/Telegram checks: not run and not
  applicable to D1; local disposable pgvector is not production evidence.
- The Important cross-workspace source/chunk relational invariant remains the
  blocker. Passing DTO, catalog, index and migration tests do not waive it.
- The disposable database was restored to `20260720_0032`; no Knowledge
  business rows were created by this review. Final container teardown remains
  Package D closure work and was not performed.
- No temporary review script or test data was retained. `compileall` reused
  the existing ignored `__pycache__` locations; no tracked application/test
  artifact was added. No Git stage/commit/reset/checkout/clean occurred.

---

## Fresh Composite-FK Remediation Re-review

### Superseding conclusion

- Re-review date: 2026-07-20
- Re-review scope: only the D1 source/chunk scope-and-version composite-FK
  remediation, its dedicated PostgreSQL tests, and preservation of the
  previously reviewed D1 contracts/migration/index boundary.
- Fresh verdict: **PASS**.
- Critical: **PASS** — 0 findings.
- Important: **PASS** — 0 open findings; the original Important finding is
  verified closed rather than waived.
- Minor: **PASS** — 0 findings.
- Gate: **D1 now permits D2 to begin**.

This fresh conclusion supersedes the original FAIL disposition at the top of
this report for the D1 gate. The original finding and evidence remain above as
the audit trail. This is not Package D completion, retrieval capability,
staging/production evidence, or authorization for any work beyond D2's
already-approved boundary.

### Reviewed remediation and scope

Read before re-review:

- `.superpowers/sdd/stage08-package-d-task-d1-scope-fk-remediation-brief.md`
- the appended remediation section in
  `.superpowers/sdd/stage08-package-d-task-d1-report.md`
- this original D1 review report and finding;
- the current ORM, migration and dedicated pgvector integration test.

The remediation implements the brief's exact relational shape in both ORM
metadata and unreleased revision `20260720_0032`:

```text
UNIQUE (id, workspace_id, content_version)
  name=uq_stage08_knowledge_source_id_workspace_version

FOREIGN KEY (source_id, workspace_id, source_version)
  REFERENCES stage08_knowledge_sources
    (id, workspace_id, content_version)
  name=fk_stage08_knowledge_chunk_source_scope_version
```

The source primary key remains `id`; the chunk's independent
`workspace_id -> workspaces.id` FK remains; the redundant source-id-only FK was
removed. No new revision, public contract, API, UoW, service, provider,
Telegram, C1/C2/B, Docker or dependency behavior was introduced. The review
updated only this report and made no Git or external-system mutation.

### Independent real PostgreSQL attacks

The reviewer did not rely only on the implementation tests. With only the
authorized dedicated synthetic `STAGE08_RAG_DATABASE_URL` set, an independent
SQLAlchemy Core attack created two disposable workspaces, one source in
workspace A, and a valid eight-dimensional test-profile chunk tuple inside a
single outer transaction. Separate nested savepoints attempted:

1. the source UUID from workspace A with copied workspace B; and
2. the correct source UUID/workspace with `source_version=8` against source
   `content_version=7`.

Fresh result:

```text
cross_workspace:
  IntegrityError / fk_stage08_knowledge_chunk_source_scope_version
wrong_version:
  IntegrityError / fk_stage08_knowledge_chunk_source_scope_version
matching_count=1
post_rollback_workspaces=0
post_rollback_sources=0
post_rollback_chunks=0
```

Thus both mismatch cases were rejected by PostgreSQL's named FK, not by a
service assertion, while the matching tuple was insertable. The outer
transaction rollback left no Knowledge or workspace test rows.

The same fresh catalog query returned exactly two remediation constraints:

```text
fk_stage08_knowledge_chunk_source_scope_version|f|
FOREIGN KEY (source_id, workspace_id, source_version)
REFERENCES stage08_knowledge_sources(id, workspace_id, content_version)

uq_stage08_knowledge_source_id_workspace_version|u|
UNIQUE (id, workspace_id, content_version)
```

This closes the original cross-workspace and wrong-version integrity finding.

### Fresh migration lifecycle proof

For Alembic only, `DATABASE_URL` was temporarily mapped from the same
dedicated synthetic `STAGE08_RAG_DATABASE_URL`; default/native variables were
removed. A guarded sequence performed `0032 -> 0031 -> 0032` and compared
non-D catalog sets before, during and after:

```text
before:
revision=20260720_0032 vector=0.8.5 d_tables=2 d_indexes=11
non_d_tables=58 hash=4b5e02fb7f6d565417e2dbdd6fae907c20c939f0a1bdaffa17f2ea4d200ef6a6
non_d_indexes=136 hash=19bdd85433d0a90617cff61fe883296fbdf9bc44c6fac662626ad9d10cf48c32

downgraded:
revision=20260720_0031 vector=0.8.5 d_tables=0 d_indexes=0
non_d_tables=58 hash=4b5e02fb7f6d565417e2dbdd6fae907c20c939f0a1bdaffa17f2ea4d200ef6a6
non_d_indexes=136 hash=19bdd85433d0a90617cff61fe883296fbdf9bc44c6fac662626ad9d10cf48c32

restored:
revision=20260720_0032 vector=0.8.5 d_tables=2 d_indexes=11
non_d_tables=58 hash=4b5e02fb7f6d565417e2dbdd6fae907c20c939f0a1bdaffa17f2ea4d200ef6a6
non_d_indexes=136 hash=19bdd85433d0a90617cff61fe883296fbdf9bc44c6fac662626ad9d10cf48c32
20260720_0032 (head)
20260720_0032 (head)
```

The eleventh D-owned index is the new composite source unique. Downgrade
removed only D objects and retained `vector`; guarded re-upgrade restored one
code/database head at `20260720_0032`.

### Fresh final verification

After re-upgrade, the complete D1 focused corpus was rerun with warnings as
errors and pytest cache disabled:

```powershell
python -m pytest -q -W error -p no:cacheprovider \
  tests/unit/test_stage08_retrieval_contracts.py \
  tests/integration/test_stage08_retrieval_pgvector.py
```

Fresh final result:

```text
62 passed in 1.19s
```

This is 56 strict contract/privacy cases and 6 dedicated pgvector integration
cases, including both real mismatch attacks and the matching tuple. Skipped
tests: `0`; warnings: `0`.

Additional verification:

```text
compileall(model + migration)=exit 0
forbidden behavior/import scan=0 matches
remediation-file trailing whitespace scan=0 matches
git diff --check (remediation paths)=exit 0
```

The full backend suite, default/native PostgreSQL, staging/production,
external Provider/LLM and Telegram were not run and are not counted as passed.
The dedicated database is restored at `20260720_0032`; no review business data
or temporary script remains. Container teardown remains Package D closure
work.
