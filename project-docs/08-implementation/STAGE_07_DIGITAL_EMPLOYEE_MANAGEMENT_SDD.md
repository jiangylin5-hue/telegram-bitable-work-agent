# Stage07 Digital Employee Management SDD

## Status

- Status: approved TD010 Option A software design; requires implementation-plan approval before code.
- Scope: safe Mini App management adapter over the current one-Base `DigitalEmployee` runtime.

## Architecture

```text
Base Canvas management entry
-> protected management directory/context reads
-> strict manager DTOs and memory-only scoped cache
-> service-level Base/table/view/member validation
-> versioned row-locked management command
-> redacted audit event
-> existing S5/TD009 safe contact/context/invocation eligibility changes
```

The adapter is not a generic runtime API. It uses FastAPI, SQLAlchemy 2.x, Alembic, existing Stage06 authorization and the existing S4 version/idempotency pattern. It does not introduce LangGraph graph configuration, a new policy engine, a second member model or a persistence mechanism in the browser.

## Data Model

### `digital_employees` additions

| Column | Type | Default | Rule |
| --- | --- | --- | --- |
| `version` | integer | `1` | positive; increments on every manager configuration, grant replacement, activation or pause |
| `access_mode` | string(20) | `workspace` for migrated rows | closed service enum `workspace|assigned` |

The pre-existing `base_id` remains immutable. Existing `status` storage remains a string but management commands accept only `draft`, `active` and `paused`; no blind data normalization is included.

### `digital_employee_member_grants`

| Column | Type | Constraint |
| --- | --- | --- |
| `id` | UUID | primary key |
| `employee_id` | UUID | foreign key to `digital_employees`; immutable |
| `workspace_member_id` | UUID | foreign key to `workspace_members`; immutable |
| `created_at`, `updated_at` | timestamps | existing timestamp convention |

`UNIQUE(employee_id, workspace_member_id)` prevents duplicate eligibility. Grant replacement locks the owning employee, validates the entire set, replaces it atomically and increments employee `version`; individual direct mutation routes are intentionally absent.

## Authorization

| Operation | Required existing action | Additional checks |
| --- | --- | --- |
| management context/create | `digital_employee.create` | caller reads Base and every selectable resource returned |
| directory/detail | `digital_employee.update` | caller reads employee Base |
| configuration/grants/activate/pause | `digital_employee.update` | employee workspace/Base current, expected version current |
| contact/context/invoke in `assigned` mode | `digital_employee.invoke` | active matching `DigitalEmployeeMemberGrant`, caller Base/view/field/record checks unchanged |

No new action string is proposed. The UI capability can be derived server-side from existing actions; mutation routes remain independently authoritative.

## Safe DTOs

```ts
type ManagedEmployeeSummary = {
  id: string
  name: string
  description: string
  status: 'draft' | 'active' | 'paused'
  accessMode: 'workspace' | 'assigned'
  tableCount: number
  viewCount: number
  memberCount: number
  version: number
}

type ManagedEmployeeDetail = ManagedEmployeeSummary & {
  baseId: string
  telegramAlias: string | null
  accessibleTableIds: string[]
  accessibleViewIds: string[]
  allowedActions: Array<'summarize' | 'draft_update'>
  memberIds: string[]
}

type EmployeeManagementContext = {
  base: { id: string; name: string }
  tables: Array<{ id: string; name: string }>
  views: Array<{ id: string; tableId: string; name: string; viewType: 'grid' | 'kanban' | 'calendar' | 'form' }>
  members: Array<{ id: string; label: string; role: string }>
}
```

Parsers require exact roots, non-empty opaque IDs, known status/access/action/view types and bounded arrays. They reject policy/configuration/runtime/record/field/provider/trace keys. IDs are only selection values, not substitute record labels or authorization claims.

## Commands And State Transition

```text
POST create -> draft@v1
PATCH config(draft|paused, expected_version) -> same status @v+1
PUT grants(draft|paused, expected_version) -> same status @v+1
POST activate(draft|paused, expected_version, idempotency key) -> active @v+1
POST pause(active, expected_version, idempotency key) -> paused @v+1
```

All commands load the employee `FOR UPDATE`. Configuration validates fixed enums and selected Base resources before mutation. Lifecycle commands re-run configuration and member eligibility validation immediately before state transition. Successful commands record only safe audit summaries: status before/after, scope counts, access mode, grant count, action set and durable IDs/version; never raw policies, member labels, record values, prompt or provider data.

## Scope Validation

1. Employee Base must exist in employee workspace and remain readable by actor.
2. Every table exists under that Base and is currently readable by actor.
3. Every view exists under that Base, is currently readable by actor and belongs to a selected table.
4. At least one selected view and `summarize` are required for activation.
5. `draft_update`, if selected, reuses TD006's current Canvas record guard; it does not become available from Home.
6. In `assigned` mode, grants must be active members of employee workspace and at least one grant is required to activate.
7. Existing active-alias uniqueness is preserved at activation; collision returns fixed conflict/reselection state.

## Query And Cache Lifecycle

All Mini App keys are prefixed by existing `{userId, workspaceId}` protected scope and then `employee-management`. Close, Base/workspace replacement, manager mutation and exact `404` remove only the relevant directory/context/detail/grant keys before authoritative reread. No URL, localStorage, sessionStorage or persisted QueryClient state is used.

## Migration And Index Plan

1. Add non-null employee `version` with server default `1`, backfill existing rows and add positive version constraint.
2. Add non-null employee `access_mode` with server default `workspace`, backfill existing rows, then add closed check constraint.
3. Create `digital_employee_member_grants` with uniqueness and foreign keys.
4. Add `ix_stage07_digital_employee_management_base_updated` on `(base_id, updated_at DESC, id DESC)` for cursor-paged manager directory.
5. Upgrade/downgrade/replay must preserve active legacy behavior and the existing partial active-alias index.

No JSONB GIN index is proposed: scope/action JSONB is validated and read by employee ID under a row lock, not queried as a broad management filter. Any future multi-Base scope needs its own relational table/index decision.

## Non-Goals And Safety

No raw generic runtime endpoint reaches Mini App management UI. No employee may obtain database credentials, raw SQL, a provider key, unrestricted send right, self-confirmation ability or a bypass of current caller permission. TD010 does not create a contact binding, Bot publication, general chat/memory, knowledge/retrieval, external send or deployment path.
