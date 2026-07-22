# Stage08 Package D / D0 — Disposable pgvector Environment Preflight

## Objective

Create the isolated local pgvector integration environment required by Package
D and prove the `vector` extension exists. This task is an environment/test
fixture only; it does not introduce Knowledge ORM, migrations, services,
APIs, embeddings, sources/chunks, or production database changes.

Read first:

- `docs/superpowers/plans/2026-07-20-stage08-package-d-rag-implementation.md` (Task 0)
- `project-docs/08-implementation/decisions/STAGE_08_D_RETRIEVAL_DATA_CONTRACT.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_D_RAG_BDD_AND_ACCEPTANCE.md`

## Required files

- Create `backend/docker-compose.stage08-rag.yml`.
- Create `backend/tests/integration/test_stage08_retrieval_pgvector.py` with
  the preflight test only; later tasks will extend it.
- Create `.superpowers/sdd/stage08-package-d-task-d0-report.md`.

## Exact requirements

1. Compose file uses `pgvector/pgvector:pg17`, database/user/password all
   named `stage08_rag_test` / `stage08_rag` / `stage08_rag`, loopback-only
   `127.0.0.1:55432:5432`, and `tmpfs: /var/lib/postgresql/data`. No bind
   mounts, no application default database, no existing `DATABASE_URL`.
2. Integration test is marked `postgres` and reads only
   `STAGE08_RAG_DATABASE_URL`. It must never fall back to `DATABASE_URL` or
   `STAGE06_LOCAL_DATABASE_URL`. If missing, it skips with exact useful
   reason; if connected, it queries `pg_extension` and asserts `vector`
   exists. It may report extension version in assertion failure but must not
   print DSN/credentials.
3. Before starting the compose service, run the new test with the variable
   unset and record RED/skip output. Do not count a skip as a pass.
4. Start Docker compose with `up -d --wait`. Construct and use only
   `STAGE08_RAG_DATABASE_URL=postgresql+psycopg://stage08_rag:stage08_rag@127.0.0.1:55432/stage08_rag_test`.
   Run the integration test; it must pass and prove installed `vector`.
5. Verify the compose container has no named/bind volume and record the
   Docker image/container status without secrets. Do not call external AI,
   Telegram or provider APIs.
6. Do not tear down the container after GREEN because D1 will use it. The
   package closure owns `down --volumes`; record this deferred cleanup.
7. Run `git diff --check` and a narrow static scan proving the test has no
   fallback env names or external application imports. Preserve all dirty
   worktree changes; never stage, commit, reset, checkout or clean.

## Report

Record exact RED/skip, Docker command/result, extension proof, GREEN result,
container isolation, static/diff commands, deferred cleanup, and risks. Do
not claim Package D, pgvector migration, real retrieval, real provider,
Telegram or deployment completion.
