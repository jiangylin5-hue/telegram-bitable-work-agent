# Stage09 Native P1-A N4A Remediation Report

## Status

- Status: local-ready only; C-01 and I-01 remediation completed on 2026-07-22.
- Scope: fixed non-secret Stage09 offline Alembic dialect URL, executable sealed-release/manifest fixtures, and executable offline-migration fixture.
- Boundary: no SSH, network, Docker, service, database, credential, or target-server action was used.

## Root Cause

- C-01: removing `DATABASE_URL` let Alembic/config initialization select its normal fallback rather than proving the offline render used an explicit Stage09-only dialect URL.
- I-01: the former test only inspected source text, so it did not prove the fixed-layout validator, deterministic manifest generator, or migration wrapper executed together.

## Changed Files

- `deploy/stage09-native/scripts/verify-fixed-migration-offline.sh`
  - defines the exact non-secret `stage09_p1` placeholder URL and supplies it explicitly to both offline Alembic commands; it does not source or read runtime configuration.
- `deploy/stage09-native/scripts/test-release-assets.sh`
  - creates and cleans a copied fixed-layout fixture, executes layout/manifest twice, rejects a private `.env` without leaking its fixture value, and executes a copied migration wrapper against a fake Alembic Python entrypoint written with `printf` (no heredoc or `cat` fixture writer).
- `deploy/stage09-native/scripts/verify-release-assets.sh`
  - statically requires the exact Stage09-only URL twice and rejects legacy `ads_agent`, runtime loading, and shell sourcing.

## Verification

Executed from the repository with Git Bash:

- `sh deploy/stage09-native/scripts/test-release-assets.sh`
  - passed;
  - created a temporary fixed-release tree, ran copied layout and manifest scripts twice, and confirmed byte-identical hash-only relative manifest lines;
  - confirmed `.env` rejection with no `fixture-secret-value` output leak;
  - invoked copied migration wrapper with a fake parent `DATABASE_URL=fixture-secret-value`, and the fake Alembic entrypoint accepted only `postgresql+psycopg://stage09_p1:offline-placeholder@127.0.0.1:5432/stage09_p1` for both `heads` and `upgrade 20260720_0032 --sql`.
- `sh deploy/stage09-native/scripts/verify-release-assets.sh`
  - passed static contract verification.
- `sh -n deploy/stage09-native/scripts/{verify-release-layout,create-release-manifest,verify-fixed-migration-offline,verify-release-assets,test-release-assets}.sh`
  - passed.
- `git diff --check`
  - passed (pre-existing shared-worktree CRLF warnings may still be emitted by Git).

## Remaining Risks

- This is local fixture evidence only. P1-B must still create the real fixed-location release tree and venv, run the wrapper against its actual Alembic environment, validate the separate static tree, and retain target-side checksum/SQL evidence.

## Temporary Cleanup

- Every release, manifest, fake Python, marker, SQL, and private `.env` fixture is created below `mktemp` and removed by the test trap.
