# Stage09 Native P1-A N2 Independent Review

## Scope And Method

- Scope: `AGENTS.md`, TDR-017, Stage09 deployment-plan sections 1/2/3/5/6/7,
  N1 runtime/preflight assets and report, plus all N2 systemd, Nginx, renderer,
  verifier and regression-test assets.
- Method: repository source inspection only. Per review constraint, no files
  other than this report were changed; no SSH, network, Docker, service,
  Nginx, systemd, or test command was executed.
- P0a: the bind address, Caddy source CIDR, hostname, and bridge path remain
  unconfirmed. N2 correctly keeps them absent; this remains a P1-B blocker.

## Verdict

- **Spec compliance: FAIL**
- **Task quality: FAIL**

The API unit satisfies the fixed account, environment, N1 preflight,
loopback-only API and hardening requirements. All three units share the fixed
`current`/`current-venv` form, and worker/outbox commands specify no listener
address or port. The Nginx template has no 80/443 listener, limits static
serving to `/`, `/index.html`, `/assets/`, and `/favicon.ico` under
`/var/www/stage09-p1/current`, and proxies all remaining routes only to
`127.0.0.1:18080`. The renderer rejects unsupported bind/CIDR/port syntax and
uses fixed failure text on rejection paths.

However, the worker and outbox units retain explicit Stage03 runtime entries,
contrary to the hard no-Stage03 dependency rule. The asset verifier then
deliberately replaces those same Stage03 strings before applying its forbidden
marker check, so it masks rather than detects the violation.

## Findings

### Critical

1. **Stage03 dependency is present and expressly exempted from validation.**

   - `stage09-p1-worker.service:11` executes
     `app.workers.stage03_runtime`; `stage09-p1-outbox-bridge.service:11`
     executes `app.workers.stage03_outbox_bridge_runtime`.
   - This violates the stated hard boundary that all three native units have no
     Stage03/Stage07/Docker dependency. The plan's historical wording about an
     “existing worker entry” cannot override the current hard constraint.
   - `verify-native-service-assets.sh:46-50` substitutes both forbidden
     `stage03` module names with allowlisted text before checking for forbidden
     markers, and lines 57-60 require those entries. Therefore its PASS result
     is not evidence of the required isolation.
   - Required correction: introduce or select Stage09-native worker and outbox
     entry points with no Stage03 dependency, point the two units to them, and
     remove the substitution exemption. Add negative tests proving that any
     `stage03`, `stage07`, Docker, or Compose marker in each unit is rejected.

### Important

1. **The static unit verifier can be bypassed by later directive resets or
   duplicate directives while still finding the required line.**

   `verify-native-service-assets.sh:27-38` only asserts that one required line
   occurs. It does not reject duplicate `EnvironmentFile`, `ExecStartPre`, or
   `ExecStart` directives, nor an empty reset directive placed after a valid
   one. Such a change can preserve the searched line while changing systemd's
   effective configuration, undermining the claimed exact preflight and fixed
   runtime contract. Reject duplicate/reset directives and verify the effective
   cardinality/order for these security-critical keys.

2. **`nginx -t` has no passing evidence.**

   The N2 report explicitly says `nginx-config-syntax: SKIPPED` because the
   local environment lacks `nginx` (report lines 68-71); the regression script
   itself makes this conditional (lines 54-65). This is an environment
   limitation, not a successful syntax check, and cannot satisfy host/module
   compatibility evidence. The fixture is useful, but an authorized host with
   Nginx must run and retain the no-secret `nginx -t` result before P1-B.

### Minor

1. **The regression script tests port 80 but not port 443.**

   `test-native-service-assets.sh:79-86` proves rejection of 80 only. The
   implementation's 1024-minimum rule also rejects 443, but the hard 80/443
   requirement should have an explicit no-value-leak 443 regression case.

## Positive Checks

- Each current unit uses `User=stage09-p1`, `Group=stage09-p1`, the exact
  `/etc/stage09-p1/runtime.env`, an ordinary (not `-`-prefixed) N1
  `verify-native-isolation.sh` `ExecStartPre`, `NoNewPrivileges`, `PrivateTmp`,
  `ProtectHome`, `ProtectSystem=strict`, and restart/backoff.
- The API is exactly `127.0.0.1:18080`; no service dependencies are declared;
  worker/outbox unit command lines do not declare a listening port.
- The renderer only accepts RFC1918/loopback IPv4 bind addresses, non-public
  CIDRs, and ports 1024..65535. Rejection output is the fixed
  `nginx-render: fail` text, so rejected values are not echoed.
- N2 does not hard-code P0a bridge values. The report correctly calls their
  absence a remaining risk/blocker rather than deployment evidence.

## Required Re-review Gate

