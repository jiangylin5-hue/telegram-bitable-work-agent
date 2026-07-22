# Stage09 Native P1-A N1 Independent Review

## Scope And Method

- Review scope: the required Stage09 decisions/plan, N1 report, `.gitignore`, and
  the three listed N1 files only.
- External actions: none. No network, SSH, Docker/Compose, container, database,
  service, or target-server action was performed.
- Evidence: source inspection and `sh -n` on both shell scripts. Both syntax
  checks exited `0`. No runtime fixture was created or executed, so no secret or
  runtime value was read, printed, hashed, or retained.

## Verdict

- **Spec compliance: FAIL**
- **Task quality: FAIL**

The N1 template is repository-safe, the safe-mode values and empty Telegram
allowlists are present, `.gitignore` tracks only the example, and normal script
output is status-only. However, the validator does not strictly enforce the
required local-only PostgreSQL data plane.

## Findings

### Critical

1. `validate_postgres_url` validates only the authority host, then accepts a
   PostgreSQL URL with query parameters unchanged. A URL whose authority is the
   approved loopback address but whose query supplies a conflicting connection
   host/socket parameter passes this validator. PostgreSQL/SQLAlchemy drivers may
   consume such parameters as connection options, so the checked authority is not
   a sufficient proof of the effective endpoint. This violates the hard
   local-only / public-data-plane rejection requirement from TDR-017 and Stage09
   sections 3, 4 and 6.

   Required correction: parse the URL with an allowlist of supported schemes and
   parameters, reject every host/port/service override in query text (including
   encoded forms), and accept only a canonical loopback authority or a canonical
   Unix-socket form. Add no-value-leak regression fixtures for these rejected
   forms.

### Important

1. The presence validator makes `TELEGRAM_WEBHOOK_SECRET` mandatory even though
   P1 remains dry-run with LLM/provider disabled and must not require Telegram
   credentials. This is not a Bot token, but it unnecessarily forces creation of
   a secret before the no-Telegram P1 gate can pass. Make it optional/absent for
   P1, or document a separate approved non-Bot local nonce rule and validate only
   its presence state without exposing its value.

2. The N1 report claims validation of Stage03/Stage07 and container markers, but
   that coverage exists only in the second wrapper script. Invoking the advertised
   `validate-runtime-presence.sh` alone accepts those markers outside its two URL
   fields. If this script is an independent P1-B gate as the plan says, move the
   complete marker and endpoint policy into it or make the isolation wrapper the
   sole documented gate.

### Minor

1. The report's fixture verification is summarized but does not provide a
   reproducible, retained no-secret test harness or exact assertions for the URL
   parser edge cases. Add a repository-safe test script/fixture convention after
   fixing the critical validation gap; it must continue to emit only fixed status
   text.

## Positive Checks

- `runtime.env.example` contains placeholders only; no real hostname, credential,
  chat ID, or deployment endpoint was found.
- The example uses the exact P1 safe values: `staging`, `dry_run`, `false`,
  `fake`, `disabled`, `false`, and `false`; listed Telegram allowlists are empty.
- The release directory is checked against the artifact-derived immutable path,
  `latest` is rejected, and the Nginx port is constrained to 1024..65535.
- The runtime target documented in the template is only
  `/etc/stage09-p1/runtime.env`; `.gitignore` ignores the runtime directory while
  re-allowing only `runtime.env.example`.
- Neither script prints or hashes runtime values on its normal success/failure
  paths.

## Required Re-review Gate

Re-review is required after the critical PostgreSQL endpoint-bypass is fixed and
the no-value-leak regression evidence covers canonical loopback, Unix socket,
query override, encoded override, and public-host rejection cases.

---

## 2026-07-22 Remediation Re-review

### Scope And Method

- Reviewed the updated runtime example, both validators, the added
  `test-runtime-preflight.sh`, the updated Stage09 decision/plan text, the N1
  report, `.gitignore`, and the existing `backend/app/core/config.py` runtime
  requirement.
- External actions: none. No network, SSH, Docker/Compose, container, database,
  service, target-server, or runtime-fixture action was performed.
- Static evidence: `sh -n` exited `0` for all three shell scripts. The preflight
  regression script was not executed in this independent review because it
  creates temporary fixture files; its source and cleanup trap were inspected.

### Verdict

- **Spec compliance: PASS**
- **Task quality: PASS**

The previous Critical endpoint-bypass is resolved. PostgreSQL now accepts only
three complete, canonical forms: fixed P1 credentials/database over IPv4
loopback, IPv6 loopback, or the one fixed Unix socket query form. Redis likewise
accepts only fixed database-0 IPv4/IPv6 loopback or its one fixed P1 Unix socket
form. No extra query, fragment, percent-encoded extension, public host, alternate
port, or alternate database can match either whitelist.

The marker denylist is now in `validate-runtime-presence.sh`; the wrapper retains
it as defense in depth. The staging webhook nonce requirement is consistent with
`backend/app/core/config.py`, which explicitly requires
`TELEGRAM_WEBHOOK_SECRET` for staging but does not require a Bot or OpenRouter
key. Documentation accurately limits it to a target-only random local-validation
nonce and the validator reports only presence state. The regression script uses
no-secret fixtures, suppresses validator output, checks representative
no-value-leak cases, and removes its temporary directory via trap.

### Findings

#### Critical

None.

#### Important

None.

#### Minor

1. The earlier `Post-implementation offline checks` block in the N1 report still
   says that the validator passes a Stage07/Compose marker while the isolation
   wrapper rejects it. That historical statement is now superseded by the
   remediation, because the main validator rejects those markers. Update or
   clearly label the older block as superseded to avoid contradictory evidence.
