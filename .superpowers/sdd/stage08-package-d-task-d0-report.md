# Stage08 Package D / D0 Report — Disposable pgvector Preflight

## Status

- Task status: complete (D0 environment fixture only)
- Scope: dedicated disposable local pgvector compose service and extension preflight test
- Out of scope and not changed: Knowledge ORM, migrations, services, APIs, embeddings, sources/chunks, existing databases, providers, Telegram, or Git state

## Files changed

- `backend/docker-compose.stage08-rag.yml` — isolated `pgvector/pgvector:pg17` service.
- `backend/tests/integration/test_stage08_retrieval_pgvector.py` — `postgres`-marked extension preflight only.
- `.superpowers/sdd/stage08-package-d-task-d0-report.md` — this evidence report.

## RED / unset-variable evidence

Before starting the compose service, the variable was removed from the test
process and the new test was run from `backend`:

```powershell
$env:STAGE08_RAG_DATABASE_URL = $null
python -m pytest tests/integration/test_stage08_retrieval_pgvector.py -q
```

Actual output:

```text
s                                                                        [100%]
SKIPPED [1] tests\integration\test_stage08_retrieval_pgvector.py:15: STAGE08_RAG_DATABASE_URL is required for the Stage08 pgvector preflight
1 skipped in 0.33s
```

This is deliberately recorded as a skip/RED precondition, not as a pass.
The test reads only `STAGE08_RAG_DATABASE_URL`; it has no fallback to
`DATABASE_URL` or `STAGE06_LOCAL_DATABASE_URL`.

## Docker environment evidence

The compose definition uses exactly:

- image: `pgvector/pgvector:pg17`
- database/user/password names: `stage08_rag_test` / `stage08_rag` / configured fixed test credential
- loopback-only port: `127.0.0.1:55432:5432`
- data storage: `tmpfs: /var/lib/postgresql/data`
- no application database URL, bind mount, or named volume.

The first `docker compose ... up -d --wait` did not complete within 124
seconds because the required image had not yet been downloaded. Inspection
confirmed no container and no local image. The required Docker image was then
pulled successfully (digest `sha256:d2ef61f42ef767baa5a1475393303cc235bcd92febd9d7014eddb48b41f3bad0`).

The service was then started successfully:

```powershell
docker compose -f backend/docker-compose.stage08-rag.yml up -d --wait --force-recreate
```

Actual result:

```text
Container backend-stage08-rag-postgres-1 Recreated
Container backend-stage08-rag-postgres-1 Started
Container backend-stage08-rag-postgres-1 Healthy
```

The health check performs an idempotent `CREATE EXTENSION IF NOT EXISTS
vector` only within this disposable tmpfs database, then checks readiness.
This is needed because the pgvector image supplies the extension files but a
fresh PostgreSQL database does not automatically register the extension.

## GREEN / extension proof

Only the task-specific environment variable was set for the test process;
the value was not printed. `DATABASE_URL` and `STAGE06_LOCAL_DATABASE_URL`
were removed from that process before execution.

```powershell
python -m pytest tests/integration/test_stage08_retrieval_pgvector.py -q
```

Actual result:

```text
.                                                                        [100%]
1 passed in 0.43s
```

An independent in-container query returned the installed extension version:

```text
0.8.5
```

## Container isolation evidence

`docker compose -f docker-compose.stage08-rag.yml ps` reported:

```text
backend-stage08-rag-postgres-1   pgvector/pgvector:pg17   Up (healthy)   127.0.0.1:55432->5432/tcp
```

`docker inspect` reported the following sanitized fields:

```text
image=pgvector/pgvector:pg17 status=running health=healthy mounts=[] binds=null ports={"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"55432"}]}
```

Therefore the container has no named or bind volumes and exposes PostgreSQL
only on loopback port 55432.

## Static and diff checks

```powershell
rg -n --pcre2 "STAGE06_LOCAL_DATABASE_URL|(?<!STAGE08_RAG_)DATABASE_URL|^from app|^import app" tests/integration/test_stage08_retrieval_pgvector.py
```

Actual result: `static-scan: no fallback env names or application imports found`.

```powershell
git diff --check
```

Actual result: exit code 0, with no whitespace-error output. Git emitted
existing-worktree CRLF conversion warnings for unrelated dirty files; no
unrelated files were modified, staged, committed, reset, checked out, or
cleaned.

## Deferred cleanup and risks

- The healthy container is intentionally still running for D1. Do **not** run
  `docker compose -f backend/docker-compose.stage08-rag.yml down --volumes`
  until Package D closure owns cleanup.
- This is local disposable Docker evidence only, not staging, production,
  migration, retrieval, provider, Telegram, or Package D completion evidence.
- The service data is intentionally ephemeral (`tmpfs`); a recreate/restart
  requires the compose health check to register `vector` again.