Re-review after replacing the two Stage03 entries and removing the validator
exemption, tightening the unit verifier against effective-directive bypasses,
adding explicit 443 rejection coverage, and obtaining an authorized-host
no-secret `nginx -t` result. P0a remains separately blocked until its approved
read-only inventory confirms the bridge values.

---

## 2026-07-22 N2 Remediation Re-review

### Scope And Method

- Reviewed the updated TDR-017, native deployment plan, all three units, the
  Nginx template, renderer, verifier, regression script, and N2 report.
- Source inspection only; no tests, fixtures, services, network, SSH, Docker,
  Nginx, or other external actions were executed.

### Verdict

- **Spec compliance: PASS** for the current repository assets, subject to the
  separately documented P0a/P1-B gate.
- **Task quality: FAIL** because the static verifier does not fully enforce its
  claimed exact-directive/no-override guarantee.

The prior Critical finding is resolved. TDR-017 and the deployment plan now
strictly distinguish two permitted historical Python *code-compatibility*
names from forbidden Stage03 operational infrastructure. The worker and outbox
units each have exactly one matching `ExecStart`; the API has exactly zero
`stage03` occurrences. `verify-native-service-assets.sh` has no global text
substitution: it counts `stage03` occurrences (0/1/1), checks the exact entry
line, and rejects Stage07/Docker/Compose/container/volume markers. Current
units each contain one exact required safe directive, including a non-optional
N1 `ExecStartPre`; the renderer rejects ports 80 and 443 as well as public
bind/CIDR values with fixed rejection output. Regression source now includes
443, duplicate-directive, extra-Stage03, empty-reset, and optional-preflight
fixtures.

### Findings

#### Critical

None.

#### Important

1. **The verifier can miss systemd directive overrides that use whitespace
   around `=`.**

   `require_exactly_one_directive` counts only `^Directive=`
   (`verify-native-service-assets.sh:15-22`). systemd unit syntax accepts
   whitespace around the assignment delimiter, so an appended
   `NoNewPrivileges = false`, `EnvironmentFile = ...`, `ExecStartPre =`, or
   `ExecStart = ...` can change the effective unit while evading this count and
   the root/ubuntu check, which likewise only accepts `^(User|Group)=` (lines
   47-48). The current units do not contain this bypass, but the verifier does
   not yet prove the required “exactly one / no reset or override” property.

   Required correction: parse/deny all assignments using a whitespace-tolerant
   directive matcher (for example `^[[:space:]]*Directive[[:space:]]*=`), then
   add no-secret fixtures for spaced unsafe duplicate/reset/override forms for
   each security-critical directive class.

#### Minor

None.

### Evidence Boundary

- `nginx -t` remains explicitly `SKIPPED` when no binary is available; the
  updated TDR, plan, script and N2 report correctly treat this as an environment
  limitation, not PASS evidence. An authorized P0a/P1-B host must still retain
  the real no-secret `nginx -t` result.
- P0a bridge bind/CIDR/hostname values remain absent and blocked; no real value
  was hard-coded or inferred.

---

## 2026-07-22 Assignment-Whitespace Remediation Re-review

### Scope And Method

- Reviewed the updated native asset verifier, no-secret regression script, N2
  report, compatibility-boundary documentation, and the three current units.
- Source inspection only; no fixture/test, service, network, SSH, Docker,
  Nginx, or target-server action was executed.

### Verdict

- **Spec compliance: PASS** for the repository-only N2 assets.
- **Task quality: PASS**.

### Findings

#### Critical

None.

#### Important

None.

#### Minor

None.

### Positive Re-review Evidence

- `require_exactly_one_directive` now counts
  `^[[:space:]]*Directive[[:space:]]*=` and requires the one canonical exact
  line. It is applied to User, Group, working directory, environment file,
  preflight, ExecStart, all listed hardening directives, and restart/backoff.
  Dependency and forbidden User/Group checks use whitespace-tolerant assignment
  patterns too.
- The no-secret fixture suite covers all requested spaced override classes:
  `NoNewPrivileges = false`, `EnvironmentFile =`, `ExecStartPre = /bin/false`,
  `ExecStart = /bin/false`, and `User = root`; each asserts only the fixed
  `native-service-assets: fail` output.
- There is no global substitution exception. API permits zero `stage03`
  occurrences; worker/outbox each permit exactly their one documented historical
  Python code-compatibility `ExecStart`, with operational Stage03/Docker/Stage07
  markers still rejected. Current unit files meet that exact boundary.
- Port 443 has an explicit fixed-output rejection fixture. P0a bridge values
  remain absent and blocked, and `nginx -t` remains correctly recorded as
  `SKIPPED` when the binary is unavailable rather than as passing evidence.
