# Stage07 Governance Write Design

## Status

- Status: proposed; awaiting user review of Technical Decision 004.
- Substage: S4 Governance Write.
- Goal: make the current fixed workspace roles and field visibility/write policy safely operable in Mini App without creating a general authorization product.

## Product Outcome

An eligible workspace operator can open Governance, change an existing active member's allowed role, replace a field's five-role policy, and open the pre-existing view-access editor for a safe V1 view. Every successful command is server-authorized, versioned, idempotent, audited and followed by an authoritative reread. Every unavailable capability is omitted or denied server-side.

## User Flow

```text
server-derived Governance entry
  -> Member roles / Field access / View access sections
  -> safe editor context (never browser-inferred authority)
  -> explicit selection + confirm
  -> versioned, idempotent server command
  -> commit + audit
  -> exact protected-query removal
  -> bootstrap/context authoritative reread
```

No flow begins from a raw member ID, raw field policy JSON, hidden Base, role action list or browser storage.

## Surfaces

### Member roles

Desktop shows a compact list of active editable members. Each row has a role selector limited to `assignable_roles`, current revision, fixed explanation and one confirm action. Mobile uses the same fields in a labelled sheet; it does not hide the confirmation path behind hover or drag.

States: initial loading, empty editable rows, selected-but-unchanged, confirm-pending, success-after-reread, stale revision, idempotency conflict, validation error, denied, expired session, missing target and network/server error. A row with no permitted role change has no editable control, not a disabled control that leaks a forbidden role.

### Field access

An authorized Base/Table selection yields only safe field policy summaries. The editor is a fixed five-row role matrix with `hidden`, `read`, `write` choices. Owner is shown as fixed `write` and is not editable. The matrix never displays records, field options, relation targets, raw JSON or a computed user-by-user entitlement.

States: selection required, safe empty table, loading, policy ready, local changed, confirm-pending, success-after-reread, 409, 422, 403, 404 and generic failure. Switching workspace/Base/table cancels or discards an old response before it can render.

### View access

S4 reuses the existing V1 access panel. It is reachable only for a safe V1 view already visible to the caller. Its states and versioned grant replacement contract remain authoritative. The Governance workbench does not duplicate or broaden that editor.

## Safe Rendering

- all labels are text nodes; no server HTML is rendered;
- unknown role/status/type/mode values map to fixed generic text and never become selectable;
- errors map from stable error codes only; response `detail`, trace, policy snapshot and raw request values never render;
- the policy matrix is local form intent, not policy enforcement; server rechecks caller, scope, mutation target and revision;
- no role/policy data is placed in URL, localStorage, telemetry or clipboard helper.

## Responsive and Accessibility Contract

At 1440/1280 the matrix remains readable without horizontal page overflow. At 430/390, selection and confirmation use a full-height labelled sheet with independently scrollable content, 44px controls, focus on heading and return to the exact opener. Loading/retry/confirm feedback is announced through a status region; destructive-looking role downgrades require an explicit confirm label naming the safe user ID and proposed fixed role. Escape/cancel makes no network write.

## Explicit Non-Goals

- invite, remove, activate/deactivate or transfer workspace owner;
- custom role/action editor, group/department policy, per-user field policy, inheritance graph or access simulation;
- field type/options/value edits, record mutations or historical policy reconstruction;
- general public/restricted view policy beyond the existing V1 member grants;
- audit export/search/detail, Bot configuration, digital-employee writes, Telegram or release work.

## Acceptance Shape

Acceptance requires route/service tests, migration upgrade/rollback/replay on disposable local PostgreSQL, frontend parser/query/application tests, built-client Browser evidence at four required widths, and BDD-by-BDD reconciliation. S4 is not accepted by a role selector rendering alone.
