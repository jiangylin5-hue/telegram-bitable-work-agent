# Stage07 Governance Write BDD And Acceptance

## Status

- Status: implementation evidence reconciled; GW-A06/GW-A07 retain the explicit negative-lifecycle gaps below.
- Authority: Technical Decision 004 and the Governance Write Design.

## BDD Scenarios

### GW-01 Server authority is independent from the visible editor

Given a client displays a role or field editor from stale capability data
When it submits a command
Then the backend independently resolves identity, active membership, resource scope, fixed action and target invariant before reading `expected_version`.

### GW-02 Member role change preserves protected roles

Given an owner changes an active non-owner member from `operator` to `builder`
When the expected version matches
Then exactly that membership role changes, its version increments once, an audit event is written and the reread receipt is canonical.

Given an admin targets an owner/admin, assigns `admin`/`owner`, changes themselves, or targets inactive membership
When the command reaches the service
Then it fails closed with an allowlisted code and writes no member mutation.

### GW-03 Role replay and conflict are deterministic

Given the same idempotency key and identical role command
When it is retried after success
Then it returns the original closed receipt and emits no second audit mutation.

Given a reused key has a different target, role or expected version
Then it returns fixed idempotency conflict with no write.

Given another valid command updated the membership first
Then stale `expected_version` returns fixed conflict and does not overwrite the new role.

### GW-04 Field policy is a fixed complete replacement

Given an owner/admin submits every fixed role with only `hidden|read|write`
When owner mode is `write` and the revision matches
Then only the field policy JSONB and permission revision change; no schema, field option, record or relation data changes.

Given an unknown role/mode, missing fixed role, duplicate semantic entry or owner not `write`
Then validation fails before any write.

### GW-05 Field mode never escalates fixed role action

Given viewer policy is `write`
When that viewer attempts record update
Then existing fixed `record.update` authorization still denies it.

Given a viewer policy is `hidden`
When safe schema, presentation, record detail or lookup is reread
Then the existing field filtering omits that field end-to-end.

### GW-06 Existing V1 view grants are reused, not broadened

Given the caller owns an already safe restricted V1 view
When they use View access
Then the existing versioned replacement endpoint and active candidate rules apply.

Given the view is system default, another owner's view, hidden, or not V1
Then S4 offers no alternate policy editor or bypass route.

### GW-07 UI lifecycle fails closed

Given `401`
Then all Stage07 protected state is cancelled and removed before expired-session rendering.

Given `403`, `404`, `409`, `422`, `5xx` or network failure
Then cleanup scope, retained safe local draft, fixed feedback and retry behavior match the SDD; server detail never enters DOM or telemetry.

Given a versioned role or field-policy command returns `409`
When the Mini App keeps the safe local selection and shows the fixed conflict message
Then it offers an explicit context-specific reread control, never retries the mutation automatically, and only clears the conflict state after the authoritative safe context resolves.

### GW-08 Responsive confirm path is complete

Given 1440, 1280, 430 and 390 widths
When an authorized actor changes a role and a field policy using synthetic data
Then selection, confirmation, pending, conflict, denied, retry and focus return have labelled reachable paths and no hidden write control.

## Acceptance Matrix

| ID | Requirement | Required evidence | Status |
| --- | --- | --- | --- |
| GW-A01 | role command independently authorizes and preserves owner/admin invariants | unit/API denial and mutation tests | implemented-local |
| GW-A02 | membership version, lock and idempotency replay/conflict are atomic | disposable PostgreSQL concurrency/replay tests | implemented-local |
| GW-A03 | field policy schema is fixed, versioned and cannot alter field/record data | service/API negative tests plus PostgreSQL rollback | implemented-local |
| GW-A04 | field read/write enforcement remains intersectional | hidden/read/write regression across schema/presentation/detail/update | implemented-local |
| GW-A05 | V1 view grant path is reused with no broader policy endpoint | contract and UI integration tests | implemented-local |
| GW-A06 | protected QueryClient cleanup and authoritative reread are exact | parser/query/App tests for 401/403/404/409/scope replacement | partial-local — immediate 401/403, exact Base 404, explicit 409 field-policy reread and focus return are covered; planned delayed mutation permutations remain open |
| GW-A07 | built UI is reachable and safe at four widths | Browser synthetic fixture, console scan and retained observation | partial-local — success/four-width/console plus safe Base 404 pass; Browser stale/denied/retry terminal-mutation permutations remain open |
| GW-A08 | audit/redaction and temporary cleanup are reconciled | BDD evidence document and cleanup proof | implemented-local |

## Prohibited Claims

S4 may not claim custom RBAC, team invitations, owner transfer, public sharing, general policy engine, Telegram identity proof, staging/production readiness or Stage07 completion.
