# Stage12 Native Release Candidate Local Gate

## Status

- Status: `passed-local-candidate`
- Date: 2026-08-01 Asia/Shanghai
- Scope: Grounded per-slot Provider candidate, P3 report gates, full local regression, real local PostgreSQL/pgvector, Mini App and repository-native release assets
- Source parent: `b9fc058`
- Production status: not deployed or activated; Stage11/r76 remains production authority

## Changed Files

- `backend/scripts/stage12_real_quality_report.py`
- `backend/tests/unit/test_stage12_real_quality_report.py`
- `backend/tests/integration/test_online_postgres_smoke.py`
- `deploy/stage09-native/systemd/stage09-p1-migrate.service`
- `deploy/stage09-native/scripts/verify-fixed-migration-offline.sh`
- `deploy/stage09-native/scripts/verify-native-data-assets.sh`
- `deploy/stage09-native/scripts/verify-release-layout.sh`
- `deploy/stage09-native/scripts/verify-release-assets.sh`
- native asset contract tests
- active Stage12 progress and acceptance documents

## What Changed

The future P3 report now requires all `144/144` answers to have
`answer_source=real_provider`, exact `fallback_count=0`, and zero transport,
schema, grounding and language failure rates. The latency gate now applies the
documented `<= 8000 ms` limit to the worst round P95 instead of the mean of the
three round P95 values.

The legacy Stage02 online PostgreSQL smoke no longer hard-codes the old
`20260728_0034` revision. It compares the migrated database with the current
repository Alembic head, which is `20260730_0039` for this candidate.

The first native-server preflight exposed a separate release-asset drift: the
native migrate unit and offline verifier still stopped at Stage10 revision
`20260728_0034`. RED/GREEN shell tests now require fixed revision
`20260730_0039`, require every Stage12 migration file `0035` through `0039` in
the sealed release, and reject `upgrade head`. This closes the risk that new
Stage12 code could start against an intentionally unmigrated database.

The first assembled r77 server candidate was rejected before activation. Its
source/runtime/manifest/offline-migration gates passed, but static parity
rejected the standard venv `lib64 -> lib` compatibility symlink. After the
candidate-only link was removed, static parity passed and the Ubuntu rollback
fixture exposed a pre-existing test portability defect: three Bash-only
`$(< file)` reads ran under declared `/bin/sh` and returned empty receipts on
Ubuntu dash. The fixture now uses POSIX `$(cat file)` and the release contract
rejects recurrence. r77 remains rejected; a new immutable candidate must be
built from the corrected pushed commit.

## Verification

| Gate | Result |
| --- | --- |
| P3 report RED/GREEN and final-campaign tests | `24 passed`; final focused rerun `15 passed` |
| Full backend | `2519 passed, 40 skipped` |
| Disposable native PostgreSQL Stage02 | `17 passed` |
| Disposable native PostgreSQL collaboration | `3 passed` |
| Disposable native PostgreSQL/pgvector retrieval | `17 passed` |
| Alembic | database current and repository head both `20260730_0039` |
| pgvector | `0.8.3`, installed in persistent `extensions` schema for disposable reset safety |
| Unexpected PostgreSQL schemas | `0` |
| Mini App | `79 files`, `413 passed` |
| Production frontend build | PASS, `1853 modules transformed` |
| Native asset fixture scripts | eight repository-safe suites PASS |
| Python compileall | PASS |
| Black | three changed Python files left unchanged after formatting |
| `git diff --check` | PASS |

The native asset suites covered data assets, service assets, internal/public
SSE Nginx templates, runtime preflight, readiness rollback behavior, release
layout and static parity. Their live `psql`, Redis, systemd and `nginx -t`
branches remain server gates and are not counted as local passes.

## Skipped Tests

The full backend reported 40 explicit environment skips:

- 3 real Redis integration tests because this Windows host has no native Redis;
- 17 Stage02 PostgreSQL tests, subsequently passed `17/17` against the disposable native PostgreSQL database;
- 3 Stage08 collaboration PostgreSQL tests, subsequently passed `3/3`;
- 17 Stage08 pgvector tests, subsequently passed `17/17`.

The unchanged Redis Streams implementation retains its 2026-07-30 disposable
real Redis evidence at `3/3`. A fresh native Redis execution is mandatory on
the target Ubuntu server before candidate activation. The legacy Docker
retirement fixture hung under Git Bash's Windows process model and was
terminated; it must also rerun on Ubuntu. No Docker/Compose deployment was
used or accepted.

## Remaining Risks

- Native server preflight, release install, migration readback, systemd, Redis,
  Nginx and rollback proof remain Task11.
- Exactly one deployed `48 x 3` P3 campaign remains Task12; local P1/P2 does
  not substitute for it.
- Real Telegram inbound/outbound validation remains restricted to the existing
  factual allowlisted test chat and has not run for this candidate.
- Production-wide Stage12 activation remains a separate final user decision.

## Temporary Cleanup

- Disposable database `ads_agent_stage12_test_20260801_01` was verified idle,
  dropped, and read back absent. The business database `ads_agent` was not
  modified.
- Generated candidate-comparison files under `backend/.tmp` were deleted after
  immutable evidence had been retained. Empty inaccessible pytest directories
  contain no files and are not Git-visible.
- No local Redis service/container, Telegram send, production migration,
  confirmed Action, business write or external Provider write was created.
