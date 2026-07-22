# Stage09 Native P1-A N2 Report

## Status

- Status: complete — repository-only, offline implementation.
- Scope: native application `systemd` units, internal-only Nginx template,
  strict offline renderer, and repository-safe static regression checks.
- External actions: none. No SSH, network, Docker/Compose, container, database,
  Redis, systemd, Nginx, Caddy, Telegram, provider, server, or remote write
  action was performed.

## Changed Files

- `deploy/stage09-native/systemd/stage09-p1-api.service`
  - Runs only `uvicorn app.main:app` from `/opt/stage09-p1/current-venv`, bound
    to `127.0.0.1:18080`.
- `deploy/stage09-native/systemd/stage09-p1-worker.service`
  - Runs the existing `python -m app.workers.stage03_runtime` entry without a
    listening address or port.
- `deploy/stage09-native/systemd/stage09-p1-outbox-bridge.service`
  - Runs the existing `python -m app.workers.stage03_outbox_bridge_runtime`
    entry without a listening address or port.
- All three units use `User=stage09-p1`, `Group=stage09-p1`, the fixed runtime
  environment file, the fixed release/current-venv paths, N1
  `verify-native-isolation.sh` as `ExecStartPre`, and the required systemd
  hardening/restart controls. They declare no service dependencies.
- `deploy/stage09-native/nginx/stage09-p1.conf.template`
  - Is an internal-only server block with parameterized non-public listen and
    Caddy-source CIDR values; it serves only the listed static paths from
    `/var/www/stage09-p1/current` and proxies every other same-origin path to
    loopback API `127.0.0.1:18080`.
- `deploy/stage09-native/scripts/render-nginx-config.sh`
  - Strictly accepts only private/loopback IPv4 bind addresses, unprivileged
    ports, and non-public source CIDRs. It rejects public bind/CIDR values,
    placeholders, Stage03/Stage07 and container markers. Success writes only
    the local rendered template to stdout; all rejection paths return the fixed
    `nginx-render: fail` text without echoing an input.
- `deploy/stage09-native/scripts/verify-native-service-assets.sh`
  - Statically checks the exact user/group/runtime/preflight/hardening/entry
    contract, absence of service dependencies and forbidden paths/markers, and
    the internal Nginx template shape.
- `deploy/stage09-native/scripts/test-native-service-assets.sh`
  - Creates no-secret `mktemp` fixtures, removes them through a shell trap, and
    validates safe rendering plus public bind, public CIDR, privileged port and
    Stage03 marker rejection without input-value leaks.

## Verification

TDD red check before N2 production assets existed:

```text
sh deploy/stage09-native/scripts/test-native-service-assets.sh
exit 1: render-nginx-config.sh did not exist
```

Post-implementation offline checks:

```text
sh -n render-nginx-config.sh                         PASS
sh -n verify-native-service-assets.sh                PASS
sh -n test-native-service-assets.sh                  PASS
sh test-native-service-assets.sh                     PASS
  safe renderer and static asset verifier            PASS
  public bind, 0.0.0.0/0, port 80, Stage03 marker    rejected without value leak
git diff --check -- deploy/stage09-native            PASS
```

The local environment does not provide an `nginx` executable, so the optional
no-secret `nginx -t` invocation within the regression script reported
`nginx-config-syntax: SKIPPED`. The fixture and conditional invocation remain
in the repository for an authorized host that has Nginx installed.

## Not Done And Remaining Risks

- No PostgreSQL, pgvector, Redis, SQL, runtime file, release artifact, server
  inventory, systemd installation/activation, Nginx test/reload, Caddy route,
  service start, or remote deployment was performed.
- The P0a-verified bind address, Caddy source CIDR, hostname and actual Caddy
  bridge route are intentionally absent. Only no-secret local fixtures are
  used until P0a supplies them.
- Offline static evidence cannot prove target-server permissions, unit runtime
  behavior, Nginx module availability, Caddy reachability, or live isolation.

## 2026-07-22 N2 Review Remediation

### Root Cause

The first asset verifier used a global text substitution to ignore the two
historical worker module names. That mixed a permitted Python code compatibility
name with forbidden Stage03 operational dependencies and did not prove directive
cardinality against empty resets, duplicates, or later overrides.

### Correction

- The native plan and TDR-017 now define the exact compatibility exception:
  worker/outbox may each contain one `stage03` occurrence only in their exact,
  designated `ExecStart` module. It remains a code compatibility name, not a
  Stage03 Docker/service/database/Redis/network/runtime dependency.
- `verify-native-service-assets.sh` now has no text-substitution exemption. API
  permits zero `stage03` occurrences; worker/outbox each permit exactly one,
  and the exact `ExecStart` cardinality check anchors that occurrence.
- Every required unit directive is now checked as exactly one assignment with
  its exact safe value. Empty resets, duplicates and later overrides fail;
  `ExecStartPre` must be the exact non-optional N1 preflight line.
- Added regression fixtures for duplicate `User=`, extra Stage03 marker, and
  port 443 fixed-output rejection. The existing Nginx binary gate remains
  `SKIPPED` when unavailable; it is not represented as a successful `nginx -t`.

### Re-verification

```text
sh -n render-nginx-config.sh                         PASS
sh -n verify-native-service-assets.sh                PASS
sh -n test-native-service-assets.sh                  PASS
sh test-native-service-assets.sh                     PASS
  duplicate User directive                           rejected
  extra worker Stage03 marker / API Stage03 marker   rejected
  empty NoNewPrivileges reset / optional preflight   rejected
  port 80 and port 443                               rejected without input leak
  safe renderer and exact static verifier            PASS
  nginx -t                                           SKIPPED (binary unavailable)
```

External actions: none. No service, network, remote, Docker/Compose, database,
Redis, Nginx, Caddy, or target-server action was performed.

## 2026-07-22 Assignment-Whitespace Remediation

### Root Cause And Correction

The unit verifier counted only assignments written as `Directive=`. A systemd
line such as `Directive = value` could therefore evade the old count while the
canonical directive remained present. `require_exactly_one_directive` now counts
`^[[:space:]]*Directive[[:space:]]*=` and still requires exactly one canonical,
exact line. Dependency and forbidden-user rejection patterns use the same
whitespace-tolerant assignment form.

### Regression Evidence

The repository-safe temporary-unit copies now verify fixed-failure rejection for
`NoNewPrivileges = false`, `EnvironmentFile =`, `ExecStartPre = /bin/false`,
`ExecStart = /bin/false`, and `User = root`. All outputs are compared to the
fixed `native-service-assets: fail` text, so no fixture content is emitted.

```text
sh test-native-service-assets.sh                     PASS
  all five spaced unsafe assignment classes          rejected
  existing strict-render and exact-cardinality cases PASS
  nginx -t                                           SKIPPED (binary unavailable)
```

No remote, external, service, database, Redis, Nginx, Caddy, or target-server
action was performed.
