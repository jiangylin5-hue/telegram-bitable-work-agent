# Stage07 Technical Decision 004: Governance Write Contract

## Status

- Decision status: accepted — user approved 2026-07-12; implementation remains bounded by this document.
- Scope: coherent S4 governance write package: existing active member role changes, role-based field read/write policy replacement, and reuse of the existing V1 restricted-view member grants.
- Does not authorize: invitation, deactivation, owner transfer, custom roles, group policy, raw policy exposure, Bot administration, draft confirmation, Telegram or deployment.

## Problem Evidence

Stage06 already has a fixed workspace role set (`owner`, `admin`, `builder`, `operator`, `viewer`), `WorkspaceMember`, role-action authorization, JSONB `PlatformField.permission_policy`, field read/write enforcement, audit recording, a Stage06 idempotency ledger, and versioned V1 view-member replacement. It does not have a safe Mini App mutation contract for workspace member roles or field policies. `WorkspaceMember` has no mutation revision, and field policy JSONB has no dedicated policy revision.

The existing V1 endpoint `PUT /views/{view_id}/members` is already versioned, validates active workspace candidates and restricts replacement to the view owner. S4 must reuse it rather than create a second general view-permission engine.

## Considered Approaches

| Option | Description | Advantages | Decision / risk |
| --- | --- | --- | --- |
| A — client-side role/policy editor over legacy generic routes | Client reconstructs role actions and sends unrestricted JSON policy | smallest apparent frontend change | rejected: browser becomes a policy engine; no concurrency guard; legacy fields can disclose policy data |
| B — introduce Casbin/OPA and generalized policy resources | Replace fixed-role checks with a new policy engine and schema | familiar mature authorization ecosystems | rejected for S4: broad migration from the verified Stage06 role model, high compatibility and audit risk, not necessary for the first platform write cut |
| C — narrow server-owned governance commands (recommended) | Reuse current fixed RBAC, SQLAlchemy locks, versioned command pattern, idempotency ledger, audit service and V1 grants; add only explicit mutation revisions | preserves current architecture, supports deterministic conflict handling, avoids self-authored policy evaluation in browser | requires two additive revision columns, explicit routes and user approval |

## Proposed Authority Model

### Fixed roles and non-escalation

The five existing role strings remain the only accepted roles. No user-defined roles, action arrays or client-defined permissions are accepted.

| Actor | May change member role | May replace a field policy | May replace V1 restricted-view grants |
| --- | --- | --- | --- |
| owner | active non-owner member to any non-owner role | yes | only when the owner also owns that V1 view |
| admin | active `builder`/`operator`/`viewer` member to `builder`/`operator`/`viewer` only | yes | only when the admin also owns that V1 view |
| builder/operator/viewer | no | no | only the existing V1 owner rule, which normally denies them |

Server invariants:

1. Workspace owner membership role is immutable in S4; owner transfer is out of scope.
2. A caller cannot change their own membership role.
3. An admin cannot change an owner or admin, and cannot assign `admin` or `owner`.
4. Inactive members cannot be changed; no request activates or deactivates a member.
5. A field policy cannot grant an action absent from the caller's fixed role actions. A `write` field mode never gives a viewer `record.update`.
6. Owner field access is forced to `write`; malformed, omitted or unknown role entries are rejected, never defaulted by the browser.

This follows the existing Feishu/Lark-style resource → role → server-side scope pattern, not an invented client ACL framework.

## Proposed Data and API Contract

### Additive migration

| Table | Column | Rule |
| --- | --- | --- |
| `workspace_members` | `version INTEGER NOT NULL DEFAULT 1` | increments only after an accepted role mutation |
| `fields` | `permission_version INTEGER NOT NULL DEFAULT 1` | increments only after an accepted field-policy replacement |

No new permission table, index, role table, group table or policy cache is proposed. Existing JSONB `permission_policy` stays the source for field enforcement.

### Member editor context and role command

`GET /mini-app/workspaces/{workspace_id}/governance/member-editor?limit=1..100&cursor?`

Requires `member.manage`. It returns only the active/editable member rows `{id,user_id,role,status,version,assignable_roles}`. The response does not contain email, profile, action list, invitation state, owner-transfer capability or raw authorization policy.

`PATCH /mini-app/workspaces/{workspace_id}/governance/members/{member_id}/role`

Requires `member.manage`, `Idempotency-Key`, and strict body:

```json
{ "role": "builder", "expected_version": 4 }
```

The route locks the target membership, rechecks the actor and all invariants, compares `expected_version`, writes the single new role, increments `version`, commits once, emits `workspace_member.role_changed`, and returns the closed mutation receipt `{id,user_id,role,status,version}`. Same idempotency key plus same request replays the receipt; the same key plus another body yields a fixed conflict; stale revision yields a fixed conflict and no write.

### Field-policy context and replacement command

`GET /mini-app/tables/{table_id}/governance/field-permissions`

Requires `field.permission.manage`. It returns only fields the caller is allowed to administrate, each with `{id,key,label,field_type,policy,permission_version}`. `policy` is exactly the fixed role-mode map; it never includes raw field options, record values, relation targets, field IDs outside the table, permissions of a user, or action lists.

`PUT /mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy`

Requires `field.permission.manage`, `Idempotency-Key`, and strict body:

```json
{
  "expected_permission_version": 2,
  "policy": {
    "owner": "write",
    "admin": "write",
    "builder": "write",
    "operator": "read",
    "viewer": "hidden"
  }
}
```

Allowed modes are exactly `hidden`, `read`, `write`; every fixed role must occur once. The service locks the field, confirms its table/workspace scope, enforces owner `write`, compares revision, writes only normalized JSONB, increments `permission_version`, emits `field.permission_policy_replaced`, and returns `{id,key,policy,permission_version}`. A request never changes field type, options, name, value or record data.

### Existing view grant reuse

S4 does not add a global view-policy route. The existing versioned `PUT /views/{view_id}/members` remains the only V1 member-grant command. Governance links an authorized operator to the existing view access editor for an already safe V1 view. Its limits remain: active candidates only, `editor|viewer` grants only, owner-only replacement, no public sharing, no role policy and no owner transfer.

## Transaction, Audit and Client-State Rules

- Every new mutation runs in one SQLAlchemy transaction behind the existing idempotency helper and a row lock.
- Audit state contains role/policy deltas and revision values but never record values, field options, raw request headers, trace tokens, Telegram data or provider credentials.
- No optimistic role or policy UI is allowed. Success clears affected protected workspace/table/governance keys, rereads bootstrap/capabilities plus authoritative editor context, and renders the reread result only.
- `401` removes all Stage07 protected state. `403` removes the active governance subtree. `404` removes only the exact member/field context. `409` retains only the safe local draft and offers a fixed reread; no automatic retry occurs. `422` retains the safe local draft and fixed allowlisted guidance. `5xx`/network expose no server text.

## Approval Boundary

Approving Option C authorizes the two revision columns, the four Mini App member/field routes, the two fixed actions `member.manage` and `field.permission.manage`, use of existing idempotency/audit patterns, and the read/write UI described by linked S4 documents. It does not authorize custom roles, role action editing, invitation/deactivation, owner transfer, general view policy, public sharing, Bot/Telegram, deployment or a new authorization dependency.
