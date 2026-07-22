# Stage09 Native P1-A N3 Independent Final Review

## Verdict

**PASS — 0 Critical / 0 Important / 0 Minor.**

This is repository-only, local-ready evidence. It is not evidence of a target-server
deployment, live PostgreSQL/pgvector/Redis/systemd validation, Nginx validation, or
external-system activity.

## Scope and constraints

Read-only review of the N3A fast review, the retained stopped-remediation record,
N1/N2/N3 assets, TDR-017, the native deployment plan, and the Stage09 progress
ledger. No deployment asset or source file was changed; only this review record was
written. No SSH, network, Docker, package installation, real
PostgreSQL, Redis, systemd, Nginx, or Git write was used.

## Review results

1. **PostgreSQL bootstrap and password input:** `stage09-p1-bootstrap.sql` uses
   `ON_ERROR_STOP`, reads only `STAGE09_P1_DATABASE_PASSWORD` into a psql variable,
   checks the `:{?variable}` existence predicate, then derives and checks a Boolean
   non-empty predicate. Both failure branches occur before `CREATE ROLE` and use
   `\\quit 1`. This is the correct psql control-flow contract for unset and empty
   target-only input; the static verifier requires the exact guards and exactly two
   non-zero exits. The password is used only as a quoted psql variable in `ALTER
   ROLE`, and no value, URL, host, or token source is embedded in the asset.

2. **Database isolation:** the bootstrap creates/updates only `stage09_p1`, creates
   only `stage09_p1` database ownership, revokes `PUBLIC` database and public-schema
   access, and enables `vector` only after connecting to the new database. The HBA
   fragment permits precisely the fixed database/role pair over local socket,
   `127.0.0.1/32`, and `::1/128`, all with `scram-sha-256`; it has no public or broad
   rule.

3. **Redis isolation and access boundary:** all three relevant locations agree on
   `unix:///run/stage09-p1/redis.sock?db=0`. Redis has `port 0`, one Unix socket,
   `protected-mode yes`, AOF, and the dedicated data directory. The Redis unit uses
   `stage09-redis:stage09-redis-socket`, creates `/run/stage09-p1` with group
   traverse permission, keeps its data directory Redis-owned, uses a restrictive
   umask, and neither loads the application runtime file nor runs application
   preflight. TDR-017 and the native plan explicitly require only `stage09-p1` as a
   supplementary member of `stage09-redis-socket`; the application does not own or
   read the Redis data directory.

4. **Migration control:** the migration unit is `Type=oneshot`, uses the protected
   application runtime and N1 isolation preflight, runs exactly `alembic upgrade
   20260720_0032`, and has no `[Install]`/`WantedBy` auto-enable path. The verifier
   rejects `head`, `latest`, direct database URLs, and duplicate/override directives.

5. **Static verifier and hostile fixtures:**
   `verify-native-data-assets.sh` requires each security-relevant directive exactly
   once and rejects extra directives even with whitespace around `=` or an empty
   reset. `test-native-data-assets.sh` covers both password guards, unsafe exit,
   public HBA, socket mismatch, TCP Redis, application-user/runtime/preflight Redis
   regressions, whitespace/reset overrides, unpinned migration, and historical
   markers. Rejection output is fixed and the fixtures assert that their marker or
   secret-like values are not leaked.

6. **Documentation and naming:** TDR-017 and
   `STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md` correctly describe this package as
   native, local-only and `local-ready`; P0a/P1-B, target-only runtime creation,
   package install, database bootstrap, service startup and ingress work remain
   separate. The SQL filename, Redis unit/config name, socket, role/database and
   fixed Alembic revision match the shipped assets. The retained
   `stage09-native-task-n3-remediation-report.md` describes an earlier stopped,
   time-bounded attempt; it does not assert completion and is correctly historical
   rather than current acceptance evidence.

## Evidence accounting

- The coordinator-provided Windows Git Bash evidence for the final N3 aggregate
  regression is `exit 0` with `native-data-assets: PASS` in approximately 34 seconds.
  It supersedes the earlier interrupted 20-second attempt recorded in the retained
  remediation report; the latter must not be used as a current failure claim.
- The N3 regression explicitly prints `psql-live-validation: SKIPPED`,
  `redis-live-validation: SKIPPED`, and `systemd-live-validation: SKIPPED`. This
  matches the plan's P0a/P1-B gate and is not represented as live evidence.
- N1's repository-only runtime regression is recorded as passing; N2's missing
  local Nginx binary remains explicitly `SKIPPED` and is outside N3 acceptance.
- `git diff --check` for the reviewed paths exited `0`; the shared dirty worktree may
  emit unrelated LF/CRLF warnings, but no whitespace error was reported.

## Remaining non-blocking deployment gates

P0a/P1-B must still produce target-host evidence for package availability, dedicated
accounts/groups and permissions, real `psql` bootstrap, pgvector, Redis socket and
ACL behavior, `systemctl`/unit status, no-secret `nginx -t`, fixed-revision offline
SQL and migration, isolated health checks, the approved HTTPS hostname/Caddy bridge,
backup readiness, and rollback. None of those actions was attempted here.
