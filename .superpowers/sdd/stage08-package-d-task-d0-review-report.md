# Stage08 Package D / D0 Independent Review Report

## Scope and verdict

- Review scope: D0 disposable pgvector compose fixture and its one extension
  preflight test only.
- Review date: 2026-07-20.
- Review verdict: **PASS** — D0 satisfies the environment gate and may permit
  Task D1 to begin.
- Critical: **PASS** (0 findings).
- Important: **PASS** (0 findings).
- Minor: **PASS** (0 findings).

This is not Package D completion evidence. It does not review or establish a
Knowledge schema, migration, source/chunk lifecycle, retrieval, provider,
Telegram, deployment, or package-level cleanup.

## Review boundary and inspected inputs

Reviewed, without changing implementation, Docker state, Git state, or any
external system:

- `.superpowers/sdd/stage08-package-d-task-d0-brief.md`
- `.superpowers/sdd/stage08-package-d-task-d0-report.md`
- `backend/docker-compose.stage08-rag.yml`
- `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- `project-docs/08-implementation/decisions/STAGE_08_D_RETRIEVAL_DATA_CONTRACT.md`
- `docs/superpowers/plans/2026-07-20-stage08-package-d-rag-implementation.md`
  (Task 0)

The test source has one environment constant,
`STAGE08_RAG_DATABASE_URL`, and calls `os.getenv` only for that constant. It
does not format or print the DSN; the only assertion message mentions the
extension name. A targeted scan also found no fallback environment names and
no application imports.

## Independent unset preflight — skip, not a pass

From `backend`, I deliberately removed `STAGE08_RAG_DATABASE_URL` while
setting deliberately unusable values for `DATABASE_URL` and
`STAGE06_LOCAL_DATABASE_URL`; that proves the test does not silently fall
back to either value. Command (the placeholder values are intentionally not
credentials):

```powershell
$env:STAGE08_RAG_DATABASE_URL = $null
$env:DATABASE_URL = 'postgresql+psycopg://fallback_user:fallback_secret@127.0.0.1:59999/fallback_db'
$env:STAGE06_LOCAL_DATABASE_URL = 'postgresql+psycopg://stage06_user:stage06_secret@127.0.0.1:59998/stage06_db'
python -m pytest tests/integration/test_stage08_retrieval_pgvector.py -q
```

Result (exit code 0 because pytest records a skip):

```text
s                                                                        [100%]
SKIPPED [1] tests\integration\test_stage08_retrieval_pgvector.py:15: STAGE08_RAG_DATABASE_URL is required for the Stage08 pgvector preflight
1 skipped in 0.23s
```

This is the expected explicit missing-environment precondition and is
recorded as a skip/RED condition, never as GREEN evidence.

## Independent dedicated-DSN preflight — GREEN

With only the dedicated local test DSN set and both fallback variables removed:

```powershell
$env:STAGE08_RAG_DATABASE_URL = 'postgresql+psycopg://stage08_rag:stage08_rag@127.0.0.1:55432/stage08_rag_test'
$env:DATABASE_URL = $null
$env:STAGE06_LOCAL_DATABASE_URL = $null
python -m pytest tests/integration/test_stage08_retrieval_pgvector.py -q
```

Result:

```text
.                                                                        [100%]
1 passed in 0.48s
```

The passed test queries `pg_extension` for `vector`. A separate, read-only
in-container query verified the installed version without printing a DSN:

```powershell
docker compose -f docker-compose.stage08-rag.yml exec -T stage08-rag-postgres psql -U stage08_rag -d stage08_rag_test -Atc "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
```

```text
0.8.5
```

## Isolation and compose inspection

The reviewed compose file specifies `pgvector/pgvector:pg17`,
`POSTGRES_DB=stage08_rag_test`, `POSTGRES_USER=stage08_rag`, fixed disposable
test password `stage08_rag`, `127.0.0.1:55432:5432`, and
`tmpfs: /var/lib/postgresql/data`. It has no named volume, bind mount,
application database name, or application database URL reference.

Read-only Docker inspection:

```powershell
docker compose -f docker-compose.stage08-rag.yml ps
docker compose -f docker-compose.stage08-rag.yml images
docker inspect <stage08-rag-postgres-container> --format 'image={{.Config.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}} mounts={{json .Mounts}} binds={{json .HostConfig.Binds}} ports={{json .NetworkSettings.Ports}} tmpfs={{json .HostConfig.Tmpfs}}'
```

Relevant results:

```text
backend-stage08-rag-postgres-1  pgvector/pgvector:pg17  Up (healthy)  127.0.0.1:55432->5432/tcp
image=pgvector/pgvector:pg17 status=running health=healthy mounts=[] binds=null ports={"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"55432"}]} tmpfs={"/var/lib/postgresql/data":""}
```

The original D0 report's historical record remains consistent with this
review: the first image pull/start timed out before the image was available,
then the image was pulled and the service became healthy. That historical
initial-pull timeout is not treated as a current failure. The container is
intentionally retained for D1; deferred cleanup belongs to Package D closure
and must eventually run `docker compose -f backend/docker-compose.stage08-rag.yml down --volumes`.

## Static and Git checks

```powershell
rg -n --pcre2 "STAGE06_LOCAL_DATABASE_URL|(?<!STAGE08_RAG_)DATABASE_URL|^from app|^import app" tests/integration/test_stage08_retrieval_pgvector.py
```

Result: exit code 1/no matches, recorded as `static-scan: no fallback env
names or application imports found`.

```powershell
git diff --check
```

Result: exit code 0 and no whitespace-error output. Git emitted only existing
dirty-worktree CRLF conversion warnings for unrelated files; this review did
not stage, commit, reset, checkout, clean, or otherwise alter Git state.

## Remaining limits and cleanup

- The running container is a local, disposable, tmpfs-backed D1 dependency;
  it is not staging or production evidence.
- Do not count the unset-variable skip as a test pass.
- Do not tear the service down while downstream D work explicitly relies on
  it; Package D closure owns `down --volumes` and must record its execution.
