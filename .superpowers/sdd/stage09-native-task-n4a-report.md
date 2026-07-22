# Stage09 Native P1-A N4A Report

## Status

- Status: local-ready only
- Scope: sealed release-layout verification, deterministic release manifest, and fixed-revision offline migration rendering.
- Current Progress: N4A implementation and repository-only checks completed on 2026-07-22. No target server, service, database, Docker, network, or credential was used.

## Changed Files

- `deploy/stage09-native/scripts/verify-release-layout.sh`
- `deploy/stage09-native/scripts/create-release-manifest.sh`
- `deploy/stage09-native/scripts/verify-fixed-migration-offline.sh`
- `deploy/stage09-native/scripts/verify-release-assets.sh`
- `deploy/stage09-native/scripts/test-release-assets.sh`
- `project-docs/08-implementation/STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md`

## Verification

- `deploy/stage09-native/scripts/verify-release-assets.sh` passed.
- `deploy/stage09-native/scripts/test-release-assets.sh` passed. It validates invalid release/artifact inputs, forbidden private-path guards, sorted SHA-256 manifest/atomic-write requirements, and the no-`DATABASE_URL` fallback contract.
- Git Bash `sh -n` passed for all five N4A scripts.

## Skipped Tests

- Live release-layout, manifest generation, and Alembic offline SQL rendering were skipped: this workstation has no `/opt/stage09-p1/releases/<artifact-id>` fixture or fixed target venv. The migration script deliberately fails closed when `/opt/stage09-p1/venv/<artifact-id>/bin/python` is unavailable.

## Remaining Risks

- N4A is not deployment evidence. P1-B must create the reviewed release tree and venv, run the fixed-revision SQL rendering, validate the separate `/var/www/stage09-p1/<artifact-id>` static asset tree, and retain the resulting checksum evidence.

## Temporary Cleanup

- No temporary release, manifest, SQL, runtime, credential, or service artifact was retained.
