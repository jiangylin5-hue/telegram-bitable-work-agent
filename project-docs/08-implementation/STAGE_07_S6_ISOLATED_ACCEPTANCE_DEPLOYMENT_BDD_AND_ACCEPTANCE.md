# Stage07 S6.3 Isolated Acceptance Deployment BDD and Acceptance

## Status

- Status: bounded real non-production delivery/identity evidence and cleanup complete; isolated resource, runtime bootstrap, HTTPS, BotFather Main Mini App, two separately authorized one-attempt TD008 sends and a real signed Telegram `initData` resolver/Base reread were observed. The first launch exposed a missing official WebApp bridge; the bridge was corrected, then a fresh explicitly authorized request completed the resolver flow. The isolated resources were then removed with Stage03 health preserved. This is supporting evidence only, not Stage07 whole-stage acceptance, and it must not be recreated or resent for audit repetition.
- Scope: parallel non-production deployment needed to obtain real TD007/TD008 evidence while preserving the historical Stage03 service.

## BDD Scenarios

### S6I-01 Parallel resources do not replace Stage03

Given the historical `telegram-bitable-stage03` containers and public Caddy host are running
When the Stage07 acceptance environment is provisioned
Then it uses a distinct Compose project, directory, PostgreSQL volume, Redis volume and container aliases
And no Stage03 container, named volume, environment file, branch, port listener or database is stopped, replaced, migrated or queried by the Stage07 services.

### S6I-02 A deployment snapshot contains approved source but no local secrets

Given the isolated Stage07 worktree has the approved source and uncommitted acceptance fixes
When it is packaged for the remote server
Then the package contains versioned source plus the explicitly tracked Stage07 documentation and deployment assets
And it excludes `.local`, `.env*`, private SSH keys, `node_modules`, build cache, local PostgreSQL data and user browser data.

### S6I-03 The runtime uses new data stores and validated key presence

Given the new Compose services have started
When migration and runtime preflight are run
Then the API/Worker use only the new Postgres and Redis service names
And key presence, one-value test-chat allowlist, `restricted_test` mode and Bot username syntax are verified without emitting values.

Given any required key is absent, the allowlist is not exactly one value, the mode differs, or the Bot username is invalid
When a delivery-capable Worker starts
Then the handler remains unavailable or fails closed
And no Telegram Bot API call is attempted.

Given the isolated environment has no configured private test target
When the one-time capture helper observes a newly sent `/stage07-bind` message
Then it accepts only a `private` chat, writes the discovered Chat/User IDs only to the ignored isolated runtime file, and restores the previous webhook in `finally`
And its result contains no raw update, message, ID, token, secret or webhook URL.

Given the marker is missing, arrives from a group/channel, or webhook restoration fails
When the helper exits
Then it records a fixed blocked/failed outcome, does not write a target value, and no controlled delivery is attempted.

Given an active Stage03 webhook persists the newly sent private marker but temporary polling does not return it
When the approved one-time persisted-marker bridge runs with its explicit `bind_window_not_before_utc`
Then it reads the existing `Message` model through SQLAlchemy ORM only
And it selects exactly one row only when text, message type, freshness and `telegram_chat_id == telegram_user_id` all match
And it uses the existing atomic isolated-env writer to update only the three approved target keys.

Given no eligible row, more than one row, a stale row, a non-text row, a non-private-equivalent row, ORM failure or writer failure
When the persisted-marker bridge exits
Then it emits only a fixed `blocked` or `failed` sanitized receipt
And it changes no Stage03 database/configuration/webhook/container state
And it does not start a delivery-capable Stage07 process or make a Telegram send.

Given the existing atomic writer uses a sibling temporary file and atomic replacement
When the C-selected runtime-layout correction is applied
Then the isolated env resides only at `runtime/.env.stage07-acceptance`, the `runtime/` directory is mode `0700`, and the env file is mode `0600`, both owned by the isolated deployment operator
And every Compose service resolves that same file through `STAGE07_ENV_FILE`
And the short-lived writer mounts only `runtime/` at `/run/stage07`, so it can atomically replace `/run/stage07/.env.stage07-acceptance` without mounting deployment source or any Stage03 path.

Given the directory-mounted atomic writer replaces the env file as the container's root user
When the bridge receives a candidate `captured` receipt
Then the wrapper restores the file owner to the invoking isolated deployment user and mode `0600` before returning its external `captured` receipt
And an ownership or permission-restoration error is a fixed `failed` receipt, leaving delivery-capable services stopped.

### S6I-04 DNS and Caddy activate a separate HTTPS hostname safely

