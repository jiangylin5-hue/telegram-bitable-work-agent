# Stage08 Package D / D1 Independent Review Brief

Review only D1 contracts/models/migration/tests and write findings solely to
`.superpowers/sdd/stage08-package-d-task-d1-review-report.md`. Do not modify
application/test/compose/report files, database state, Docker, external
systems or Git.

Read:

- D1 brief and implementation report;
- D data contract and BDD;
- changed files listed in the brief;
- current migration head and dedicated pgvector test fixture.

Review requirements:

1. Verify allowed-file scope and no accidental C1/C2/B/UoW/service/API/provider/Telegram behavior.
2. Attack `RetrievalSafeView` and every nested contract with dict, subclass,
   `model_construct`, fake nested usage and extra fields. Confirm public
   surface contains no content/body, UUID/ID, source ref, scope values, hash,
   profile, embedding, query, score, actor, authority, renderer or diagnostics.
3. Inspect ORM/migration against exact source/chunk names, fields, statuses,
   JSON/hash/version/check/unique/index contracts. In dedicated pgvector DB
   verify `vector`, GIN keyword index and exact partial HNSW expression/index
   name through PostgreSQL catalog rather than SQLAlchemy `NullType` reflection.
4. Independently prove downgrade removes only D objects, retains `vector`,
   re-upgrade restores a single `20260720_0032` head. Do not accept default or
   native DB as evidence.
5. Re-run proportionate strict unit/integration with `-W error`, compile and
   production import/privacy scans. Treat skipped/unavailable checks as not
   passed. Record C/I/M, commands, scope, PASS/FAIL. A PASS permits D2 only.
