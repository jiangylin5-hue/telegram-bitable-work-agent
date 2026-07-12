# Stage07 Governance Write Local Evidence

## Status

- Evidence status: partial acceptance reconciliation.
- Scope: approved S4/TD004 only — active-member role replacement, fixed field-policy replacement and existing V1 restricted-view grant reuse.
- Environment: disposable local PostgreSQL `stage06_smoke` and a synthetic local built Mini App. This is not Telegram, staging, production or an identity proof.

## Implemented Behaviour

1. `WorkspaceMember.version` and `PlatformField.permission_version` are additive revision columns. Both start at `1`; migration `20260712_0023` downgrades to `20260711_0022` and upgrades back to head.
2. Owner/admin only receive `member.manage` and `field.permission.manage`. The service still locks the concrete member/field, rechecks scope and role-target invariants, compares the expected revision, uses the existing idempotency ledger and records a sanitized audit event.
3. The Mini App consumes closed DTOs only. It has no optimistic member/policy rendering, does not render raw response detail and refetches the authoritative safe context after an accepted write.
4. A governance owner can open a previously existing, owned `restricted` V1 view and is routed into the current V1 View Builder and its existing versioned member-grant editor. No S4 view-policy route, general view ACL, public sharing or second member-grant mutation exists.

## Fresh Automated Evidence

| Command / check | Result | What it establishes |
| --- | --- | --- |
| `alembic downgrade 20260711_0022; alembic upgrade head` | passed on disposable local PostgreSQL | S4 migration rollback/upgrade is reversible and ends at `20260712_0023`. |
| `python -m pytest -q tests/unit/test_stage07_governance_write_api.py tests/unit/test_stage07_governance_api.py tests/unit/test_stage06_authorization.py tests/unit/test_stage06_audit_redaction.py tests/unit/test_stage06_lookup_permissions.py tests/integration/test_stage07_governance_write_postgres.py` | `19 passed` | fixed actions, closed routes, invariant denial, replay/stale behaviour, real row-lock contention, audit counts, field hiding, presentation omission, lookup fail-closed regression and fixed-role update denial. |
| `npm.cmd test -- --run src/test/view-access-panel.test.tsx src/test/governance-write-api.test.ts src/test/governance-write-query.test.ts src/test/governance-write-workbench.test.tsx src/test/governance-write-app-flow.test.tsx` | `5 files / 19 tests passed` | typed parser/key boundary, no raw-detail rendering, typed 409 retention plus explicit field-policy reread, restricted-owner V1 selection, exact Base 404 cleanup, close-focus return, and delayed old-workspace role outcomes `401/403/404/409` that cannot deny or repopulate the replacement workspace. |
| `npm.cmd run build` | passed | TypeScript and production Vite build. |
| `python scripts/stage06_local_postgres_migration_smoke.py` | passed at `20260712_0023` | clean disposable schema migration smoke. |

The field-policy PostgreSQL case uses the write command itself, then proves the hidden field is absent from safe schema, view presentation and Record Detail; a viewer `PATCH /records/{id}` remains `403`, even if a field policy would otherwise allow `write`.

## Built Mini App Observations

All data was synthetic and reset after the check.

- On the local built client, an owner changed `stage07-operator` from `builder` to `operator`; the role selector reread the canonical `operator` state and disabled its now-noop confirmation.
- The owner changed `Internal note` viewer access from `read` to `hidden`; the field-policy selector reread the canonical hidden value. No optimistic receipt was displayed.
- A synthetic owned restricted V1 view appeared as the only selectable V1 reuse target. Selecting it opened the existing View Builder, then its existing `访问权限` editor with active candidates and only `viewer|editor` choices. The S3 readback overlay is closed before opening the builder, so it cannot intercept the V1 editor.
- The restricted V1 editor says `此视图是受限视图…`; it no longer incorrectly says that a restricted view is private.
- At `1440x900`, `1280x800`, `430x932` and `390x844`, the labelled role selector, field selector and close path remained present. The 430/390 presentation uses the documented mobile sheet and mobile navigation. The final local page console `error`/`warn` scan returned `[]`.
- A later built-client `404` fixture selected an otherwise authorized Base whose table context was removed. The workspace Home and Governance panel remained visible; only the S4 Base selector reset and rendered the fixed `所选 Base 已不可用，请重新选择。` alert. The fixture-only raw detail was absent and final console `error`/`warn` was `[]`.
- The later `409 -> reread` Browser fixture is deliberately not counted: its local backend/proxy pair passed direct bootstrap checks, but the available in-app Browser could not reach the disposable loopback listener (`ERR_CONNECTION_REFUSED`). The component regression and production build are the evidence for this increment; the fixture scripts, services and synthetic data were removed/reset immediately.

## Acceptance Reconciliation

| ID | Status | Evidence-supported conclusion |
| --- | --- | --- |
| GW-A01 | `implemented-local` | independent role authorization, immutable owner/admin boundaries and closed safe responses are covered by unit/API tests and the real PostgreSQL route run. |
| GW-A02 | `implemented-local` | real PostgreSQL replay/stale and concurrent row-lock tests pass; one role update/audit/version increment wins. |
| GW-A03 | `implemented-local` | exact fixed policy grammar, revision, no record/field-shape mutation, migration downgrade/upgrade and sanitized audit paths are covered. |
| GW-A04 | `implemented-local` | post-policy safe schema/presentation/detail omit the hidden field and viewer record update remains denied; existing field/lookup enforcement remains unchanged. |
| GW-A05 | `implemented-local` | no new view-policy route was added; component and Browser paths reach only existing V1 owner-restricted grant controls. |
| GW-A06 | `partial-local` | typed parser/key, no-optimistic reread, immediate 401/403 boundary, exact Base 404 cleanup, component 409 retention with explicit reread and close-focus return are covered. The delayed role-mutation `401/403/404/409` replacement-workspace matrix is now covered; delayed field-policy and built-client terminal permutations remain open. |
| GW-A07 | `partial-local` | built UI, role/policy success, V1 reuse, four target widths, a real local Base 404 safety path and clean console are observed; Browser stale/denied/retry terminal-mutation permutations remain unobserved. |
| GW-A08 | `implemented-local` | audited writes, redaction regression, temporary seed/proxy deletion, stopped local services and fresh disposable migration smoke are recorded. |

## Explicit Non-Claims

- No invitation, deactivation, self-role change, owner transfer, custom role, group/per-user policy, public sharing or general authorization engine was added.
- No new V1 member-grant endpoint or permission model was added.
- No Telegram, external identity, staging, production, deployment or whole-Stage07 acceptance is claimed.
- S4 is a coherent implemented local vertical slice, but its two retained negative-lifecycle evidence rows above prevent claiming a fully closed S4 acceptance matrix.

## Cleanup

The temporary browser seed script and same-origin proxy script were removed. The temporary backend/proxy processes on ports `8004` and `4178` were stopped; both ports were then closed. The disposable database was reset by the migration smoke script after Browser use.
