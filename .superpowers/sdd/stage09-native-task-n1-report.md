# Stage09 Native P1-A N1 Report

## Status

- Status: complete — repository-only, offline implementation
- Scope: Native runtime key-name contract and offline preflight validators only
- External actions: none. No SSH, network, Docker/Compose, container, database,
  Redis, systemd, Nginx, Telegram, provider, or remote write action was performed.

## Changed Files

- `deploy/stage09-native/runtime/runtime.env.example`
  - Documents the target-only runtime location `/etc/stage09-p1/runtime.env`.
  - Provides required key names, safe P1 defaults, empty Telegram allowlists, and
    non-secret target placeholders only.
- `deploy/stage09-native/scripts/validate-runtime-presence.sh`
  - Parses without sourcing the runtime file and never prints or hashes a value.
  - Requires the P1 contract keys; enforces `staging`, all P1 safe modes, empty
    Telegram allowlists, loopback/Unix-socket data URLs, a compliant artifact and
    matching immutable release directory, and a 1024..65535 internal Nginx port.
- `deploy/stage09-native/scripts/verify-native-isolation.sh`
  - Accepts a runtime file, invokes the contract validator with suppressed output,
    and returns only fixed `native-isolation: pass` or `native-isolation: fail`.
  - Rejects historical Stage03/Stage07 and Docker/Compose/volume/container markers
    as well as non-dry-run wording.
- `.gitignore`
  - Ignores the Stage09 runtime directory contents while allowing only
    `runtime.env.example` to be tracked.

## Verification

TDD red check, before implementation:

```text
C:\Program Files\Git\bin\sh.exe deploy/stage09-native/scripts/validate-runtime-presence.sh <safe-fixture>
exit 127 (script did not exist)
```

Post-implementation offline checks:

```text
sh -n deploy/stage09-native/scripts/validate-runtime-presence.sh     PASS
sh -n deploy/stage09-native/scripts/verify-native-isolation.sh      PASS
safe fixture: validator                                              PASS
safe fixture: isolation verifier                                     PASS
Stage03 database marker fixture                                      rejected, no value leak
non-empty Telegram allowlist fixture                                 rejected, no value leak
unsafe Telegram mode fixture                                         rejected, no value leak
public Redis URL fixture                                              rejected, no value leak
Stage07/compose marker fixture: validator passes; isolation rejects, no value leak
git check-ignore runtime.env / runtime.env.example                   PASS (ignored / trackable)
```

All test fixtures were no-secret placeholders and were deleted after the checks.

## Not Done

- No systemd unit, Nginx, PostgreSQL, pgvector, Redis, Caddy, release manifest,
  server inventory, migration, deployment, or health-check asset was created.
- No runtime file was written at `/etc/stage09-p1/runtime.env`; that path remains
  target-server-only and requires its separate authorization gate.

## Remaining Risks

- These scripts validate only supplied file text; they do not prove target-server
  file permissions, service ownership, socket availability, release integrity, or
  live service isolation. Those belong to later Stage09 tasks.

## 2026-07-22 URL Hardening Remediation

### Finding And Reproduction

The original PostgreSQL validator accepted a loopback authority followed by a
conflicting `host` query parameter. A no-secret `mktemp -d` fixture with that
shape returned the fixed status `runtime-validation: pass`, proving the bypass
before the change. The fixture was removed by its shell trap.

### Remediation

- Replaced authority-only PostgreSQL and Redis validation with complete canonical
  URL whitelists. Accepted PostgreSQL forms are fixed `stage09_p1` loopback
  endpoints on port 5432, or the one fixed local socket form. Accepted Redis
  forms are fixed database-0 loopback endpoints on port 6379, or the one fixed
  P1 socket/database form. Query overrides, percent encoding, fragments, extra
  parameters, alternate ports/databases and public hosts are rejected.
- Moved the Stage03/Stage07/Docker/Compose/volume/container/non-dry-run marker
  denylist into `validate-runtime-presence.sh`. The isolation wrapper retains the
  same check as defense in depth.
- Added `deploy/stage09-native/scripts/test-runtime-preflight.sh`. It uses
  `mktemp -d` and a cleanup trap, writes no-secret fixtures only, suppresses
  validator output, and prints assertion names with fixed PASS/FAIL results.
- Documented that staging requires `TELEGRAM_WEBHOOK_SECRET` because the current
  application settings require it. It remains a target-only random local webhook
  validation nonce, not a Bot token; it neither enables Telegram nor writes to
  an external system. The validator checks only presence.

### Commands And Results

```text
sh -n validate-runtime-presence.sh                                  PASS
sh -n verify-native-isolation.sh                                    PASS
sh -n test-runtime-preflight.sh                                     PASS
sh test-runtime-preflight.sh                                        PASS
  canonical-loopback, canonical-unix-socket                         PASS
  query-host-override, encoded-host-override, public-host           rejected
  Stage03 marker, Stage07 marker, allowlist, unsafe mode            rejected
  all rejected cases                                                 no value leak
validate runtime.env.example                                        PASS
verify-native-isolation runtime.env.example                         PASS
```

No SSH, network, Docker/Compose, container, server configuration, database,
Redis, Telegram, provider, or other external action was performed. Temporary
fixtures were cleaned by the test script trap.
