# Stage09 Native N4A R2 Final Review

## Scope

- Read-only review of the R2 remediation record, release-layout verifier,
  manifest writer, offline fixture test, and static verifier.
- No SSH, network, database, Docker, service, or target-host operation ran.

## Verified

- `verify-release-layout.sh` has exactly 21 required P1-B paths: 2 backend,
  1 runtime, 1 Nginx, 2 PostgreSQL, 1 Redis, 5 systemd, and 9 script assets.
- It rejects a linked release root, any link below that root, and every
  required path unless it is a non-link regular file.
- `create-release-manifest.sh` invokes the layout verifier before creating its
  temporary output; therefore a missing required asset cannot leave a manifest.
- The fixture creates the full allowlist, deletes `stage09-p1-api.service`,
  then proves both layout and manifest fail with fixed generic output. It also
  proves no fixture path or fixture secret is emitted and no output manifest is
  created.
- The fixture executes deterministic-manifest comparison and the explicit
  fixed offline database URL path; it does not depend on runtime settings.

## Fresh Verification

- `C:\\Program Files\\Git\\bin\\bash.exe deploy/stage09-native/scripts/test-release-assets.sh`
  -> `release-assets: PASS`.
- `C:\\Program Files\\Git\\bin\\bash.exe deploy/stage09-native/scripts/verify-release-assets.sh`
  -> `release-assets: pass`.
- `git diff --check` returned exit 0; it reported only existing CRLF conversion
  warnings and no whitespace error.

## Verdict

- C: 0
- I: 0
- M: 1 -- target-host P0a/P1-B evidence (real fixed path, native venv Alembic
  SQL, Nginx/static tree, service readiness) is deliberately still unrun.
- Repository-only N4A R2 remediation: PASS. Overall release acceptance remains
  HOLD pending that external target-host evidence.