Given the selected Stage07 hostname resolves to the Tencent Cloud instance
When the candidate Caddy host block validates
Then only that hostname proxies static Mini App files to `stage07-web` and API paths to `stage07-api`
And the existing Stage03 Caddy host block remains byte-for-byte present.

Given DNS does not resolve correctly, the candidate config fails validation, certificate issuance fails, or HTTPS health is not `200`
When ingress activation is attempted
Then no TD008 delivery or Telegram Mini App test is run
And the existing Caddy configuration is restored or remains active unchanged.

### S6I-05 Real delivery remains exactly one controlled attempt

Given HTTPS, BotFather Main Mini App, synthetic fixture, one active binding and the fixed test-chat allowlist are ready
When an authorized operator creates and confirms one TD008 delivery request
Then the existing Worker reserves the request before mint/send and records only a sanitized terminal receipt
And the test user opens the resulting button in Telegram, sending signed `initData` to the already deployed S6.1 resolver.

Given the request is blocked, rejected or uncertain
When its terminal receipt is persisted
Then no automatic retry occurs, the pointer is revoked where applicable, and the result is recorded as a bounded failure rather than a passed smoke.

### S6I-06 Cleanup restores the initial server boundary

Given the real smoke has a terminal result
When S6.3 cleanup runs
Then the Stage07 acceptance Compose project, isolated volumes, synthetic data, Caddy host block and temporary SSH public key are removed unless the user explicitly authorizes retention
And the historical Stage03 health endpoint remains available throughout.

## Acceptance Matrix

| ID | Requirement | Required evidence | Initial status |
| --- | --- | --- | --- |
| S6I-A01 | distinct project/data/network resources | sanitized `docker compose config`, container/volume names and Stage03-before/after status | accepted-bounded; isolated services run and Stage03 health remained `200` before/after |
| S6I-A02 | source snapshot excludes secrets | archive manifest and exclusion scan without file content | evidence-observed; staged archive excluded local secrets |
| S6I-A03 | new migration head and API/worker health | isolated migration head plus `/health` result | accepted-bounded; API/Worker/Outbox/Web running and isolated API `/health=200` |
| S6I-A04 | strict controlled-send preflight and private target bootstrap | sanitized key-presence/mode/count/username validation plus capture-helper test/status | accepted-bounded; exactly-one preflight passed after captured target bootstrap |
| S6I-A04b | one-time persisted-marker fallback is safe | source-specific BDD/SDD, failing/passing selector tests, C-selected runtime-directory migration/revalidation, sanitized live receipt and unchanged Stage03 state | accepted-bounded; fixed `captured` receipt, owner/mode restoration and unchanged Stage03 health observed |
| S6I-A05 | dedicated HTTPS host and same-origin routing | DNS result, Caddy candidate validation, certificate/HTTPS status and no Stage03 route mutation | accepted-bounded; candidate validation and active HTTPS API/Web `200`, Stage03 `200` |
| S6I-A06 | one real private TD008 delivery | sanitized terminal receipts: latest delivery `sent`, Outbox `processed`, response message ID present and no outcome error | accepted-bounded; two distinct user-approved requests each made one terminal send. The second is a fresh, explicit request after the first pointer expired; it is not an automatic retry. |
| S6I-A07 | real Mini App identity/resolver/reread | recipient screenshot of resolved Base plus sanitized persisted resolver audit (`resolved`, destination `base`) | accepted-bounded; the endpoint's required verified-launch dependency admits only server-validated `initData`; the resulting resolver audit and real Base UI prove the bounded end-to-end path without persisting raw launch data. |
| S6I-A08 | rollback/cleanup preserves Stage03 | before/after health and removal record | accepted-bounded; Caddy host/backup, isolated Compose services/volumes/runtime directory and temporary SSH key removed; Stage03 was `200` before, during and after cleanup |

## Failure Classification

| Class | Meaning | Required handling |
| --- | --- | --- |
| `blocked-external-authority` | DNS, BotFather, test-chat ownership or external service access unavailable | record exact prerequisite; do not substitute a mock |
| `blocked-runtime-config` | safe key-presence/mode/allowlist/username guard rejects | correct only approved isolated runtime configuration; do not print values |
| `failed-deployment` | build/migration/health/Caddy validation fails | stop before delivery, preserve Stage03, retain sanitized diagnostics |
| `delivery-terminal-failure` | TD008 records `blocked`, `failed` or `delivery_unknown` | no automatic retry; preserve terminal receipt only |
| `accepted-bounded` | all S6I and S6D/S6.1 external rows have direct evidence | update only those rows; do not claim production or whole Stage07 acceptance |

## Non-Claims

Passing S6I-A01 through S6I-A08 proves a disposable non-production acceptance environment only. It does not authorize production, public access, batch sends, user-data migration or unbounded retention of the temporary server resources.
